"""
Auto Post Diario — CuritibaBlog
Busca o tema mais comentado do dia em tech/dev/IA, gera post completo,
capa via Google Flow, faz upload para IDrive E2, insere no MongoDB (via SSH tunnel)
e rebuilda os 5 blogs (build local + SCP).

Requer: ANTHROPIC_API_KEY em .env (na mesma pasta deste script)
"""
import os, sys, json, uuid, re, subprocess, time, datetime, socket, threading
from pathlib import Path

# carrega .env se existir
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

import requests
import boto3
from botocore.client import Config
import pymongo
import anthropic
import paramiko

THIS_DIR = Path(__file__).parent
LOGS_DIR = THIS_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# CONFIGURACAO
# ---------------------------------------------------------------------------
MONGO_USER   = "curitibasoftware"
MONGO_PASS   = "Curitiba@2025+++"
MONGO_DB     = "curitibasoftware"
MONGO_COL    = "blogposts"

IDRIVE_URL    = "https://s3.us-east-1.idrivee2.com"
IDRIVE_KEY    = "W5HR4oX6jKc53WENnNUe"
IDRIVE_SECRET = "vRDJCcHHBk7vYLbQ05iEvvnWVD4zw3afMXsOQX0X"
IDRIVE_BUCKET = "curitibasoftware-blog"
PUBLIC_BASE   = "https://api.curitibasoftware.com.br/api/blog/image"

VPS_HOST = "31.97.252.45"
VPS_PORT = 2222
VPS_USER = "ubuntu"
SSH_KEY  = str(Path.home() / ".ssh" / "id_server_nopass")

BLOGS = ["curitibablog", "blogdudu", "devlevelup", "dozeroaojunior", "levelupdev"]
BLOG_LOCAL = {
    "curitibablog":   "E:/PROJETOS/curitibablog.com.br/07.curitibablog.blog",
    "blogdudu":       "E:/PROJETOS/blogdudu.com.br/07.blogdudu.blog",
    "devlevelup":     "E:/PROJETOS/devlevelup.com.br/07.devlevelup.blog",
    "dozeroaojunior": "E:/PROJETOS/dozeroaojunior.com.br/07.dozeroaojunior.blog",
    "levelupdev":     "E:/PROJETOS/levelupdev.com.br/07.levelupdev.blog",
}
BLOG_REMOTE = {
    "curitibablog":   "/opt/curitibablog",
    "blogdudu":       "/opt/blogdudu",
    "devlevelup":     "/opt/devlevelup",
    "dozeroaojunior": "/opt/dozeroaojunior",
    "levelupdev":     "/opt/levelupdev",
}

CHARS_PROIBIDOS = ["—", "–", "“", "”", "‘", "’", "…"]

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def check_post(post: dict):
    fields = [post.get(k, "") for k in ["title", "summary", "metaTitle", "metaDescription", "content"]]
    for faq in post.get("faqs", []):
        fields += [faq.get("question", ""), faq.get("answer", "")]
    for block in post.get("blocks", []):
        fields.append(block.get("title", ""))
        for item in block.get("items", []):
            fields += [item.get("label", ""), item.get("value", ""), item.get("text", "")]
    for f in fields:
        for c in CHARS_PROIBIDOS:
            if c in f:
                raise ValueError(f"Char proibido U+{ord(c):04X} em: {f[:80]!r}")


def slugify(text: str) -> str:
    text = text.lower()
    for pat, rep in [("[àáâãä]","a"),("[èéêë]","e"),("[ìíîï]","i"),("[òóôõö]","o"),
                     ("[ùúûü]","u"),("[ç]","c"),("[ñ]","n")]:
        text = re.sub(pat, rep, text)
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    return re.sub(r"-+", "-", text)[:80]


# ---------------------------------------------------------------------------
# SSH TUNNEL para MongoDB
# ---------------------------------------------------------------------------

def _criar_tunnel_mongo(local_port: int = 27018):
    """Abre SSH tunnel local_port -> VPS:27017. Retorna (ssh, server_socket)."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VPS_HOST, port=VPS_PORT, username=VPS_USER, key_filename=SSH_KEY, timeout=30)
    transport = ssh.get_transport()

    def _forward(local_sock):
        try:
            chan = transport.open_channel("direct-tcpip", ("127.0.0.1", 27017), ("127.0.0.1", local_port))
            while True:
                import select
                r, _, _ = select.select([local_sock, chan], [], [], 1)
                if local_sock in r:
                    data = local_sock.recv(1024)
                    if not data: break
                    chan.send(data)
                if chan in r:
                    data = chan.recv(1024)
                    if not data: break
                    local_sock.send(data)
        except: pass
        finally: local_sock.close()

    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", local_port))
    server.listen(1)
    server.settimeout(5)

    def _accept():
        try:
            while True:
                try:
                    conn, _ = server.accept()
                    threading.Thread(target=_forward, args=(conn,), daemon=True).start()
                except socket.timeout:
                    if not transport.is_active(): break
        except: pass

    threading.Thread(target=_accept, daemon=True).start()
    time.sleep(0.5)
    return ssh, server


# ---------------------------------------------------------------------------
# 1. PESQUISA DE TENDENCIAS
# ---------------------------------------------------------------------------

def fetch_hn_top() -> list:
    try:
        ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10).json()[:25]
        stories = []
        for sid in ids:
            try:
                item = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5).json()
                if item.get("score", 0) >= 50 and item.get("title"):
                    stories.append({"title": item["title"], "score": item.get("score", 0),
                                    "comments": item.get("descendants", 0)})
            except: pass
        return stories
    except Exception as e:
        log(f"HN erro: {e}"); return []


def fetch_devto_trending() -> list:
    try:
        resp = requests.get("https://dev.to/api/articles?top=1&per_page=10",
                            headers={"Accept": "application/json"}, timeout=10)
        return [{"title": a["title"], "reactions": a.get("public_reactions_count", 0)}
                for a in resp.json()]
    except Exception as e:
        log(f"Dev.to erro: {e}"); return []


def selecionar_tema(hn_stories: list, devto: list) -> str:
    client = anthropic.Anthropic()
    ctx = "Hacker News top stories:\n"
    for s in hn_stories[:10]:
        ctx += f"- {s['title']} (score:{s['score']}, comments:{s['comments']})\n"
    ctx += "\nDev.to trending:\n"
    for a in devto[:5]:
        ctx += f"- {a['title']} (reactions:{a['reactions']})\n"

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content":
            f"Analise as tendencias abaixo e escolha UM tema para post de blog em PT-BR sobre tecnologia/dev/IA. "
            f"Relevante para devs brasileiros, pratico e educativo. "
            f"Responda APENAS com o tema em portugues, max 15 palavras, sem travessao ou aspas curvas.\n\n{ctx}\nTema:"}]
    )
    tema = msg.content[0].text.strip()
    for c in CHARS_PROIBIDOS:
        tema = tema.replace(c, " ")
    return tema


# ---------------------------------------------------------------------------
# 2. GERACAO DO CONTEUDO
# ---------------------------------------------------------------------------

_PROMPT_FILE = THIS_DIR / "prompt_post.md"
PROMPT_POST  = _PROMPT_FILE.read_text(encoding="utf-8")


def gerar_conteudo(tema: str) -> dict:
    client = anthropic.Anthropic()
    log(f"Gerando conteudo para: {tema}")

    tema_simples = tema.split(":")[0].strip()
    prompt = PROMPT_POST.replace("{tema}", tema).replace("{tema_simplificado}", tema_simples)

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=12000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = msg.content[0].text.strip()
    m = re.search(r"\{[\s\S]+\}", raw)
    if not m:
        raise ValueError(f"Resposta sem JSON valido: {raw[:200]}")
    data = json.loads(m.group(0))

    # remover links invalidos
    for block in data.get("blocks", []):
        if block.get("type") == "links":
            block["items"] = [
                i for i in block.get("items", [])
                if re.match(r"https?://[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", i.get("value", ""))
            ]

    cats_validas = {"ferramentas-de-ia", "desenvolvimento", "tecnologia", "negocios"}
    if data.get("category") not in cats_validas:
        data["category"] = "tecnologia"
    if not data.get("categories"):
        data["categories"] = [data["category"], "tecnologia"]
    if isinstance(data.get("tags"), str):
        data["tags"] = [t.strip() for t in data["tags"].split(",") if t.strip()]

    return data


# ---------------------------------------------------------------------------
# 3. CAPA via Google Flow (com fallback Pillow)
# ---------------------------------------------------------------------------

def gerar_capa_post(titulo: str, subtitulo: str, post_data: dict, output_path: str) -> str:
    sys.path.insert(0, str(THIS_DIR))
    try:
        from gerar_capa_flow import gerar_capa_flow
        gerar_capa_flow(titulo=titulo, subtitulo=subtitulo, output_path=output_path)
        log(f"Capa gerada via Flow: {output_path}")
    except Exception as e_flow:
        log(f"Flow falhou ({e_flow}) — usando Pillow")
        from gerar_capa import gerar_capa
        gerar_capa(
            titulo=titulo, subtitulo=subtitulo,
            card1_titulo=post_data.get("card1_titulo", "Ponto 1"),
            card1_texto=post_data.get("card1_texto", ""),
            card2_titulo=post_data.get("card2_titulo", "Ponto 2"),
            card2_texto=post_data.get("card2_texto", ""),
            card3_titulo=post_data.get("card3_titulo", "Ponto 3"),
            card3_texto=post_data.get("card3_texto", ""),
            output_path=output_path,
        )
        log(f"Capa gerada via Pillow: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# 4. UPLOAD IDRIVE E2
# ---------------------------------------------------------------------------

def upload_capa(local_path: str) -> tuple:
    file_key = f"covers/{uuid.uuid4()}-cover.jpg"
    s3 = boto3.client(
        "s3",
        endpoint_url=IDRIVE_URL,
        aws_access_key_id=IDRIVE_KEY,
        aws_secret_access_key=IDRIVE_SECRET,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name="us-east-1",
    )
    try:
        s3.head_bucket(Bucket=IDRIVE_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=IDRIVE_BUCKET)
    s3.upload_file(local_path, IDRIVE_BUCKET, file_key, ExtraArgs={"ContentType": "image/jpeg"})
    public_url = f"{PUBLIC_BASE}/{file_key}"
    log(f"Upload OK: {file_key}")
    return file_key, public_url


# ---------------------------------------------------------------------------
# 5. INSERT MONGODB (via SSH tunnel)
# ---------------------------------------------------------------------------

def inserir_post(post: dict) -> str:
    from urllib.parse import quote
    ssh, server = _criar_tunnel_mongo(local_port=27018)
    try:
        uri = f"mongodb://{MONGO_USER}:{quote(MONGO_PASS)}@127.0.0.1:27018/admin?authSource=admin&authMechanism=SCRAM-SHA-1"
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=15000)
        col = client[MONGO_DB][MONGO_COL]

        slug = post["slug"]
        if col.find_one({"slug": slug}):
            hoje = datetime.date.today().strftime("%Y%m%d")
            slug = f"{slug}-{hoje}"
            post["slug"] = slug
            if col.find_one({"slug": slug}):
                raise ValueError(f"Slug ja existe: {slug}")

        result = col.insert_one(post)
        inserted_id = str(result.inserted_id)
        client.close()
    finally:
        server.close()
        ssh.close()
    return inserted_id


# ---------------------------------------------------------------------------
# 6. REBUILD E DEPLOY (build local + SCP, igual publicar_post.py)
# ---------------------------------------------------------------------------

def rebuild_blogs() -> dict:
    import tarfile
    results = {}
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VPS_HOST, port=VPS_PORT, username=VPS_USER, key_filename=SSH_KEY, timeout=30)
    sftp = ssh.open_sftp()

    for blog in BLOGS:
        local_dir = BLOG_LOCAL[blog]
        remote_dir = BLOG_REMOTE[blog]
        log(f"Build {blog}...")
        try:
            npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
            result = subprocess.run(
                [npm_cmd, "run", "build"],
                cwd=local_dir, capture_output=True, text=True, timeout=300,
            )
            if result.returncode != 0:
                raise RuntimeError(f"npm build falhou: {result.stderr[-300:]}")
            log(f"  {blog}: build OK")

            dist_dir = f"{local_dir}/dist"
            tar_path = f"{local_dir}/{blog}-build.tar.gz"
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(dist_dir, arcname=".")
            log(f"  {blog}: tar criado")

            remote_tar = f"/tmp/{blog}-autopost.tar.gz"
            sftp.put(tar_path, remote_tar)
            log(f"  {blog}: SCP OK")

            cmd = (f"sudo find {remote_dir} -mindepth 1 -delete 2>/dev/null; "
                   f"sudo tar -xzf {remote_tar} -C {remote_dir}; "
                   f"sudo chown -R www-data:www-data {remote_dir}; "
                   f"rm {remote_tar}")
            _, stdout, stderr = ssh.exec_command(cmd, timeout=120)
            stdout.read()
            log(f"  {blog}: deploy OK")
            results[blog] = {"ok": True}
        except Exception as e:
            log(f"  {blog}: ERRO - {e}")
            results[blog] = {"ok": False, "erro": str(e)}

    sftp.close()
    ssh.close()
    return results


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    hoje = datetime.date.today().isoformat()
    log_path = LOGS_DIR / f"{hoje}.json"
    run_log = {"data": hoje, "etapas": {}}

    try:
        # 0. Verificar API key
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY ausente. Crie o arquivo .env na pasta auto-post com:\n"
                "ANTHROPIC_API_KEY=sk-ant-..."
            )

        # 1. Tendencias
        log("Buscando tendencias...")
        hn    = fetch_hn_top()
        devto = fetch_devto_trending()
        log(f"  HN: {len(hn)} stories | Dev.to: {len(devto)} artigos")
        run_log["etapas"]["tendencias"] = {"hn": len(hn), "devto": len(devto)}

        # 2. Tema
        tema = selecionar_tema(hn, devto)
        log(f"Tema: {tema}")
        run_log["etapas"]["tema"] = tema

        # 3. Conteudo
        post_data = gerar_conteudo(tema)
        titulo    = post_data["title"]
        subtitulo = post_data.get("subtitulo_capa", "")
        slug      = slugify(post_data.get("slug", titulo))
        post_data["slug"] = slug
        log(f"Post: {titulo} | slug: {slug}")
        run_log["etapas"]["conteudo"] = {"titulo": titulo, "slug": slug}

        # 4. Validar chars
        check_post(post_data)
        log("checkPost OK")

        # 5. Capa
        capa_path = str(LOGS_DIR / f"{hoje}-cover.jpg")
        gerar_capa_post(titulo, subtitulo, post_data, capa_path)
        run_log["etapas"]["capa"] = capa_path

        # 6. Upload
        cover_key, cover_url = upload_capa(capa_path)
        run_log["etapas"]["upload"] = {"key": cover_key, "url": cover_url}

        # 7. Montar doc
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        doc = {
            "isActive": True,
            "title": titulo,
            "slug": slug,
            "summary": post_data.get("summary", ""),
            "metaTitle": post_data.get("metaTitle", titulo[:60]),
            "metaDescription": post_data.get("metaDescription", ""),
            "content": post_data.get("content", ""),
            "faqs": post_data.get("faqs", []),
            "blocks": post_data.get("blocks", []),
            "tags": post_data.get("tags", []),
            "category": post_data.get("category", "tecnologia"),
            "categories": post_data.get("categories", ["tecnologia"]),
            "authorId": "system",
            "authorName": "CuritibaBlog",
            "isPublished": True,
            "publishedAt": now_utc,
            "isFeatured": False,
            "sequence": 0,
            "views": 0,
            "coverImageKey": cover_key,
            "coverImageUrl": cover_url,
            "sites": BLOGS,
        }
        check_post(doc)

        # 8. Inserir MongoDB
        inserted_id = inserir_post(doc)
        log(f"Post inserido: {inserted_id}")
        run_log["etapas"]["mongo"] = {"id": inserted_id, "slug": slug}

        # 9. Rebuild
        rebuild_results = rebuild_blogs()
        run_log["etapas"]["rebuild"] = rebuild_results

        # 10. HTTP check
        try:
            r = requests.get(f"https://curitibablog.com.br/{slug}", timeout=15)
            http_status = r.status_code
        except:
            http_status = 0
        log(f"HTTP curitibablog/{slug}: {http_status}")
        run_log["etapas"]["http_check"] = http_status

        run_log["status"] = "CONCLUIDO"
        run_log["post_url"] = f"https://curitibablog.com.br/{slug}"
        log(f"CONCLUIDO: https://curitibablog.com.br/{slug}")

    except Exception as e:
        import traceback
        run_log["status"] = "ERRO"
        run_log["erro"] = str(e)
        run_log["traceback"] = traceback.format_exc()
        log(f"ERRO: {e}")
        sys.exit(1)
    finally:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(run_log, f, ensure_ascii=False, indent=2, default=str)
        log(f"Log: {log_path}")

    return run_log.get("status") == "CONCLUIDO"


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)

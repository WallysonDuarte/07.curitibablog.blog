"""
publicar_post.py — Recebe JSON do post, gera capa, faz upload, insere MongoDB, rebuilda blogs.
Uso: python publicar_post.py <caminho_para_json>

O JSON deve ter todos os campos do post (title, slug, content, faqs, blocks, etc.)
Gerado pelo agente Claude Code a partir do prompt_post.md.
"""
import os, sys, json, uuid, re, datetime
from pathlib import Path

import requests
import boto3
from botocore.client import Config
import pymongo

THIS_DIR = Path(__file__).parent
LOGS_DIR = THIS_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

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

# Paths locais (source Astro) e remotos (deploy no VPS)
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


def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def slugify(text: str) -> str:
    text = text.lower()
    for pat, rep in [("[àáâãä]","a"),("[èéêë]","e"),("[ìíîï]","i"),("[òóôõö]","o"),("[ùúûü]","u"),("[ç]","c"),("[ñ]","n")]:
        text = re.sub(pat, rep, text)
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    return re.sub(r"-+", "-", text)[:80]


def check_post(post: dict):
    fields = [post.get(k, "") for k in ["title","summary","metaTitle","metaDescription","content"]]
    for faq in post.get("faqs", []):
        fields += [faq.get("question",""), faq.get("answer","")]
    for block in post.get("blocks", []):
        fields.append(block.get("title",""))
        for item in block.get("items", []):
            fields += [item.get("label",""), item.get("value",""), item.get("text","")]
    for f in fields:
        for c in CHARS_PROIBIDOS:
            if c in f:
                raise ValueError(f"Char proibido U+{ord(c):04X} em: {f[:80]!r}")


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


def inserir_post(post: dict) -> str:
    """Insere via SSH tunnel: encaminha porta local 27018 para 127.0.0.1:27017 no VPS."""
    import paramiko, threading, socket

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VPS_HOST, port=VPS_PORT, username=VPS_USER, key_filename=SSH_KEY, timeout=30)

    transport = ssh.get_transport()
    local_port = 27018

    # Cria o tunnel em background
    def _forward(local_sock):
        try:
            chan = transport.open_channel("direct-tcpip", ("127.0.0.1", 27017), ("127.0.0.1", local_port))
            while True:
                r, _, _ = __import__("select").select([local_sock, chan], [], [], 1)
                if local_sock in r:
                    data = local_sock.recv(1024)
                    if not data:
                        break
                    chan.send(data)
                if chan in r:
                    data = chan.recv(1024)
                    if not data:
                        break
                    local_sock.send(data)
        except Exception:
            pass
        finally:
            local_sock.close()

    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", local_port))
    server.listen(1)
    server.settimeout(5)

    def _accept_loop():
        try:
            while True:
                try:
                    conn, _ = server.accept()
                    t = threading.Thread(target=_forward, args=(conn,), daemon=True)
                    t.start()
                except socket.timeout:
                    if not transport.is_active():
                        break
        except Exception:
            pass

    t = threading.Thread(target=_accept_loop, daemon=True)
    t.start()

    import time; time.sleep(0.5)  # aguarda tunnel abrir

    from urllib.parse import quote
    uri = f"mongodb://{MONGO_USER}:{quote(MONGO_PASS)}@127.0.0.1:{local_port}/admin?authSource=admin&authMechanism=SCRAM-SHA-1"
    client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=15000)
    db = client[MONGO_DB]
    col = db[MONGO_COL]

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
    server.close()
    ssh.close()
    return inserted_id


def rebuild_blogs() -> dict:
    """Build local (npm run build) + deploy via SCP para cada blog."""
    import paramiko, subprocess, tarfile, tempfile

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
            # 1. npm run build local (npm.cmd no Windows)
            npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
            result = subprocess.run(
                [npm_cmd, "run", "build"],
                cwd=local_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                raise RuntimeError(f"npm build falhou: {result.stderr[-300:]}")
            log(f"  {blog}: build OK")

            # 2. Tar do dist/
            dist_dir = f"{local_dir}/dist"
            tar_path = f"{local_dir}/{blog}-build.tar.gz"
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(dist_dir, arcname=".")
            log(f"  {blog}: tar criado")

            # 3. SCP para VPS
            remote_tar = f"/tmp/{blog}-autopost.tar.gz"
            sftp.put(tar_path, remote_tar)
            log(f"  {blog}: SCP OK")

            # 4. Extrair no VPS
            cmd = f"sudo find {remote_dir} -mindepth 1 -delete 2>/dev/null; sudo tar -xzf {remote_tar} -C {remote_dir}; sudo chown -R www-data:www-data {remote_dir}; rm {remote_tar}"
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


def main(json_path: str):
    hoje = datetime.date.today().isoformat()
    log_path = LOGS_DIR / f"{hoje}.json"
    run_log = {"data": hoje, "etapas": {}}

    try:
        # 1. Ler JSON do post gerado pelo agente
        log(f"Lendo post de: {json_path}")
        with open(json_path, encoding="utf-8") as f:
            post_data = json.load(f)

        titulo    = post_data["title"]
        subtitulo = post_data.get("subtitulo_capa", "")
        slug      = slugify(post_data.get("slug", titulo))
        post_data["slug"] = slug

        log(f"Post: {titulo} | slug: {slug}")

        # 2. Validar chars proibidos
        check_post(post_data)
        log("checkPost OK")

        # 3. Garantir category valida
        cats_validas = {"ferramentas-de-ia", "desenvolvimento", "tecnologia", "negocios"}
        if post_data.get("category") not in cats_validas:
            post_data["category"] = "tecnologia"
        if not post_data.get("categories"):
            post_data["categories"] = [post_data["category"], "tecnologia"]

        # 4. Gerar capa
        sys.path.insert(0, str(THIS_DIR))
        from gerar_capa import gerar_capa
        capa_path = str(LOGS_DIR / f"{hoje}-cover.jpg")
        gerar_capa(
            titulo=titulo,
            subtitulo=subtitulo,
            card1_titulo=post_data.get("card1_titulo", "Ponto 1"),
            card1_texto=post_data.get("card1_texto", ""),
            card2_titulo=post_data.get("card2_titulo", "Ponto 2"),
            card2_texto=post_data.get("card2_texto", ""),
            card3_titulo=post_data.get("card3_titulo", "Ponto 3"),
            card3_texto=post_data.get("card3_texto", ""),
            output_path=capa_path,
        )
        log(f"Capa gerada: {capa_path}")
        run_log["etapas"]["capa"] = capa_path

        # 5. Upload IDrive E2
        cover_key, cover_url = upload_capa(capa_path)
        run_log["etapas"]["upload"] = {"key": cover_key, "url": cover_url}

        # 6. Montar doc MongoDB
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

        # 7. Inserir MongoDB
        inserted_id = inserir_post(doc)
        log(f"Post inserido: {inserted_id}")
        run_log["etapas"]["mongo"] = {"id": inserted_id, "slug": slug}

        # 8. Rebuild blogs
        rebuild_results = rebuild_blogs()
        run_log["etapas"]["rebuild"] = rebuild_results

        # 9. Verificar HTTP
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
    if len(sys.argv) < 2:
        print("Uso: python publicar_post.py <caminho_para_json>")
        sys.exit(1)
    ok = main(sys.argv[1])
    sys.exit(0 if ok else 1)

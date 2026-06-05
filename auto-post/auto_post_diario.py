"""
Auto Post Diario — CuritibaBlog
Busca o tema mais comentado do dia em tech/dev/IA, gera post completo,
capa, faz upload para IDrive E2, insere no MongoDB e rebuilda os 5 blogs.
"""
import os, sys, json, uuid, re, textwrap, subprocess, time, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependencias: pip install requests boto3 pymongo pillow paramiko
# ---------------------------------------------------------------------------
import requests
import boto3
from botocore.client import Config
import pymongo
import anthropic

# ---------------------------------------------------------------------------
# CONFIGURACAO
# ---------------------------------------------------------------------------
THIS_DIR = Path(__file__).parent
LOGS_DIR = THIS_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

MONGO_URI = "mongodb://curitibasoftware:Curitiba%402025%2B%2B%2B@127.0.0.1:27017/admin?authSource=admin&authMechanism=SCRAM-SHA-1"
MONGO_DB  = "curitibasoftware"
MONGO_COL = "blogposts"

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
BLOG_PATHS = {
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
    """Lanca ValueError se encontrar caracteres proibidos."""
    fields = [
        post.get("title",""), post.get("summary",""), post.get("metaTitle",""),
        post.get("metaDescription",""), post.get("content",""),
    ]
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


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[àáâãä]", "a", text)
    text = re.sub(r"[èéêë]", "e", text)
    text = re.sub(r"[ìíîï]", "i", text)
    text = re.sub(r"[òóôõö]", "o", text)
    text = re.sub(r"[ùúûü]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    text = re.sub(r"[ñ]", "n", text)
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text[:80]


# ---------------------------------------------------------------------------
# 1. PESQUISA DE TENDENCIAS
# ---------------------------------------------------------------------------

def fetch_github_trending() -> list[dict]:
    """Retorna lista de repos trending do GitHub."""
    try:
        resp = requests.get(
            "https://github.com/trending",
            headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        repos = []
        for m in re.finditer(
            r'href="/([^/"]+/[^/"]+)"[^>]*>\s*</span>\s*([^<]{3,80})',
            resp.text
        ):
            pass
        # Parsing simplificado via regex no HTML
        for m in re.finditer(r'<h2[^>]*class="[^"]*h3[^"]*"[^>]*>\s*<a[^>]*href="/([^"]+)"', resp.text):
            repos.append({"repo": m.group(1)})
            if len(repos) >= 10:
                break
        return repos
    except Exception as e:
        log(f"GitHub trending erro: {e}")
        return []


def fetch_hn_top() -> list[dict]:
    """Top stories do Hacker News."""
    try:
        ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10).json()[:20]
        stories = []
        for sid in ids:
            try:
                item = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5).json()
                if item.get("score", 0) >= 50 and item.get("title"):
                    stories.append({
                        "title": item["title"],
                        "url": item.get("url", ""),
                        "score": item.get("score", 0),
                        "comments": item.get("descendants", 0),
                    })
            except:
                pass
        return stories
    except Exception as e:
        log(f"HN erro: {e}")
        return []


def fetch_devto_trending() -> list[dict]:
    """Artigos trending do Dev.to."""
    try:
        resp = requests.get(
            "https://dev.to/api/articles?top=1&per_page=10",
            headers={"Accept": "application/json"},
            timeout=10,
        )
        return [
            {"title": a["title"], "tags": a.get("tag_list", []), "reactions": a.get("public_reactions_count", 0)}
            for a in resp.json()
        ]
    except Exception as e:
        log(f"Dev.to erro: {e}")
        return []


def selecionar_tema(hn_stories, devto, github_repos) -> str:
    """Usa Claude para selecionar o melhor tema do dia."""
    client = anthropic.Anthropic()

    contexto = "Hacker News top stories:\n"
    for s in hn_stories[:10]:
        contexto += f"- {s['title']} (score:{s['score']}, comments:{s['comments']})\n"

    contexto += "\nDev.to trending:\n"
    for a in devto[:5]:
        contexto += f"- {a['title']} (reactions:{a['reactions']})\n"

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Analise as tendencias abaixo e escolha UM tema para um post de blog em PT-BR sobre tecnologia/desenvolvimento/IA.
O tema deve ser relevante para desenvolvedores brasileiros, pratico e educativo.
Responda APENAS com o tema escolhido em portugues, em uma frase curta (max 15 palavras).
NAO use travessao, aspas curvas ou reticencias compostas.

{contexto}

Tema escolhido:"""
        }]
    )
    tema = msg.content[0].text.strip()
    # remover chars proibidos do tema
    for c in CHARS_PROIBIDOS:
        tema = tema.replace(c, " ")
    return tema


# ---------------------------------------------------------------------------
# 2. GERACAO DO CONTEUDO
# ---------------------------------------------------------------------------

# Prompt carregado do arquivo externo — edite prompt_post.md para ajustar
_PROMPT_FILE = THIS_DIR / "prompt_post.md"
PROMPT_POST = _PROMPT_FILE.read_text(encoding="utf-8")

def gerar_conteudo(tema: str) -> dict:
    client = anthropic.Anthropic()
    log(f"Gerando conteudo para: {tema}")

    tema_simples = tema.split(":")[0].strip()
    prompt = (PROMPT_POST
              .replace("{tema}", tema)
              .replace("{tema_simplificado}", tema_simples))

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=12000,
        messages=[{
            "role": "user",
            "content": prompt
        }]
    )

    raw = msg.content[0].text.strip()
    # extrair JSON (pode ter texto antes/depois)
    m = re.search(r'\{[\s\S]+\}', raw)
    if not m:
        raise ValueError(f"Resposta nao contem JSON valido: {raw[:200]}")

    data = json.loads(m.group(0))

    # Validar links do bloco "links" — remover items com URLs claramente inventadas
    for block in data.get("blocks", []):
        if block.get("type") == "links":
            items_validos = []
            for item in block.get("items", []):
                url = item.get("value", "")
                # Manter apenas URLs com dominio reconhecivel (tem pelo menos um . apos https://)
                if re.match(r'https?://[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', url):
                    items_validos.append(item)
                else:
                    log(f"  Link removido (URL invalida): {url}")
            block["items"] = items_validos

    # Garantir category valida
    cats_validas = {"ferramentas-de-ia", "desenvolvimento", "tecnologia", "negocios"}
    if data.get("category") not in cats_validas:
        data["category"] = "tecnologia"
    if not data.get("categories"):
        data["categories"] = [data["category"], "tecnologia"]

    # Garantir tags como lista
    if isinstance(data.get("tags"), str):
        data["tags"] = [t.strip() for t in data["tags"].split(",") if t.strip()]

    return data


# ---------------------------------------------------------------------------
# 3. UPLOAD IDRIVE E2
# ---------------------------------------------------------------------------

def upload_capa(local_path: str) -> tuple[str, str]:
    """Faz upload da capa e retorna (key, public_url)."""
    file_key = f"covers/{uuid.uuid4()}-cover.jpg"

    s3 = boto3.client(
        "s3",
        endpoint_url=IDRIVE_URL,
        aws_access_key_id=IDRIVE_KEY,
        aws_secret_access_key=IDRIVE_SECRET,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )

    # garantir bucket existe
    try:
        s3.head_bucket(Bucket=IDRIVE_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=IDRIVE_BUCKET)

    s3.upload_file(
        local_path,
        IDRIVE_BUCKET,
        file_key,
        ExtraArgs={"ContentType": "image/jpeg"},
    )

    public_url = f"{PUBLIC_BASE}/{file_key}"
    log(f"Imagem uploaded: {file_key}")
    return file_key, public_url


# ---------------------------------------------------------------------------
# 4. INSERT MONGODB
# ---------------------------------------------------------------------------

def inserir_post(post: dict) -> str:
    client = pymongo.MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    col = db[MONGO_COL]

    # verificar slug unico
    slug = post["slug"]
    existing = col.find_one({"slug": slug})
    if existing:
        # adicionar sufixo data
        hoje = datetime.date.today().strftime("%Y%m%d")
        slug = f"{slug}-{hoje}"
        post["slug"] = slug
        existing2 = col.find_one({"slug": slug})
        if existing2:
            raise ValueError(f"Slug ja existe: {slug}")

    result = col.insert_one(post)
    client.close()
    return str(result.inserted_id)


# ---------------------------------------------------------------------------
# 5. REBUILD E DEPLOY DOS 5 BLOGS
# ---------------------------------------------------------------------------

def rebuild_blogs() -> dict:
    """SSH no VPS e rebuilda/copia cada blog."""
    import paramiko

    results = {}
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VPS_HOST, port=VPS_PORT, username=VPS_USER, key_filename=SSH_KEY, timeout=30)

    for blog, path in BLOG_PATHS.items():
        log(f"Rebuilding {blog}...")
        cmd = f"cd {path} && npm run build 2>&1 | tail -5"
        _, stdout, stderr = ssh.exec_command(cmd, timeout=300)
        out = stdout.read().decode()
        err = stderr.read().decode()
        ok = "done" in out.lower() or "built" in out.lower() or "complete" in out.lower()
        results[blog] = {"ok": ok, "out": out[-200:], "err": err[-100:]}
        log(f"  {blog}: {'OK' if ok else 'ERRO'}")

    ssh.close()
    return results


def verificar_http(url: str, slug: str) -> int:
    """Verifica HTTP status de um post publicado."""
    try:
        r = requests.get(f"{url}/{slug}", timeout=15, allow_redirects=True)
        return r.status_code
    except:
        return 0


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    hoje = datetime.date.today().isoformat()
    log_path = LOGS_DIR / f"{hoje}.json"
    run_log = {"data": hoje, "etapas": {}}

    try:
        # 1. Tendencias
        log("Buscando tendencias...")
        hn = fetch_hn_top()
        devto = fetch_devto_trending()
        github = fetch_github_trending()
        run_log["etapas"]["tendencias"] = {
            "hn_count": len(hn), "devto_count": len(devto), "github_count": len(github)
        }

        # 2. Selecionar tema
        tema = selecionar_tema(hn, devto, github)
        log(f"Tema selecionado: {tema}")
        run_log["etapas"]["tema"] = tema

        # 3. Gerar conteudo
        post_data = gerar_conteudo(tema)

        titulo    = post_data["title"]
        subtitulo = post_data.get("subtitulo_capa", "")
        slug      = slugify(post_data.get("slug", titulo))

        log(f"Post gerado: {titulo}")
        run_log["etapas"]["conteudo"] = {"titulo": titulo, "slug": slug}

        # 4. Validar chars proibidos
        check_post(post_data)
        log("checkPost OK")

        # 5. Gerar capa
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

        # 6. Upload IDrive E2
        cover_key, cover_url = upload_capa(capa_path)
        run_log["etapas"]["upload"] = {"key": cover_key, "url": cover_url}

        # 7. Montar doc MongoDB
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

        # validar doc final
        check_post(doc)

        # 8. Inserir MongoDB
        inserted_id = inserir_post(doc)
        log(f"Post inserido: {inserted_id}")
        run_log["etapas"]["mongo"] = {"id": inserted_id, "slug": slug}

        # 9. Rebuild blogs
        rebuild_results = rebuild_blogs()
        run_log["etapas"]["rebuild"] = rebuild_results

        # 10. Verificar HTTP (curitibablog)
        http_status = verificar_http("https://curitibablog.com.br", slug)
        log(f"HTTP curitibablog/{slug}: {http_status}")
        run_log["etapas"]["http_check"] = http_status

        run_log["status"] = "CONCLUIDO"
        run_log["post_url"] = f"https://curitibablog.com.br/{slug}"

    except Exception as e:
        import traceback
        run_log["status"] = "ERRO"
        run_log["erro"] = str(e)
        run_log["traceback"] = traceback.format_exc()
        log(f"ERRO: {e}")

    finally:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(run_log, f, ensure_ascii=False, indent=2, default=str)
        log(f"Log salvo: {log_path}")

    return run_log.get("status") == "CONCLUIDO"


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)

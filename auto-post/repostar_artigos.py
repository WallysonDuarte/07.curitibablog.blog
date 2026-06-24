"""
Repostar Artigos Antigos — CuritibaBlog
Publica posts existentes nas redes sociais (Facebook, Instagram, X, LinkedIn).
NÃO posta no WhatsApp grupo (anti-spam).

Fluxo por execução:
  1. Carrega (ou gera) repost-checklist.json com todos os posts ordenados por createdAt ASC
  2. Acha o próximo post com status "pendente"
  3. Publica em todos os canais ativos
  4. Marca como "publicado" no checklist

Uso:
  python repostar_artigos.py              -> posta 1 post e sai
  python repostar_artigos.py --gerar      -> (re)gera checklist do zero sem postar
  python repostar_artigos.py --status     -> exibe progresso sem postar
  python repostar_artigos.py --pausar     -> salva flag de pausa (sem postar)
  python repostar_artigos.py --retomar    -> remove flag de pausa
"""
import sys, json, datetime
from pathlib import Path

import requests

THIS_DIR   = Path(__file__).parent
LOGS_DIR   = THIS_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

CHECKLIST_PATH = LOGS_DIR / "repost-checklist.json"
PAUSA_FLAG     = LOGS_DIR / "repost-pausado.flag"

API_BASE = "https://api.curitibasoftware.com.br"
COVER_BASE = f"{API_BASE}/api/blog/cover"


def log(msg: str):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")
    # Append ao log diário
    log_path = LOGS_DIR / f"repost-run-{datetime.date.today().isoformat()}.log"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now().isoformat()}] {msg}\n")


# ---------------------------------------------------------------------------
# Checklist
# ---------------------------------------------------------------------------

def _buscar_todos_posts() -> list[dict]:
    """Busca todos os posts publicados via API, ordenados por createdAt ASC."""
    todos = []
    page  = 1
    size  = 100

    log("Buscando posts da API...")
    while True:
        try:
            r = requests.get(
                f"{API_BASE}/api/blog/posts",
                params={"site": "curitibablog", "page": page, "size": size},
                timeout=30,
            )
            r.raise_for_status()
            envelope = r.json()
        except Exception as e:
            log(f"ERRO ao buscar página {page}: {e}")
            break

        # API retorna {"success":true,"data":{"items":[...],"hasNext":bool,...}}
        if isinstance(envelope, dict) and "data" in envelope:
            data_obj = envelope["data"]
            items    = data_obj.get("items", [])
            has_next = data_obj.get("hasNext", False)
        elif isinstance(envelope, list):
            items    = envelope
            has_next = len(items) == size
        else:
            items    = []
            has_next = False

        if not items:
            break
        todos.extend(items)
        log(f"  Página {page}: {len(items)} posts ({len(todos)} total)")
        if not has_next:
            break
        page += 1

    # Ordena por createdAt ASC (mais antigo primeiro)
    def _parse_dt(p):
        v = p.get("createdAt") or p.get("publishedAt") or ""
        try:
            return datetime.datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return datetime.datetime.min

    todos.sort(key=_parse_dt)
    return todos


def gerar_checklist(forcar: bool = False) -> dict:
    """Gera repost-checklist.json. Se já existe e não forcar, mantém status existente."""
    existente: dict = {}
    if CHECKLIST_PATH.exists() and not forcar:
        try:
            dados = json.loads(CHECKLIST_PATH.read_text(encoding="utf-8"))
            existente = {p["slug"]: p for p in dados.get("posts", [])}
            log(f"Checklist existente carregado ({len(existente)} entradas)")
        except Exception as e:
            log(f"AVISO: checklist corrompido, regenerando — {e}")

    posts_api = _buscar_todos_posts()
    if not posts_api:
        log("ERRO: nenhum post retornado pela API")
        sys.exit(1)

    entradas = []
    for p in posts_api:
        slug = p.get("slug", "")
        if not slug:
            continue

        if slug in existente:
            # Preserva status já existente (publicado, erro etc.)
            entradas.append(existente[slug])
        else:
            entradas.append({
                "id":          str(p.get("id", p.get("_id", ""))),
                "slug":        slug,
                "titulo":      p.get("title", ""),
                "summary":     p.get("summary", ""),
                "createdAt":   p.get("createdAt", ""),
                "cover_url":   f"{COVER_BASE}/{slug}",
                "status":      "pendente",
                "publicado_em": None,
                "resultados":  {},
            })

    checklist = {
        "gerado_em":  datetime.datetime.now().isoformat(),
        "total":      len(entradas),
        "publicados": sum(1 for e in entradas if e["status"] == "publicado"),
        "pendentes":  sum(1 for e in entradas if e["status"] == "pendente"),
        "erros":      sum(1 for e in entradas if e["status"] == "erro"),
        "posts":      entradas,
    }

    CHECKLIST_PATH.write_text(json.dumps(checklist, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Checklist salvo: {len(entradas)} posts ({checklist['publicados']} publicados, {checklist['pendentes']} pendentes)")
    return checklist


def carregar_checklist() -> dict:
    """Carrega checklist existente ou gera do zero."""
    if not CHECKLIST_PATH.exists():
        log("Checklist não encontrado — gerando pela primeira vez...")
        return gerar_checklist()
    try:
        return json.loads(CHECKLIST_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"Checklist corrompido — regenerando: {e}")
        return gerar_checklist(forcar=True)


def salvar_checklist(checklist: dict):
    checklist["publicados"] = sum(1 for p in checklist["posts"] if p["status"] == "publicado")
    checklist["pendentes"]  = sum(1 for p in checklist["posts"] if p["status"] == "pendente")
    checklist["erros"]      = sum(1 for p in checklist["posts"] if p["status"] == "erro")
    CHECKLIST_PATH.write_text(json.dumps(checklist, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Publicação
# ---------------------------------------------------------------------------

def _importar_funcoes():
    """Importa funções de publicar_post.py sem executar o pipeline completo."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("publicar_post", THIS_DIR / "publicar_post.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def publicar_post_redes(entrada: dict) -> dict:
    """Publica um post em FB + IG + X + LinkedIn. Retorna dict com resultados por canal."""
    slug      = entrada["slug"]
    titulo    = entrada["titulo"]
    summary   = entrada.get("summary", "")
    cover_url = entrada.get("cover_url") or f"{COVER_BASE}/{slug}"

    log(f"Publicando: {slug}")
    log(f"  Título: {titulo[:80]}")

    try:
        pp = _importar_funcoes()
    except Exception as e:
        log(f"ERRO ao importar publicar_post: {e}")
        return {"erro_import": str(e)}

    resultados = {}

    # Facebook + Instagram
    try:
        r_social = pp.postar_redes_sociais(titulo, summary, slug, cover_url)
        resultados["facebook"]  = r_social.get("facebook", {})
        resultados["instagram"] = r_social.get("instagram", {})
        log(f"  Facebook: {r_social.get('facebook', {})}")
        log(f"  Instagram: {r_social.get('instagram', {})}")
    except Exception as e:
        log(f"  Facebook/Instagram EXCECAO: {e}")
        resultados["facebook"]  = {"ok": False, "erro": str(e)}
        resultados["instagram"] = {"ok": False, "erro": str(e)}

    # X (Twitter)
    try:
        r_x = pp.postar_x_twitter(titulo, summary, slug)
        resultados["x"] = r_x
        log(f"  X: {r_x}")
    except Exception as e:
        log(f"  X EXCECAO: {e}")
        resultados["x"] = {"ok": False, "erro": str(e)}

    # LinkedIn
    try:
        r_li = pp.postar_linkedin(titulo, summary, slug)
        resultados["linkedin"] = r_li
        log(f"  LinkedIn: {r_li}")
    except Exception as e:
        log(f"  LinkedIn EXCECAO: {e}")
        resultados["linkedin"] = {"ok": False, "erro": str(e)}

    # WhatsApp grupo: EXCLUÍDO (anti-spam)
    resultados["whatsapp_grupo"] = "excluido_anti_spam"

    return resultados


def _algum_ok(resultados: dict) -> bool:
    """Retorna True se ao menos um canal publicou com sucesso."""
    for canal, r in resultados.items():
        if canal == "whatsapp_grupo":
            continue
        if isinstance(r, dict) and r.get("ok"):
            return True
    return False


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------

def cmd_status():
    checklist = carregar_checklist()
    total      = checklist.get("total", 0)
    publicados = checklist.get("publicados", 0)
    pendentes  = checklist.get("pendentes", 0)
    erros      = checklist.get("erros", 0)
    pausado    = PAUSA_FLAG.exists()

    print(f"\n=== REPOST ARTIGOS — STATUS {'[PAUSADO]' if pausado else ''} ===")
    print(f"Total:      {total}")
    print(f"Publicados: {publicados} ({100*publicados//total if total else 0}%)")
    print(f"Pendentes:  {pendentes}")
    print(f"Erros:      {erros}")

    if pendentes > 0:
        proximo = next((p for p in checklist["posts"] if p["status"] == "pendente"), None)
        if proximo:
            print(f"\nPróximo:    {proximo['slug']}")
            print(f"            Criado em: {proximo.get('createdAt','?')[:10]}")

    print()


def cmd_postar():
    """Posta 1 post (o próximo pendente) e atualiza checklist."""
    if PAUSA_FLAG.exists():
        log("Repost PAUSADO — rode com --retomar para continuar")
        sys.exit(0)

    checklist = carregar_checklist()
    entrada = next((p for p in checklist["posts"] if p["status"] == "pendente"), None)

    if not entrada:
        log("Todos os posts já foram publicados nas redes sociais!")
        sys.exit(0)

    resultados = publicar_post_redes(entrada)

    # Determina status final
    ok = _algum_ok(resultados)
    entrada["status"]       = "publicado" if ok else "erro"
    entrada["publicado_em"] = datetime.datetime.now().isoformat()
    entrada["resultados"]   = resultados

    salvar_checklist(checklist)

    publicados = checklist.get("publicados", 0)
    total      = checklist.get("total", 0)
    log(f"Checklist atualizado: {publicados}/{total} publicados")

    if not ok:
        log(f"AVISO: nenhum canal publicou com sucesso para '{entrada['slug']}'")
        log(f"Resultados: {json.dumps(resultados, ensure_ascii=False)}")
        sys.exit(1)


def cmd_gerar():
    log("Regerando checklist do zero...")
    gerar_checklist(forcar=True)


def cmd_pausar():
    PAUSA_FLAG.write_text("pausado", encoding="utf-8")
    log("Repost PAUSADO. Use --retomar para continuar.")


def cmd_retomar():
    if PAUSA_FLAG.exists():
        PAUSA_FLAG.unlink()
        log("Repost RETOMADO.")
    else:
        log("Não estava pausado.")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--gerar" in args:
        cmd_gerar()
    elif "--status" in args:
        cmd_status()
    elif "--pausar" in args:
        cmd_pausar()
    elif "--retomar" in args:
        cmd_retomar()
    else:
        cmd_postar()

"""
Auto Post Diario - CuritibaBlog
Fluxo correto:
  1. Busca tendencias do dia (HN + Dev.to) e salva em logs/temas-YYYY-MM-DD.json
  2. Claude Code (o vigilante) le as tendencias, escolhe tema, gera o JSON do post
     e salva em logs/post-YYYY-MM-DD.json
  3. Este script le o JSON gerado e publica (capa Flow + IDrive + MongoDB + deploy)

Nao usa Anthropic SDK - a geracao de conteudo e feita pelo Claude Code diretamente.
Uso:
  python auto_post_diario.py buscar_temas   -> etapa 1: busca e salva tendencias
  python auto_post_diario.py publicar       -> etapa 3: publica o post do dia (JSON ja gerado)
  (sem argumento)                           -> executa etapa 1 e aguarda o Claude gerar o post
"""
import os, sys, json, datetime
from pathlib import Path

import requests

THIS_DIR = Path(__file__).parent
LOGS_DIR = THIS_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

HOJE = datetime.date.today().isoformat()
TEMAS_PATH = LOGS_DIR / f"temas-{HOJE}.json"
POST_PATH  = LOGS_DIR / f"post-{HOJE}.json"


def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ---------------------------------------------------------------------------
# ETAPA 1 - Busca tendencias
# ---------------------------------------------------------------------------

def _notificar_admin(mensagem: str):
    """Envia alerta WhatsApp para o admin via publicar_post.notificar_whatsapp_pessoal."""
    try:
        sys.path.insert(0, str(THIS_DIR))
        from publicar_post import notificar_whatsapp_pessoal
        notificar_whatsapp_pessoal(mensagem)
    except Exception as e:
        log(f"Falha ao notificar WhatsApp admin: {e}")


def buscar_temas() -> dict:
    """Busca HN + Dev.to e salva em logs/temas-HOJE.json"""
    from buscar_temas import fetch_hn_top, fetch_devto_trending
    log("Buscando tendencias HN + Dev.to...")
    hn    = fetch_hn_top()
    devto = fetch_devto_trending()

    # Detectar falha: listas vazias ou contendo apenas erros
    hn_ok    = [x for x in hn    if "erro" not in x and x.get("titulo")]
    devto_ok = [x for x in devto if "erro" not in x and x.get("titulo")]

    if not hn_ok and not devto_ok:
        hora = datetime.datetime.now().strftime("%H:%M")
        log(f"AVISO: busca de temas falhou completamente ({hora}) — notificando admin")
        _notificar_admin(
            f"⚠️ *curitibablog — busca de temas FALHOU* ({hora})\n\n"
            f"HN: {hn}\n\nDev.to: {devto}\n\n"
            f"Post das {hora} NAO sera gerado automaticamente.\n"
            f"Verifique conexao com internet e rode manualmente se necessario."
        )
    elif not hn_ok:
        log("AVISO: HN retornou vazio — usando apenas Dev.to")
    elif not devto_ok:
        log("AVISO: Dev.to retornou vazio — usando apenas HN")

    resultado = {"data": HOJE, "hn": hn, "devto": devto}
    TEMAS_PATH.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Tendencias salvas: {TEMAS_PATH}")
    log(f"  HN: {len(hn_ok)} stories validas | Dev.to: {len(devto_ok)} artigos validos")
    print("\n=== TEMAS DO DIA ===")
    print(TEMAS_PATH.read_text(encoding="utf-8"))
    print("\n=== PROXIMO PASSO ===")
    print("Claude Code deve:")
    print("1. Ler o arquivo de temas acima")
    print("2. Escolher o tema mais relevante para devs brasileiros")
    print("3. Gerar o JSON completo do post seguindo prompt_post.md")
    print(f"4. Salvar em: {POST_PATH}")
    print("5. Rodar: python auto_post_diario.py publicar")
    return resultado


# ---------------------------------------------------------------------------
# ETAPA 3 - Publica post ja gerado
# ---------------------------------------------------------------------------

def publicar() -> bool:
    """Le logs/post-HOJE.json e executa o pipeline de publicacao"""
    if not POST_PATH.exists():
        log(f"ERRO: arquivo de post nao encontrado: {POST_PATH}")
        log("Claude Code precisa gerar o post primeiro.")
        return False

    log(f"Publicando post de: {POST_PATH}")
    result = os.system(
        f'python "{THIS_DIR / "publicar_post.py"}" "{POST_PATH}"'
    )
    return result == 0


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "buscar_temas"

    if cmd == "buscar_temas":
        buscar_temas()
    elif cmd == "publicar":
        ok = publicar()
        sys.exit(0 if ok else 1)
    else:
        print(f"Comando desconhecido: {cmd}")
        print("Uso: python auto_post_diario.py [buscar_temas|publicar]")
        sys.exit(1)

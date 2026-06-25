"""
gerar_capa_flow.py — Gera capa de blog via Google Flow (Playwright + CDP).

Fluxo:
1. Conecta ao Chrome via CDP (perfil wallyson.duarte.temp@gmail.com)
2. Abre o projeto Flow do curitibablog
3. Clica em "Incluir no comando" em uma imagem de referencia da galeria
4. Cola o prompt PT-BR via clipboard (sem Enter no meio)
5. Clica em Criar e aguarda a imagem aparecer
6. Baixa e salva como JPEG

Uso:
    from gerar_capa_flow import gerar_capa_flow
    path = gerar_capa_flow(titulo, subtitulo, output_path)
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

# --- Configuracao ---
CHROME_USER_DATA = r"C:\Users\Poseidon\AppData\Local\Google\Chrome\User Data"
CHROME_PROFILE   = "Default"  # wallyson.duarte.temp@gmail.com
FLOW_URL         = "https://labs.google/fx/pt/tools/flow/project/a2f801ad-a8ee-45e1-94bb-4c0de816c631"
DEBUG_PORT       = 9222

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]

EXCLUIR_SRCS = [
    "accounts.google", "favicon", "csw.lenovo", "vantage",
    "gstatic.com/images/branding", "lh3.googleusercontent.com/a/",
]

# Prompt curto (~800 chars) para evitar filtro de "atividade incomum" do Flow
PROMPT_TEMPLATE = (
    'YouTube thumbnail 16:9, dark tech background, minimal and premium. '
    'Large bold title text: "{titulo}". '
    'IMPORTANT: do NOT make the entire title white — use color hierarchy: '
    'key words in cyan, green or orange; secondary words in white or gray. Max 3 colors in title. '
    'Small header at top: "Entendendo na prática" in light gray. '
    'One tech visual element on the side (AI chip, neural network, code screen). '
    'Footer text small: "curitibablog.com.br • devlevelup.com.br • dozeroaojunior.com.br". '
    'Three small icon cards at bottom. '
    'Clean, sharp, readable on mobile. No clutter, no distorted text, no monochrome title. '
    'Spell every word in the title exactly as written.'
)


# ---------------------------------------------------------------------------
# Chrome helpers
# ---------------------------------------------------------------------------

def _encontrar_chrome() -> str:
    for p in CHROME_PATHS:
        if Path(p).exists():
            return p
    raise FileNotFoundError("Chrome nao encontrado.")


def _fechar_chrome():
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
    time.sleep(2)


def _abrir_chrome_com_debug(chrome_path: str):
    cmd = [
        chrome_path,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={CHROME_USER_DATA}",
        f"--profile-directory={CHROME_PROFILE}",
        "--no-first-run",
        "--no-default-browser-check",
        "--no-sandbox",
        "about:blank",
    ]
    subprocess.Popen(cmd)
    print(f"  Chrome aberto (debug port {DEBUG_PORT})")
    time.sleep(8)


# ---------------------------------------------------------------------------
# Playwright helpers
# ---------------------------------------------------------------------------

async def _get_srcs_galeria(page) -> list:
    # Filtra apenas imagens reais geradas (exclui ícones, avatares e cards de erro)
    return await page.evaluate("""(excluir) => {
        return Array.from(document.querySelectorAll('img'))
            .filter(img => {
                const rect = img.getBoundingClientRect();
                const src = img.src || '';
                // Deve ter tamanho significativo e src com blob ou ggpht (imagens geradas)
                const isGenerated = src.startsWith('blob:') || src.includes('ggpht') || src.includes('generated') || (src.startsWith('http') && src.length > 60);
                return rect.width > 100 && rect.height > 80 && isGenerated
                    && !excluir.some(x => src.includes(x));
            })
            .map(img => img.src);
    }""", EXCLUIR_SRCS)


async def _colar_texto_no_campo(page, texto: str) -> bool:
    """
    Cola o texto no contenteditable usando clipboard API do browser.
    Evita keyboard.type() que transforma newlines em Enter (submete o form).
    """
    # Coloca o texto no clipboard via JS
    escaped = texto.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
    ok = await page.evaluate(f"""async () => {{
        try {{
            await navigator.clipboard.writeText(`{escaped}`);
            return true;
        }} catch(e) {{
            // Fallback: cria um textarea temporario e copia
            const ta = document.createElement('textarea');
            ta.value = `{escaped}`;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            return true;
        }}
    }}""")

    if not ok:
        return False

    # Clica no contenteditable e cola
    try:
        await page.click('[contenteditable="true"]', timeout=8000)
        await asyncio.sleep(0.4)
        # Seleciona tudo e substitui pelo conteudo do clipboard
        await page.keyboard.press("Control+a")
        await asyncio.sleep(0.2)
        await page.keyboard.press("Control+v")
        await asyncio.sleep(0.8)
        return True
    except Exception as e:
        print(f"  Erro ao colar: {e}")
        return False


async def _clicar_incluir_no_comando(page) -> bool:
    """
    Clica em 'Incluir no comando' na primeira imagem disponivel na galeria.
    Esse botao aparece ao passar o mouse sobre uma imagem gerada anteriormente.
    """
    # Busca imagens visiveis na galeria (exclui icones/avatares)
    imgs = await page.query_selector_all("img")
    imagens_galeria = []
    for img in imgs:
        try:
            box = await img.bounding_box()
            src = await img.get_attribute("src") or ""
            if (box and box["width"] > 80 and box["height"] > 80
                    and not any(x in src for x in EXCLUIR_SRCS)):
                imagens_galeria.append(img)
        except Exception:
            continue

    if not imagens_galeria:
        print("  Nenhuma imagem na galeria para 'Incluir no comando'")
        return False

    # Passa o mouse sobre a primeira imagem para revelar o menu
    img_ref = imagens_galeria[0]
    try:
        await img_ref.hover(timeout=3000)
        await asyncio.sleep(1.5)
    except Exception:
        pass

    # Tenta encontrar o botao "Incluir no comando" por texto ou role
    btn = None
    for seletor in [
        'button[role="menuitem"]:has-text("Incluir no comando")',
        'button:has-text("Incluir no comando")',
        '[role="menuitem"]:has-text("Incluir")',
    ]:
        try:
            loc = page.locator(seletor)
            if await loc.count() > 0:
                btn = loc.first
                break
        except Exception:
            continue

    if btn is None:
        # Tenta clicar com botao direito para abrir menu de contexto
        try:
            await img_ref.click(button="right", timeout=3000)
            await asyncio.sleep(1)
            for seletor in [
                'button[role="menuitem"]:has-text("Incluir no comando")',
                'button:has-text("Incluir no comando")',
                '[role="menuitem"]:has-text("Incluir")',
                'text=Incluir no comando',
            ]:
                try:
                    loc = page.locator(seletor)
                    if await loc.count() > 0:
                        btn = loc.first
                        break
                except Exception:
                    continue
        except Exception:
            pass

    if btn:
        try:
            await btn.click(timeout=3000)
            print("  'Incluir no comando' clicado")
            await asyncio.sleep(1)
            return True
        except Exception as e:
            print(f"  Erro ao clicar 'Incluir no comando': {e}")

    print("  Botao 'Incluir no comando' nao encontrado — prosseguindo sem imagem de referencia")
    return False


async def _digitar_e_enviar(page, prompt: str) -> tuple[bool, set]:
    """
    Prepara e envia o prompt.
    Retorna (sucesso, srcs_antes_do_envio) onde srcs_antes ja reflete o estado
    pos-'Incluir no comando', para comparacao correta na deteccao de nova imagem.
    """
    await page.keyboard.press("Escape")
    await asyncio.sleep(0.5)

    # Garante que esta no Flow
    if "flow/project" not in page.url:
        try:
            await page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=20000)
        except Exception:
            pass
        await asyncio.sleep(4)

    # Verifica se tem imagens na galeria para usar como referencia
    srcs = await _get_srcs_galeria(page)
    if srcs:
        print(f"  {len(srcs)} imagem(ns) na galeria — tentando 'Incluir no comando'")
        await _clicar_incluir_no_comando(page)
        await asyncio.sleep(2)  # aguarda UI estabilizar apos acao
    else:
        print("  Galeria vazia — gerando sem imagem de referencia")

    # Verifica se o contenteditable existe
    campo = await page.query_selector('[contenteditable="true"]')
    if not campo:
        print("  contenteditable nao encontrado — recarregando...")
        try:
            await page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=20000)
        except Exception:
            pass
        await asyncio.sleep(5)
        campo = await page.query_selector('[contenteditable="true"]')
        if not campo:
            print("  Nao encontrou contenteditable apos reload")
            return False

    # Cola o prompt via clipboard (sem Enter no meio)
    print(f"  Colando prompt ({len(prompt)} chars) via clipboard...")
    colado = await _colar_texto_no_campo(page, prompt)
    if not colado:
        return False

    # Confirma que o texto foi inserido
    await asyncio.sleep(0.5)
    texto_atual = await page.evaluate("""() => {
        const el = document.querySelector('[contenteditable="true"]');
        return el ? (el.innerText || el.textContent || '').trim() : '';
    }""")
    if len(texto_atual) < 10:
        print("  Campo vazio apos colar — tentando keyboard.type() sem newlines")
        # Fallback: prompt em uma linha so (sem newlines)
        prompt_linha = prompt.replace("\n", " ")
        try:
            await page.click('[contenteditable="true"]', timeout=5000)
            await page.keyboard.press("Control+a")
            await asyncio.sleep(0.2)
            await page.keyboard.type(prompt_linha, delay=5)
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"  Fallback type() falhou: {e}")
            return False
    else:
        print(f"  Campo OK: {texto_atual[:80]}...")

    # Captura srcs APOS toda preparacao, ANTES de clicar Criar
    srcs_antes_envio = set(await _get_srcs_galeria(page))
    print(f"  Galeria antes do envio: {len(srcs_antes_envio)} imagens")

    # Clica no botao Criar
    clicou = False
    try:
        btns = page.locator("button")
        n = await btns.count()
        for i in range(n):
            btn = btns.nth(i)
            try:
                txt = (await btn.inner_text()).strip()
                # Botao "Criar" mas NAO o "Incluir no comando"
                if "Criar" in txt and "Incluir" not in txt and "add" not in txt.lower():
                    await btn.click(timeout=3000)
                    print(f"  Botao clicado: '{txt[:40]}'")
                    clicou = True
                    break
            except Exception:
                continue
    except Exception:
        pass

    if not clicou:
        print("  Usando Ctrl+Enter como fallback")
        await page.keyboard.press("Control+Enter")
        clicou = True

    await asyncio.sleep(1)
    return clicou, srcs_antes_envio


async def _aguardar_e_baixar(page, srcs_antes: set, output_path: str) -> bool:
    """Aguarda nova imagem e faz download."""
    print("  Aguardando geracao (ate 180s)...")
    nova_src = None
    for i in range(36):
        await asyncio.sleep(5)
        try:
            srcs_agora = set(await _get_srcs_galeria(page))
        except Exception as e:
            print(f"  Erro ao verificar galeria: {e}")
            return False
        novas = srcs_agora - srcs_antes
        if novas:
            nova_src = list(novas)[-1]
            print(f"  Nova imagem detectada apos {(i + 1) * 5}s")
            break
        if i % 4 == 3:
            print(f"  Aguardando... {(i + 1) * 5}s ({len(srcs_agora)} imgs)")

    if not nova_src:
        print("  Timeout: nenhuma imagem gerada em 180s")
        return False

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    try:
        if nova_src.startswith("http"):
            resp = await page.request.get(nova_src)
            if resp.ok:
                conteudo = await resp.body()
                tmp_png = str(Path(output_path).with_suffix(".tmp.png"))
                Path(tmp_png).write_bytes(conteudo)
                _converter_para_jpg(tmp_png, output_path)
                Path(tmp_png).unlink(missing_ok=True)
                tamanho = Path(output_path).stat().st_size // 1024
                print(f"  Imagem salva ({tamanho}KB): {output_path}")
                return True
    except Exception as e:
        print(f"  Erro HTTP download: {e}")

    # Fallback: screenshot do elemento
    try:
        el = await page.query_selector(f'img[src="{nova_src}"]')
        if el:
            tmp_png = str(Path(output_path).with_suffix(".tmp.png"))
            await el.screenshot(path=tmp_png)
            _converter_para_jpg(tmp_png, output_path)
            Path(tmp_png).unlink(missing_ok=True)
            print(f"  Imagem salva (screenshot): {output_path}")
            return True
    except Exception as e:
        print(f"  Erro screenshot: {e}")

    return False


def _converter_para_jpg(src: str, dst: str):
    try:
        from PIL import Image
        img = Image.open(src).convert("RGB")
        img.save(dst, "JPEG", quality=92)
    except ImportError:
        import shutil
        shutil.copy2(src, dst)


# ---------------------------------------------------------------------------
# Conexao Chrome
# ---------------------------------------------------------------------------

async def _conectar_chrome(p, forcar_restart: bool = False):
    chrome_path = _encontrar_chrome()

    if not forcar_restart:
        for tentativa in range(3):
            try:
                browser = await p.chromium.connect_over_cdp(
                    f"http://localhost:{DEBUG_PORT}", timeout=5000
                )
                ctx = browser.contexts[0] if browser.contexts else None
                if ctx:
                    # Busca pagina do Flow ja aberta
                    page = next(
                        (pg for pg in ctx.pages if "flow/project" in pg.url),
                        None,
                    )
                    if page:
                        print("  Reutilizando aba do Flow ja aberta")
                        return browser, page
                    # Abre nova aba no Chrome ja aberto
                    page = await ctx.new_page()
                    await page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(4)
                    return browser, page
            except Exception:
                if tentativa < 2:
                    await asyncio.sleep(2)

    # Reinicia Chrome
    print("  Fechando Chrome...")
    _fechar_chrome()
    print("  Abrindo Chrome (perfil wallyson.duarte.temp@gmail.com)...")
    _abrir_chrome_com_debug(chrome_path)

    browser = None
    for tentativa in range(10):
        try:
            browser = await p.chromium.connect_over_cdp(
                f"http://localhost:{DEBUG_PORT}", timeout=5000
            )
            break
        except Exception:
            print(f"  Aguardando Chrome... ({tentativa + 1}/10)")
            await asyncio.sleep(2)

    if not browser:
        raise RuntimeError("Nao foi possivel conectar ao Chrome.")

    ctx = browser.contexts[0] if browser.contexts else None
    if not ctx:
        raise RuntimeError("Nenhum contexto no Chrome.")

    # Abre nova aba (evita pagina do Lenovo Vantage que nao navega)
    page = await ctx.new_page()
    print(f"  Navegando para Flow...")
    for tentativa_nav in range(5):
        try:
            await page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            if "flow/project" in page.url or "labs.google" in page.url:
                print(f"  Flow OK (tentativa {tentativa_nav + 1})")
                break
        except Exception as e_nav:
            print(f"  Nav {tentativa_nav + 1}/5 falhou ({type(e_nav).__name__}) — aguardando...")
            await asyncio.sleep(4)

    await asyncio.sleep(3)

    # Trata landing page nao autenticada
    try:
        btn = await page.query_selector("text=Create with Google Flow")
        if btn:
            print("  Clicando em 'Create with Google Flow'...")
            await btn.click()
            await asyncio.sleep(8)
    except Exception:
        pass

    # Aguarda login se necessario
    for _ in range(20):
        url = page.url
        if "accounts.google.com" in url or "signin" in url:
            print("  Login necessario — faca login com wallyson.duarte.temp@gmail.com...")
            await asyncio.sleep(5)
        elif "flow/project" in url:
            break
        else:
            await asyncio.sleep(3)

    print(f"  Flow pronto: {page.url[:80]}")
    return browser, page


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def _gerar_async(titulo: str, output_path: str, prompt_extra: str = "") -> str:
    prompt = PROMPT_TEMPLATE.format(titulo=titulo[:200])
    if prompt_extra:
        prompt = prompt + " " + prompt_extra
    print(f"  Prompt: {prompt[:140]}...")

    async with async_playwright() as p:
        browser, page = await _conectar_chrome(p)

        ok, srcs_antes = await _digitar_e_enviar(page, prompt)
        if not ok:
            print("  Falha no envio — reiniciando Chrome e tentando novamente...")
            browser, page = await _conectar_chrome(p, forcar_restart=True)
            ok, srcs_antes = await _digitar_e_enviar(page, prompt)
            if not ok:
                raise RuntimeError("Nao foi possivel enviar o prompt para o Flow.")

        await asyncio.sleep(3)
        sucesso = await _aguardar_e_baixar(page, srcs_antes, output_path)

        if not sucesso:
            raise RuntimeError("Flow nao gerou imagem dentro do timeout de 180s.")

    return output_path


def gerar_capa_flow(titulo: str, output_path: str, subtitulo: str = "", prompt_extra: str = "") -> str:
    """
    Gera capa de blog via Google Flow.

    Args:
        titulo: Titulo do post
        output_path: Caminho de saida (.jpg)
        subtitulo: Ignorado (mantido por compatibilidade)
        prompt_extra: Instrucao adicional para corrigir geracao anterior

    Returns:
        Caminho da imagem gerada

    Raises:
        RuntimeError: Se nao conseguir gerar
    """
    print(f"\n[Flow] Gerando capa: {titulo[:60]}...")
    return asyncio.run(_gerar_async(titulo, output_path, prompt_extra))


# ---------------------------------------------------------------------------
# CLI standalone
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python gerar_capa_flow.py <titulo> [output.jpg]")
        sys.exit(1)

    _titulo = sys.argv[1]
    _output = sys.argv[2] if len(sys.argv) > 2 else "E:/tmp/capa-flow.jpg"

    resultado = gerar_capa_flow(_titulo, _output)
    print(f"\nCapa gerada: {resultado}")

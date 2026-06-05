"""
gerar_capa_flow.py — Gera capa de blog via Google Flow (Playwright + CDP).
Reutiliza a mesma automacao do projeto duts-guia-lendas-brasileiras.

Uso:
    from gerar_capa_flow import gerar_capa_flow
    path = gerar_capa_flow(titulo, subtitulo, output_path)

Ou standalone:
    python gerar_capa_flow.py "Titulo do post" "Subtitulo" "E:/tmp/capa.jpg"

Requisitos:
    pip install playwright
    playwright install chromium
    Chrome aberto com perfil wallyson.duarte.temp@gmail.com logado no Google Flow
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

# --- Configuracao (mesma do duts) ---
CHROME_USER_DATA = r"C:\Users\Poseidon\AppData\Local\Google\Chrome\User Data"
CHROME_PROFILE   = "Default"  # Pessoa 1 = wallyson.duarte.temp@gmail.com
FLOW_URL         = "https://labs.google/fx/pt/tools/flow/project/d76c7f19-c5e6-4502-9c6f-5c6202818b0a"
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

# Dimensao ideal para capa de blog: proporcao 16:9
# O Flow gera em quadrado por default; pedimos 16:9 no prompt
PROMPT_TEMPLATE = """
Blog cover image, 16:9 landscape format, professional tech blog style.
Topic: {titulo}
Subtitle: {subtitulo}
Style: modern, dark background with subtle blue/cyan tech elements, clean typography layout,
high contrast, suitable for a Brazilian tech blog. No text overlay. Cinematic quality.
Hyper-realistic digital art. Wide format banner composition.
""".strip()


def _encontrar_chrome() -> str:
    for p in CHROME_PATHS:
        if Path(p).exists():
            return p
    raise FileNotFoundError("Chrome nao encontrado. Instale o Google Chrome.")


def _fechar_chrome():
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"],
                   capture_output=True)
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
        FLOW_URL,
    ]
    subprocess.Popen(cmd)
    print(f"  Chrome aberto (debug port {DEBUG_PORT})")
    time.sleep(6)


async def _get_srcs_galeria(page) -> list:
    return await page.evaluate("""(excluir) => {
        return Array.from(document.querySelectorAll('img'))
            .filter(img => {
                const rect = img.getBoundingClientRect();
                const src = img.src || '';
                return rect.width > 80 && rect.height > 80 && src.length > 30
                    && !excluir.some(x => src.includes(x));
            })
            .map(img => img.src);
    }""", EXCLUIR_SRCS)


async def _conectar_chrome(p, forcar_restart: bool = False):
    """Conecta ao Chrome via CDP. Reinicia se nao conseguir ou se forcar_restart=True."""
    chrome_path = _encontrar_chrome()

    if not forcar_restart:
        # Tenta conectar ao Chrome ja aberto
        for tentativa in range(3):
            try:
                browser = await p.chromium.connect_over_cdp(
                    f"http://localhost:{DEBUG_PORT}", timeout=5000
                )
                ctx = browser.contexts[0] if browser.contexts else None
                if ctx:
                    page = next(
                        (pg for pg in ctx.pages if "labs.google" in pg.url),
                        ctx.pages[0] if ctx.pages else None,
                    )
                    if page and "flow/project" in page.url:
                        print("  Reutilizando Chrome ja conectado ao Flow")
                        return browser, page
                    if page:
                        # Navega para o Flow se estiver em outra pagina
                        try:
                            await page.goto(FLOW_URL, wait_until="commit", timeout=20000)
                            await asyncio.sleep(4)
                            return browser, page
                        except Exception:
                            pass
            except Exception:
                if tentativa < 2:
                    await asyncio.sleep(2)

    # Reinicia Chrome
    print("  Fechando Chrome...")
    _fechar_chrome()
    print("  Abrindo Chrome com perfil wallyson.duarte.temp@gmail.com...")
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

    page = next(
        (pg for pg in ctx.pages if "labs.google" in pg.url),
        ctx.pages[0] if ctx.pages else await ctx.new_page(),
    )

    if "flow/project" not in page.url:
        try:
            await page.goto(FLOW_URL, wait_until="commit", timeout=30000)
        except Exception:
            pass
        await asyncio.sleep(5)

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
            print("  Login necessario. Aguardando (faca login com wallyson.duarte.temp@gmail.com)...")
            await asyncio.sleep(5)
        elif "flow/project" in url:
            break
        else:
            await asyncio.sleep(3)

    if "flow/project" not in page.url:
        await page.goto(FLOW_URL, wait_until="commit", timeout=20000)
        await asyncio.sleep(4)

    print(f"  Flow pronto: {page.url[:80]}")
    return browser, page


async def _digitar_e_enviar(page, prompt: str) -> bool:
    """Digita o prompt no contenteditable e clica em Criar."""
    await page.keyboard.press("Escape")
    await asyncio.sleep(0.5)

    # Garante que esta no Flow
    if "flow/project" not in page.url:
        try:
            await page.goto(FLOW_URL, wait_until="commit", timeout=20000)
        except Exception:
            pass
        await asyncio.sleep(4)

    # Clica no campo de entrada
    try:
        await page.click('[contenteditable="true"]', timeout=10000)
        await asyncio.sleep(0.5)
    except Exception:
        print("  contenteditable nao encontrado — recarregando...")
        try:
            await page.goto(FLOW_URL, wait_until="commit", timeout=20000)
        except Exception:
            pass
        await asyncio.sleep(5)
        try:
            await page.click('[contenteditable="true"]', timeout=8000)
            await asyncio.sleep(0.5)
        except Exception:
            print("  Nao encontrou contenteditable apos reload")
            return False

    # Limpa e digita o prompt
    await page.keyboard.press("Control+a")
    await asyncio.sleep(0.2)
    await page.keyboard.press("Backspace")
    await asyncio.sleep(0.3)

    print(f"  Digitando prompt ({len(prompt)} chars)...")
    await page.keyboard.type(prompt, delay=8)
    await asyncio.sleep(0.5)

    # Confirma texto no campo
    texto = await page.evaluate("""() => {
        const el = document.querySelector('[contenteditable="true"]');
        return el ? (el.innerText || el.textContent || '').trim() : '';
    }""")
    if len(texto) < 10:
        print("  Campo vazio apos digitacao")
        return False
    print(f"  Campo OK: {texto[:60]}...")

    # Clica no botao Criar
    clicou = False
    try:
        btns = page.locator("button")
        n = await btns.count()
        for i in range(n):
            btn = btns.nth(i)
            try:
                txt = (await btn.inner_text()).strip()
                if "Criar" in txt and "add" not in txt.lower():
                    await btn.click(timeout=3000)
                    print(f"  Botao clicado: '{txt[:30]}'")
                    clicou = True
                    break
            except Exception:
                continue
    except Exception:
        pass

    if not clicou:
        for aria in ["riar", "end", "ubmit", "enerar"]:
            try:
                loc = page.locator(f'button[aria-label*="{aria}"]')
                if await loc.count() > 0:
                    await loc.first.click(timeout=3000)
                    clicou = True
                    break
            except Exception:
                continue

    if not clicou:
        print("  Usando Ctrl+Enter")
        await page.keyboard.press("Control+Enter")
        clicou = True

    await asyncio.sleep(1)
    return clicou


async def _aguardar_e_baixar(page, srcs_antes: set, output_path: str) -> bool:
    """Aguarda nova imagem aparecer na galeria e faz download."""
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
            print(f"  Aguardando... {(i + 1) * 5}s ({len(srcs_agora)} imgs na galeria)")

    if not nova_src:
        print("  Timeout: nenhuma imagem gerada em 180s")
        return False

    # Baixa a imagem
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    try:
        if nova_src.startswith("http"):
            resp = await page.request.get(nova_src)
            if resp.ok:
                conteudo = await resp.body()
                # Salva como PNG primeiro, converte para JPEG se necessario
                tmp_png = output_path.replace(".jpg", ".tmp.png").replace(".jpeg", ".tmp.png")
                Path(tmp_png).write_bytes(conteudo)
                _converter_para_jpg(tmp_png, output_path)
                Path(tmp_png).unlink(missing_ok=True)
                tamanho = Path(output_path).stat().st_size // 1024
                print(f"  Imagem salva ({tamanho}KB): {output_path}")
                return True
    except Exception as e:
        print(f"  Erro HTTP: {e}")

    # Fallback: screenshot do elemento
    try:
        el = await page.query_selector(f'img[src="{nova_src}"]')
        if el:
            tmp_png = output_path.replace(".jpg", ".tmp.png").replace(".jpeg", ".tmp.png")
            await el.screenshot(path=tmp_png)
            _converter_para_jpg(tmp_png, output_path)
            Path(tmp_png).unlink(missing_ok=True)
            print(f"  Imagem salva (screenshot): {output_path}")
            return True
    except Exception as e:
        print(f"  Erro screenshot: {e}")

    return False


def _converter_para_jpg(src: str, dst: str):
    """Converte PNG/qualquer formato para JPEG usando Pillow."""
    try:
        from PIL import Image
        img = Image.open(src).convert("RGB")
        img.save(dst, "JPEG", quality=92)
    except ImportError:
        # Sem Pillow: copia como esta (pode nao ser JPEG valido)
        import shutil
        shutil.copy2(src, dst)


async def _gerar_async(titulo: str, subtitulo: str, output_path: str) -> str:
    """Logica principal async de geracao de imagem."""
    prompt = PROMPT_TEMPLATE.format(
        titulo=titulo[:200],
        subtitulo=subtitulo[:300] if subtitulo else titulo[:200],
    )

    async with async_playwright() as p:
        browser, page = await _conectar_chrome(p)

        srcs_antes = set(await _get_srcs_galeria(page))
        print(f"  Galeria atual: {len(srcs_antes)} imagens")

        ok = await _digitar_e_enviar(page, prompt)
        if not ok:
            # Tenta reconectar e reenviar uma vez
            print("  Falha no envio — reiniciando Chrome...")
            browser, page = await _conectar_chrome(p, forcar_restart=True)
            srcs_antes = set(await _get_srcs_galeria(page))
            ok = await _digitar_e_enviar(page, prompt)
            if not ok:
                raise RuntimeError("Nao foi possivel enviar o prompt para o Flow.")

        await asyncio.sleep(3)
        sucesso = await _aguardar_e_baixar(page, srcs_antes, output_path)

        if not sucesso:
            raise RuntimeError("Flow nao gerou imagem dentro do timeout de 180s.")

    return output_path


def gerar_capa_flow(titulo: str, subtitulo: str, output_path: str) -> str:
    """
    Gera capa de blog via Google Flow usando Playwright.

    Args:
        titulo: Titulo do post (sera usado no prompt de imagem)
        subtitulo: Subtitulo/descricao do post
        output_path: Caminho de saida (.jpg)

    Returns:
        Caminho da imagem gerada (mesmo que output_path)

    Raises:
        RuntimeError: Se Chrome nao estiver disponivel ou Flow nao gerar imagem
    """
    print(f"\n[Flow] Gerando capa para: {titulo[:60]}...")
    return asyncio.run(_gerar_async(titulo, subtitulo, output_path))


# --- CLI standalone ---
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python gerar_capa_flow.py <titulo> <subtitulo> [output.jpg]")
        print('Exemplo: python gerar_capa_flow.py "VoidZero e Cloudflare" "O que muda para o Vite" "E:/tmp/capa.jpg"')
        sys.exit(1)

    _titulo    = sys.argv[1]
    _subtitulo = sys.argv[2]
    _output    = sys.argv[3] if len(sys.argv) > 3 else "E:/tmp/capa-flow.jpg"

    resultado = gerar_capa_flow(_titulo, _subtitulo, _output)
    print(f"\nCapa gerada: {resultado}")

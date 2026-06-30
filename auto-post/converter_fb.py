"""
converter_fb.py — Converte imagem quadrada para 1200x630 com blurred background.

Técnica: mesma imagem borrada e escurecida no fundo para preencher o espaço
retangular, imagem original centralizada na frente.
"""
from PIL import Image, ImageFilter, ImageEnhance


FB_W, FB_H = 1200, 630


def converter_para_fb(input_path: str, output_path: str | None = None) -> str:
    """
    Recebe imagem quadrada (ex: 1024x1024) e retorna 1200x630 com blur bg.
    Se output_path for None, sobrescreve o input.
    Retorna o caminho do arquivo gerado.
    """
    if output_path is None:
        output_path = input_path

    img = Image.open(input_path).convert("RGB")
    orig_w, orig_h = img.size

    # Já é retangular com proporção correta — só otimiza e salva
    ratio = orig_w / orig_h
    if 1.85 <= ratio <= 1.97:
        img.save(output_path, "JPEG", quality=82, optimize=True, progressive=True)
        return output_path

    # --- Background: escala para cobrir 1200x630, blur forte, escurece ---
    bg_scale = max(FB_W / orig_w, FB_H / orig_h)
    bg = img.resize((int(orig_w * bg_scale), int(orig_h * bg_scale)), Image.LANCZOS)
    left = (bg.width - FB_W) // 2
    top  = (bg.height - FB_H) // 2
    bg = bg.crop((left, top, left + FB_W, top + FB_H))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=28))
    bg = ImageEnhance.Brightness(bg).enhance(0.35)

    # --- Foreground: escala para caber em FB_H (altura total) ---
    fg_scale = min(FB_W / orig_w, FB_H / orig_h)
    fg = img.resize((int(orig_w * fg_scale), int(orig_h * fg_scale)), Image.LANCZOS)

    # --- Compõe ---
    canvas = bg.copy()
    fx = (FB_W - fg.width) // 2
    fy = (FB_H - fg.height) // 2
    canvas.paste(fg, (fx, fy))

    canvas.save(output_path, "JPEG", quality=82, optimize=True, progressive=True)
    return output_path

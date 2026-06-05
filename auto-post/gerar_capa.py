"""
Gerador de capa 1280x720 para o CuritibaBlog.
Padrao visual: fundo tech escuro + "ENTENDENDO NA PRATICA" + titulo neon + 3 cards + personagem
"""
import os, math, random
from PIL import Image, ImageDraw, ImageFont

# Dimensoes padrao
W, H = 1280, 720

def _font(size, bold=False):
    """Carrega fonte do sistema ou fallback."""
    candidates = []
    if bold:
        candidates = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "C:/Windows/Fonts/verdanab.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/verdana.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_rounded_rect(draw, xy, radius, fill, outline=None, outline_width=2):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill,
                            outline=outline, width=outline_width)


def _wrap_text(text, font, max_width, draw):
    """Quebra texto em linhas que cabem em max_width."""
    words = text.split()
    lines, line = [], ""
    for w in words:
        test = (line + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def _draw_centered_text(draw, text, font, cx, y, fill, max_width=None):
    """Desenha texto centralizado em cx, retorna altura ocupada."""
    if max_width:
        lines = _wrap_text(text, font, max_width, draw)
    else:
        lines = [text]
    total_h = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        draw.text((cx - lw // 2, y + total_h), line, font=font, fill=fill)
        total_h += lh + 4
    return total_h


def _tech_background(img, draw):
    """Fundo gradiente escuro com elementos tech sutis."""
    # Gradiente vertical azul-marinho
    for y in range(H):
        ratio = y / H
        r = int(13 + ratio * 8)
        g = int(27 + ratio * 15)
        b = int(42 + ratio * 30)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Grade de pontos tech
    dot_color = (0, 180, 220, 30)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for gx in range(0, W, 40):
        for gy in range(0, H, 40):
            odraw.ellipse([gx-1, gy-1, gx+1, gy+1], fill=dot_color)
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"), (0, 0))

    # Linhas de circuito sutis (esquerda)
    lc = (0, 120, 160, 60)
    overlay2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    o2 = ImageDraw.Draw(overlay2)
    for i, (sx, sy, ex, ey) in enumerate([
        (30, 200, 30, 400), (30, 300, 80, 300), (80, 250, 80, 350), (80, 300, 130, 300),
        (20, 450, 20, 600), (20, 520, 60, 520), (60, 490, 60, 550),
        (W-40, 100, W-40, 300), (W-40, 200, W-90, 200),
    ]):
        o2.line([(sx, sy), (ex, ey)], fill=lc, width=1)
        o2.ellipse([sx-3, sy-3, sx+3, sy+3], fill=lc)
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay2).convert("RGB"), (0, 0))

    # Binarios no canto superior direito
    fn = _font(11)
    for i, txt in enumerate(["0001 0010 1011", "0111 1102 118", "0010 1001 0011"]):
        draw.text((W - 160, 10 + i * 16), txt, font=fn, fill=(0, 200, 240, 80))

    return draw


def _draw_character(img):
    """Desenha personagem placeholder (homem cartoon apontando)."""
    # Area do personagem: x 820-1150, y 80-680
    cx, cy = 980, 400
    char_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(char_layer)

    # Corpo (jacket escuro)
    cd.ellipse([cx-60, cy-200, cx+60, cy-80], fill=(50, 80, 120, 220))  # cabeca
    cd.rounded_rectangle([cx-80, cy-80, cx+80, cy+180], radius=20, fill=(40, 60, 100, 220))  # torso
    # Braco apontando
    cd.line([(cx-40, cy-20), (cx-150, cy-80)], fill=(40, 60, 100, 220), width=30)
    cd.ellipse([cx-165, cy-95, cx-135, cy-65], fill=(200, 160, 120, 220))  # mao
    # Pernas
    cd.rounded_rectangle([cx-60, cy+180, cx-10, cy+320], radius=10, fill=(30, 50, 80, 220))
    cd.rounded_rectangle([cx+10, cy+180, cx+60, cy+320], radius=10, fill=(30, 50, 80, 220))
    # Rosto simplificado
    cd.ellipse([cx-45, cy-190, cx+45, cy-90], fill=(200, 160, 120, 220))
    cd.ellipse([cx-20, cy-165, cx-8, cy-155], fill=(50, 30, 20, 220))  # olho e
    cd.ellipse([cx+8, cy-165, cx+20, cy-155], fill=(50, 30, 20, 220))   # olho d
    cd.arc([cx-15, cy-145, cx+15, cy-130], 0, 180, fill=(80, 40, 20, 220), width=2)  # boca

    img.paste(char_layer, (0, 0), char_layer)
    return img


def gerar_capa(titulo, subtitulo, card1_titulo, card1_texto,
               card2_titulo, card2_texto, card3_titulo, card3_texto,
               output_path="capa.jpg"):
    """
    Gera imagem de capa 1280x720 no padrao do blog.
    Retorna o path da imagem gerada.
    """
    img = Image.new("RGB", (W, H), (13, 27, 42))
    draw = ImageDraw.Draw(img)

    # --- FUNDO ---
    _tech_background(img, draw)
    draw = ImageDraw.Draw(img)  # redesenhar apos composicao

    # --- TOPO: "ENTENDENDO NA PRATICA" ---
    fn_topo = _font(34, bold=True)
    _draw_centered_text(draw, "ENTENDENDO NA PRATICA", fn_topo,
                        cx=W // 2, y=18, fill=(255, 255, 255))

    # Linha separadora neon
    draw.line([(60, 70), (W - 60, 70)], fill=(0, 200, 240), width=2)

    # --- BOX PRINCIPAL (esquerda-centro) ---
    box_x0, box_y0, box_x1, box_y1 = 40, 85, 760, 380
    _draw_rounded_rect(draw, [box_x0, box_y0, box_x1, box_y1],
                       radius=12, fill=(10, 20, 50, 220),
                       outline=(0, 200, 240), outline_width=3)

    # Titulo principal no box (ciano/amarelo)
    fn_titulo = _font(38, bold=True)
    fn_sub = _font(22)
    titulo_upper = titulo.upper()
    lines = _wrap_text(titulo_upper, fn_titulo, box_x1 - box_x0 - 40, draw)

    ty = box_y0 + 20
    for i, line in enumerate(lines[:3]):
        color = (0, 220, 255) if i == 0 else (255, 220, 0) if i == 1 else (255, 255, 255)
        bbox = draw.textbbox((0, 0), line, font=fn_titulo)
        lw = bbox[2] - bbox[0]
        draw.text((box_x0 + 20, ty), line, font=fn_titulo, fill=color)
        ty += (bbox[3] - bbox[1]) + 6

    # Subtitulo
    if subtitulo and ty < box_y1 - 60:
        sub_lines = _wrap_text(subtitulo, fn_sub, box_x1 - box_x0 - 40, draw)
        for line in sub_lines[:3]:
            draw.text((box_x0 + 20, ty), line, font=fn_sub, fill=(200, 220, 240))
            bbox = draw.textbbox((0, 0), line, font=fn_sub)
            ty += (bbox[3] - bbox[1]) + 4

    # --- 3 CARDS NA PARTE INFERIOR ---
    card_y0, card_y1 = 400, 680
    card_w = (W - 80) // 3
    cards = [
        (card1_titulo, card1_texto),
        (card2_titulo, card2_texto),
        (card3_titulo, card3_texto),
    ]
    fn_ctit = _font(18, bold=True)
    fn_ctxt = _font(15)

    for i, (ctit, ctxt) in enumerate(cards):
        cx0 = 40 + i * (card_w + 10)
        cx1 = cx0 + card_w
        _draw_rounded_rect(draw, [cx0, card_y0, cx1, card_y1],
                           radius=10, fill=(15, 30, 60, 230),
                           outline=(0, 160, 200), outline_width=2)
        # Titulo do card
        _draw_centered_text(draw, ctit.upper(), fn_ctit,
                            cx=(cx0 + cx1) // 2, y=card_y0 + 15,
                            fill=(0, 200, 240), max_width=card_w - 20)
        # Texto do card
        sub_lines = _wrap_text(ctxt, fn_ctxt, card_w - 20, draw)
        ty2 = card_y0 + 60
        for line in sub_lines[:4]:
            bbox = draw.textbbox((0, 0), line, font=fn_ctxt)
            lw = bbox[2] - bbox[0]
            draw.text(((cx0 + cx1) // 2 - lw // 2, ty2), line,
                      font=fn_ctxt, fill=(180, 200, 220))
            ty2 += (bbox[3] - bbox[1]) + 3

    # --- PERSONAGEM (lado direito, sobre tudo) ---
    img = _draw_character(img)
    draw = ImageDraw.Draw(img)

    # --- SALVAR ---
    img = img.convert("RGB")
    img.save(output_path, "JPEG", quality=92)
    return output_path


# Teste standalone
if __name__ == "__main__":
    path = gerar_capa(
        titulo="Windsor.ai no Claude Code: conecte 325 fontes de dados",
        subtitulo="Integre Google Analytics, Meta Ads e Shopify ao seu assistente de IA via MCP server em menos de 5 minutos.",
        card1_titulo="325+ Conectores",
        card1_texto="Google Ads, GA4, Meta Ads, Shopify e muito mais disponíveis.",
        card2_titulo="MCP Nativo",
        card2_texto="Configure em 2 linhas de JSON e comece a perguntar ao Claude.",
        card3_titulo="30 Dias Gratis",
        card3_texto="Teste sem cartao de credito e veja o impacto real no seu fluxo.",
        output_path="E:/tmp/test-capa.jpg"
    )
    print("Capa gerada:", path)

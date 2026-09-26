"""
slides.py — Desenha os slides do carrossel (1080x1350, formato retrato do Instagram).
"""
import random
import urllib.parse
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import RAIZ, cfg, cfg_bool

W, H = 1080, 1350
MARGEM = 100

# (cor do fundo 1, cor do fundo 2, cor de destaque)
PALETAS = [
    ((24, 32, 72), (88, 48, 140), (255, 214, 102)),
    ((10, 60, 70), (20, 130, 120), (255, 255, 255)),
    ((60, 20, 40), (180, 60, 80), (255, 230, 200)),
    ((20, 20, 20), (60, 60, 70), (120, 220, 170)),
    ((30, 50, 110), (0, 150, 200), (255, 255, 255)),
    ((70, 40, 10), (200, 110, 40), (255, 245, 225)),
]


# ------------------------------------------------------------------ utilitários
def fonte(tamanho, negrito=False):
    nomes = (["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"]
             if negrito else
             ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "arial.ttf", "Arial.ttf"])
    pastas = [RAIZ / "fontes", "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation",
              "/usr/share/fonts/truetype/liberation2", "C:/Windows/Fonts", "/Library/Fonts",
              "/System/Library/Fonts/Supplemental"]
    for pasta in pastas:
        for nome in nomes:
            p = Path(pasta) / nome
            if p.exists():
                return ImageFont.truetype(str(p), tamanho)
    return ImageFont.load_default(size=tamanho)


def quebrar(draw, texto, f, largura):
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = f"{atual} {palavra}".strip()
        if draw.textlength(teste, font=f) <= largura:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def encaixar(draw, texto, negrito, tam_max, tam_min, largura, altura_max, espac):
    """Diminui a fonte até o texto caber na área."""
    for tam in range(tam_max, tam_min - 1, -4):
        f = fonte(tam, negrito)
        linhas = quebrar(draw, texto, f, largura)
        if len(linhas) * tam * espac <= altura_max:
            return f, linhas, tam
    f = fonte(tam_min, negrito)
    return f, quebrar(draw, texto, f, largura), tam_min


def escrever(draw, linhas, f, tam, x, y, cor, espac, centralizar=False):
    for linha in linhas:
        px = (W - draw.textlength(linha, font=f)) // 2 if centralizar else x
        draw.text((px, y), linha, font=f, fill=cor)
        y += int(tam * espac)
    return y


def gradiente(c1, c2):
    peq = Image.new("RGB", (54, 68))
    px = peq.load()
    for y in range(68):
        for x in range(54):
            t = x / 54 * 0.35 + y / 68 * 0.65
            px[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
    return peq.resize((W, H), Image.BICUBIC)


def baixar_fundo_ia(prompt, destino):
    """Foto de fundo grátis (Pollinations, sem chave). Salva em destino. Se falhar, retorna False."""
    try:
        url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt + ", photography, no text") +
               f"?width={W}&height={H}&nologo=true&seed={random.randint(1, 10**6)}")
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        Image.open(BytesIO(r.content)).convert("RGB").resize((W, H)).save(destino, "JPEG", quality=90)
        return True
    except Exception as e:
        print(f"  ⚠ fundo com IA falhou ({e}); usando gradiente.")
        return False


def rodape(d, destaque, texto_direita):
    perfil = cfg("PERFIL")
    if perfil:
        d.text((MARGEM, H - 150), perfil, font=fonte(38, True), fill=destaque)
    f = fonte(34)
    d.text((W - MARGEM - d.textlength(texto_direita, font=f), H - 146), texto_direita, font=f, fill=(220, 220, 225))


# ------------------------------------------------------------------ slides
def slide_capa(dados, paleta, fundo_foto):
    c1, c2, destaque = paleta
    if fundo_foto and fundo_foto.exists():
        foto = Image.open(fundo_foto).convert("RGB").filter(ImageFilter.GaussianBlur(2))
        img = Image.blend(foto, Image.new("RGB", (W, H)), 0.55)  # escurece para o texto aparecer
    else:
        img = gradiente(c1, c2)

    d = ImageDraw.Draw(img)
    d.rounded_rectangle([MARGEM, 250, MARGEM + 140, 264], radius=7, fill=destaque)
    f, linhas, tam = encaixar(d, dados["titulo"], True, 104, 56, W - 2 * MARGEM, 520, 1.15)
    y = escrever(d, linhas, f, tam, MARGEM, 320, (255, 255, 255), 1.15) + 50
    f, linhas, tam = encaixar(d, dados["subtitulo"], False, 50, 32, W - 2 * MARGEM, H - y - 220, 1.35)
    escrever(d, linhas, f, tam, MARGEM, y, (235, 235, 240), 1.35)
    rodape(d, destaque, "arraste para o lado →")
    return img


def slide_conteudo(slide, numero, total, paleta):
    c1, c2, destaque = paleta
    img = gradiente(c1, c2)
    d = ImageDraw.Draw(img)

    d.text((MARGEM, 150), f"{numero:02d}", font=fonte(150, True), fill=destaque)
    f, linhas, tam = encaixar(d, slide["titulo"], True, 84, 50, W - 2 * MARGEM, 330, 1.15)
    y = escrever(d, linhas, f, tam, MARGEM, 380, (255, 255, 255), 1.15) + 30
    d.rounded_rectangle([MARGEM, y, MARGEM + 90, y + 8], radius=4, fill=destaque)
    y += 50
    f, linhas, tam = encaixar(d, slide["texto"], False, 52, 32, W - 2 * MARGEM, H - y - 220, 1.4)
    escrever(d, linhas, f, tam, MARGEM, y, (235, 235, 240), 1.4)
    rodape(d, destaque, f"{numero + 1}/{total}  →")
    return img


def slide_final(dados, paleta):
    c1, c2, destaque = paleta
    img = gradiente(c2, c1)
    d = ImageDraw.Draw(img)

    chamada = dados.get("chamada_final") or "Salve este post para consultar depois!"
    f, linhas, tam = encaixar(d, chamada, True, 90, 50, W - 2 * MARGEM, 560, 1.2)
    y = (H - len(linhas) * int(tam * 1.2)) // 2 - 80
    y = escrever(d, linhas, f, tam, 0, y, (255, 255, 255), 1.2, centralizar=True) + 60
    escrever(d, ["salvar  •  comentar  •  compartilhar"], fonte(38), 38, 0, y, destaque, 1, centralizar=True)
    perfil = cfg("PERFIL")
    if perfil:
        escrever(d, [f"Siga {perfil}"], fonte(46, True), 46, 0, H - 200, destaque, 1, centralizar=True)
    return img


# ------------------------------------------------------------------ carrossel
def desenhar_carrossel(dados, pasta: Path):
    """Desenha todos os slides a partir de dados (post.json). Retorna a lista de arquivos.
    Pode ser chamado de novo depois de editar o post.json (comando 'redesenhar')."""
    pasta.mkdir(parents=True, exist_ok=True)
    if "paleta" not in dados:
        dados["paleta"] = random.randrange(len(PALETAS))
    paleta = PALETAS[dados["paleta"] % len(PALETAS)]

    fundo = pasta / "fundo_capa.jpg"
    if cfg_bool("USAR_IMAGEM_IA") and not fundo.exists() and dados.get("prompt_imagem"):
        print("→ Baixando foto de fundo da capa...")
        baixar_fundo_ia(dados["prompt_imagem"], fundo)

    total = len(dados["slides"]) + 2
    imagens = [slide_capa(dados, paleta, fundo)]
    imagens += [slide_conteudo(s, i, total, paleta) for i, s in enumerate(dados["slides"], start=1)]
    imagens.append(slide_final(dados, paleta))

    for antigo in pasta.glob("[0-9][0-9].jpg"):
        antigo.unlink()
    arquivos = []
    for i, img in enumerate(imagens, start=1):
        arq = pasta / f"{i:02d}.jpg"
        img.save(arq, "JPEG", quality=92, optimize=True)  # Instagram exige JPEG
        arquivos.append(arq)
    return arquivos

"""
slides.py — Desenha os slides do carrossel (1080x1350, formato retrato do Instagram).

Conceito: cada slide é uma quadra de vôlei vista de cima.
  • capa: com foto, a foto ocupa a quadra e se funde com o piso embaixo do título;
          sem foto, a rede com as antenas no alto e a bola saindo pela direita
  • conteúdo: foto na zona de ataque (se houver), número estilo camisa e o texto
  • final: chamada para ação e a bola parada na quadra

Temas (variável TEMA): quadra | areia | alternar
"""
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

import fotos
from config import FILA, PUBLICADOS, RAIZ, cfg

W, H = 1080, 1350
S = 2  # desenha em 2x e reduz no final: bordas e curvas ficam lisas

TEMAS = {
    "quadra": {  # quadra coberta
        "zona": (238, 106, 44),      # zona livre laranja
        "piso": (29, 78, 158),       # quadra azul
        "linha": (244, 246, 250),    # linhas brancas
        "titulo": (255, 255, 255),
        "texto": (220, 230, 247),
        "numero": (255, 207, 51),    # amarelo da bola
        "sombra": (15, 35, 80),
        "rede": (15, 35, 80),
        "fita": (244, 246, 250),
        "botao": (255, 207, 51),
        "botao_texto": (15, 35, 80),
        "degrade": (22, 58, 124),    # azul da quadra, um pouco mais escuro
        "grao": 5,
    },
    "areia": {  # vôlei de praia
        "zona": (214, 180, 124),
        "piso": (234, 208, 160),
        "linha": (31, 95, 191),      # fita azul das quadras de praia
        "titulo": (19, 41, 75),
        "texto": (45, 63, 94),
        "numero": (228, 71, 47),     # coral
        "sombra": (19, 41, 75),
        "rede": (19, 41, 75),
        "fita": (31, 95, 191),
        "botao": (19, 41, 75),
        "botao_texto": (255, 255, 255),
        "degrade": (234, 208, 160),  # cor da areia
        "grao": 8,
    },
}

# medidas da quadra (em pixels do slide final, 1080 de largura)
ZONA = 44          # largura da zona livre (borda)
RECUO = 34         # distância da borda da quadra até a linha
LINHA = 8          # espessura das linhas
X0 = ZONA + RECUO + LINHA + 40          # margem esquerda do texto
LARG_TEXTO = W - 2 * X0


# ------------------------------------------------------------------ utilitários
def s(v):
    return int(round(v * S))


def fonte(estilo, tamanho):
    arquivos = {
        "display": ["Anton-Regular.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"],
        "texto": ["Barlow-Medium.ttf", "DejaVuSans.ttf", "arial.ttf"],
        "forte": ["Barlow-SemiBold.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"],
    }[estilo]
    pastas = [RAIZ / "fontes", Path("/usr/share/fonts/truetype/dejavu"), Path("C:/Windows/Fonts")]
    for nome in arquivos:
        for pasta in pastas:
            if (pasta / nome).exists():
                return ImageFont.truetype(str(pasta / nome), s(tamanho))
    return ImageFont.load_default(size=s(tamanho))


EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]+")


def limpar(texto):
    """Tira emojis (a fonte não desenha) e espaços sobrando."""
    return re.sub(r"\s+", " ", EMOJI.sub("", texto or "")).strip()


def quebrar(draw, texto, f, largura):
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = f"{atual} {palavra}".strip()
        if draw.textlength(teste, font=f) <= s(largura) or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def encaixar(draw, texto, estilo, tam_max, tam_min, largura, altura_max, entrelinha):
    """Maior tamanho de fonte em que o texto cabe na área."""
    for tam in range(tam_max, tam_min - 1, -2):
        f = fonte(estilo, tam)
        linhas = quebrar(draw, texto, f, largura)
        largura_ok = all(draw.textlength(l, font=f) <= s(largura) for l in linhas)
        if largura_ok and len(linhas) * tam * entrelinha <= altura_max:
            return f, linhas, tam
    f = fonte(estilo, tam_min)
    return f, quebrar(draw, texto, f, largura), tam_min


def escrever(draw, linhas, f, tam, x, y, cor, entrelinha, centro=False):
    for linha in linhas:
        px = (s(W) - draw.textlength(linha, font=f)) / 2 if centro else s(x)
        draw.text((px, s(y)), linha, font=f, fill=cor)
        y += tam * entrelinha
    return y


# ------------------------------------------------------------------ elementos da quadra
def piso(t):
    img = Image.new("RGB", (s(W), s(H)), t["zona"])
    ImageDraw.Draw(img).rectangle([s(ZONA), s(ZONA), s(W - ZONA), s(H - ZONA)], fill=t["piso"])
    # textura: bem leve na quadra coberta, mais marcada na areia
    ruido = Image.effect_noise((s(W) // 2, s(H) // 2), t["grao"] * 4).resize((s(W), s(H)))
    ruido = Image.merge("RGB", (ruido, ruido, ruido))
    return ImageChops.add(img, ruido, scale=1.0, offset=-128).convert("RGBA")


def linhas_quadra(d, t, y_ataque=None, com_fundo=True):
    a = ZONA + RECUO
    if com_fundo:
        d.rectangle([s(a), s(a), s(W - a), s(H - a)], outline=t["linha"], width=s(LINHA))
    else:  # capa: a rede fica sobre a linha central, então não há linha acima dela
        d.rectangle([s(a), s(ZONA), s(a + LINHA), s(H - a)], fill=t["linha"])
        d.rectangle([s(W - a - LINHA), s(ZONA), s(W - a), s(H - a)], fill=t["linha"])
        d.rectangle([s(a), s(H - a - LINHA), s(W - a), s(H - a)], fill=t["linha"])
    if y_ataque:
        d.rectangle([s(a), s(y_ataque), s(W - a), s(y_ataque + LINHA)], fill=t["linha"])


def rede(img, t, y):
    """Fita superior larga, malha, fita inferior e antenas listradas nas laterais."""
    x_ini, x_fim = ZONA * 0.5, W - ZONA * 0.5
    alt, passo = 128, 22
    malha = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dm = ImageDraw.Draw(malha)
    cor = t["rede"] + (170,)
    x = x_ini
    while x <= x_fim:
        dm.line([s(x), s(y), s(x), s(y + alt)], fill=cor, width=s(2))
        x += passo
    for yy in range(y, y + alt, passo):
        dm.line([s(x_ini), s(yy), s(x_fim), s(yy)], fill=cor, width=s(2))
    img.alpha_composite(malha)

    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([s(x_ini), s(y - 14), s(x_fim), s(y + 10)], fill=t["fita"])
    d.rectangle([s(x_ini), s(y + alt - 4), s(x_fim), s(y + alt + 4)], fill=t["fita"])
    for xa in (ZONA + RECUO + LINHA / 2, W - ZONA - RECUO - LINHA / 2):
        topo, base = y - 110, y + alt + 6
        for i, yy in enumerate(range(topo, base, 20)):
            d.rectangle([s(xa - 6), s(yy), s(xa + 6), s(min(yy + 20, base))],
                        fill=(214, 40, 40) if i % 2 == 0 else (255, 255, 255))
    return y + alt


def bola(img, cx, cy, r, sombra=True):
    """Bola de vôlei: três gomos curvos (azul, amarelo e branco), cada um com suas faixas,
    costuras escuras, volume e sombra no chão."""
    if sombra:
        camada = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(camada).ellipse(
            [s(cx - r * 0.85), s(cy + r * 0.82), s(cx + r * 0.95), s(cy + r * 1.1)], fill=(0, 0, 0, 110))
        img.alpha_composite(camada.filter(ImageFilter.GaussianBlur(s(12))))

    tam = s(r * 2)
    k = tam / 2  # 1 unidade = raio da bola

    def circulo(cx_u, cy_u, raio_u):  # círculo em coordenadas da bola (centro = 0,0)
        return [k + (cx_u - raio_u) * k, k + (cy_u - raio_u) * k, k + (cx_u + raio_u) * k, k + (cy_u + raio_u) * k]

    # três círculos grandes que passam perto do centro: as bordas deles são as costuras principais
    gomos = [((-1.22, 0.30), 1.26, (30, 86, 176)),     # esquerda: azul
             ((0.78, -1.02), 1.38, (255, 207, 51)),    # cima/direita: amarelo
             ((0.52, 1.18), 1.30, (246, 246, 240))]    # baixo/direita: branco
    b = Image.new("RGBA", (tam, tam), gomos[2][2] + (255,))
    ocupado = Image.new("L", (tam, tam), 0)
    costura = (15, 35, 80, 255)
    fina = max(2, int(tam * 0.009))
    for (gx, gy), raio, cor in gomos:
        m = Image.new("L", (tam, tam), 0)
        ImageDraw.Draw(m).ellipse(circulo(gx, gy, raio), fill=255)
        if cor != gomos[2][2]:
            m = ImageChops.subtract(m, ocupado)
            b.paste(cor + (255,), (0, 0), m)
            ocupado = ImageChops.lighter(ocupado, m)
        else:
            m = ImageChops.subtract(Image.new("L", (tam, tam), 255), ocupado)
        # faixas do gomo: arcos paralelos à borda, só dentro do próprio gomo
        faixas = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
        df = ImageDraw.Draw(faixas)
        for recuo in (0.24, 0.48):
            df.ellipse(circulo(gx, gy, raio - recuo), outline=costura, width=fina)
        b.paste(faixas, (0, 0), ImageChops.multiply(faixas.getchannel("A"), m))

    # costuras principais (bordas dos gomos), mais grossas
    grossa = max(3, int(tam * 0.016))
    linhas = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    dl = ImageDraw.Draw(linhas)
    for (gx, gy), raio, cor in gomos[:2]:
        dl.ellipse(circulo(gx, gy, raio), outline=costura, width=grossa)
    # a costura do 2º gomo só aparece fora do 1º
    m1 = Image.new("L", (tam, tam), 0)
    ImageDraw.Draw(m1).ellipse(circulo(*gomos[0][0], gomos[0][1] - 0.01), fill=255)
    so_fora = ImageChops.subtract(linhas.getchannel("A"), m1)
    borda1 = Image.new("L", (tam, tam), 0)
    ImageDraw.Draw(borda1).ellipse(circulo(*gomos[0][0], gomos[0][1]), outline=255, width=grossa)
    b.paste(costura, (0, 0), ImageChops.lighter(so_fora, borda1))

    # volume: escurece embaixo à direita, brilho em cima à esquerda
    luz = Image.new("L", (tam, tam), 0)
    ImageDraw.Draw(luz).ellipse([tam * 0.3, tam * 0.3, tam * 1.45, tam * 1.45], fill=70)
    escuro = Image.new("RGBA", (tam, tam), costura)
    escuro.putalpha(luz.filter(ImageFilter.GaussianBlur(tam * 0.13)))
    b.alpha_composite(escuro)
    brilho = Image.new("L", (tam, tam), 0)
    ImageDraw.Draw(brilho).ellipse([tam * 0.16, tam * 0.1, tam * 0.5, tam * 0.38], fill=90)
    claro = Image.new("RGBA", (tam, tam), (255, 255, 255, 255))
    claro.putalpha(brilho.filter(ImageFilter.GaussianBlur(tam * 0.06)))
    b.alpha_composite(claro)

    mascara = Image.new("L", (tam, tam), 0)
    ImageDraw.Draw(mascara).ellipse([0, 0, tam - 1, tam - 1], fill=255)
    b.putalpha(mascara)
    ImageDraw.Draw(b).ellipse([1, 1, tam - 2, tam - 2], outline=costura, width=max(3, int(tam * 0.014)))
    img.paste(b, (s(cx - r), s(cy - r)), b)


def seta(d, x, y, cor, tam=15):
    """Chevron desenhado (não depende da fonte)."""
    d.line([s(x), s(y - tam), s(x + tam), s(y), s(x), s(y + tam)], fill=cor, width=s(5), joint="curve")


def rodape(d, t, direita, com_seta=True):
    y = H - ZONA - RECUO - LINHA - 76
    perfil = cfg("PERFIL")
    if perfil:
        d.text((s(X0), s(y)), perfil, font=fonte("forte", 34), fill=t["titulo"])
    f = fonte("forte", 32)
    larg = d.textlength(direita, font=f) / S
    x = W - X0 - larg - (32 if com_seta else 0)
    d.text((s(x), s(y + 2)), direita, font=f, fill=t["texto"])
    if com_seta:
        seta(d, W - X0 - 15, y + 23, t["titulo"])


def colocar_foto(img, caminho, caixa, t, escurecer):
    """Cola a foto recortada para preencher a caixa e aplica um degradê na cor do tema.
    escurecer = lista de (posição 0..1 na altura, opacidade 0..255) do degradê."""
    x1, y1, x2, y2 = [s(v) for v in caixa]
    try:
        foto = Image.open(caminho).convert("RGB")
    except Exception:
        return False
    foto = ImageOps.fit(foto, (x2 - x1, y2 - y1), Image.LANCZOS, centering=(0.5, 0.4))
    # puxa levemente as cores para a paleta do tema: todas as fotos ficam "da mesma família"
    foto = Image.blend(foto, Image.new("RGB", foto.size, t["piso"]), 0.14)
    img.paste(foto, (x1, y1))

    alt = y2 - y1
    mascara = Image.new("L", (1, alt))
    pontos = sorted(escurecer)
    for y in range(alt):
        pos = y / alt
        for (p0, a0), (p1, a1) in zip(pontos, pontos[1:]):
            if p0 <= pos <= p1:
                a = a0 + (a1 - a0) * ((pos - p0) / (p1 - p0) if p1 > p0 else 0)
                break
        else:
            a = pontos[0][1] if pos < pontos[0][0] else pontos[-1][1]
        mascara.putpixel((0, y), int(a))
    mascara = mascara.resize((x2 - x1, alt))
    cor = Image.new("RGBA", (x2 - x1, alt), t["degrade"] + (255,))
    cor.putalpha(mascara)
    img.alpha_composite(cor, (x1, y1))
    return True


# ------------------------------------------------------------------ slides
def slide_capa(dados, t, foto=None):
    img = piso(t)
    com_foto = bool(foto) and colocar_foto(
        img, foto, (ZONA, ZONA, W - ZONA, H - ZONA), t,
        [(0.0, 30), (0.22, 15), (0.42, 195), (0.55, 242), (1.0, 250)])
    linhas_quadra(ImageDraw.Draw(img, "RGBA"), t, com_fundo=False)
    d = ImageDraw.Draw(img, "RGBA")

    if com_foto:
        # texto ancorado embaixo, sobre a parte "piso" do degradê
        larg = LARG_TEXTO
        f_t, l_t, tam_t = encaixar(d, limpar(dados["titulo"]), "display", 124, 68, larg, 400, 1.13)
        f_s, l_s, tam_s = encaixar(d, limpar(dados["subtitulo"]), "texto", 44, 30, larg, 170, 1.3)
        altura = len(l_t) * tam_t * 1.13 + 34 + len(l_s) * tam_s * 1.3
        y = 1120 - altura
        y = escrever(d, l_t, f_t, tam_t, X0, y, t["titulo"], 1.13) + 34
        escrever(d, l_s, f_s, tam_s, X0, y, t["texto"], 1.3)
    else:
        y = rede(img, t, 180) + 96
        d = ImageDraw.Draw(img, "RGBA")
        larg = LARG_TEXTO - 140  # espaço para a bola à direita
        f, linhas, tam = encaixar(d, limpar(dados["titulo"]), "display", 132, 70, larg, 480, 1.13)
        y = escrever(d, linhas, f, tam, X0, y, t["titulo"], 1.13) + 40
        f, linhas, tam = encaixar(d, limpar(dados["subtitulo"]), "texto", 46, 32, larg - 20, 1110 - y, 1.3)
        escrever(d, linhas, f, tam, X0, y, t["texto"], 1.3)
        bola(img, W + 25, 1010, 175)  # metade para fora: convida a arrastar

    rodape(ImageDraw.Draw(img, "RGBA"), t, "Arraste")
    return img


def slide_conteudo(slide, numero, total, t, foto=None):
    img = piso(t)
    y_ataque = 470
    if foto:
        colocar_foto(img, foto, (ZONA, ZONA, W - ZONA, y_ataque + LINHA), t,
                     [(0.0, 20), (0.45, 60), (1.0, 175)])
    d = ImageDraw.Draw(img, "RGBA")
    linhas_quadra(d, t, y_ataque)

    # número estilo camisa: sombra deslocada + número
    f = fonte("display", 300)
    d.text((s(X0 + 12), s(92 + 12)), str(numero), font=f, fill=t["sombra"])
    d.text((s(X0), s(92)), str(numero), font=f, fill=t["numero"])

    y = y_ataque + LINHA + 56
    f, linhas, tam = encaixar(d, limpar(slide["titulo"]), "display", 92, 56, LARG_TEXTO, 320, 1.13)
    y = escrever(d, linhas, f, tam, X0, y, t["titulo"], 1.13) + 30
    area = H - ZONA - RECUO - 140 - y
    f, linhas, tam = encaixar(d, limpar(slide["texto"]), "texto", 54, 34, LARG_TEXTO, area, 1.36)
    escrever(d, linhas, f, tam, X0, y, t["texto"], 1.38)

    rodape(d, t, f"{numero + 1}/{total}")
    return img


def slide_final(dados, t):
    img = piso(t)
    d = ImageDraw.Draw(img, "RGBA")
    linhas_quadra(d, t, 470)

    chamada = limpar(dados.get("chamada_final")) or "Salve este post para consultar depois"
    f, linhas, tam = encaixar(d, chamada, "display", 100, 58, LARG_TEXTO, 310, 1.13)
    y = 145 + (300 - len(linhas) * tam * 1.13) / 2
    escrever(d, linhas, f, tam, 0, y, t["titulo"], 1.13, centro=True)

    perfil = cfg("PERFIL")
    if perfil:
        f = fonte("forte", 44)
        texto = f"Siga {perfil}"
        larg = d.textlength(texto, font=f) / S + 104
        x, y = (W - larg) / 2, 566
        d.rounded_rectangle([s(x), s(y), s(x + larg), s(y + 100)], radius=s(50), fill=t["botao"])
        d.text((s(W / 2), s(y + 50)), texto, font=f, fill=t["botao_texto"], anchor="mm")

    bola(img, W / 2, 935, 160)
    return img


# ------------------------------------------------------------------ carrossel
def escolher_tema(dados):
    tema = cfg("TEMA", "quadra").lower()
    if tema in TEMAS:
        return tema
    if dados.get("tema") in TEMAS:  # 'alternar' mantém o tema na hora de redesenhar
        return dados["tema"]
    total = sum(1 for p in list(FILA.glob("*")) + list(PUBLICADOS.glob("*")) if p.is_dir())
    return list(TEMAS)[total % len(TEMAS)]


def desenhar_carrossel(dados, pasta: Path):
    """Desenha todos os slides a partir de dados (post.json). Retorna a lista de arquivos.
    Pode ser chamado de novo depois de editar o post.json (comando 'redesenhar')."""
    pasta.mkdir(parents=True, exist_ok=True)
    dados["tema"] = escolher_tema(dados)
    t = TEMAS[dados["tema"]]

    fotos.garantir_arquivos(dados, pasta)
    lista = dados.get("fotos") or {}
    capa = fotos.arquivo(pasta, lista.get("capa"))
    por_slide = list(lista.get("slides") or [])
    por_slide += [None] * (len(dados["slides"]) - len(por_slide))

    def existe(c):
        return c if c and c.exists() else None

    total = len(dados["slides"]) + 2
    imagens = [slide_capa(dados, t, existe(capa))]
    imagens += [slide_conteudo(sl, i, total, t, existe(fotos.arquivo(pasta, por_slide[i - 1])))
                for i, sl in enumerate(dados["slides"], start=1)]
    imagens.append(slide_final(dados, t))

    for antigo in pasta.glob("[0-9][0-9].jpg"):
        antigo.unlink()
    arquivos = []
    for i, img in enumerate(imagens, start=1):
        arq = pasta / f"{i:02d}.jpg"
        img.convert("RGB").resize((W, H), Image.LANCZOS).save(arq, "JPEG", quality=93, optimize=True)
        arquivos.append(arq)
    return arquivos

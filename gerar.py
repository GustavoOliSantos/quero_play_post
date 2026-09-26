"""
gerar.py — Gera um CARROSSEL para o Instagram (texto com Gemini + imagens com Pillow).

Uso:
  python gerar.py          -> gera usando o Gemini
  python gerar.py --teste  -> gera com um texto de exemplo (sem Gemini), para testar a imagem

Saídas:
  posts/AAAA-MM-DD_HHMMSS/01.jpg, 02.jpg...  -> slides 1080x1350 (capa + conteúdo + final)
  ultimo_post.json                           -> caminhos das imagens + legenda (lido pelo postar.py)
  historico.json              -> temas já usados (para não repetir)
"""
import datetime
import json
import os
import random
import re
import sys
import urllib.parse
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ------------------------------------------------------------------ config
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()  # .strip() evita erro de espaço/quebra de linha no secret
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "").strip()   # opcional: força um modelo
NICHO = os.environ.get("NICHO", "").strip() or "dicas de produtividade e bem-estar"
PERFIL = os.environ.get("PERFIL", "").strip()               # ex: @meuperfil (aparece no rodapé da imagem)
USAR_IMAGEM_IA = os.environ.get("USAR_IMAGEM_IA", "").strip().lower() in ("1", "true", "sim", "yes")
try:
    SLIDES = max(2, min(8, int(os.environ.get("SLIDES", "").strip() or 5)))  # slides de conteúdo (capa e final são extras)
except ValueError:
    SLIDES = 5

BASE = "https://generativelanguage.googleapis.com/v1beta"
W, H = 1080, 1350
RAIZ = Path(__file__).parent
PASTA_POSTS = RAIZ / "posts"
HISTORICO = RAIZ / "historico.json"

PALETAS = [
    ((24, 32, 72), (88, 48, 140), (255, 214, 102)),
    ((10, 60, 70), (20, 130, 120), (255, 255, 255)),
    ((60, 20, 40), (180, 60, 80), (255, 230, 200)),
    ((20, 20, 20), (60, 60, 70), (120, 220, 170)),
    ((30, 50, 110), (0, 150, 200), (255, 255, 255)),
    ((70, 40, 10), (200, 110, 40), (255, 245, 225)),
]


def erro(msg):
    print(f"\n❌ {msg}\n", file=sys.stderr)
    sys.exit(1)


# ------------------------------------------------------------------ Gemini
def _headers():
    return {"x-goog-api-key": GEMINI_KEY, "Content-Type": "application/json"}


def _explicar_erro_chave(r):
    try:
        detalhe = r.json().get("error", {}).get("message", r.text)
    except Exception:
        detalhe = r.text
    erro(
        "O Gemini recusou a chave (HTTP %s): %s\n\n"
        "Como resolver:\n"
        "  1. Crie a chave em https://aistudio.google.com/apikey (não use chave do Google Cloud com restrições).\n"
        "  2. No GitHub: Settings > Secrets and variables > Actions > New repository secret\n"
        "     Nome EXATO: GEMINI_API_KEY  (é secret, não 'variable').\n"
        "  3. Cole só a chave, sem aspas e sem espaços." % (r.status_code, detalhe)
    )


def listar_modelos():
    """Descobre quais modelos a SUA chave pode usar, em vez de chutar um nome
    (nome de modelo desatualizado é a causa mais comum do 'erro na chave')."""
    r = requests.get(f"{BASE}/models", headers=_headers(), params={"pageSize": 200}, timeout=30)
    if r.status_code in (400, 401, 403):
        _explicar_erro_chave(r)
    r.raise_for_status()

    bloqueados = ("image", "tts", "audio", "live", "embedding", "vision", "robotics", "computer", "thinking-exp")
    nomes = []
    for m in r.json().get("models", []):
        nome = m["name"].split("/", 1)[-1]
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        if not nome.startswith("gemini") or "flash" not in nome:
            continue
        if any(b in nome for b in bloqueados):
            continue
        nomes.append(nome)

    def prioridade(n):
        v = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
        versao = float(v.group(1)) if v else 0
        return (
            0 if "lite" in n else 1,          # Flash-Lite tem mais cota grátis por dia
            1 if ("preview" in n or "exp" in n) else 0,
            1 if n.endswith("latest") else 0,
            -versao,
        )

    return sorted(set(nomes), key=prioridade)


def gerar_texto():
    if not GEMINI_KEY:
        erro("GEMINI_API_KEY está vazia. Cadastre o secret GEMINI_API_KEY no repositório (veja o README).")

    historico = carregar_historico()
    evitar = "; ".join(historico[-30:]) or "nenhum"

    prompt = f"""Você é um criador de conteúdo brasileiro para Instagram, especialista em carrosséis.
Nicho do perfil: {NICHO}

Crie UM carrossel novo e útil com exatamente {SLIDES} slides de conteúdo.
NÃO repita estes temas já usados: {evitar}

Regras dos slides: cada slide traz UMA ideia, prática e específica, fácil de ler no celular.
Os slides seguem uma sequência lógica (passos, dicas, erros, mitos x verdades etc.).

Responda SOMENTE com um JSON neste formato:
{{
  "tema": "tema do post em até 6 palavras",
  "titulo": "título da capa que dá vontade de arrastar, no máximo 9 palavras",
  "subtitulo": "complemento da capa, no máximo 18 palavras",
  "slides": [
    {{"titulo": "título do slide, no máximo 7 palavras", "texto": "explicação do slide, no máximo 35 palavras"}}
  ],
  "chamada_final": "frase do último slide pedindo para salvar/seguir/comentar, no máximo 14 palavras",
  "legenda": "legenda do post em português do Brasil, 2 a 4 parágrafos curtos, tom próximo, alguns emojis, convide a arrastar para o lado e termine com uma chamada para ação",
  "hashtags": ["8 a 12 hashtags relevantes sem o símbolo #"],
  "prompt_imagem": "descrição curta EM INGLÊS de uma foto de fundo bonita e sem texto que combine com o tema"
}}"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 1.0},
    }

    candidatos = [GEMINI_MODEL] if GEMINI_MODEL else []
    candidatos += [m for m in listar_modelos() if m != GEMINI_MODEL]
    if not candidatos:
        erro("Sua chave não tem nenhum modelo Gemini Flash disponível. Verifique a chave no AI Studio.")

    ultimo_erro = ""
    for modelo in candidatos[:6]:
        print(f"→ Tentando modelo {modelo} ...")
        r = requests.post(f"{BASE}/models/{modelo}:generateContent", headers=_headers(), json=payload, timeout=120)
        if r.status_code in (401, 403):
            _explicar_erro_chave(r)
        if r.status_code != 200:
            ultimo_erro = f"{modelo}: HTTP {r.status_code} {r.text[:300]}"
            print(f"  ⚠ falhou ({r.status_code}), tentando o próximo...")
            continue
        try:
            partes = r.json()["candidates"][0]["content"]["parts"]
            bruto = "".join(p.get("text", "") for p in partes if not p.get("thought"))
            bruto = re.sub(r"^```(?:json)?|```$", "", bruto.strip(), flags=re.M).strip()
            dados = json.loads(bruto)
            for campo in ("tema", "titulo", "subtitulo", "slides", "legenda", "hashtags"):
                if not dados.get(campo):
                    raise ValueError(f"campo '{campo}' veio vazio")
            dados["slides"] = [sl for sl in dados["slides"] if sl.get("titulo") and sl.get("texto")][:SLIDES]
            if len(dados["slides"]) < 2:
                raise ValueError("poucos slides válidos")
            print(f"  ✔ texto gerado com {modelo}")
            return dados
        except Exception as e:
            ultimo_erro = f"{modelo}: resposta inválida ({e})"
            print("  ⚠ resposta inválida, tentando o próximo...")

    erro(
        "Nenhum modelo respondeu. Último erro:\n  " + ultimo_erro +
        "\n\nSe for HTTP 429, a cota grátis do dia acabou — espere algumas horas ou poste menos vezes por dia."
    )


def texto_de_teste():
    return {
        "tema": "teste de carrossel",
        "titulo": "5 hábitos que mudam sua rotina",
        "subtitulo": "Pequenas ações diárias que somam muito no fim do mês.",
        "slides": [
            {"titulo": "Acorde no mesmo horário", "texto": "Seu corpo se ajusta ao ritmo e você passa a acordar com mais disposição, até nos fins de semana."},
            {"titulo": "Planeje o dia na véspera", "texto": "Anote 3 prioridades antes de dormir. De manhã você já começa sabendo o que importa."},
            {"titulo": "Beba água ao acordar", "texto": "Um copo logo cedo ajuda a despertar e cria um gatilho para os próximos hábitos."},
            {"titulo": "Blocos de foco de 25 min", "texto": "Trabalhe sem notificações por 25 minutos e descanse 5. Repita quatro vezes e faça uma pausa maior."},
            {"titulo": "Revise a semana no domingo", "texto": "Dez minutos para ver o que funcionou e ajustar o que não funcionou valem mais que qualquer app."},
        ],
        "chamada_final": "Salve este post e comece hoje por um hábito só.",
        "legenda": "Post de teste gerado sem o Gemini. ✨\n\nArraste para o lado para ver os 5 hábitos 👉\n\nSalve para lembrar depois 📌",
        "hashtags": ["produtividade", "habitos", "rotina"],
        "prompt_imagem": "calm minimalist desk with plants, morning light",
    }


# ------------------------------------------------------------------ imagem
def fonte(tamanho, negrito=False):
    nomes = (
        ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"]
        if negrito else
        ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Arial.ttf", "arial.ttf"]
    )
    pastas = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation",
              "/usr/share/fonts/truetype/liberation2", "/Library/Fonts", "C:/Windows/Fonts", str(RAIZ)]
    for pasta in pastas:
        for nome in nomes:
            p = Path(pasta) / nome
            if p.exists():
                return ImageFont.truetype(str(p), tamanho)
    return ImageFont.load_default(size=tamanho)


def quebrar(draw, texto, f, largura_max):
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = f"{atual} {palavra}".strip()
        if draw.textlength(teste, font=f) <= largura_max:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def encaixar(draw, texto, negrito, tam_max, tam_min, largura, altura_max, espac=1.2):
    """Diminui a fonte até o texto caber na área."""
    for tam in range(tam_max, tam_min - 1, -4):
        f = fonte(tam, negrito)
        linhas = quebrar(draw, texto, f, largura)
        if len(linhas) * tam * espac <= altura_max:
            return f, linhas, tam
    f = fonte(tam_min, negrito)
    return f, quebrar(draw, texto, f, largura), tam_min


def fundo_gradiente(c1, c2):
    img = Image.new("RGB", (W, H), c1)
    px = img.load()
    for y in range(H):
        for x in range(0, W, 1):
            t = (x / W * 0.35) + (y / H * 0.65)
            px[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
    return img


def fundo_ia(prompt):
    """Imagem de fundo grátis via Pollinations (sem chave). Se falhar, retorna None."""
    try:
        url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) +
               f"?width={W}&height={H}&nologo=true&seed={random.randint(1, 10**6)}")
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        from io import BytesIO
        img = Image.open(BytesIO(r.content)).convert("RGB").resize((W, H))
        img = img.filter(ImageFilter.GaussianBlur(2))
        escuro = Image.new("RGB", (W, H), (0, 0, 0))
        return Image.blend(img, escuro, 0.55)  # escurece para o texto ficar legível
    except Exception as e:
        print(f"  ⚠ imagem IA falhou ({e}); usando gradiente.")
        return None


def rodape(d, destaque, texto_direita):
    margem = 100
    if PERFIL:
        d.text((margem, H - 150), PERFIL, font=fonte(38, True), fill=destaque)
    f = fonte(34)
    d.text((W - margem - d.textlength(texto_direita, font=f), H - 146), texto_direita, font=f, fill=(220, 220, 225))


def slide_capa(dados, estilo):
    c1, c2, destaque = estilo
    img = None
    if USAR_IMAGEM_IA and dados.get("prompt_imagem"):
        print("→ Gerando fundo da capa com IA...")
        img = fundo_ia(dados["prompt_imagem"] + ", photography, no text")
    if img is None:
        img = fundo_gradiente(c1, c2)

    d = ImageDraw.Draw(img)
    margem, largura = 100, W - 200
    d.rounded_rectangle([margem, 250, margem + 140, 264], radius=7, fill=destaque)

    f_tit, linhas, tam = encaixar(d, dados["titulo"], True, 104, 56, largura, 520, 1.15)
    y = 320
    for linha in linhas:
        d.text((margem, y), linha, font=f_tit, fill=(255, 255, 255))
        y += int(tam * 1.15)

    y += 50
    f_sub, linhas, tam = encaixar(d, dados["subtitulo"], False, 50, 32, largura, H - y - 220, 1.35)
    for linha in linhas:
        d.text((margem, y), linha, font=f_sub, fill=(235, 235, 240))
        y += int(tam * 1.35)

    rodape(d, destaque, "arraste para o lado →")
    return img


def slide_conteudo(slide, numero, total, estilo):
    c1, c2, destaque = estilo
    img = fundo_gradiente(c1, c2)
    d = ImageDraw.Draw(img)
    margem, largura = 100, W - 200

    # número grande do passo
    f_num = fonte(150, True)
    d.text((margem, 150), f"{numero:02d}", font=f_num, fill=destaque)

    f_tit, linhas, tam = encaixar(d, slide["titulo"], True, 84, 50, largura, 330, 1.15)
    y = 380
    for linha in linhas:
        d.text((margem, y), linha, font=f_tit, fill=(255, 255, 255))
        y += int(tam * 1.15)

    y += 30
    d.rounded_rectangle([margem, y, margem + 90, y + 8], radius=4, fill=destaque)
    y += 50
    f_txt, linhas, tam = encaixar(d, slide["texto"], False, 52, 32, largura, H - y - 220, 1.4)
    for linha in linhas:
        d.text((margem, y), linha, font=f_txt, fill=(235, 235, 240))
        y += int(tam * 1.4)

    rodape(d, destaque, f"{numero + 1}/{total}  →")
    return img


def slide_final(dados, total, estilo):
    c1, c2, destaque = estilo
    img = fundo_gradiente(c2, c1)  # gradiente invertido para destacar o fim
    d = ImageDraw.Draw(img)
    margem, largura = 100, W - 200

    chamada = dados.get("chamada_final") or "Salve este post para consultar depois!"
    f, linhas, tam = encaixar(d, chamada, True, 90, 50, largura, 560, 1.2)
    altura = len(linhas) * int(tam * 1.2)
    y = (H - altura) // 2 - 80
    for linha in linhas:
        d.text(((W - d.textlength(linha, font=f)) // 2, y), linha, font=f, fill=(255, 255, 255))
        y += int(tam * 1.2)

    y += 60
    icones = "salvar  •  comentar  •  compartilhar"
    f_ic = fonte(38)
    d.text(((W - d.textlength(icones, font=f_ic)) // 2, y), icones, font=f_ic, fill=destaque)

    if PERFIL:
        f_p = fonte(46, True)
        txt = f"Siga {PERFIL}"
        d.text(((W - d.textlength(txt, font=f_p)) // 2, H - 200), txt, font=f_p, fill=destaque)
    return img


def criar_carrossel(dados, pasta):
    estilo = random.choice(PALETAS)  # mesma paleta em todos os slides
    total = len(dados["slides"]) + 2
    imagens = [slide_capa(dados, estilo)]
    for i, slide in enumerate(dados["slides"], start=1):
        imagens.append(slide_conteudo(slide, i, total, estilo))
    imagens.append(slide_final(dados, total, estilo))

    pasta.mkdir(parents=True, exist_ok=True)
    caminhos = []
    for i, img in enumerate(imagens, start=1):
        c = pasta / f"{i:02d}.jpg"
        img.save(c, "JPEG", quality=92, optimize=True)  # Instagram exige JPEG
        caminhos.append(c)
    return caminhos


# ------------------------------------------------------------------ util
def carregar_historico():
    try:
        return json.loads(HISTORICO.read_text(encoding="utf-8"))
    except Exception:
        return []


def main():
    teste = "--teste" in sys.argv
    dados = texto_de_teste() if teste else gerar_texto()

    agora = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)  # horário de Brasília
    pasta = PASTA_POSTS / f"{agora:%Y-%m-%d_%H%M%S}"
    caminhos = criar_carrossel(dados, pasta)

    tags = " ".join("#" + re.sub(r"[^\wÀ-ÿ]", "", h.lstrip("#")) for h in dados["hashtags"][:15])
    legenda = f"{dados['legenda'].strip()}\n\n{tags}"[:2150]  # limite do Instagram: 2200 caracteres

    (RAIZ / "ultimo_post.json").write_text(
        json.dumps({"imagens": [c.relative_to(RAIZ).as_posix() for c in caminhos], "legenda": legenda,
                    "tema": dados["tema"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not teste:
        hist = carregar_historico() + [dados["tema"]]
        HISTORICO.write_text(json.dumps(hist[-60:], ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✅ Carrossel gerado: {pasta.name} ({len(caminhos)} slides)\n   Tema: {dados['tema']}\n")
    print(legenda)


if __name__ == "__main__":
    main()

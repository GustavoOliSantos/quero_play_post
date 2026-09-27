"""
conteudo.py — Pede à IA o texto do carrossel.

Provedores (os dois têm plano grátis):
  • Gemini (Google)  -> GEMINI_API_KEY   https://aistudio.google.com/apikey
  • Groq             -> GROQ_API_KEY     https://console.groq.com/keys

IA_PROVEDOR=auto (padrão) tenta o Gemini e, se ele falhar, usa o Groq.
Os nomes dos modelos são descobertos automaticamente (eles mudam com o tempo).
"""
import json
import re

import requests

import config
from config import cfg, cfg_int, erro

GEMINI = "https://generativelanguage.googleapis.com/v1beta"
GROQ = "https://api.groq.com/openai/v1"


class FalhaIA(Exception):
    pass


def _descrever_chave(nome):
    v = cfg(nome)
    origem = config.ORIGEM.get(nome, "?")
    return f"{nome}: começa com '{v[:4]}…', {len(v)} caracteres, lida de: {origem}"


def _detalhe(r):
    try:
        e = r.json().get("error", {})
        motivos = [d.get("reason") for d in e.get("details", []) if d.get("reason")]
        return e.get("message", r.text[:300]), (motivos[0] if motivos else "")
    except Exception:
        return r.text[:300], ""


# ------------------------------------------------------------------ Gemini
def _gemini_headers():
    return {"x-goog-api-key": cfg("GEMINI_API_KEY"), "Content-Type": "application/json"}


def _gemini_falha_chave(r):
    msg, motivo = _detalhe(r)
    texto = f"O Gemini recusou a chave (HTTP {r.status_code}{', ' + motivo if motivo else ''}): {msg}\n   {_descrever_chave('GEMINI_API_KEY')}"
    if motivo in ("ACCESS_TOKEN_TYPE_UNSUPPORTED", "API_KEY_SERVICE_BLOCKED") or cfg("GEMINI_API_KEY").startswith("AQ."):
        texto += ("\n\n   Esse é um problema conhecido do Google com as chaves novas que começam com 'AQ.':"
                  "\n   em algumas contas elas são recusadas mesmo estando certas. Tente:"
                  "\n     1. No AI Studio, criar a chave num PROJETO NOVO (Create API key > Create in new project)"
                  "\n     2. Conferir se copiou a chave inteira (as chaves AQ. são longas)"
                  "\n     3. Se continuar, use o Groq (grátis): preencha GROQ_API_KEY no .env — veja o README")
    else:
        texto += ("\n\n   1. Crie a chave em https://aistudio.google.com/apikey"
                  "\n   2. Cole só a chave no .env, sem aspas e sem espaços")
    raise FalhaIA(texto)


def listar_modelos_gemini():
    r = requests.get(f"{GEMINI}/models", headers=_gemini_headers(), params={"pageSize": 200}, timeout=30)
    if r.status_code in (400, 401, 403):
        _gemini_falha_chave(r)
    if r.status_code != 200:
        raise FalhaIA(f"Gemini fora do ar? HTTP {r.status_code}: {_detalhe(r)[0]}")

    fora = ("image", "tts", "audio", "live", "embedding", "vision", "robotics", "computer")
    nomes = set()
    for m in r.json().get("models", []):
        nome = m["name"].split("/", 1)[-1]
        if ("generateContent" in m.get("supportedGenerationMethods", [])
                and nome.startswith("gemini") and "flash" in nome
                and not any(f in nome for f in fora)):
            nomes.add(nome)

    def prioridade(n):
        v = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
        return (0 if "lite" in n else 1, 1 if ("preview" in n or "exp" in n) else 0,
                1 if n.endswith("latest") else 0, -(float(v.group(1)) if v else 0))

    return sorted(nomes, key=prioridade)


def _gerar_gemini(prompt):
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "generationConfig": {"responseMimeType": "application/json", "temperature": 1.0}}
    forcado = cfg("GEMINI_MODEL")
    modelos = ([forcado] if forcado else []) + [m for m in listar_modelos_gemini() if m != forcado]
    if not modelos:
        raise FalhaIA("Sua chave do Gemini não tem nenhum modelo Flash disponível.")

    ultimo = ""
    for modelo in modelos[:6]:
        print(f"→ Gemini: tentando {modelo} ...")
        r = requests.post(f"{GEMINI}/models/{modelo}:generateContent",
                          headers=_gemini_headers(), json=payload, timeout=120)
        if r.status_code in (401, 403):
            _gemini_falha_chave(r)
        if r.status_code != 200:
            ultimo = f"{modelo}: HTTP {r.status_code} {_detalhe(r)[0]}"
            print(f"  ⚠ falhou ({r.status_code}), tentando o próximo...")
            continue
        try:
            partes = r.json()["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in partes if not p.get("thought")), modelo
        except Exception as e:
            ultimo = f"{modelo}: resposta vazia ({e})"
    raise FalhaIA("Nenhum modelo do Gemini respondeu. Último erro: " + ultimo +
                  ("\n   (HTTP 429 = cota grátis do dia acabou)" if "429" in ultimo else ""))


# ------------------------------------------------------------------ Groq
def _groq_headers():
    return {"Authorization": f"Bearer {cfg('GROQ_API_KEY')}", "Content-Type": "application/json"}


def listar_modelos_groq():
    r = requests.get(f"{GROQ}/models", headers=_groq_headers(), timeout=30)
    if r.status_code in (401, 403):
        raise FalhaIA(f"O Groq recusou a chave (HTTP {r.status_code}): {_detalhe(r)[0]}\n"
                      f"   {_descrever_chave('GROQ_API_KEY')}\n"
                      "   Crie a chave em https://console.groq.com/keys e cole no .env (GROQ_API_KEY=)")
    if r.status_code != 200:
        raise FalhaIA(f"Groq fora do ar? HTTP {r.status_code}: {_detalhe(r)[0]}")

    fora = ("whisper", "tts", "guard", "compound", "playai", "embed", "vision", "orpheus", "safeguard")
    nomes = [m["id"] for m in r.json().get("data", []) if m.get("active", True)
             and not any(f in m["id"].lower() for f in fora)]
    preferidos = ("gpt-oss-120b", "llama-3.3-70b", "llama-4", "qwen", "kimi", "gpt-oss-20b", "llama")

    def prioridade(n):
        for i, p in enumerate(preferidos):
            if p in n.lower():
                return i
        return len(preferidos)

    return sorted(nomes, key=prioridade)


def _gerar_groq(prompt):
    forcado = cfg("GROQ_MODEL")
    modelos = ([forcado] if forcado else []) + [m for m in listar_modelos_groq() if m != forcado]
    ultimo = ""
    for modelo in modelos[:5]:
        print(f"→ Groq: tentando {modelo} ...")
        corpo = {"model": modelo, "temperature": 1.0,
                 "messages": [{"role": "system", "content": "Responda sempre só com JSON válido."},
                              {"role": "user", "content": prompt}],
                 "response_format": {"type": "json_object"}}
        r = requests.post(f"{GROQ}/chat/completions", headers=_groq_headers(), json=corpo, timeout=120)
        if r.status_code == 400:  # alguns modelos não aceitam o modo JSON; tenta sem
            corpo.pop("response_format")
            r = requests.post(f"{GROQ}/chat/completions", headers=_groq_headers(), json=corpo, timeout=120)
        if r.status_code in (401, 403):
            listar_modelos_groq()  # gera a mensagem de chave inválida
        if r.status_code != 200:
            ultimo = f"{modelo}: HTTP {r.status_code} {_detalhe(r)[0]}"
            print(f"  ⚠ falhou ({r.status_code}), tentando o próximo...")
            continue
        try:
            return r.json()["choices"][0]["message"]["content"], modelo
        except Exception as e:
            ultimo = f"{modelo}: resposta vazia ({e})"
    raise FalhaIA("Nenhum modelo do Groq respondeu. Último erro: " + ultimo)


# ------------------------------------------------------------------ geral
def provedores():
    escolha = cfg("IA_PROVEDOR", "auto").lower()
    if escolha in ("gemini", "groq"):
        return [escolha]
    lista = [p for p, k in (("gemini", "GEMINI_API_KEY"), ("groq", "GROQ_API_KEY")) if cfg(k)]
    if not lista:
        erro("Nenhuma chave de IA configurada. Preencha GEMINI_API_KEY ou GROQ_API_KEY no .env\n"
             "   (no GitHub: Settings > Secrets and variables > Actions > Secrets)")
    return lista


def _validar(bruto, slides):
    bruto = re.sub(r"^```(?:json)?|```$", "", bruto.strip(), flags=re.M).strip()
    inicio, fim = bruto.find("{"), bruto.rfind("}")
    dados = json.loads(bruto[inicio:fim + 1])
    for campo in ("tema", "titulo", "subtitulo", "slides", "legenda", "hashtags"):
        if not dados.get(campo):
            raise ValueError(f"campo '{campo}' vazio")
    dados["slides"] = [s for s in dados["slides"] if s.get("titulo") and s.get("texto")][:slides]
    if len(dados["slides"]) < 2:
        raise ValueError("poucos slides válidos")
    if isinstance(dados["hashtags"], str):
        dados["hashtags"] = dados["hashtags"].replace(",", " ").split()
    return dados


def _montar_prompt(nicho, slides, temas_usados):
    evitar = "; ".join(temas_usados[-30:]) or "nenhum"
    return f"""Você é um criador de conteúdo brasileiro para Instagram, especialista em carrosséis.
Nicho do perfil: {nicho}

Crie UM carrossel novo e útil com exatamente {slides} slides de conteúdo.
NÃO repita estes temas já usados: {evitar}

Regras: cada slide traz UMA ideia prática e específica, fácil de ler no celular.
Os slides seguem uma sequência lógica (passos, dicas, erros, mitos x verdades etc.).
Nos títulos e textos dos slides: sem emojis, sem hashtags e sem tudo em maiúsculas
(escreva normal, só a primeira letra maiúscula). Emojis só na legenda.

Responda SOMENTE com um JSON neste formato:
{{
  "tema": "tema do post em até 6 palavras",
  "titulo": "título da capa que dá vontade de arrastar, no máximo 9 palavras",
  "subtitulo": "complemento da capa, no máximo 18 palavras",
  "slides": [
    {{"titulo": "título do slide, no máximo 7 palavras", "texto": "explicação do slide, no máximo 35 palavras", "foto": "busca EM INGLÊS para uma foto de banco de imagens que mostre o assunto deste slide, 2 a 4 palavras"}}
  ],
  "chamada_final": "frase do último slide pedindo para salvar/seguir/comentar, no máximo 14 palavras",
  "legenda": "legenda em português do Brasil, 2 a 4 parágrafos curtos, tom próximo, alguns emojis, convide a arrastar para o lado e termine com uma chamada para ação",
  "hashtags": ["8 a 12 hashtags relevantes sem o símbolo #"],
  "foto_capa": "busca EM INGLÊS para a foto da capa, 2 a 4 palavras, algo bem visual do tema",
  "assunto_foto": "o assunto principal do perfil EM INGLÊS em 1 ou 2 palavras (usado se as outras buscas não acharem nada)"
}}

Para as buscas de foto: pense em fotos reais que existem em bancos de imagem (pessoas jogando,
treinando, a bola, a quadra, a rede, detalhes de mãos e tênis). Evite coisas abstratas ou muito
específicas que ninguém fotografou. Sempre inclua o esporte/assunto na busca (ex: "volleyball block at net")."""


def gerar_texto(temas_usados):
    nicho = cfg("NICHO", "dicas de produtividade e bem-estar")
    slides = cfg_int("SLIDES", 5, 2, 8)
    prompt = _montar_prompt(nicho, slides, temas_usados)

    falhas = []
    for prov in provedores():
        try:
            for tentativa in range(2):  # se o JSON vier quebrado, pede de novo uma vez
                bruto, modelo = (_gerar_gemini if prov == "gemini" else _gerar_groq)(prompt)
                try:
                    dados = _validar(bruto, slides)
                    dados["modelo"] = f"{prov}/{modelo}"
                    print(f"  ✔ texto gerado com {prov}/{modelo}")
                    return dados
                except Exception as e:
                    print(f"  ⚠ resposta fora do formato ({e}), pedindo de novo...")
            raise FalhaIA("a IA respondeu fora do formato duas vezes")
        except FalhaIA as e:
            falhas.append(f"[{prov}] {e}")
            print(f"\n⚠ {prov} falhou." + (" Tentando o próximo provedor...\n" if prov != provedores()[-1] else ""))

    erro("Não consegui gerar o texto.\n\n" + "\n\n".join(falhas))


def testar_provedor(prov):
    """Usado pelo 'python main.py checar'. Retorna (ok, mensagem)."""
    try:
        modelos = listar_modelos_gemini() if prov == "gemini" else listar_modelos_groq()
        if not modelos:
            return False, "chave aceita, mas nenhum modelo de texto disponível"
        bruto, modelo = (_gerar_gemini if prov == "gemini" else _gerar_groq)(
            'Responda só com este JSON: {"ok": true}')
        return True, f"funcionando ({modelo})"
    except FalhaIA as e:
        return False, str(e)


def texto_de_teste():
    return {
        "tema": "teste de carrossel",
        "titulo": "Você sabia destas regras estranhas do vôlei?",
        "subtitulo": "Detalhes do regulamento oficial que quase ninguém conhece nas quadras.",
        "slides": [
            {"titulo": "O líbero não pode atacar acima da rede", "texto": "Ele pode defender e passar à vontade, mas nunca completar um ataque com a bola acima da altura da fita.", "foto": "volleyball libero dig"},
            {"titulo": "Tocar a rede nem sempre é falta", "texto": "Só é falta quando o toque atrapalha a jogada ou acontece entre as antenas durante a ação de jogar a bola.", "foto": "volleyball net block"},
            {"titulo": "Pisar na linha central é permitido", "texto": "Você pode invadir com parte do pé, desde que alguma parte dele continue em contato com a linha ou acima dela.", "foto": "volleyball court line shoes"},
            {"titulo": "Dois toques no primeiro contato valem", "texto": "Na recepção, a bola pode encostar em partes diferentes do corpo, desde que seja numa mesma ação.", "foto": "volleyball reception pass"},
            {"titulo": "O saque tem só 8 segundos", "texto": "Depois do apito do árbitro, o sacador tem oito segundos para bater na bola. Passou disso, é ponto do adversário.", "foto": "volleyball serve"},
        ],
        "chamada_final": "Salve para mostrar pro seu time no próximo treino",
        "legenda": "Post de TESTE gerado sem IA. 🏐\n\nArraste para o lado e veja 5 regras que pegam muita gente de surpresa 👉\n\nMarca aquele amigo que vive discutindo com o juiz 😂",
        "hashtags": ["volei", "voleibol", "regrasdovolei"],
        "foto_capa": "volleyball referee whistle",
        "assunto_foto": "volleyball",
        "modelo": "teste",
    }

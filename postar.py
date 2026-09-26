"""
postar.py — Publica um CARROSSEL no Instagram usando a API oficial da Meta (grátis),
sem Buffer. Precisa de uma conta Instagram Profissional (Criador de conteúdo ou Empresa).

Lê ultimo_post.json (criado pelo gerar.py). As imagens precisam estar num link público:
aqui usamos o próprio repositório do GitHub (que por isso precisa ser PÚBLICO).
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

TOKEN = os.environ.get("IG_TOKEN", "").strip()
IG_USER_ID = os.environ.get("IG_USER_ID", "").strip()
VERSAO = os.environ.get("IG_API_VERSION", "").strip() or "v24.0"
REPO = os.environ.get("GITHUB_REPOSITORY", "").strip()      # preenchido automaticamente no GitHub Actions
NOVO_TOKEN_PATH = os.environ.get("NOVO_TOKEN_PATH", "").strip()

API = f"https://graph.instagram.com/{VERSAO}"
RAIZ = Path(__file__).parent

DICAS = {
    190: "Token inválido ou expirado. Gere um novo token no painel da Meta e atualize o secret IG_TOKEN.",
    10: "Falta permissão. Ao gerar o token, a permissão instagram_business_content_publish precisa estar marcada.",
    200: "Falta permissão. Ao gerar o token, a permissão instagram_business_content_publish precisa estar marcada.",
    100: "Parâmetro inválido. Confira se IG_USER_ID é o ID da conta Instagram (aparece no painel da Meta ao lado do token).",
    9004: "O Instagram não conseguiu baixar a imagem. O repositório precisa ser PÚBLICO.",
    9007: "A mídia ainda não estava pronta. Rode de novo.",
    4: "Limite de chamadas atingido. Espere 1 hora.",
    25: "Limite de posts por dia atingido (máx. ~25 em 24h).",
}


def erro(msg):
    print(f"\n❌ {msg}\n", file=sys.stderr)
    sys.exit(1)


def checar(r, etapa):
    try:
        dados = r.json()
    except Exception:
        erro(f"{etapa}: resposta inesperada (HTTP {r.status_code}): {r.text[:300]}")
    if "error" in dados:
        e = dados["error"]
        codigo = e.get("code")
        sub = e.get("error_subcode")
        dica = DICAS.get(sub) or DICAS.get(codigo) or ""
        if sub == 2207052 or "fetch" in str(e.get("message", "")).lower():
            dica = DICAS[9004]
        erro(f"{etapa} falhou: {e.get('message')} (code {codigo}, subcode {sub})\n   👉 {dica}")
    return dados


def url_publica(caminho_rel):
    if not REPO:
        erro("GITHUB_REPOSITORY não definido. Rode pelo GitHub Actions (ou defina GITHUB_REPOSITORY=usuario/repo).")
    # usa o hash do commit (não o nome da branch) para evitar cache velho do GitHub
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=RAIZ, text=True).strip()
    return f"https://raw.githubusercontent.com/{REPO}/{sha}/{caminho_rel}"


def esperar_url(url, tentativas=12):
    for i in range(tentativas):
        r = requests.head(url, timeout=20, allow_redirects=True)
        if r.status_code == 200:
            return
        time.sleep(5)
    erro(f"A imagem não ficou acessível em {url}\n   👉 O repositório precisa ser PÚBLICO para o Instagram baixar a imagem.")


def renovar_token():
    """Tokens duram 60 dias. Renovar a cada post mantém ele vivo para sempre
    (se o secret GH_PAT estiver configurado, o workflow salva o token novo)."""
    try:
        r = requests.get("https://graph.instagram.com/refresh_access_token",
                         params={"grant_type": "ig_refresh_token", "access_token": TOKEN}, timeout=30)
        dados = r.json()
        novo = dados.get("access_token")
        if novo and NOVO_TOKEN_PATH:
            Path(NOVO_TOKEN_PATH).write_text(novo)
            dias = int(dados.get("expires_in", 0)) // 86400
            print(f"🔄 Token renovado (vale mais {dias} dias).")
        elif not novo:
            print(f"ℹ Não deu para renovar o token agora (normal se ele tem menos de 24h): {dados.get('error', {}).get('message', '')}")
    except Exception as e:
        print(f"ℹ Renovação do token pulada: {e}")


def esperar_pronto(container, etapa):
    for _ in range(36):
        r = requests.get(f"{API}/{container}", timeout=30,
                         params={"fields": "status_code,status", "access_token": TOKEN})
        status = checar(r, etapa)
        if status.get("status_code") == "FINISHED":
            return
        if status.get("status_code") == "ERROR":
            erro(f"{etapa}: o Instagram rejeitou a mídia: {status.get('status')}")
        time.sleep(5)
    erro(f"{etapa}: o Instagram demorou demais para processar. Rode de novo.")


def main():
    if not TOKEN:
        erro("IG_TOKEN está vazio. Cadastre o secret IG_TOKEN (veja o README).")
    if not IG_USER_ID:
        erro("IG_USER_ID está vazio. Cadastre o secret IG_USER_ID (veja o README).")

    post = json.loads((RAIZ / "ultimo_post.json").read_text(encoding="utf-8"))
    imagens = post["imagens"][:10]  # limite da API: 10 itens por carrossel
    if len(imagens) < 2:
        erro("Um carrossel precisa de pelo menos 2 imagens.")

    urls = [url_publica(c) for c in imagens]
    for u in urls:
        esperar_url(u)

    # 1) um container para cada slide
    filhos = []
    for i, url in enumerate(urls, start=1):
        r = requests.post(f"{API}/{IG_USER_ID}/media", timeout=60, data={
            "image_url": url, "is_carousel_item": "true", "access_token": TOKEN})
        cid = checar(r, f"Slide {i}")["id"]
        esperar_pronto(cid, f"Slide {i}")
        filhos.append(cid)
        print(f"→ Slide {i}/{len(urls)} enviado")

    # 2) container do carrossel juntando os slides + legenda
    r = requests.post(f"{API}/{IG_USER_ID}/media", timeout=60, data={
        "media_type": "CAROUSEL", "children": ",".join(filhos),
        "caption": post["legenda"], "access_token": TOKEN})
    carrossel = checar(r, "Criar carrossel")["id"]
    esperar_pronto(carrossel, "Carrossel")
    print(f"→ Carrossel montado: {carrossel}")

    # 3) publica
    r = requests.post(f"{API}/{IG_USER_ID}/media_publish", timeout=60,
                      data={"creation_id": carrossel, "access_token": TOKEN})
    media_id = checar(r, "Publicar")["id"]
    print(f"\n✅ Carrossel publicado no Instagram! ID do post: {media_id}")

    renovar_token()


if __name__ == "__main__":
    main()

"""
instagram.py — Publica carrosséis pela API oficial do Instagram (grátis, sem Buffer).
Precisa de conta Profissional (Criador de conteúdo ou Empresa).
"""
import time

import requests

from config import cfg, erro

DICAS = {
    190: "Token inválido ou expirado. Gere um novo no painel da Meta e atualize o IG_TOKEN.",
    10: "Falta a permissão instagram_business_content_publish no token.",
    200: "Falta a permissão instagram_business_content_publish no token.",
    100: "Parâmetro inválido. Confira o IG_USER_ID (rode: python main.py checar).",
    4: "Limite de chamadas atingido. Espere 1 hora.",
    25: "Limite de posts por dia atingido.",
}
DICA_IMAGEM = ("O Instagram não conseguiu baixar as imagens. O repositório precisa ser PÚBLICO "
               "e as imagens precisam estar no GitHub (git push).")


def _api():
    return f"https://graph.instagram.com/{cfg('IG_API_VERSION', 'v24.0')}"


def _token():
    t = cfg("IG_TOKEN")
    if not t:
        erro("IG_TOKEN está vazio. Preencha no .env (computador) ou nos Secrets (GitHub).")
    return t


def _checar(r, etapa):
    try:
        dados = r.json()
    except Exception:
        erro(f"{etapa}: resposta inesperada (HTTP {r.status_code}): {r.text[:300]}")
    if "error" in dados:
        e = dados["error"]
        cod, sub, msg = e.get("code"), e.get("error_subcode"), e.get("message", "")
        dica = DICA_IMAGEM if (sub in (2207052, 2207003) or "fetch" in msg.lower() or "download" in msg.lower()) \
            else DICAS.get(cod, "")
        erro(f"{etapa} falhou: {msg} (code {cod}, subcode {sub})" + (f"\n   👉 {dica}" if dica else ""))
    return dados


def conferir_conta():
    """Confere o token sem postar nada. Retorna (user_id, username)."""
    r = requests.get(f"{_api()}/me", timeout=30,
                     params={"fields": "user_id,username,account_type", "access_token": _token()})
    d = _checar(r, "Conferir token")
    return str(d.get("user_id") or d.get("id")), d.get("username"), d.get("account_type")


def esperar_url(url, tentativas=12):
    for _ in range(tentativas):
        try:
            if requests.head(url, timeout=20, allow_redirects=True).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(5)
    erro(f"A imagem não está acessível em:\n   {url}\n   👉 {DICA_IMAGEM}")


def _esperar_pronto(container, etapa):
    for _ in range(36):
        r = requests.get(f"{_api()}/{container}", timeout=30,
                         params={"fields": "status_code,status", "access_token": _token()})
        st = _checar(r, etapa)
        if st.get("status_code") == "FINISHED":
            return
        if st.get("status_code") == "ERROR":
            erro(f"{etapa}: o Instagram rejeitou a mídia: {st.get('status')}")
        time.sleep(5)
    erro(f"{etapa}: o Instagram demorou demais para processar. Tente de novo.")


def publicar_carrossel(urls, legenda):
    user_id = cfg("IG_USER_ID")
    if not user_id:
        erro("IG_USER_ID está vazio. Rode 'python main.py checar' para descobrir o seu.")
    if not 2 <= len(urls) <= 10:
        erro(f"Um carrossel precisa ter de 2 a 10 imagens (este tem {len(urls)}).")

    for u in urls:
        esperar_url(u)

    filhos = []
    for i, url in enumerate(urls, start=1):
        r = requests.post(f"{_api()}/{user_id}/media", timeout=60, data={
            "image_url": url, "is_carousel_item": "true", "access_token": _token()})
        cid = _checar(r, f"Slide {i}")["id"]
        _esperar_pronto(cid, f"Slide {i}")
        filhos.append(cid)
        print(f"→ Slide {i}/{len(urls)} enviado")

    r = requests.post(f"{_api()}/{user_id}/media", timeout=60, data={
        "media_type": "CAROUSEL", "children": ",".join(filhos),
        "caption": legenda, "access_token": _token()})
    carrossel = _checar(r, "Montar carrossel")["id"]
    _esperar_pronto(carrossel, "Carrossel")

    r = requests.post(f"{_api()}/{user_id}/media_publish", timeout=60,
                      data={"creation_id": carrossel, "access_token": _token()})
    media_id = _checar(r, "Publicar")["id"]

    link = None
    try:
        r = requests.get(f"{_api()}/{media_id}", timeout=30,
                         params={"fields": "permalink", "access_token": _token()})
        link = r.json().get("permalink")
    except Exception:
        pass
    return media_id, link


def renovar_token():
    """Tokens duram 60 dias; renovar a cada post mantém ele sempre válido."""
    try:
        r = requests.get("https://graph.instagram.com/refresh_access_token", timeout=30,
                         params={"grant_type": "ig_refresh_token", "access_token": _token()})
        d = r.json()
        if d.get("access_token"):
            return d["access_token"], int(d.get("expires_in", 0)) // 86400
        print(f"ℹ Token não renovado agora (normal se tem menos de 24h): {d.get('error', {}).get('message', '')}")
    except Exception as e:
        print(f"ℹ Renovação do token pulada: {e}")
    return None, 0

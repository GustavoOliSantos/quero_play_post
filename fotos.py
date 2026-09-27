"""
fotos.py — Busca fotos que combinam com cada slide no Pexels (banco de fotos gratuito).

Chave grátis em https://www.pexels.com/api/  ->  PEXELS_API_KEY no .env
Regras do Pexels: citar a Pexels e, quando possível, os fotógrafos. O crédito vai
automaticamente no fim da legenda.

As fotos baixadas ficam em fila/<ID>/fotos/ (não vão para o GitHub, para o repositório
não crescer demais). Se faltarem, são baixadas de novo pelo link salvo no post.json.
"""
import json
import random

import requests

from config import RAIZ, cfg

API = "https://api.pexels.com/v1/search"
USADAS = RAIZ / "fotos_usadas.json"


def ativo():
    return bool(cfg("PEXELS_API_KEY")) and cfg("FOTOS", "sim").lower() not in ("nao", "não", "false", "0")


def _usadas():
    try:
        return set(json.loads(USADAS.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _salvar_usadas(ids):
    USADAS.write_text(json.dumps(sorted(ids)[-800:]), encoding="utf-8")


def _buscar(consulta, orientacao, evitar):
    r = requests.get(API, timeout=30, headers={"Authorization": cfg("PEXELS_API_KEY")},
                     params={"query": consulta, "orientation": orientacao, "per_page": 30})
    if r.status_code in (401, 403):
        raise RuntimeError("chave do Pexels recusada. Confira PEXELS_API_KEY (https://www.pexels.com/api/)")
    if r.status_code == 429:
        raise RuntimeError("limite do Pexels atingido (200 buscas por hora). Tente mais tarde")
    r.raise_for_status()
    novas = [f for f in r.json().get("photos", []) if f["id"] not in evitar]
    if not novas:
        return None
    f = random.choice(novas[:10])  # sorteia entre as mais relevantes, para variar
    return {
        "id": f["id"],
        "busca": consulta,
        "orientacao": orientacao,
        "baixar": f["src"].get("large2x") or f["src"]["original"],
        "fotografo": f.get("photographer", ""),
        "pagina": f.get("url", ""),
    }


def escolher(consultas, orientacao, evitar):
    """Tenta as buscas em ordem (da mais específica para a mais geral)."""
    for consulta in [c for c in consultas if c]:
        foto = _buscar(consulta, orientacao, evitar)
        if foto:
            return foto
    return None


def baixar(foto, destino):
    if destino.exists():
        return True
    try:
        r = requests.get(foto["baixar"], timeout=60)
        r.raise_for_status()
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(r.content)
        return True
    except Exception as e:
        print(f"  ⚠ não consegui baixar a foto {foto.get('id')}: {e}")
        return False


def buscar_para_post(dados, pasta):
    """Escolhe e baixa a foto da capa e a de cada slide. Guarda tudo em dados['fotos']."""
    if not ativo():
        return
    geral = dados.get("assunto_foto") or "sport"
    usadas = _usadas()
    no_post = set()
    fotos = {"capa": None, "slides": []}
    print("→ Buscando fotos no Pexels...")
    try:
        fotos["capa"] = escolher([dados.get("foto_capa"), geral], "portrait", usadas | no_post)
        if fotos["capa"]:
            no_post.add(fotos["capa"]["id"])
        for sl in dados["slides"]:
            f = escolher([sl.get("foto"), dados.get("foto_capa"), geral], "landscape", usadas | no_post)
            if f:
                no_post.add(f["id"])
            fotos["slides"].append(f)
    except Exception as e:
        print(f"  ⚠ fotos: {e}. Seguindo sem as fotos que faltaram.")
        fotos["slides"] += [None] * (len(dados["slides"]) - len(fotos["slides"]))

    dados["fotos"] = fotos
    _salvar_usadas(usadas | no_post)
    garantir_arquivos(dados, pasta)
    achadas = sum(1 for f in [fotos["capa"]] + fotos["slides"] if f)
    print(f"  ✔ {achadas} fotos encontradas")


def trocar(dados, pasta, qual):
    """Troca uma foto (0 = capa, 1..N = slides) por outra da mesma busca."""
    fotos = dados.get("fotos") or {"capa": None, "slides": [None] * len(dados["slides"])}
    atual = fotos["capa"] if qual == 0 else fotos["slides"][qual - 1]
    usadas = _usadas()
    ja_no_post = {f["id"] for f in [fotos["capa"]] + fotos["slides"] if f}
    if qual == 0:
        consultas, orient = [dados.get("foto_capa"), dados.get("assunto_foto")], "portrait"
    else:
        consultas = [dados["slides"][qual - 1].get("foto"), dados.get("foto_capa"), dados.get("assunto_foto")]
        orient = "landscape"
    if atual:
        consultas = [atual["busca"]] + consultas
    nova = escolher(consultas, orient, usadas | ja_no_post)
    if not nova:
        return False
    if qual == 0:
        fotos["capa"] = nova
    else:
        fotos["slides"][qual - 1] = nova
    dados["fotos"] = fotos
    _salvar_usadas(usadas | {nova["id"]})
    garantir_arquivos(dados, pasta)
    return True


def arquivo(pasta, foto):
    return pasta / "fotos" / f"{foto['id']}.jpg" if foto else None


def garantir_arquivos(dados, pasta):
    """Baixa de novo as fotos que não estão na pasta (ex: post gerado no GitHub)."""
    fotos = dados.get("fotos") or {}
    for f in [fotos.get("capa")] + list(fotos.get("slides") or []):
        if f:
            baixar(f, arquivo(pasta, f))


def credito(dados):
    fotos = dados.get("fotos") or {}
    nomes = []
    for f in [fotos.get("capa")] + list(fotos.get("slides") or []):
        if f and f.get("fotografo") and f["fotografo"] not in nomes:
            nomes.append(f["fotografo"])
    if not nomes:
        return ""
    lista = nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]
    return f"📷 Fotos: {lista} (Pexels)"

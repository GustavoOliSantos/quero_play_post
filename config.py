"""
config.py — Lê as configurações do arquivo .env (no seu computador)
ou dos Secrets/Variables (no GitHub Actions).

As chaves NUNCA ficam no código: ficam no .env, que não sobe para o GitHub.
"""
import os
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ARQ_ENV = RAIZ / ".env"
ARQ_EXEMPLO = RAIZ / ".env.exemplo"

FILA = RAIZ / "fila"               # posts gerados esperando revisão
PUBLICADOS = RAIZ / "publicados"   # posts que já foram para o Instagram
HISTORICO = RAIZ / "historico.json"

NA_NUVEM = os.environ.get("GITHUB_ACTIONS") == "true"


ORIGEM = {}  # de onde veio cada chave (.env ou variável do sistema), para diagnóstico


def _ler_pares(arquivo):
    pares = {}
    for linha in arquivo.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        pares[chave.strip()] = valor.split(" #")[0].strip().strip('"').strip("'")
    return pares


def carregar_env():
    """Carrega o .env. No computador, o .env tem prioridade sobre variáveis do sistema
    (evita uma chave antiga, definida no terminal, 'grudar' e ser usada no lugar da nova).
    Na primeira vez, cria o .env a partir do .env.exemplo."""
    if not ARQ_ENV.exists():
        if NA_NUVEM:
            return
        if ARQ_EXEMPLO.exists():
            shutil.copy(ARQ_EXEMPLO, ARQ_ENV)
            print("📝 Criei o arquivo .env. Abra ele, preencha suas chaves e rode de novo.\n")
        return

    pares = _ler_pares(ARQ_ENV)

    # se o .env.exemplo ganhou opções novas, acrescenta no seu .env (vazias)
    if not NA_NUVEM and ARQ_EXEMPLO.exists():
        faltando = [k for k in _ler_pares(ARQ_EXEMPLO) if k not in pares]
        if faltando:
            with open(ARQ_ENV, "a", encoding="utf-8") as f:
                f.write("\n# --- opções novas adicionadas automaticamente (veja o .env.exemplo) ---\n")
                f.writelines(f"{k}=\n" for k in faltando)
            print(f"📝 Adicionei ao seu .env as opções novas: {', '.join(faltando)}\n")

    for chave, valor in pares.items():
        existente = os.environ.get(chave, "").strip()
        if valor and (not existente or not NA_NUVEM):
            if existente and existente != valor:
                ORIGEM[chave] = ".env (ignorei um valor diferente definido no terminal/sistema)"
            else:
                ORIGEM[chave] = ".env"
            os.environ[chave] = valor
        elif existente:
            ORIGEM[chave] = "variável do terminal/sistema"


def atualizar_env(chave, valor):
    """Troca o valor de uma chave dentro do .env (usado para salvar o token renovado)."""
    if not ARQ_ENV.exists():
        return False
    linhas = ARQ_ENV.read_text(encoding="utf-8").splitlines()
    achou = False
    for i, linha in enumerate(linhas):
        if linha.strip().startswith(f"{chave}="):
            linhas[i] = f"{chave}={valor}"
            achou = True
    if not achou:
        linhas.append(f"{chave}={valor}")
    ARQ_ENV.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return True


def cfg(nome, padrao=""):
    return os.environ.get(nome, "").strip() or padrao


def cfg_bool(nome):
    return cfg(nome).lower() in ("1", "true", "sim", "yes")


def cfg_int(nome, padrao, minimo, maximo):
    try:
        return max(minimo, min(maximo, int(cfg(nome) or padrao)))
    except ValueError:
        return padrao


def erro(msg):
    print(f"\n❌ {msg}\n", file=sys.stderr)
    sys.exit(1)

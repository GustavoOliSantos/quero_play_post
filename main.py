"""
main.py — Carrossel automático para Instagram com revisão antes de postar.

Comandos:
  python main.py checar            confere as chaves do .env (Gemini e Instagram), sem postar nada
  python main.py gerar             gera um carrossel novo e coloca na FILA para você revisar
  python main.py gerar --teste     gera um carrossel de exemplo, sem usar o Gemini
  python main.py listar            mostra o que está na fila e o que já foi publicado
  python main.py ver [ID]          abre a prévia do post no navegador (padrão: o mais recente da fila)
  python main.py redesenhar ID     refaz as imagens depois que você editar o post.json
  python main.py trocar-foto ID N  troca uma foto que não combinou (0 = capa, 1, 2... = slides)
  python main.py postar [ID]       publica um post da fila (padrão: o mais antigo)

Fluxo: gerar -> revisar (e editar se quiser) -> postar.
"""
import datetime
import html
import json
import os
import re
import shutil
import subprocess
import sys
import webbrowser

import config
from config import FILA, HISTORICO, NA_NUVEM, PUBLICADOS, RAIZ, cfg, erro

config.carregar_env()  # precisa vir antes de usar qualquer chave

import conteudo  # noqa: E402
import fotos  # noqa: E402
import instagram  # noqa: E402
import slides  # noqa: E402


# ------------------------------------------------------------------ utilitários
def agora_brasilia():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3)))


def ler_json(caminho, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except Exception:
        return padrao


def salvar_json(caminho, dados):
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def imagens_do_post(pasta):
    return sorted(pasta.glob("[0-9][0-9].jpg"))


def posts_na_fila():
    return sorted(p for p in FILA.glob("*") if p.is_dir() and (p / "post.json").exists())


def achar_post(post_id, padrao="antigo"):
    if post_id:
        pasta = FILA / post_id
        if not pasta.exists():
            erro(f"Não achei o post '{post_id}' na fila. Rode 'python main.py listar'.")
        return pasta
    fila = posts_na_fila()
    if not fila:
        erro("A fila está vazia. Rode 'python main.py gerar' primeiro.")
    return fila[0] if padrao == "antigo" else fila[-1]


def montar_legenda(dados):
    tags = " ".join("#" + re.sub(r"[^\wÀ-ÿ]", "", h.lstrip("#")) for h in dados.get("hashtags", [])[:15])
    partes = [dados["legenda"].strip(), fotos.credito(dados), tags]
    return "\n\n".join(p for p in partes if p)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=RAIZ, text=True, stderr=subprocess.DEVNULL).strip()


def repositorio():
    repo = cfg("GITHUB_REPOSITORY") or cfg("GITHUB_REPO")
    if repo:
        return repo
    try:  # tenta descobrir pelo git remote
        url = git("remote", "get-url", "origin")
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
        if m:
            return m.group(1)
    except Exception:
        pass
    erro("Não sei qual é o seu repositório no GitHub. Preencha GITHUB_REPO no .env (ex: seuusuario/insta-auto).")


def urls_publicas(pasta):
    """Links públicos das imagens no GitHub (usa o hash do commit para evitar cache antigo)."""
    rel = pasta.relative_to(RAIZ).as_posix()
    if not NA_NUVEM:
        try:
            pendente = [l for l in git("status", "--porcelain", "--untracked-files=all", "--", rel).splitlines() if l.endswith(".jpg")]
            if pendente:
                erro("As imagens deste post ainda não foram enviadas ao GitHub.\n"
                     "   Rode: git add -A && git commit -m \"novo post\" && git push")
            if git("rev-list", "--count", "@{u}..HEAD") != "0":
                erro("Você tem commits que ainda não foram enviados. Rode: git push")
        except subprocess.CalledProcessError:
            pass
        except FileNotFoundError:
            erro("Para postar do computador você precisa do git instalado e do projeto ligado ao GitHub.\n"
                 "   Ou poste pelo GitHub Actions (veja o README).")
    sha = git("rev-parse", "HEAD")
    return [f"https://raw.githubusercontent.com/{repositorio()}/{sha}/{rel}/{a.name}"
            for a in imagens_do_post(pasta)]


# ------------------------------------------------------------------ prévias
def escrever_previas(pasta, dados):
    legenda = (pasta / "legenda.txt").read_text(encoding="utf-8")
    imgs = imagens_do_post(pasta)
    perfil = cfg("PERFIL", "@seuperfil")

    # README.md -> o GitHub mostra isso ao abrir a pasta do post
    md = [f"# {dados['tema']}", "",
          f"**Status:** aguardando revisão · {len(imgs)} slides · gerado com `{dados.get('modelo', '?')}`", "",
          " ".join(f'<img src="{a.name}" width="240">' for a in imgs), "",
          "## Legenda", ""]
    md += [f"> {l}" if l else ">" for l in legenda.splitlines()]
    md += ["", "---",
           "**Quer mudar algo?** Edite o `legenda.txt` para trocar a legenda, ou o `post.json` para trocar "
           "os textos dos slides (depois rode `python main.py redesenhar " + pasta.name + "`).",
           "Foto não combinou? `python main.py trocar-foto " + pasta.name + " N` (0 = capa, 1, 2... = slides).",
           "Para descartar este post, apague esta pasta."]
    (pasta / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # preview.html -> imitação do Instagram para ver no computador
    slides_html = "".join(f'<img src="{a.name}">' for a in imgs)
    pontos = "".join("<i></i>" for _ in imgs)
    (pasta / "preview.html").write_text(f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Prévia: {html.escape(dados['tema'])}</title>
<style>
body{{margin:0;background:#fafafa;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#111}}
.post{{max-width:470px;margin:24px auto;background:#fff;border:1px solid #dbdbdb;border-radius:8px;overflow:hidden}}
.topo{{display:flex;align-items:center;gap:10px;padding:12px;font-weight:600}}
.avatar{{width:32px;height:32px;border-radius:50%;background:linear-gradient(45deg,#f9ce34,#ee2a7b,#6228d7)}}
.car{{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;aspect-ratio:4/5;background:#000}}
.car img{{width:100%;flex:0 0 100%;object-fit:cover;scroll-snap-align:start}}
.pontos{{display:flex;justify-content:center;gap:4px;padding:10px}}
.pontos i{{width:6px;height:6px;border-radius:50%;background:#c7c7c7}}
.legenda{{padding:0 14px 16px;white-space:pre-wrap;line-height:1.4;font-size:14px}}
.aviso{{max-width:470px;margin:0 auto 32px;font-size:13px;color:#555;padding:0 8px}}
</style></head><body>
<div class="post"><div class="topo"><div class="avatar"></div>{html.escape(perfil)}</div>
<div class="car">{slides_html}</div><div class="pontos">{pontos}</div>
<div class="legenda"><b>{html.escape(perfil)}</b> {html.escape(legenda)}</div></div>
<p class="aviso">Arraste as imagens para o lado. Para editar: <code>legenda.txt</code> (legenda) ou
<code>post.json</code> + <code>python main.py redesenhar {pasta.name}</code> (textos dos slides).</p>
</body></html>""", encoding="utf-8")


def abrir_previa(pasta):
    if not NA_NUVEM and "--sem-abrir" not in sys.argv:
        webbrowser.open((pasta / "preview.html").resolve().as_uri())


# ------------------------------------------------------------------ comandos
def cmd_checar():
    print("🔎 Conferindo configurações...\n")
    ok = True

    nomes = {"gemini": "Gemini", "groq": "Groq"}
    algum_ok = False
    for prov, chave in (("gemini", "GEMINI_API_KEY"), ("groq", "GROQ_API_KEY")):
        if not cfg(chave):
            print(f"➖ {nomes[prov]}: {chave} vazia no .env")
            continue
        certo, msg = conteudo.testar_provedor(prov)
        algum_ok |= certo
        print(f"{'✅' if certo else '❌'} {nomes[prov]}: {msg}\n")
    if not algum_ok:
        print("❌ Nenhuma IA funcionando. Preencha GEMINI_API_KEY ou GROQ_API_KEY no .env (basta uma).")
        ok = False

    if cfg("IG_TOKEN"):
        user_id, username, tipo = instagram.conferir_conta()
        print(f"✅ Instagram: token válido para @{username} (conta {tipo or '?'})")
        if not cfg("IG_USER_ID"):
            print(f"   ⚠ IG_USER_ID vazio. Coloque no .env: IG_USER_ID={user_id}")
            ok = False
        elif cfg("IG_USER_ID") != user_id:
            print(f"   ⚠ IG_USER_ID no .env ({cfg('IG_USER_ID')}) é diferente do da conta ({user_id}). Use {user_id}.")
            ok = False
        else:
            print(f"✅ IG_USER_ID confere ({user_id})")
    else:
        print("❌ Instagram: IG_TOKEN vazio no .env")
        ok = False

    print("\n" + ("Tudo certo! 🎉" if ok else "Corrija os itens acima e rode de novo."))


def cmd_gerar():
    teste = "--teste" in sys.argv
    historico = ler_json(HISTORICO, [])
    dados = conteudo.texto_de_teste() if teste else conteudo.gerar_texto(historico)
    dados["gerado_em"] = agora_brasilia().isoformat(timespec="minutes")

    post_id = agora_brasilia().strftime("%Y-%m-%d_%H%M%S") + ("_teste" if teste else "")
    pasta = FILA / post_id
    fotos.buscar_para_post(dados, pasta)
    slides.desenhar_carrossel(dados, pasta)
    salvar_json(pasta / "post.json", dados)
    (pasta / "legenda.txt").write_text(montar_legenda(dados), encoding="utf-8")
    escrever_previas(pasta, dados)

    if not teste:
        salvar_json(HISTORICO, (historico + [dados["tema"]])[-60:])

    if NA_NUVEM and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"post_id={post_id}\n")

    print(f"\n✅ Carrossel na fila: fila/{post_id}  ({len(imagens_do_post(pasta))} slides)")
    print(f"   Tema: {dados['tema']}")
    if not NA_NUVEM:
        print("\n👀 Abrindo a prévia no navegador. Se gostar, publique com:")
        print(f"   python main.py postar {post_id}")
        abrir_previa(pasta)


def cmd_listar():
    fila = posts_na_fila()
    print(f"📥 Na fila ({len(fila)}):")
    for p in fila:
        d = ler_json(p / "post.json", {})
        print(f"   {p.name}  ·  {d.get('tema', '?')}  ·  {len(imagens_do_post(p))} slides")
    pubs = sorted(p for p in PUBLICADOS.glob("*") if p.is_dir())
    print(f"\n✅ Publicados ({len(pubs)}):")
    for p in pubs[-10:]:
        d = ler_json(p / "post.json", {})
        info = ler_json(p / "publicado.json", {})
        print(f"   {p.name}  ·  {d.get('tema', '?')}  ·  {info.get('link', '')}")


def cmd_ver(post_id):
    pasta = achar_post(post_id, padrao="recente")
    escrever_previas(pasta, ler_json(pasta / "post.json", {}))
    print(f"👀 Abrindo prévia de {pasta.name}")
    abrir_previa(pasta)


def cmd_redesenhar(post_id):
    if not post_id:
        erro("Diga qual post: python main.py redesenhar ID  (veja os IDs com 'python main.py listar')")
    pasta = achar_post(post_id)
    dados = ler_json(pasta / "post.json", None)
    if not dados:
        erro(f"O post.json de {post_id} está com erro de formatação. Confira vírgulas e aspas.")
    slides.desenhar_carrossel(dados, pasta)
    salvar_json(pasta / "post.json", dados)
    escrever_previas(pasta, dados)
    print(f"🎨 Imagens refeitas: {len(imagens_do_post(pasta))} slides")
    abrir_previa(pasta)


def cmd_trocar_foto(post_id, qual):
    if not post_id or qual is None or not qual.isdigit():
        erro("Use: python main.py trocar-foto ID N   (N: 0 = capa, 1, 2... = slides de conteúdo)")
    if not fotos.ativo():
        erro("Preencha PEXELS_API_KEY no .env para usar fotos (veja o README).")
    pasta = achar_post(post_id)
    dados = ler_json(pasta / "post.json", {})
    n = int(qual)
    if n > len(dados.get("slides", [])):
        erro(f"Este post tem só {len(dados['slides'])} slides de conteúdo (use 0 a {len(dados['slides'])}).")
    if not fotos.trocar(dados, pasta, n):
        erro("Não achei outra foto para essa busca. Edite o campo 'foto' no post.json e tente de novo.")
    slides.desenhar_carrossel(dados, pasta)
    salvar_json(pasta / "post.json", dados)
    # atualiza o crédito dos fotógrafos na legenda, preservando edições feitas à mão
    legenda = (pasta / "legenda.txt").read_text(encoding="utf-8")
    legenda = re.sub(r"📷 Fotos: .*", fotos.credito(dados), legenda)
    (pasta / "legenda.txt").write_text(legenda, encoding="utf-8")
    escrever_previas(pasta, dados)
    print(f"🔄 Foto {'da capa' if n == 0 else f'do slide {n}'} trocada.")
    abrir_previa(pasta)


def cmd_postar(post_id):
    pasta = achar_post(post_id)
    dados = ler_json(pasta / "post.json", {})
    legenda = (pasta / "legenda.txt").read_text(encoding="utf-8").strip()[:2200]
    print(f"🚀 Publicando: {pasta.name} · {dados.get('tema', '')}")

    media_id, link = instagram.publicar_carrossel(urls_publicas(pasta), legenda)
    print(f"\n✅ Publicado no Instagram! {link or media_id}")

    destino = PUBLICADOS / pasta.name
    PUBLICADOS.mkdir(exist_ok=True)
    shutil.move(str(pasta), str(destino))
    salvar_json(destino / "publicado.json", {"media_id": media_id, "link": link,
                                            "publicado_em": agora_brasilia().isoformat(timespec="minutes")})
    (destino / "preview.html").unlink(missing_ok=True)
    readme = destino / "README.md"
    if readme.exists():
        readme.write_text(readme.read_text(encoding="utf-8").replace(
            "**Status:** aguardando revisão", f"**Status:** ✅ publicado · [ver no Instagram]({link or '#'})"),
            encoding="utf-8")

    novo, dias = instagram.renovar_token()
    if novo:
        if NA_NUVEM and cfg("NOVO_TOKEN_PATH"):
            open(cfg("NOVO_TOKEN_PATH"), "w").write(novo)
            print(f"🔄 Token renovado (mais {dias} dias).")
        elif config.atualizar_env("IG_TOKEN", novo):
            print(f"🔄 Token renovado e salvo no .env (mais {dias} dias).")

    if not NA_NUVEM:
        print("\nℹ O post foi movido para publicados/. Envie a mudança pro GitHub:")
        print('   git add -A && git commit -m "publicado" && git push')


def cmd_resumo(post_id):
    """Uso interno do GitHub Actions: mostra a prévia na página da execução."""
    pasta = FILA / post_id
    dados = ler_json(pasta / "post.json", {})
    legenda = (pasta / "legenda.txt").read_text(encoding="utf-8")
    repo, sha = repositorio(), git("rev-parse", "HEAD")
    base, branch = f"https://github.com/{repo}", cfg("GITHUB_REF_NAME", "main")
    imgs = " ".join(f'<img src="https://raw.githubusercontent.com/{repo}/{sha}/fila/{post_id}/{a.name}" width="220">'
                    for a in imagens_do_post(pasta))
    texto = "\n".join([
        f"## 📸 {dados.get('tema', post_id)}", "", imgs, "", "### Legenda", "",
        *[f"> {l}" if l else ">" for l in legenda.splitlines()], "",
        "### O que fazer agora",
        "- **Gostou?** Clique em **Review deployments** no topo desta página → marque *instagram* → **Approve and deploy**.",
        f"- **Quer ajustar a legenda antes?** Edite [`fila/{post_id}/legenda.txt`]({base}/edit/{branch}/fila/{post_id}/legenda.txt), "
        "salve, e depois aprove. A versão editada é a que vai ser postada.",
        "- **Não gostou?** Clique em **Reject**. O post fica na fila; apague a pasta se não quiser mais ele.",
    ])
    with open(os.environ.get("GITHUB_STEP_SUMMARY", os.devnull), "a", encoding="utf-8") as f:
        f.write(texto + "\n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return
    cmd, alvo = args[0], (args[1] if len(args) > 1 else None)
    extra = args[2] if len(args) > 2 else None
    comandos = {
        "checar": lambda: cmd_checar(),
        "gerar": lambda: cmd_gerar(),
        "listar": lambda: cmd_listar(),
        "ver": lambda: cmd_ver(alvo),
        "redesenhar": lambda: cmd_redesenhar(alvo),
        "trocar-foto": lambda: cmd_trocar_foto(alvo, extra),
        "postar": lambda: cmd_postar(alvo),
        "resumo": lambda: cmd_resumo(alvo),
    }
    if cmd not in comandos:
        print(__doc__)
        erro(f"Comando desconhecido: {cmd}")
    comandos[cmd]()


if __name__ == "__main__":
    main()

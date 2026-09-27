# Carrossel automático no Instagram — com revisão antes de postar

Funciona como o Buffer, só que grátis:

```
 GERAR  ──►  FILA (você revisa e edita)  ──►  APROVAR  ──►  POSTA NO INSTAGRAM
 Gemini/Groq  prévia no navegador ou           1 clique       API oficial da Meta
 + slides     na página do GitHub
```

Nada vai para o Instagram sem você ver antes (a menos que você queira).

## O que tem aqui

| Arquivo | Para que serve |
|---|---|
| `main.py` | o programa: todos os comandos começam por ele |
| `.env.exemplo` | modelo do arquivo de chaves |
| `config.py` | lê o `.env` (computador) ou os Secrets (GitHub) |
| `conteudo.py` | pede o texto à IA (Gemini ou Groq) |
| `fotos.py` | busca no Pexels uma foto que combina com cada slide |
| `slides.py` | desenha as imagens: cada slide é uma quadra de vôlei vista de cima |
| `fontes/` | fontes Anton e Barlow (gratuitas, licença livre OFL). Precisam ir para o GitHub junto |
| `instagram.py` | publica o carrossel na API do Instagram |
| `fila/` | posts esperando revisão, cada um numa pasta |
| `publicados/` | posts que já foram ao ar (com o link) |
| `.github/workflows/` | automação na nuvem (gerar todo dia + postar com aprovação) |

Cada post na fila é uma pasta com: `01.jpg`, `02.jpg`… (slides), `legenda.txt` (a legenda que vai ser postada), `post.json` (textos dos slides) e `README.md` (prévia que o GitHub mostra).

---

# Parte 1 — Rodar no seu computador

### 1.1 Instalar

Precisa do **Python 3.10+** (https://python.org, no Windows marque *"Add Python to PATH"* na instalação).
Abra o terminal na pasta do projeto e rode:

```
pip install -r requirements.txt
```

### 1.2 Criar o `.env` (suas chaves)

Rode qualquer comando uma vez, por exemplo `python main.py checar`. Ele cria o arquivo `.env` a partir do `.env.exemplo`. Abra o `.env` num editor de texto e preencha:

- **GEMINI_API_KEY** e/ou **GROQ_API_KEY** → a IA que escreve os posts (basta uma; veja "Qual IA usar" abaixo)
- **IG_TOKEN** → veja "Como pegar o token do Instagram" abaixo
- **IG_USER_ID** → pode deixar vazio; o próximo passo mostra o seu
- **PEXELS_API_KEY** → fotos que combinam com cada slide (opcional, veja "Fotos" abaixo)
- **NICHO** e **PERFIL** → assunto dos posts e seu @

### 1.3 Conferir se está tudo certo (não posta nada)

```
python main.py checar
```

Ele testa as chaves de IA (fazendo uma chamada de verdade) e o token do Instagram. Se o IG_USER_ID estiver vazio, ele mostra o número certo para você colar no `.env`.

### 1.4 Gerar e revisar

```
python main.py gerar
```

Gera o carrossel, salva em `fila/` e **abre uma prévia no navegador** imitando o Instagram (dá para arrastar os slides e ler a legenda).

**Não gostou de algo?**
- **Legenda:** edite `fila/<ID>/legenda.txt`. É exatamente o que vai ser postado.
- **Texto dos slides:** edite `fila/<ID>/post.json` e rode `python main.py redesenhar <ID>`.
- **Uma foto não combinou:** `python main.py trocar-foto <ID> <N>` (0 = capa, 1, 2... = slides). Ele busca outra foto e refaz as imagens.
- **Não quer esse post:** apague a pasta dele.
- **Quer só ver de novo:** `python main.py ver`

Para testar sem gastar Gemini: `python main.py gerar --teste`

Outros comandos: `python main.py listar` mostra a fila e os publicados.

### 1.5 Postar do computador (opcional)

O Instagram precisa baixar as imagens de um link público, então o post precisa estar no GitHub primeiro (Parte 2). Depois de configurar:

```
git add -A && git commit -m "novo post" && git push
python main.py postar <ID>
```

Se você esquecer o `git push`, o programa avisa antes de tentar.

---

# Parte 2 — Subir para o GitHub

1. Crie um repositório **público** (o Instagram precisa acessar as imagens).
2. Envie os arquivos usando o **GitHub Desktop** (https://desktop.github.com) ou o `git` no terminal. Os dois respeitam o `.gitignore` e **não enviam o seu `.env`**.

> ⚠ **Cuidado com o upload pelo site** ("Add file → Upload files"): ele ignora o `.gitignore`. Se usar o site, **não selecione o arquivo `.env`**. Se ele subir sem querer, apague do repositório e **gere chaves novas** (as antigas ficaram expostas).

3. *Settings → Actions → General → Workflow permissions* → marque **Read and write permissions** → Save.

---

# Parte 3 — Chaves no GitHub

No GitHub as chaves não usam o `.env`: vão em *Settings → Secrets and variables → Actions*.

**Aba Secrets** (o mesmo conteúdo do seu `.env`):

| Nome | Valor |
|---|---|
| `GEMINI_API_KEY` | chave do Gemini (se usar) |
| `GROQ_API_KEY` | chave do Groq (se usar) |
| `PEXELS_API_KEY` | chave do Pexels (para as fotos) |
| `IG_TOKEN` | token do Instagram |
| `IG_USER_ID` | ID da conta (o `checar` mostra) |
| `GH_PAT` | opcional, veja "Token que não expira" |

**Aba Variables** (opcionais): `NICHO`, `PERFIL`, `SLIDES`, `TEMA`, `FOTOS`, com os mesmos valores do `.env`.

---

# Parte 4 — Ligar a revisão (aprovação antes de postar)

1. *Settings → Environments → New environment* → nome: **`instagram`** → Configure.
2. Marque **Required reviewers** e adicione **você mesmo**.
3. Deixe **desmarcado** o "Prevent self-review" (senão você não consegue aprovar seus próprios posts).
4. **Save protection rules**.

Sem esse passo, a automação posta direto, sem esperar aprovação. Isso serve como "modo automático", se um dia você quiser.

---

# Como fica o dia a dia

1. Todo dia às **9h** (Brasília) o GitHub gera um carrossel e coloca na fila.
2. Você recebe um **e-mail/notificação** do GitHub dizendo que há um post esperando aprovação.
3. Abra o link: a página mostra **todos os slides e a legenda**.
4. Escolha:
   - **Aprovar:** clique em **Review deployments** → marque *instagram* → **Approve and deploy**. Posta na hora.
   - **Editar antes:** a página tem um link para editar o `legenda.txt` direto no site. Salve e depois aprove.
   - **Rejeitar:** clique em **Reject**. O post fica na fila; apague a pasta se não quiser mais.

Também dá para aprovar pelo app do GitHub no celular.

**Rodar na hora:** aba *Actions* → **1. Gerar carrossel** → *Run workflow*.
**Postar algo que ficou na fila:** aba *Actions* → **2. Postar da fila** → *Run workflow* (deixe o ID vazio para o mais antigo).
**Mudar o horário:** linha `cron` em `.github/workflows/gerar.yml` (horário em UTC = Brasília + 3h).

---

## Visual dos slides

Cada slide é desenhado como uma quadra de vôlei vista de cima: a capa tem a rede com as antenas e a bola saindo pela direita (convidando a arrastar), os slides de conteúdo têm o número no estilo camisa, e o último tem a chamada e o botão "Siga".

Escolha o visual pela opção `TEMA` (no `.env` e nas Variables do GitHub):

- `quadra`: quadra coberta azul com zona livre laranja (padrão)
- `areia`: vôlei de praia, areia com linhas azuis
- `alternar`: um post de cada, para variar o feed

Para ver um post da fila com outro tema, troque o `TEMA` no `.env` e rode `python main.py redesenhar <ID>`.

## Fotos

Com a chave do Pexels, cada post ganha fotos reais que combinam com o assunto: a IA sugere uma busca para a capa e uma para cada slide, e o programa escolhe fotos que ainda não foram usadas no perfil (a lista fica em `fotos_usadas.json`).

- **Capa:** a foto ocupa a quadra e se funde com a cor do piso embaixo do título.
- **Slides de conteúdo:** a foto ocupa a parte de cima, com o número por cima.
- **Slide final:** sem foto, com a bola.

Para pegar a chave: crie uma conta em https://www.pexels.com, abra https://www.pexels.com/api/ e peça a chave (é grátis e sai na hora). Cole no `.env` como `PEXELS_API_KEY=` e, no GitHub, crie o secret `PEXELS_API_KEY`.

O Pexels pede que os fotógrafos recebam crédito quando possível, então o programa acrescenta uma linha "📷 Fotos: ..." no fim da legenda. Sem a chave (ou com `FOTOS=nao`), os slides saem só com o desenho da quadra, como antes.

## Qual IA usar

As duas são grátis e você pode preencher as duas: o programa tenta o Gemini e, se ele falhar, usa o Groq sozinho.

**Gemini** (https://aistudio.google.com/apikey): boa qualidade em português. Em 2026 o Google passou a dar chaves que começam com `AQ.`, e em algumas contas elas são recusadas com erro 401 mesmo estando certas. Se acontecer com você, tente criar a chave num **projeto novo** no AI Studio; se não resolver, use o Groq.

**Groq** (https://console.groq.com/keys): crie a conta (dá para entrar com o Google), clique em **Create API Key** e copie. Não pede cartão. O plano grátis permite centenas de pedidos por dia, muito mais do que a automação usa.

## Como pegar o token do Instagram

1. No app do Instagram: *Configurações → Tipo de conta e ferramentas → Mudar para conta profissional* (Criador de conteúdo ou Empresa).
2. Em https://developers.facebook.com → **Criar app** → escolha o caso de uso de **gerenciar mensagens e conteúdo no Instagram**.
3. No app, abra **Configuração da API com login do Instagram** (*API setup with Instagram login*).
4. Em **Gerar tokens de acesso** → **Adicionar conta** → entre com seu Instagram → copie o token.

Os nomes dos menus da Meta mudam às vezes, mas o caminho é esse. Como o app é seu, não precisa de revisão da Meta para postar na sua conta.

## Token que não expira

O token do Instagram dura 60 dias. O programa renova a cada post:
- **No computador:** salva o token novo no `.env` sozinho.
- **No GitHub:** precisa do secret `GH_PAT`. Crie em *GitHub → sua foto → Settings → Developer settings → Personal access tokens → Fine-grained tokens*, escolha só este repositório e dê a permissão **Secrets: Read and write**.

Sem o `GH_PAT`, gere um token novo na Meta a cada ~50 dias e atualize o secret.

## Se der erro

A mensagem sempre diz o que fazer, mas os mais comuns são:

- **"O Gemini recusou a chave" (401)** → veja "Qual IA usar". A mensagem mostra como a chave começa, quantos caracteres tem e de onde foi lida, para você conferir se é a chave certa.
- **HTTP 429** → acabou a cota grátis do dia; espere algumas horas (ou preencha a outra IA).
- **"O Instagram não conseguiu baixar as imagens"** → repositório privado ou faltou `git push`.
- **"Token inválido" (code 190)** → gere um token novo na Meta.
- **Erro no passo que salva no repositório** → Parte 2, item 3 (Read and write permissions).
- **Postou sem pedir aprovação** → falta a Parte 4.

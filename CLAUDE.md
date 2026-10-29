# Kit de edição de vídeo: instruções para o Claude

Este repositório é um kit de comandos de terminal para edição de vídeo no Mac. Tudo roda local
(ffmpeg, whisper.cpp, Vision do macOS, API de script do DaVinci Resolve); nenhum comando chama API paga.
O manual de uso de cada comando está em `skill/kit-edicao-video/SKILL.md`, que o instalador copia para
`~/.claude/skills/` para valer em qualquer pasta.

## Se o usuário pediu para instalar

1. Confira que é um Mac (`uname` = Darwin). Em Linux ou Windows, pare e avise: o `aroll` usa o Vision do
   macOS e o encoder de hardware da Apple.
2. Confira o espaço livre (`df -h ~`): os modelos do whisper ocupam 1,6 GB.
3. Avise o usuário antes: o instalador usa o Homebrew para instalar o que faltar (ffmpeg, whisper-cpp,
   yt-dlp, exiftool, python@3.12), baixa 1,6 GB do Hugging Face, copia LUTs para a pasta do DaVinci
   Resolve e acrescenta um bloco ao `~/.zshrc` (com backup). Leva de 5 a 15 minutos, quase tudo download.
4. Se não houver Homebrew, peça para o usuário instalar (https://brew.sh): o instalador do Homebrew pede a
   senha do Mac, então quem roda é o próprio usuário, no terminal. Se faltar o `swiftc`, peça `xcode-select --install`.
5. Rode `zsh install.sh` a partir desta pasta, em segundo plano, e acompanhe até o fim.
6. Verifique:
   - `venv/bin/pytest -q` (uns 10 s, tudo tem que passar);
   - `zsh -ic 'which aroll transcreve folha decupa'` encontra os comandos;
   - um teste real de transcrição curta:
     `say -o /tmp/kit_teste.aiff "testando o kit de edição" && zsh -ic 'transcreve /tmp/kit_teste.aiff'`
     e conferir o `.txt` gerado.
7. Diga ao usuário que abra um terminal novo (ou `source ~/.zshrc`) e mostre a tabela de comandos do
   `skill/kit-edicao-video/SKILL.md`, em uma linha por comando.

Variáveis opcionais: `KIT_VIDEO_MODELOS` muda onde ficam os modelos (padrão `~/.kit-video/modelos`);
`TRILHAS_DIR` muda a pasta do `trilha`.

## Se o usuário pediu para usar

Siga a skill `kit-edicao-video` (o mesmo `skill/kit-edicao-video/SKILL.md`). Se ela não carregou, leia o
arquivo direto.

## Se o usuário pediu para atualizar

`git pull` nesta pasta e `zsh install.sh` de novo (idempotente: não baixa o que já existe).

## Estrutura

- `bin/`: os comandos (os em Python chamam `comandos/` com o venv do kit).
- `comandos/`: `folha`, `alinha-cameras`, `sobrepoe`, `decupa`, `acha-offline` e a ligação com o Resolve.
- `src/aroll-pessoas.swift`: detector de pessoa em quadro do `aroll`, compilado pelo instalador.
- `luts/`: LUTs e DCTLs (Stadium Warm e emulações Fuji X100VI).
- `tests/`: testes automáticos (`venv/bin/pytest -q`), geram clipes sintéticos, não precisam de mídia.

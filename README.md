# kit-edicao-video

Comandos de terminal para edição de vídeo no Mac, feitos no dia a dia de edição. Tudo roda no seu
computador: nada de API paga, nada de crédito, funciona offline (menos o que baixa da internet).

| Comando | O que faz |
|---|---|
| `aroll PASTA` | separa os takes falados do B-roll e exporta cada take aparado, com nome tirado da fala |
| `transcreve ALVO` | transcreve arquivo, pasta ou link (YouTube, Instagram, TikTok...) em `.txt` e `.srt` |
| `transcreve-playlist URL` | transcreve uma playlist inteira do YouTube; pode parar e retomar |
| `trilha URL` | baixa o áudio em MP3 na qualidade máxima |
| `compila PASTA` | junta subpastas duplicadas ("SELECT", "SELECT 2", "SELECT 3") numa só |
| `folha PASTA` | folha de contato: um quadro por clipe com o nome embaixo |
| `decupa ...` | decupagem de uma pasta de clipes em planilha com miniaturas |
| `acha-offline VIDEO` | acha a tela "Media Offline" do Resolve num render antes de entregar |
| `alinha-cameras REF OUTRA` | sincroniza duas câmeras pelo áudio (e monta a trilha no Resolve) |
| `sobrepoe PASTA` | preenche os marcadores da timeline do Resolve com takes de cada pasta |

Vem junto: LUTs para o DaVinci Resolve (Stadium Warm e três emulações Fuji X100VI) e um manual com
receitas de ffmpeg já testadas (estabilização, conferência de render, limpeza de áudio).

## Instalar com o Claude Code (o jeito fácil)

Precisa de um Mac (Apple Silicon ou Intel) e do Claude Code. Cole isto no Claude:

> Clona https://github.com/leosgf-cyber/kit-edicao-video em ~/Apps/kit-edicao-video, lê o CLAUDE.md
> de lá e instala o kit seguindo as instruções.

O Claude instala as dependências, baixa o modelo de transcrição (1,6 GB) e aprende a usar cada comando.
Depois é só pedir em português: "separa os takes dessa pasta", "transcreve esse vídeo", "faz a folha de
contato do cartão", "sincroniza a câmera B com a A".

## Instalar na mão

```
git clone https://github.com/leosgf-cyber/kit-edicao-video ~/Apps/kit-edicao-video
cd ~/Apps/kit-edicao-video && zsh install.sh
```

Precisa do [Homebrew](https://brew.sh) e das ferramentas de linha de comando da Apple
(`xcode-select --install`). O DaVinci Resolve só é necessário para `alinha-cameras --resolve`, `sobrepoe` e as
LUTs; os dois comandos precisam do Resolve **Studio** (a versão grátis bloqueia script externo nas
versões recentes). As LUTs funcionam nas duas.

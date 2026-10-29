---
name: kit-edicao-video
description: Use quando o usuário pedir pra transcrever áudio ou vídeo (arquivo, pasta, link ou playlist), separar os takes falados de um bruto (A-roll x B-roll), fazer folha de contato de uma pasta de clipes, sincronizar duas câmeras pelo áudio, decupar clipes em planilha, baixar trilha em MP3, juntar pastas duplicadas ("NOME", "NOME 2"), montar sobreposições no DaVinci Resolve, conferir um render (Media Offline, preto, vídeo truncado), estabilizar, limpar áudio ruim ou aplicar as LUTs do kit. Tudo roda local no Mac, sem API paga.
---

# Kit de edição de vídeo

Comandos de terminal para Mac que rodam 100% local: ffmpeg, whisper.cpp, Vision do macOS e a API de
script do DaVinci Resolve. Nenhum chama API paga. O kit está em `__RAIZ__` e os comandos ficam em
`__RAIZ__/bin` (no PATH depois do `install.sh`).

Se um comando der "command not found", rode com o caminho inteiro (`__RAIZ__/bin/<comando>`) ou
reinstale com `zsh __RAIZ__/install.sh` (idempotente).

## Regras de uso

- **Nada apaga mídia.** Os comandos gravam a saída numa subpasta ao lado (`_AROLL/`, `_DECUPA/`,
  `_folha.jpg`). Não apague nem mova arquivo do usuário sem ele pedir. A exceção é o `compila`, que
  move arquivos de propósito: mostre o que vai ser fundido antes de rodar.
- **Cartão de memória:** se a pasta está em `/Volumes/...` (cartão da câmera), avise antes. `aroll` e
  `decupa` gravam a saída dentro da pasta apontada. O melhor é copiar pro disco antes.
- **Máquina leve:** vídeo 4K em lote, no máximo 2 a 4 ffmpeg ao mesmo tempo, com `-threads 2` e `scale`
  antes de qualquer `lut3d`. 36 ffmpeg de 4K em paralelo já travaram um Mac de 16 GB.
- **Processo longo:** transcrição e `aroll` em pasta grande levam minutos ou horas. Rode em segundo plano
  e diga ao usuário quanto deve demorar (o whisper anda a uns 10x o tempo real num M1/M2/M3).
- **Confira no olho antes de dizer que ficou bom.** Relatório automático erra; folha de contato e
  quadro extraído mostram o que aconteceu.

## Os comandos

| Comando | Para quê | Precisa do Resolve? |
|---|---|---|
| `aroll PASTA` | separa os takes falados (A-roll) do B-roll e exporta cada take aparado | não |
| `transcreve [ALVO]` | transcreve arquivo, pasta ou link (YouTube, Instagram, TikTok...) | não |
| `transcreve-playlist URL` | transcreve uma playlist inteira do YouTube, com retomada | não |
| `trilha URL` | baixa o áudio em MP3 pra `~/Music/TRILHAS` | não |
| `compila [PASTA]` | funde subpastas duplicadas (`SELECT`, `SELECT 2`...) | não |
| `folha PASTA` | folha de contato: um quadro por clipe com o nome embaixo | não |
| `decupa ...` | decupagem de uma pasta de clipes em planilha xlsx | não |
| `acha-offline VIDEO` | varre um render atrás da tela "Media Offline" do Resolve | não |
| `alinha-cameras REF OUTRA` | mede pelo áudio o deslocamento de relógio entre duas câmeras | só com `--resolve` |
| `sobrepoe PASTA` | monta a trilha de sobreposições na timeline pelos marcadores | sim |

### aroll

```
aroll PASTA                 processa e exporta
aroll PASTA --seco          só analisa e imprime, não corta
aroll PASTA --aparar        um take por arquivo: só apara início e fim
aroll PASTA --so-audio      não olha a imagem (aceita fala fora de quadro)
aroll PASTA --refaz         reprocessa o que já tem saída
aroll PASTA --idioma en     idioma da transcrição (padrão pt)
```

Varre a pasta e as subpastas. Detecta voz com o VAD Silero dentro do whisper.cpp, transcreve, e abre um
take num gatilho ("rodando", "gravando", "ação", "valendo") e fecha numa pausa longa, no próximo gatilho
ou numa palavra de erro ("corta", "de novo", "errei", palavrão). Cada take sai aparado com 1 s de margem
em `PASTA/_AROLL/`, nome `<clipe>_takeNN_<6 primeiras palavras>.mp4`; take com erro leva `_ERRO`.
O resumo fica em `_AROLL/relatorio.md`. Saída em H.264 por hardware, resolução preservada, rotação já
aplicada (vertical sai em pé).

Filtros anti-alucinação: o whisper inventa "Obrigado." ou "E aí" em cima de barulho com confiança alta.
O que separa fala real de ruído é a densidade (caracteres por segundo de áudio): fala real dá 10 a 25,
alucinação fica abaixo de 3.

Armadilhas:
- Calibrado para talking head em plano fechado (pessoa ocupando 0,5 do quadro ou mais). Entrevista em
  plano aberto (pessoa a 0,13 do quadro) cai TODA em "B-roll (fala fora de quadro)". Sinal: relatório
  com "maior pessoa: 0.1x" em clipes longos com fala. Conserto: pôr só os clipes da entrevista numa pasta
  (hard link com `ln`, zero espaço) e rodar `aroll <pasta> --so-audio`. Na pasta inteira, `--so-audio`
  exportaria também a direção falando atrás da câmera.
- O whisper às vezes perde um clipe inteiro ("nenhum recorte chega a 5s") mesmo com áudio bom. Medir com
  `ffmpeg -i X -af volumedetect -f null -`; se o volume está normal, transcrever direto com
  `whisper-cli -ml 60 -osrt` e cortar à mão.
- Gatilhos, palavras de erro e limiares estão no topo de `__RAIZ__/bin/aroll`, em português. Para outro
  idioma ou outro jeito de dirigir, ajuste ali.
- Antes de entregar, rode `folha PASTA/_AROLL` e olhe.

### transcreve

```
transcreve                         áudio mais recente do ~/Downloads
transcreve arquivo.m4a             um arquivo (áudio ou vídeo)
transcreve arquivo.m4a en          outro idioma (padrão pt)
transcreve "https://..."           baixa só o áudio (yt-dlp), transcreve e apaga o download
transcreve PASTA                   todos os áudios da pasta (.opus .m4a .mp3 .ogg .wav .aac, sem subpastas)
transcreve PASTA apos 2026-07-20   só os modificados depois da data (aceita "2026-07-20 14:30")
```

Sai `.txt` (texto corrido) e `.srt` (com tempos) em `~/Documents/Transcrições/MM-AA/VIDEO` ou `.../AUDIO`.
Usa os cookies do Chrome no yt-dlp (o YouTube exige; sem eles dá 403).

Armadilhas do whisper (valem para todos os comandos que transcrevem):
- **Música:** entra em loop e repete a mesma frase centenas de vezes, engolindo a fala. Refazer o trecho
  com `-mc 0` (desliga o contexto) e emendar somando o deslocamento.
- **Silêncio longo:** inventa créditos de legenda ("Legenda por Fulano", "Inscreva-se"). Cortar o silêncio
  antes ou descartar esses blocos.
- **Material bilíngue:** `-l auto` erra (um take de 37 s em inglês virou "Hello. Hello. Hello."). Forçar o
  idioma certo.

### transcreve-playlist

`transcreve-playlist "URL" [idioma] [quantos]`. Baixa um áudio, transcreve, apaga, vai pro próximo (não
enche o disco). Pode parar com Ctrl-C e rodar de novo: `_feitos.txt` guarda o que já foi, `_falhas.txt` o
que deu errado. Idioma padrão `auto`. Segura o Mac acordado sozinho. Saída em
`~/Documents/Transcrições/PLAYLISTS/<playlist>/NNN - título.txt` (+ `.srt`).

### trilha

`trilha "URL"`: MP3 na qualidade máxima em `~/Music/TRILHAS` (a variável `TRILHAS_DIR` muda a pasta).

### compila

`compila [PASTA]` (sem argumento, a pasta atual; caminho com espaço vai entre aspas). Acha grupos de
subpastas que só diferem pelo número no fim (`SELECT`, `SELECT 2`, `SELECT 3`) e funde tudo na de nome
base, mantendo a estrutura interna. Subpasta com o mesmo nome da raiz funde na raiz. Duplicata idêntica
(conferida byte a byte) é descartada; mesmo nome com conteúdo diferente vira `nome 2.ext`. **Move
arquivos:** mostre ao usuário a lista de grupos (`ls`) antes de rodar.

### folha

`folha PASTA [--saida X.jpg] [--quadros N]`: grava `PASTA/_folha.jpg`, um quadro por clipe (a 40% da
duração), nome embaixo, 8 colunas. `--quadros 3` tira 3 quadros espalhados por clipe com o tempo no
rótulo. NEV (RAW da Nikon) usa o proxy `.MP4` irmão; sem ele, cartão cinza "sem prévia".

Folha serve para conferir enquadramento, continuidade e o que tem em cada clipe. **Não serve para julgar
qualidade de imagem** (a redução esconde defeito e o JPEG inventa borrão).

### decupa

Decupagem de uma pasta de clipes numa planilha. Os passos 1, 2 e 4 são locais; o passo 3 é você.

1. `decupa preparar PASTA [--lut auto|slog3|nenhuma|X.cube] [--paralelo 2] [--idioma pt] [--sem-fala]`:
   metadados, quadros (em `_DECUPA/frames`), uma folha por clipe, áudio e transcrição. Idempotente.
   `--lut auto` aplica a LUT S-Log3 da Sony quando o metadado diz; cópia exportada pelo Finder perde o
   metadado, aí use `--lut slog3`.
2. `decupa situacao PASTA [--lote 20]`: quantos preparados, transcritos e descritos; separa os sem
   descrição em `_DECUPA/lotes.json`.
3. **Descrição (você):** rode `decupa campos` e siga. Para cada clipe do lote, olhe a folha, leia o
   metadado e a transcrição e grave `_DECUPA/descricoes/<clipe>.json`. Este é o único passo que gasta
   token da sessão. Se o usuário quiser zero token, pule: a planilha sai com metadados e fala.
4. `decupa planilha PASTA [--titulo T] [--origem "câmera, de onde veio"] [--saida X.xlsx]`: xlsx com
   miniatura e abas Decupagem, Por grupo, Para olhar e Como ler. `--drive-pasta ID` põe link por clipe e
   sobe a planilha como Google Sheet; precisa de um remote do rclone chamado `gdrive`.

### acha-offline

`acha-offline VIDEO`: lê o vídeo inteiro quadro a quadro e lista os trechos com a tela vinho de "Media
Offline" do Resolve. Rode em **todo** render antes de entregar, inclusive na reexportação de uma correção
pequena, junto com a busca de preto:

```
ffmpeg -i VIDEO -vf "blackdetect=d=0.04:pix_th=0.10" -an -f null - 2>&1 | grep blackdetect
```

Quadro de amostra espalhado não basta: o defeito costuma estar no crédito ou no título herdado de uma
timeline antiga, justamente onde ninguém olha.

### alinha-cameras

`alinha-cameras PASTA_REF PASTA_OUTRA [--resolve]`. Mede pelo áudio quanto o relógio da outra câmera está
deslocado da referência (a câmera que está na V1). Grava `ALINHAMENTO_<outra>.md` e
`alinhamento_<outra>.json` na pasta da outra. Com `--resolve` e o Resolve aberto na timeline, cria a
trilha `<outra> (sync)` desligada, com cada clipe da outra câmera sobre o momento exato do clipe da V1.
Clipe laranja = encaixado só pelo relógio (até ±0,5 s): conferir no olho.

### sobrepoe

`sobrepoe PASTA [--take 2.5]`. A pasta tem uma subpasta por rubrica. Espelha as subpastas como bins e lê
os marcadores com duração da timeline corrente: o nome do marcador é o começo do nome da subpasta ("03"
casa com "03 ATO II - ..."). Enche cada marcador com takes colados de 2,5 s na trilha `SOBREPOSIÇÕES`,
desligada. Rodar de novo refaz. Marcador sem duração ou sem subpasta é ignorado.

## DaVinci Resolve

Para `alinha-cameras --resolve`, `sobrepoe` e qualquer script na API:

- O Resolve tem que estar **aberto no projeto e na timeline certos antes** de rodar, sem nenhum popup na
  tela. O comando não abre nada. Não mexer no Resolve enquanto roda.
- Precisa do Resolve **Studio**: a versão grátis bloqueia script externo nas versões recentes.
- Preferences > System > General > "External scripting using" = **Local** (sem isso a API não conecta).
- A API só funciona com Python 3.12 ou anterior (no 3.14 a escrita volta `None`). O venv do kit já é 3.12.
- `GetCurrentPage()` devolvendo `None` = interface travada por um diálogo; toda escrita falha calada.
- `GetCurrentProject()` pode ser outro projeto ("X (1)", "X (Copy)"): confira o `.GetName()`.
- `dvr.scriptapp("Resolve")` às vezes volta `None` por um instante: tente de novo em laço.
- Na página Deliver, `SetTrackEnable` responde True sem fazer nada: `resolve.OpenPage("edit")` antes.
- Salvar é `ProjectManager.SaveProject()` (o `Project.SaveProject` vem `None` no 21).
- `GetEndFrame()` e o `endFrame` do `AppendToTimeline` são **exclusivos** (duração = fim - início).
  Tratar como inclusivo deixa 1 quadro preto entre os clipes.
- `MediaPool.DeleteClips([item])` num item que é timeline **apaga a timeline**, sem lixeira. Antes de
  limpar bin em lote, exporte as timelines (`tl.Export(caminho, resolve.EXPORT_DRT)`) e filtre por
  `GetClipProperty("Type") != "Timeline"`.
- Religar mídia offline: `MediaPoolItem.ReplaceClip(caminho_absoluto)` funciona; `RelinkClips(pasta)` só
  casa por nome idêntico.
- Importar `11.png ... 15.png` vira uma sequência só: renomeie com nomes não numéricos antes.

Para o Claude editar no Resolve por linguagem natural (cortar, aplicar LUT, exportar) existe um MCP de
código aberto: https://github.com/samuelgursky/davinci-resolve-mcp. Não vem no kit; instale só se o
usuário pedir.

## LUTs

O `install.sh` copia para a pasta de LUT do Resolve (aparecem depois de reabrir, ou em Project Settings >
Color Management > Update Lists). Cada uma vem em `.cube` (universal, serve em qualquer programa) e
`.dctl` (no Resolve via ResolveFX DCTL, com controle de intensidade). Originais em `__RAIZ__/luts`.

- `Stadium Warm/Sony_AdobeRGB_StadiumWarm`: material Sony neutro para um look de esporte no sol: altas
  âmbar, sombras petróleo, pretos levantados e azulados, vermelho e azul saturados, verde contido.
- `Fuji X100VI/`: emulações de filme. Classic Negative (sombra azul-esverdeada, âmbar, vermelho tijolo,
  verde oliva), Classic Chrome (documental, dessaturado, plano) e Nostalgic Neg (anos 70: âmbar forte,
  preto leitoso, quente). Para material já em Rec.709.

## Receitas que já foram testadas

### Conferir um vídeo antes de dizer que está bom

- Quadro de amostra **nunca** com `-ss` antes do `-i`: isso pula pro keyframe, que é sempre limpo, mesmo
  num arquivo destruído. Decodifique em sequência:
  `ffmpeg -i X -vf "select='eq(n\,24)+eq(n\,120)'" -vsync 0 q_%d.png`
- Para julgar nitidez e artefato: recorte 1:1 em PNG, sem escala, num pedaço com detalhe fino:
  `-vf "select='eq(n\,N)',crop=1280:720:1200:600"`.
- Para saber se o defeito é do filtro ou do codificador, renderize em ProRes (`-c:v prores_ks -profile:v 3`):
  se aparece no ProRes, o codificador é inocente.
- **Duração:** `format=duration` devolve o MAIOR stream. Um MP4 com áudio inteiro e imagem pela metade
  parece íntegro. Meça `ffprobe -select_streams v:0 -show_entries stream=duration`.
- `-ss` além do fim da fonte não dá erro: sai código 0 e um arquivo vazio (WAV de 78 bytes, MP4 de 262
  bytes com `-shortest`). Confira antes que a fonte alcança o trecho pedido.
- Leia sempre a última linha do ffmpeg: `drop=` alto denuncia timestamp desalinhado mesmo com código 0.

### Vídeo de celular e rotação

Celular em pé grava os pixels deitados (3840x2160) com `rotation=-90` no metadado; o `ffprobe` mostra os
números crus. O ffmpeg já gira na entrada, então tamanho fixo em filtro (`scale=`, `pad=`, `zoompan=s=`)
usa a orientação JÁ girada. Conferir: `ffprobe -v error -select_streams v:0 -show_entries stream_side_data_list X`.
O Google Drive ignora a rotação por metadado e também não toca HEVC; cópia de aprovação vai em H.264:
`ffmpeg -i in.mp4 -c:v libx264 -crf 19 -preset medium -pix_fmt yuv420p -c:a copy -movflags +faststart out.mp4`

### Estabilização (ffmpeg com vidstab, local)

Antes de escolher o modo, compare o primeiro e o último quadro do original: se o enquadramento muda sozinho,
o take tem movimento.

- **Take parado (tripé virtual):**
  passada 1 `vidstabdetect=shakiness=8:accuracy=15:stepsize=6:mincontrast=0.3:tripod=1:fileformat=ascii:result=X.trf`
  passada 2 `vidstabtransform=input=X.trf:tripod=1:smoothing=0:optzoom=1:interpol=bicubic:crop=black,unsharp=5:5:0.8:3:3:0.4`
- **Take com movimento:** detecção SEM `tripod` e `smoothing=30` na transformação. `tripod=1` em take
  que anda rasga a imagem e piora ao longo do clipe.
- **Rápido (1080p):** `accuracy=9:stepsize=12` na detecção, `smoothing=12:optzoom=1` na transformação.
- Sempre `fileformat=ascii` (o `.trf` binário quebra a passada 2 com `Cannot parse localmotion!`).
- A detecção usa uma thread só (4K: ~3,5 s por quadro). Vários clipes: um processo por clipe em paralelo.
- Guarde o `.trf`: com ele, refazer só a passada 2 com outro parâmetro é de graça.
- Celular vem em faixa cheia (`yuvj420p`): na passada 2 passe
  `-color_range pc -colorspace bt709 -color_primaries bt709 -color_trc bt709` e `-map 0:v:0 -map 0:a:0`.
- Saída: `-c:v hevc_videotoolbox -b:v 40M -tag:v hvc1 -c:a copy` (hardware do Mac).

### Comparativo lado a lado (antes e depois)

Corte dentro do filtro e zere o relógio dos dois lados; nunca `-ss` como opção de entrada num lado só
(o `hstack` descarta quadros e sai derretido):
```
[0:v]trim=start=2:end=10,setpts=PTS-STARTPTS,fps=24,scale=960:-2[a];
[1:v]setpts=PTS-STARTPTS,fps=24,scale=960:-2[b];[a][b]hstack=inputs=2[v]
```
Bitrate de 25M. Para medir tremor, os dois lados precisam passar pela mesma cadeia de filtros (o `unsharp`
infla a diferença entre quadros). Na dúvida, entregue o lado a lado e deixe o olho decidir.

### Áudio ruim

Ordem de eficácia medida em gravação real (folga de ruído, maior é melhor): bruto 12,8 dB; `afftdn` 15,2 dB
(fraco, não perca tempo); **`arnndn` 22,6 dB**, a melhor opção de graça, sem empastar a voz:
```
curl -sL -o sh.rnnn https://raw.githubusercontent.com/GregorR/rnnoise-models/master/somnolent-hogwash-2018-09-01/sh.rnnn
ffmpeg -i in.wav -af "arnndn=m=sh.rnnn" out.wav
```
Separar voz e música (stems): Demucs, local e grátis (`pip install demucs` num venv Python 3.12):
`python -m demucs -n htdemucs_ft -d mps -o SAIDA arquivo` sai `vocals/drums/bass/other.wav`;
`--two-stems vocals` dá só voz e instrumental.

### Câmera com áudio 32-bit float (Nikon ZR e outras)

Pico acima de 0 dBFS fica intacto no arquivo, mas render com áudio 24-bit inteiro vira platô (ceifado).
Diagnóstico: extrair com `-f f32le` e medir o pico; acima de 1,0 sem valores exatos em ±1,0 é float limpo.
Conserto: aplicar o ganho (-40 a -50 dB) ainda em float e só então gravar em 24-bit.

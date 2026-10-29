#!/bin/zsh
# Instala o kit: dependências do Homebrew, modelos do whisper (1,6 GB, uma vez), venv,
# detector de pessoas do aroll, LUTs no Resolve, skill do Claude Code e bin/ no PATH
# (bloco marcado no ~/.zshrc, com backup). Idempotente: rodar de novo só completa o que falta.
set -e
RAIZ="$(cd "$(dirname "$0")" && pwd)"
MODELOS="${KIT_VIDEO_MODELOS:-$HOME/.kit-video/modelos}"
LUT_RESOLVE="/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT"

[[ "$(uname)" == Darwin ]] || { echo "erro: o kit é só pra macOS"; exit 1; }

# 1. dependências (comando -> pacote do brew)
typeset -A PACOTE=(ffmpeg ffmpeg whisper-cli whisper-cpp yt-dlp yt-dlp exiftool exiftool python3.12 python@3.12)
falta=()
for cmd pac in ${(kv)PACOTE}; do command -v $cmd >/dev/null || falta+=($pac); done
if (( ${#falta} )); then
  command -v brew >/dev/null || { echo "erro: falta o Homebrew (https://brew.sh) para instalar: ${falta[*]}"; exit 1; }
  echo "instalando com o brew: ${falta[*]}"
  brew install ${falta[@]}
fi
command -v swiftc >/dev/null || { echo "erro: falta o swiftc (xcode-select --install)"; exit 1; }

# 2. modelos do whisper (transcrição e detecção de voz)
mkdir -p "$MODELOS"
baixa() {  # baixa $1 de $2 e confere o tamanho $3
  local alvo="$MODELOS/$1"
  if [[ -f "$alvo" && $(stat -f %z "$alvo") == $3 ]]; then echo "modelo ok: $1"; return; fi
  echo "baixando $1..."
  curl -fL -C - --retry 3 -o "$alvo" "$2"
  [[ $(stat -f %z "$alvo") == $3 ]] || { echo "erro: $1 veio com tamanho errado, rode de novo"; exit 1; }
}
baixa ggml-large-v3-turbo.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin 1624555275
baixa ggml-silero-v5.1.2.bin https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v5.1.2.bin 885098

# 3. venv dos comandos em Python (3.12: a API de script do Resolve não funciona no 3.14)
PY="$(command -v python3.12)"
[[ -d "$RAIZ/venv" ]] || "$PY" -m venv "$RAIZ/venv"
"$RAIZ/venv/bin/pip" install -q -r "$RAIZ/requirements.txt"

# 4. detector de pessoa em quadro do aroll (Vision do macOS)
swiftc -O -o "$RAIZ/bin/aroll-pessoas" "$RAIZ/src/aroll-pessoas.swift"

# 5. LUTs: as do kit vão pro Resolve; a S-Log3 da Sony (vem com o Resolve) vem pro decupa
if [[ -d "$LUT_RESOLVE" ]]; then
  if cp -R "$RAIZ/luts/"* "$LUT_RESOLVE/" 2>/dev/null; then
    echo "LUTs copiadas pro Resolve (aparecem depois de reabrir o Resolve ou de Project Settings > Color Management > Update Lists)"
  else
    echo "aviso: sem permissão na pasta de LUT do Resolve; copie à mão: sudo cp -R \"$RAIZ/luts/\"* \"$LUT_RESOLVE/\""
  fi
  SONY="$LUT_RESOLVE/Sony/SLog3SGamut3.CineToLC-709TypeA.cube"
  [[ -f "$SONY" ]] && cp "$SONY" "$RAIZ/comandos/luts/slog3_709.cube"
else
  echo "aviso: DaVinci Resolve não encontrado; LUTs ficam em $RAIZ/luts e o decupa roda sem a LUT S-Log3"
fi

# 6. skill do Claude Code (ensina o Claude a usar o kit em qualquer pasta)
mkdir -p "$HOME/.claude/skills/kit-edicao-video"
sed "s#__RAIZ__#$RAIZ#g" "$RAIZ/skill/kit-edicao-video/SKILL.md" > "$HOME/.claude/skills/kit-edicao-video/SKILL.md"

# 7. PATH no ~/.zshrc
ZRC="$HOME/.zshrc"; touch "$ZRC"; cp "$ZRC" "$ZRC.bak-$(date +%Y%m%d-%H%M%S)"
sed -i '' '/# kit-edicao-video inicio/,/# kit-edicao-video fim/d' "$ZRC"
cat >> "$ZRC" <<BLOCO
# kit-edicao-video inicio
export PATH="$RAIZ/bin:\$PATH"
export KIT_VIDEO_MODELOS="$MODELOS"
# kit-edicao-video fim
BLOCO

echo
echo "pronto. Comandos: aroll, transcreve, transcreve-playlist, trilha, compila, folha, alinha-cameras, sobrepoe, decupa, acha-offline."
echo "Abra um terminal novo (ou: source ~/.zshrc)."

"""Leitura de mídia com ffprobe/ffmpeg: lista de clipes, metadados, um quadro, áudio mono. Sem Resolve."""
import io, json, os, re, subprocess
from datetime import datetime, timezone
from PIL import Image

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mts", ".mxf", ".avi", ".nev"}

def chave_natural(nome):
    """'c10' depois de 'c2'."""
    return [int(t) if t.isdigit() else t.casefold() for t in re.split(r"(\d+)", nome)]

def stem(caminho):
    return os.path.splitext(os.path.basename(caminho))[0]

def listar_clipes(pasta):
    nomes = [n for n in os.listdir(pasta) if not n.startswith(".") and os.path.splitext(n)[1].lower() in VIDEO_EXTS
              and os.path.isfile(os.path.join(pasta, n))]
    return [os.path.join(pasta, n) for n in sorted(nomes, key=chave_natural)]

def _creation_time_utc(ct):
    """Converte a string creation_time do ffprobe (ISO 8601) em segundos UTC, ou None se ausente/invalida.
    Sem fuso na string, assume UTC (nao hora local)."""
    if not ct:
        return None
    try:
        dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).timestamp()

def probe(caminho):
    """dict(caminho, nome, dur, inicio, fps, tem_audio) ou None se o ffprobe não lê.
    inicio = creation_time do contêiner em segundos UTC, ou None se não existe (sem fuso na tag, assume UTC).
    fps = None se o clipe não tem faixa de vídeo com r_frame_rate legível."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration:format_tags=creation_time:stream=codec_type,r_frame_rate",
                            "-of", "json", caminho], capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0:
        return None
    d = json.loads(r.stdout or "{}"); fmt = d.get("format", {}); streams = d.get("streams", [])
    try:
        dur = float(fmt["duration"])
    except (KeyError, ValueError):
        return None
    inicio = _creation_time_utc((fmt.get("tags") or {}).get("creation_time"))
    fps = None
    for s in streams:
        if s.get("codec_type") == "video" and s.get("r_frame_rate") not in (None, "0/0"):
            try:
                num, den = s["r_frame_rate"].split("/"); fps = float(num) / float(den)
            except (ValueError, ZeroDivisionError):
                fps = None
            break
    return {"caminho": caminho, "nome": stem(caminho), "dur": dur, "inicio": inicio, "fps": fps,
            "tem_audio": any(s.get("codec_type") == "audio" for s in streams)}

def irmao_mp4(caminho):
    """Arquivo .mp4 (qualquer caixa) com o mesmo nome na mesma pasta, ou None."""
    pasta, nome = os.path.split(caminho); base = os.path.splitext(nome)[0]
    try:
        nomes = os.listdir(pasta or ".")
    except OSError:
        return None
    for n in nomes:
        if n != nome and os.path.splitext(n)[0] == base and os.path.splitext(n)[1].lower() == ".mp4":
            return os.path.join(pasta, n)
    return None

def _frame(caminho, t):
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", caminho, "-frames:v", "1",
                            "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1"], capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0 or not r.stdout:
        return None
    try:
        return Image.open(io.BytesIO(r.stdout)).convert("RGB")
    except Exception:
        return None

def _quadro_de(alvo, fracao):
    """Imagem RGB de um quadro de `alvo` a `fracao` da duração, ou None se `alvo` for None ou não abrir."""
    if not alvo:
        return None
    info = probe(alvo)
    if not info:
        return None
    t = min(max(0.2, info["dur"] * fracao), max(0.0, info["dur"] - 2.5 / (info["fps"] or 25)))
    return _frame(alvo, t)

def quadro(caminho, fracao=0.4):
    """Imagem RGB de um quadro a `fracao` da duração. Se o clipe não abre (NEV), tenta o irmão .mp4. None se nada abre.
    A imagem já vem auto-rotacionada pelo ffmpeg (um clipe 3840x2160 com rotation=90 sai 2160x3840); quem desenha
    deve usar `img.size`, não presumir a orientação original."""
    img = _quadro_de(caminho, fracao)
    if img:
        return img
    return _quadro_de(irmao_mp4(caminho), fracao)

def tempos(dur, n):
    """n instantes espalhados pelo clipe, no meio de cada fatia (nunca 0 nem o fim exato)."""
    return [round((i + 0.5) * dur / n, 2) for i in range(n)]

def quadros(caminho, n):
    """[(t, imagem RGB ou None)] com n quadros espalhados pelo clipe, um ffprobe só.
    Se o clipe não abre (NEV), usa o irmão .mp4. Lista vazia se nada abre."""
    for alvo in (caminho, irmao_mp4(caminho)):
        info = probe(alvo) if alvo else None
        if info:
            return [(t, _frame(alvo, t)) for t in tempos(info["dur"], n)]
    return []

def audio_wav(caminho, destino, sr=8000):
    """Extrai áudio mono pcm_s16le a `sr` Hz. Devolve o destino ou None."""
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", caminho, "-vn", "-ac", "1", "-ar", str(sr),
                            "-c:a", "pcm_s16le", destino], capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None
    return destino if r.returncode == 0 and os.path.exists(destino) else None

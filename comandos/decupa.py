"""decupa: decupagem de uma pasta de clipes. Os passos 1, 2 e 4 não usam IA.

  1. decupa preparar PASTA   metadados, quadros, folha por clipe, áudio e transcrição em PASTA/_DECUPA
  2. decupa situacao PASTA   o que falta; separa os clipes sem descrição em lotes (_DECUPA/lotes.json)
  3. (IA) descreve cada clipe em _DECUPA/descricoes/<clipe>.json, campos em `decupa campos`
  4. decupa planilha PASTA   xlsx com miniatura, 1 linha por clipe; --drive-pasta ID sobe como Google Sheet

"""
import argparse, json, math, os, re, subprocess, sys, time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from . import midia

AQUI = os.path.dirname(os.path.abspath(__file__))
LUT_SLOG3 = os.path.join(AQUI, "luts", "slog3_709.cube")   # Sony S-Log3/SGamut3.Cine -> Rec709 (o install.sh copia do Resolve)
CAMPOS = os.path.join(AQUI, "decupa_campos.md")
MODELOS = os.environ.get("KIT_VIDEO_MODELOS", os.path.expanduser("~/.kit-video/modelos"))
WHISPER_MODELO = os.path.join(MODELOS, "ggml-large-v3-turbo.bin")
WHISPER_VAD = os.path.join(MODELOS, "ggml-silero-v5.1.2.bin")
SUBPASTAS = ("meta", "frames", "folhas", "audio", "transcr", "descricoes")
FONTE = "/System/Library/Fonts/Helvetica.ttc"
MAX_PARALELO = 4      # 26/10: 36 ffmpeg de 4K travaram o Mac de 16 GB; o padrão é 2
FFMPEG_LEVE = ["-threads", "2", "-filter_threads", "1"]


def pasta_decupa(pasta):
    return os.path.join(pasta, "_DECUPA")


def n_quadros(dur):
    """~1 quadro a cada 2,5 s, entre 6 e 18."""
    return min(18, max(6, math.ceil(dur / 2.5)))


def mmss(t):
    t = float(t)
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def run(cmd, timeout=900):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 1, "", "tempo esgotado")


def clipes_da_pasta(pasta):
    """Clipes de vídeo em ordem natural. NEV com proxy .MP4 irmão fica de fora (o proxy já está na lista)."""
    return [c for c in midia.listar_clipes(pasta)
            if not (c.lower().endswith(".nev") and midia.irmao_mp4(c))]


# ---------- passo 1: preparar ----------

def montar_meta(caminho, probe, exif):
    """Metadados do clipe a partir do JSON do ffprobe e do exiftool (-G1 -n). Sem efeito colateral."""
    v = next(s for s in probe["streams"] if s.get("codec_type") == "video")
    a = next((s for s in probe["streams"] if s.get("codec_type") == "audio"), None)
    dur = float(v.get("duration") or probe["format"]["duration"])
    rot = 0
    for sd in v.get("side_data_list", []):
        if "rotation" in sd:
            rot = int(sd["rotation"])
    w, h = int(v["width"]), int(v["height"])
    if abs(rot) == 90:
        w, h = h, w
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))

    def ex(*chaves):
        for k in chaves:
            for kk, vv in exif.items():
                if kk.split(":")[-1] == k:
                    return vv
        return None

    return {
        "clipe": midia.stem(caminho), "arquivo": caminho, "tamanho_bytes": os.path.getsize(caminho),
        "duracao_s": round(dur, 3), "largura": w, "altura": h,
        "orientacao": "vertical" if h > w else "horizontal", "rotacao_meta": rot,
        "fps": round(num / den, 3) if den else None, "codec": v.get("codec_name"), "perfil": v.get("profile"),
        "bitrate_mbps": round(int(probe["format"].get("bit_rate", 0)) / 1e6, 1),
        "creation_time_utc": probe["format"].get("tags", {}).get("creation_time"),
        "data_local": ex("CreationDateValue", "DateTimeOriginal"),
        "timecode": next((s.get("tags", {}).get("timecode") for s in probe["streams"]
                          if s.get("tags", {}).get("timecode")), None),
        "camera": ex("DeviceModelName", "Model"), "lente": ex("LensModelName", "LensModel"),
        "gamma": ex("AcquisitionRecordGroupItemValue"),
        "audio_canais": a.get("channels") if a else 0,
    }


def filtro_video(meta, lut):
    """-vf dos quadros: scale ANTES da LUT (metade da memória). lut = auto | nenhuma | slog3 | caminho .cube."""
    vf = "scale='if(gt(iw,ih),1280,-2)':'if(gt(iw,ih),-2,1280)'"
    arq = None
    if lut == "slog3" or (lut == "auto" and "log3" in str(meta.get("gamma") or "").lower()):
        arq = LUT_SLOG3
    elif lut not in ("auto", "nenhuma", "slog3"):
        arq = lut
    if arq == LUT_SLOG3 and not os.path.exists(arq):   # só existe se o install.sh achou o Resolve
        print(f"aviso: LUT S-Log3 não encontrada ({arq}), quadros sem LUT", file=sys.stderr); arq = None
    return vf + (f",lut3d='{arq}'" if arq else "")


def folha_do_clipe(nome, tempos, arquivos, orientacao, saida):
    """Folha de contato de UM clipe: quadros com 'nome mm:ss' embaixo; 6 colunas se vertical, 4 se deitado."""
    cols = 6 if orientacao == "vertical" else 4
    tam = (315, 560) if orientacao == "vertical" else (480, 270)
    try:
        fonte = ImageFont.truetype(FONTE, 20)
    except OSError:
        fonte = ImageFont.load_default(size=20)
    faixa, gap = 28, 3
    linhas = math.ceil(len(arquivos) / cols)
    f = Image.new("RGB", (cols * (tam[0] + gap) + gap, linhas * (tam[1] + faixa + gap) + gap), (34, 34, 34))
    d = ImageDraw.Draw(f)
    for i, (t, arq) in enumerate(zip(tempos, arquivos)):
        x = gap + (i % cols) * (tam[0] + gap)
        y = gap + (i // cols) * (tam[1] + faixa + gap)
        if os.path.exists(arq):
            im = Image.open(arq).convert("RGB")
            im.thumbnail(tam)
            f.paste(im, (x + (tam[0] - im.width) // 2, y + (tam[1] - im.height) // 2))
        d.text((x + tam[0] // 2, y + tam[1] + faixa // 2), f"{nome}  {mmss(t)}", fill="white", font=fonte, anchor="mm")
    f.save(saida, "JPEG", quality=85)


def preparar_um(caminho, dec, lut):
    """Um clipe: meta, quadros, folha e áudio. Idempotente (meta/<clipe>.json é gravado por último).
    Devolve (nome, 'ok' | 'pulado' | 'erro: ...')."""
    nome = midia.stem(caminho)
    meta_path = os.path.join(dec, "meta", f"{nome}.json")
    if os.path.exists(meta_path):
        return nome, "pulado"
    r = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", caminho], 120)
    try:
        probe = json.loads(r.stdout)
        exif_r = run(["exiftool", "-j", "-G1", "-n", caminho], 120)
        exif = json.loads(exif_r.stdout)[0] if exif_r.returncode == 0 and exif_r.stdout.strip() else {}
        meta = montar_meta(caminho, probe, exif)
    except (ValueError, KeyError, StopIteration, IndexError) as e:
        return nome, f"erro: ffprobe não leu ({type(e).__name__})"

    meta["tempos_quadros"] = midia.tempos(meta["duracao_s"], n_quadros(meta["duracao_s"]))
    vf = filtro_video(meta, lut)
    arquivos = []
    for i, t in enumerate(meta["tempos_quadros"], 1):
        out = os.path.join(dec, "frames", f"{nome}_{i:02d}.jpg")
        run(["ffmpeg", "-v", "error", "-y", *FFMPEG_LEVE, "-ss", str(t), "-i", caminho,
             "-frames:v", "1", "-vf", vf, "-q:v", "3", out])
        arquivos.append(out)
    if not any(os.path.exists(a) for a in arquivos):
        return nome, "erro: nenhum quadro saiu (codec que o ffmpeg não lê?)"
    folha_do_clipe(nome, meta["tempos_quadros"], arquivos, meta["orientacao"],
                   os.path.join(dec, "folhas", f"{nome}.jpg"))

    if meta["audio_canais"]:
        vol = run(["ffmpeg", "-threads", "2", "-i", caminho, "-vn", "-af", "volumedetect", "-f", "null", "-"]).stderr
        m = re.search(r"mean_volume: ([-\d.]+)", vol)
        p = re.search(r"max_volume: ([-\d.]+)", vol)
        meta["audio_media_db"] = float(m.group(1)) if m else None
        meta["audio_pico_db"] = float(p.group(1)) if p else None
        midia.audio_wav(caminho, os.path.join(dec, "audio", f"{nome}.wav"), sr=16000)

    with open(meta_path, "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return nome, "ok"


def transcrever(dec, idioma):
    """whisper-cli em série nos WAV sem transcrição. Devolve (feitos, falhas)."""
    if not (os.path.exists(WHISPER_MODELO) and subprocess.run(["which", "whisper-cli"], capture_output=True).returncode == 0):
        print("aviso: whisper-cli ou o modelo não estão instalados; transcrição pulada")
        return 0, []
    wavs = sorted(f for f in os.listdir(os.path.join(dec, "audio")) if f.endswith(".wav"))
    pend = [w for w in wavs if not os.path.exists(os.path.join(dec, "transcr", w[:-4] + ".json"))]
    falhas = []
    for i, w in enumerate(pend, 1):
        saida = os.path.join(dec, "transcr", w[:-4])
        cmd = ["whisper-cli", "-m", WHISPER_MODELO, "-f", os.path.join(dec, "audio", w), "-l", idioma,
               "-ml", "60", "-oj", "-osrt", "-np", "-of", saida]
        if os.path.exists(WHISPER_VAD):
            cmd[5:5] = ["--vad", "-vm", WHISPER_VAD]
        if run(cmd, 1800).returncode != 0:
            falhas.append(w[:-4])
        progresso("transcrição", i, len(pend))
    return len(pend) - len(falhas), falhas


def progresso(rotulo, i, n):
    """No terminal, uma linha que se reescreve; fora dele (Claude, log), só a cada 25%. Saída curta = menos token."""
    if sys.stdout.isatty():
        print(f"\r{rotulo}: {i}/{n}", end="" if i < n else "\n", flush=True)
    elif n and (i == n or i % max(1, n // 4) == 0):
        print(f"{rotulo}: {i}/{n}", flush=True)


def cmd_preparar(a):
    pasta = os.path.abspath(a.pasta)
    clipes = clipes_da_pasta(pasta)
    if not clipes:
        print(f"erro: nenhum clipe de vídeo em {pasta}"); return 1
    dec = pasta_decupa(pasta)
    for s in SUBPASTAS:
        os.makedirs(os.path.join(dec, s), exist_ok=True)
    paralelo = max(1, min(a.paralelo, MAX_PARALELO))
    t0, res = time.time(), []
    with ThreadPoolExecutor(max_workers=paralelo) as pool:
        for i, r in enumerate(pool.map(lambda c: preparar_um(c, dec, a.lut), clipes), 1):
            res.append(r)
            progresso("clipes", i, len(clipes))
    erros = [(n, s) for n, s in res if s.startswith("erro")]
    feitos = sum(s == "ok" for _, s in res)
    print(f"clipes: {feitos} novos, {sum(s == 'pulado' for _, s in res)} já prontos, {len(erros)} com erro "
          f"({time.time() - t0:.0f} s)")
    for n, s in erros:
        print(f"  {n}: {s}")
    if not a.sem_fala:
        n, falhas = transcrever(dec, a.idioma)
        print(f"transcrição: {n} novas" + (f", falhou em {', '.join(falhas)}" if falhas else ""))
    print(f"pronto em {dec}. Próximo: decupa situacao \"{pasta}\"")
    return 1 if erros else 0


# ---------- passo 2: situação ----------

def ler_json(caminho, padrao=None):
    try:
        with open(caminho) as f:
            return json.load(f)
    except (OSError, ValueError):
        return padrao


def contagem(pasta):
    dec = pasta_decupa(pasta)
    nomes = [midia.stem(c) for c in clipes_da_pasta(pasta)]
    tem = lambda sub, ext: {n for n in nomes if os.path.exists(os.path.join(dec, sub, n + ext))}
    return nomes, tem("meta", ".json"), tem("audio", ".wav"), tem("transcr", ".json"), tem("descricoes", ".json")


def cmd_situacao(a):
    pasta = os.path.abspath(a.pasta)
    nomes, meta, audio, transcr, desc = contagem(pasta)
    if not nomes:
        print(f"erro: nenhum clipe de vídeo em {pasta}"); return 1
    print(f"{len(nomes)} clipes | preparados {len(meta)} | com áudio {len(audio)} | transcritos {len(transcr)} "
          f"| descritos {len(desc)}")
    if len(meta) < len(nomes):
        print(f"faltam preparar {len(nomes) - len(meta)}: decupa preparar \"{pasta}\"")
    sem = [n for n in nomes if n in meta and n not in desc]
    if not sem:
        print("todos os preparados têm descrição. Próximo: decupa planilha" if meta else "")
        return 0
    lotes = {f"L{i // a.lote + 1}": sem[i:i + a.lote] for i in range(0, len(sem), a.lote)}
    destino = os.path.join(pasta_decupa(pasta), "lotes.json")
    with open(destino, "w") as f:
        json.dump(lotes, f, ensure_ascii=False, indent=1)
    print(f"{len(sem)} sem descrição em {len(lotes)} lote(s) de até {a.lote}: {destino}")
    print(f"como descrever: {CAMPOS}")
    return 0


# ---------- passo 4: planilha ----------

def numeros_faltando(nomes):
    """Buracos na numeração ('C4849'...'C5042'), só quando todos têm o mesmo prefixo."""
    partes = [re.fullmatch(r"(\D*)(\d+)", n) for n in nomes]
    if not partes or not all(partes) or len({p.group(1) for p in partes}) != 1:
        return []
    pre, larg = partes[0].group(1), len(partes[0].group(2))
    nums = {int(p.group(2)) for p in partes}
    return [f"{pre}{n:0{larg}d}" for n in range(min(nums), max(nums) + 1) if n not in nums]


def hora(meta):
    if meta.get("data_local"):
        return str(meta["data_local"])[11:19]
    ts = midia._creation_time_utc(meta.get("creation_time_utc"))
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S") if ts else "?"


def fala(dec, clipe):
    segs = (ler_json(os.path.join(dec, "transcr", f"{clipe}.json"), {}) or {}).get("transcription", [])
    return " / ".join(s["text"].strip() for s in segs if s.get("text", "").strip())


def drive_ids(pasta_id):
    r = run(["rclone", "lsjson", "gdrive:", "--drive-root-folder-id", pasta_id, "--files-only"], 300)
    if r.returncode != 0:
        print(f"aviso: rclone não listou a pasta do Drive ({r.stderr.strip()[:200]}); sem links")
        return {}
    return {midia.stem(x["Name"]): x["ID"] for x in json.loads(r.stdout or "[]")}


def montar_planilha(pasta, saida, titulo, origem, drive=None):
    """Grava o xlsx e devolve (linhas, sem_descricao)."""
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    drive = drive or {}
    dec = pasta_decupa(pasta)
    fino = Side(style="thin", color="BFBFBF")
    borda = Border(left=fino, right=fino, top=fino, bottom=fino)
    quebra = Alignment(wrap_text=True, vertical="top")
    cor_aprov = {"Alto": "C6EFCE", "Médio": "FFEB9C", "Baixo": "F8CBAD", "Descartar": "D9D9D9"}

    def cabecalho(ws, cols):
        for i, (nome, larg) in enumerate(cols, 1):
            c = ws.cell(row=1, column=i, value=nome)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="1F2A36")
            c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
            c.border = borda
            ws.column_dimensions[get_column_letter(i)].width = larg
        ws.row_dimensions[1].height = 32

    def escrever(ws, r, valores):
        for i, v in enumerate(valores, 1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.alignment = quebra
            cell.border = borda

    nomes = [midia.stem(c) for c in clipes_da_pasta(pasta)]
    linhas = []
    for c in nomes:
        meta = ler_json(os.path.join(dec, "meta", f"{c}.json"))
        if meta:
            linhas.append((c, meta, ler_json(os.path.join(dec, "descricoes", f"{c}.json"), {}) or {}))

    wb = Workbook()
    ws = wb.active
    ws.title = "Decupagem"
    ws.sheet_properties.tabColor = "2E75B6"
    cols = [("Miniatura", 38), ("Clipe", 12), ("Hora", 9), ("Duração", 8), ("Grupo", 20), ("Categoria", 15),
            ("Assunto", 30), ("Itens em cena", 32), ("Descrição", 48), ("Ações (linha do tempo)", 60),
            ("Enquadramento", 18), ("Movimento", 18), ("Pessoas", 24), ("Texto visível", 16),
            ("Qualidade / problemas", 30), ("Melhor trecho", 30), ("Aproveitamento", 13), ("Incertezas", 30),
            ("Formato", 22), ("Fala / áudio", 40), ("Timecode", 12)]
    cabecalho(ws, cols)
    os.makedirs(os.path.join(dec, "thumbs"), exist_ok=True)
    for r, (c, meta, d) in enumerate(linhas, 2):
        fps = meta.get("fps") or 0
        formato = (f"{meta['orientacao'].capitalize()} {meta['largura']}x{meta['altura']} · "
                   f"{str(fps).replace('.', ',')}p"
                   + (f" (dá câmera lenta {fps / 23.976:.1f}x em 23,976)".replace(".", ",") if fps > 30 else "")
                   + ("" if meta.get("camera") else ". Sem metadados da câmera (cópia exportada?): hora pode estar errada"))
        f = fala(dec, c)
        if d.get("fala"):
            audio = d["fala"]
        elif f:
            audio = f'Transcrição automática (conferir; pode ser ruído): "{f[:400]}{"…" if len(f) > 400 else ""}"'
        else:
            audio = "Sem fala detectada" if meta.get("audio_canais") else "Sem áudio"
        if meta.get("audio_media_db") is not None:
            audio += f" · nível médio {str(meta['audio_media_db']).replace('.', ',')} dB"
        escrever(ws, r, [None, c, hora(meta), mmss(meta["duracao_s"]), d.get("grupo", ""), d.get("categoria", ""),
                         d.get("assunto", "(sem descrição)"), d.get("itens", ""), d.get("descricao", ""),
                         d.get("acoes", ""), d.get("enquadramento", ""), d.get("movimento", ""), d.get("pessoas", ""),
                         d.get("texto_visivel", ""), d.get("qualidade", ""), d.get("melhor_trecho", ""),
                         d.get("aproveitamento", ""), d.get("incertezas", ""), formato, audio,
                         meta.get("timecode") or ""])
        if c in drive:
            cl = ws.cell(row=r, column=2)
            cl.hyperlink = f"https://drive.google.com/file/d/{drive[c]}/view"
            cl.font = Font(bold=True, color="0563C1", underline="single")
        if d.get("aproveitamento") in cor_aprov:
            ws.cell(row=r, column=17).fill = PatternFill("solid", fgColor=cor_aprov[d["aproveitamento"]])
            ws.cell(row=r, column=17).font = Font(bold=True)
        n = len(meta.get("tempos_quadros", [])) or 1
        src = os.path.join(dec, "frames", f"{c}_{n // 2 + 1:02d}.jpg")
        if os.path.exists(src):
            thumb = os.path.join(dec, "thumbs", f"{c}.jpg")
            im = Image.open(src)
            im.thumbnail((150 * 16 // 9, 150))
            im.save(thumb, quality=82)
            ws.add_image(XLImage(thumb), f"A{r}")
            ws.row_dimensions[r].height = max(im.height * 0.75 + 6, 120)
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"B1:{get_column_letter(len(cols))}{len(linhas) + 1}"

    wg = wb.create_sheet("Por grupo")
    wg.sheet_properties.tabColor = "70AD47"
    cabecalho(wg, [("Grupo", 26), ("Categoria", 18), ("Clipes", 8), ("Duração total", 11),
                   ("Hora (1º a último)", 16), ("Aproveitamento Alto", 34), ("Todos os clipes", 60)])
    grupos = OrderedDict()
    for c, meta, d in linhas:
        grupos.setdefault(d.get("grupo") or "(sem descrição)", []).append((c, meta, d))
    for r, (g, itens) in enumerate(grupos.items(), 2):
        cats = list(OrderedDict.fromkeys(d.get("categoria", "") for _, _, d in itens if d.get("categoria")))
        horas = [hora(m)[:5] for _, m, _ in itens]
        escrever(wg, r, [g, " / ".join(cats), len(itens), mmss(sum(m["duracao_s"] for _, m, _ in itens)),
                         f"{horas[0]} a {horas[-1]}",
                         ", ".join(c for c, _, d in itens if d.get("aproveitamento") == "Alto"),
                         ", ".join(c for c, _, _ in itens)])
    wg.freeze_panes = "B2"

    para_olhar = ler_json(os.path.join(dec, "para_olhar.json"), [])
    if para_olhar:
        wp = wb.create_sheet("Para olhar")
        wp.sheet_properties.tabColor = "C00000"
        cabecalho(wp, [("Assunto", 26), ("Clipes", 34), ("O que é", 90)])
        for r, item in enumerate(para_olhar, 2):
            escrever(wp, r, [item.get("assunto", ""), item.get("clipes", ""), item.get("o_que_e", "")]
                     if isinstance(item, dict) else list(item))
        wp.freeze_panes = "A2"

    wl = wb.create_sheet("Como ler")
    wl.sheet_properties.tabColor = "A5A5A5"
    total = sum(m["duracao_s"] for _, m, _ in linhas)
    faltam = numeros_faltando(nomes)
    texto = [("Origem", origem or os.path.basename(pasta)),
             ("Volume", f"{len(linhas)} clipes, {mmss(total)} de material bruto (mm:ss)"
                        + (f", de {linhas[0][0]} a {linhas[-1][0]}." if linhas else "."))]
    if faltam:
        texto.append(("Números que não estão na pasta", f"{len(faltam)}: " + ", ".join(faltam)))
    texto += [
        ("Miniatura", "Quadro do meio do clipe, reduzido. Se tiver LUT, ela é só para enxergar (não é a cor final). "
                      "As miniaturas ficam por cima das células: ao ordenar ou filtrar, elas NÃO acompanham a linha."),
        ("Clipe", "Quando a planilha foi feita com a pasta do Drive, o número é link direto para o arquivo."),
        ("Ações", "Tempos aproximados (mm:ss), tirados de quadros a cada ~2,5 s."),
        ("Áudio", "A coluna mostra o que o reconhecimento de fala achou; em ruído ele inventa palavras soltas, "
                  "então trate como pista, não como fala confirmada."),
        ("Aproveitamento", "Alto = pronto para usar; Médio = usar com corte; Baixo = só se faltar; Descartar = sem uso."),
        ("Incertezas", "O que não dá para afirmar só pela imagem. Nenhum nome foi inventado."),
    ]
    wl.column_dimensions["A"].width = 30
    wl.column_dimensions["B"].width = 110
    for r, (k, v) in enumerate([("Título", titulo)] + texto, 1):
        wl.cell(row=r, column=1, value=k).font = Font(bold=True)
        wl.cell(row=r, column=2, value=v).alignment = quebra
        wl.row_dimensions[r].height = 15 * max(1, len(v) // 100 + 1)

    wb.save(saida)
    return len(linhas), [c for c, _, d in linhas if not d]


def cmd_planilha(a):
    pasta = os.path.abspath(a.pasta)
    if not os.path.isdir(pasta_decupa(pasta)):
        print(f"erro: {pasta} ainda não foi preparada (decupa preparar)"); return 1
    nome = os.path.basename(pasta.rstrip("/"))
    titulo = a.titulo or f"DECUPAGEM {nome}"
    saida = os.path.abspath(a.saida) if a.saida else os.path.join(pasta, re.sub(r"\s+", "_", titulo) + ".xlsx")
    drive = drive_ids(a.drive_pasta) if a.drive_pasta else {}
    n, sem = montar_planilha(pasta, saida, titulo, a.origem, drive)
    print(f"planilha: {saida} ({n} clipes, {len(sem)} sem descrição"
          + (f": {', '.join(sem[:10])}{'...' if len(sem) > 10 else ''}" if sem else "") + ")")
    if a.drive_pasta:
        r = run(["rclone", "copyto", saida, f"gdrive:{titulo}.xlsx", "--drive-root-folder-id", a.drive_pasta,
                 "--drive-import-formats", "xlsx"], 600)
        if r.returncode != 0:
            print(f"erro ao subir pro Drive: {r.stderr.strip()[:300]}"); return 1
        print(f"no Drive como Google Sheet \"{titulo}\": https://drive.google.com/drive/folders/{a.drive_pasta}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="decupa", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="passo", required=True)
    p = sub.add_parser("preparar", help="metadados, quadros, folhas, áudio e transcrição")
    p.add_argument("pasta")
    p.add_argument("--lut", default="auto", help="auto (S-Log3 da Sony quando o metadado diz), nenhuma, slog3 ou um .cube")
    p.add_argument("--paralelo", type=int, default=2, help=f"clipes ao mesmo tempo (padrão 2, máximo {MAX_PARALELO})")
    p.add_argument("--idioma", default="pt")
    p.add_argument("--sem-fala", action="store_true", help="não roda o whisper")
    s = sub.add_parser("situacao", help="o que falta e lotes para descrever")
    s.add_argument("pasta")
    s.add_argument("--lote", type=int, default=20)
    sub.add_parser("campos", help="mostra como descrever um clipe (o passo da IA)")
    pl = sub.add_parser("planilha", help="xlsx com miniaturas; --drive-pasta sobe como Google Sheet")
    pl.add_argument("pasta")
    pl.add_argument("--titulo")
    pl.add_argument("--origem", help="texto da linha Origem na aba Como ler (câmera, de onde veio)")
    pl.add_argument("--saida")
    pl.add_argument("--drive-pasta", help="ID da pasta do Drive com os clipes: links por clipe + sobe a planilha lá")
    a = ap.parse_args(argv)
    if a.passo == "campos":
        print(open(CAMPOS).read()); return 0
    if not os.path.isdir(a.pasta):
        print(f"erro: pasta não existe: {a.pasta}"); return 1
    return {"preparar": cmd_preparar, "situacao": cmd_situacao, "planilha": cmd_planilha}[a.passo](a)


if __name__ == "__main__":
    sys.exit(main())

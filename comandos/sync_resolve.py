"""Trilha DESLIGADA com a segunda câmera sobre os clipes da referência que estão na V1 (consome alinhamento_<outra>.json)."""
import json, os
from . import midia, resolve_api as ra

MIN_S = 0.5     # sobreposição menor que isso é pulada (12 quadros a 24 fps)

def trechos_sync(itens_v1, pares_por_ref, fps_outra):
    """itens_v1 = [dict(nome, left, dur, pos, fps)] em quadros; pares_por_ref = {nome_ref: [par]}. Colocações em quadros."""
    out = []
    for it in itens_v1:
        a = it["left"] / it["fps"]; b = (it["left"] + it["dur"]) / it["fps"]
        for p in pares_por_ref.get(it["nome"], []):
            o1 = max(a, p["lag_s"]); o2 = min(b, p["lag_s"] + p["dur_outra_s"])
            if o2 - o1 < MIN_S:
                continue
            rec = it["pos"] + round((o1 - a) * it["fps"]); sin = round((o1 - p["lag_s"]) * fps_outra); n = round((o2 - o1) * fps_outra)
            out.append({"outra": p["outra"], "ref": it["nome"], "sin": sin, "sout": sin + n, "rec": rec, "fonte": p["fonte"]})
    return out

def executar(ref_dir, outra_dir, json_path):
    d = json.load(open(json_path, encoding="utf-8")); nome = os.path.basename(os.path.normpath(outra_dir))
    por_ref = {}
    for p in d["pares"]:
        por_ref.setdefault(p["ref"], []).append(p)
    try:
        r, pm, proj, tl, mp = ra.conectar()
    except ra.ResolveErro as e:
        print(f"erro: {e}"); return 4
    S = tl.GetStartFrame(); itens_v1 = []
    for it in tl.GetItemListInTrack("video", 1) or []:
        mpi = it.GetMediaPoolItem()
        if not mpi:
            continue
        nome_ref = midia.stem(mpi.GetClipProperty("File Name"))
        if nome_ref not in por_ref:
            continue
        fps = float(mpi.GetClipProperty("FPS") or proj.GetSetting("timelineFrameRate"))
        itens_v1.append({"nome": nome_ref, "left": it.GetLeftOffset(), "dur": it.GetDuration(), "pos": it.GetStart() - S, "fps": fps})
    if not itens_v1:
        print("erro: nenhum clipe da V1 tem par no alinhamento (a V1 usa os arquivos da pasta de referência?)"); return 5
    clipes = {midia.stem(c): c for c in midia.listar_clipes(outra_dir)}
    fps_outra = (midia.probe(next(iter(clipes.values()))) or {}).get("fps") or 23.976
    plano = trechos_sync(itens_v1, por_ref, fps_outra)
    if not plano:
        print("erro: nenhuma sobreposição de pelo menos 0,5 s"); return 5
    bin_ = ra.sub_bin(mp, mp.GetRootFolder(), nome)
    itens = ra.importar(mp, bin_, [clipes[x["outra"]] for x in plano])
    idx = ra.trilha_video(tl, f"{nome} (sync)"); ok = 0
    for x in plano:
        g = ra.colocar(mp, itens[clipes[x["outra"]]], x["sin"], x["sout"], idx, S + x["rec"])
        if g:
            ok += 1
            if x["fonte"] != "audio":
                g.SetClipColor("Orange")
        else:
            print(f"  falhou: {x['outra']} em {x['rec']}")
    ra.desligar_trilha(r, tl, idx); ra.salvar(pm)
    print(f"trilha '{nome} (sync)' (V{idx}, desligada): {ok}/{len(plano)} trechos; {sum(1 for x in plano if x['fonte'] != 'audio')} laranja (por relógio)")
    return 0 if ok == len(plano) else 6

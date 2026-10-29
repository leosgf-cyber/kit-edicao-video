"""alinha-cameras REFERENCIA OUTRA [--resolve]: deslocamento de relógio entre duas câmeras medido por áudio."""
import argparse, json, os, sys, tempfile
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfiltfilt, correlate
from . import midia

FS, ER = 8000, 200                      # áudio a 8 kHz; envelope a 200 Hz (passo de 5 ms)
PICO_MIN, RAZAO_MIN, JANELA = 0.30, 1.8, 5.0
_SOS = butter(4, [200, 3500], btype="band", fs=FS, output="sos")

def envelope(x):
    """Envelope normalizado a ER Hz (spec §4): passa-banda 200–3500 Hz, RMS por 5 ms, log, menos média móvel de 1 s, /desvio."""
    x = np.asarray(x, dtype=np.float64)
    if x.size and np.abs(x).max() > 1.5:
        x = x / 32768.0
    hop = FS // ER; n = len(x) // hop
    if n < ER:
        return np.zeros(0)
    x = sosfiltfilt(_SOS, x)
    e = np.log(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(axis=1)) + 1e-12)
    k = ER
    borda = np.pad(e, (k // 2, k - 1 - k // 2), mode="edge")
    e = e - np.convolve(borda, np.ones(k) / k, mode="valid")
    return e / (e.std() + 1e-9)

def correlacao(ref, seg):
    """Correlação normalizada de `seg` deslizando sobre `ref` (ambos envelopes). len(ref) - len(seg) + 1 valores."""
    m = len(seg); c = correlate(ref, seg, mode="valid", method="fft")
    cs = np.concatenate([[0.0], np.cumsum(ref ** 2)])
    norma = np.sqrt(cs[m:m + len(c)] - cs[:len(c)]) * np.sqrt((seg ** 2).sum()) + 1e-9
    return c / norma

def pico(nc):
    """(índice do maior valor, valor, segundo maior fora de ±2 s, ou None se a máscara cobrir o vetor inteiro)."""
    i = int(np.argmax(nc)); mask = np.ones(len(nc), bool); mask[max(0, i - 2 * ER):i + 2 * ER] = False
    return i, float(nc[i]), float(nc[mask].max()) if mask.any() else None

def forte(p, s):
    return s is not None and p >= PICO_MIN and p >= RAZAO_MIN * s

def linha_do_tempo(ref):
    """ref = [dict(nome, inicio, dur, env)]. (t0, tl, occ): envelope contínuo da referência pelo creation_time; occ = onde há áudio."""
    t0 = min(c["inicio"] for c in ref); t1 = max(c["inicio"] + len(c["env"]) / ER for c in ref)
    L = int((t1 - t0) * ER) + 1; tl = np.zeros(L); occ = np.zeros(L, bool)
    for c in sorted(ref, key=lambda c: c["inicio"]):
        i = int((c["inicio"] - t0) * ER); e = c["env"][:L - i]; tl[i:i + len(e)] = e; occ[i:i + len(e)] = True
    return t0, tl, occ

def busca_global(outra, ref):
    """Cada clipe da OUTRA contra a linha inteira da REF (só onde a REF cobre ≥ 50% dele). delta = quanto somar ao relógio da OUTRA."""
    t0, tl, occ = linha_do_tempo(ref); cov = np.concatenate([[0], np.cumsum(occ)]); res = []
    for c in outra:
        e = c["env"]; m = len(e)
        if m == 0 or m > len(tl):
            res.append({"nome": c["nome"], "forte": False, "pico": 0.0, "segundo": 0.0}); continue
        nc = correlacao(tl, e); covf = (cov[m:m + len(nc)] - cov[:len(nc)]) / m
        nc = np.where(covf >= 0.5, nc, -1.0); i, p, s = pico(nc); inicio_real = t0 + i / ER
        res.append({"nome": c["nome"], "pico": p, "segundo": s, "forte": forte(p, s),
                    "delta": inicio_real - c["inicio"], "inicio_real": inicio_real})
    return res

def deslocamento_global(res):
    """Mediana dos deltas dos pares fortes, ou None se houver menos de 2."""
    d = [r["delta"] for r in res if r.get("forte")]
    if len(d) < 2:
        return None
    return {"deslocamento_s": float(np.median(d)), "pares_fortes": len(d), "dispersao_s": [float(min(d)), float(max(d))]}

def refino(ref_env, outra_env, lag_esperado):
    """Onde a OUTRA começa dentro da REF (s), procurando ±JANELA em volta do esperado; REF com zeros nas pontas."""
    m = len(outra_env); pad = int((JANELA + m / ER) * ER); refp = np.concatenate([np.zeros(pad), ref_env, np.zeros(pad)])
    lo = max(int((lag_esperado - JANELA) * ER) + pad, 0); hi = min(int((lag_esperado + JANELA) * ER) + pad, len(refp) - m)
    if hi <= lo or m == 0:
        return None
    nc = correlacao(refp[lo:hi + m], outra_env); i, p, s = pico(nc)
    return {"lag_s": (lo + i - pad) / ER, "pico": p, "segundo": s, "forte": forte(p, s)}

def pares(outra, ref, deslocamento):
    """Um registro por par (clipe da OUTRA, clipe da REF) que se sobrepõe pelo relógio corrigido. lag_s = onde a OUTRA começa na REF."""
    out = []
    for o in outra:
        for r in ref:
            esperado = (o["inicio"] + deslocamento) - r["inicio"]
            if esperado + o["dur"] <= 0 or esperado >= r["dur"]:
                continue
            rf = refino(r["env"], o["env"], esperado); f = rf or {"lag_s": esperado, "pico": 0.0, "forte": False}
            out.append({"outra": o["nome"], "ref": r["nome"], "lag_s": round(f["lag_s"] if f["forte"] else esperado, 3),
                        "lag_audio_s": round(f["lag_s"], 3) if rf is not None else None, "lag_relogio_s": round(esperado, 3),
                        "pico": round(f["pico"], 2), "fonte": "audio" if f["forte"] else "relogio",
                        "dur_outra_s": round(o["dur"], 3), "dur_ref_s": round(r["dur"], 3)})
    return out

def consolidar(ps, outra, ref):
    """Deslocamento final: mediana, sobre os pares confirmados por áudio no refino, de (início da REF + lag) - início da OUTRA."""
    ini_o = {o["nome"]: o["inicio"] for o in outra}; ini_r = {r["nome"]: r["inicio"] for r in ref}
    d = [ini_r[p["ref"]] + p["lag_s"] - ini_o[p["outra"]] for p in ps if p["fonte"] == "audio"]
    if len(d) < 2:
        return None
    return {"deslocamento_s": float(np.median(d)), "pares_fortes": len(d), "dispersao_s": [float(min(d)), float(max(d))]}

class Erro(RuntimeError):
    """Erro com mensagem pronta pra imprimir."""

def carregar(pasta, tmp):
    """Lê todos os clipes da pasta: probe + áudio + envelope. Erro claro se falta creation_time ou áudio.
    Dedup por nome sem extensão: fica só o primeiro da ordem natural (ex.: DSC_4675.MP4 antes do .NEV do mesmo take)."""
    clipes = midia.listar_clipes(pasta)
    if not clipes:
        raise Erro(f"nenhum clipe de vídeo em {pasta}")
    vistos = set(); unicos = []
    for c in clipes:
        nome = midia.stem(c)
        if nome in vistos:
            continue
        vistos.add(nome); unicos.append(c)
    out = []
    for c in unicos:
        info = midia.probe(c)
        if not info:
            raise Erro(f"o ffprobe não lê {c}")
        if not info["tem_audio"]:
            raise Erro(f"{os.path.basename(c)} não tem áudio; alinhamento por áudio impossível")
        if info["inicio"] is None:
            raise Erro(f"{os.path.basename(c)} não tem creation_time no contêiner; sem hora de gravação não dá pra alinhar")
        wav = midia.audio_wav(c, os.path.join(tmp, info["nome"] + ".wav"))
        if not wav:
            raise Erro(f"não consegui extrair o áudio de {c}")
        _, x = wavfile.read(wav)
        out.append({**info, "env": envelope(x)})
    return out

def _hms(t):
    t = int(round(t)) % 86400
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"

def _v(x, casas=1):
    return f"{x:.{casas}f}".replace(".", ",")

def relatorio(ref_dir, outra_dir, g, ps, outra, destino):
    """Grava ALINHAMENTO_<outra>.md e alinhamento_<outra>.json em `destino`. Devolve (md, json)."""
    nome = os.path.basename(os.path.normpath(outra_dir)); d = g["deslocamento_s"]
    por_outra = {}
    for p in ps:
        por_outra.setdefault(p["outra"], []).append(p)
    linhas = [f"# Alinhamento: {nome} contra {os.path.basename(os.path.normpath(ref_dir))}", "",
              f"- Relógio da câmera **{nome}** está **{_v(abs(d))} s {'atrás' if d > 0 else 'à frente'}** da referência "
              f"(some {_v(d, 3)} s ao creation_time dela pra cair no relógio da referência).",
              f"- Confiança: {g['pares_fortes']} pares fortes; dispersão de {_v(g['dispersao_s'][0], 2)} a {_v(g['dispersao_s'][1], 2)} s "
              "(a dispersão de até ±0,5 s é o arredondamento a segundo inteiro do creation_time).", "",
              "| clipe | hora gravada (UTC) | início real no relógio da referência | dur | cai dentro de | fonte |", "|---|---|---|---|---|---|"]
    for o in outra:
        pp = por_outra.get(o["nome"], [])
        cai = ", ".join(f"{p['ref']} ({_v(p['lag_s'], 2)} s)" for p in pp) or "nenhum clipe da referência"
        fonte = ", ".join(sorted({p["fonte"] for p in pp})) or "sem par"
        linhas.append(f"| {o['nome']} | {_hms(o['inicio'])} | {_hms(o['inicio'] + d)} | {_v(o['dur'])} s | {cai} | {fonte} |")
    md = os.path.join(destino, f"ALINHAMENTO_{nome}.md"); open(md, "w", encoding="utf-8").write("\n".join(linhas) + "\n")
    js = os.path.join(destino, f"alinhamento_{nome}.json")
    json.dump({"referencia": ref_dir, "outra": outra_dir, **g, "pares": ps}, open(js, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return md, js

def main(argv=None):
    ap = argparse.ArgumentParser(prog="alinha-cameras", description="Deslocamento de relógio entre duas câmeras, medido por áudio.")
    ap.add_argument("referencia", help="pasta da câmera de referência (a que está na V1)")
    ap.add_argument("outra", help="pasta da outra câmera")
    ap.add_argument("--resolve", action="store_true", help="também cria a trilha desligada na timeline corrente do Resolve")
    a = ap.parse_args(argv)
    for p in (a.referencia, a.outra):
        if not os.path.isdir(p):
            print(f"erro: pasta não existe: {p}"); return 1
    try:
        with tempfile.TemporaryDirectory() as tmp:
            print("lendo a referência…"); ref = carregar(a.referencia, tmp)
            print("lendo a outra câmera…"); outra = carregar(a.outra, tmp)
    except Erro as e:
        print(f"erro: {e}"); return 2
    g0 = deslocamento_global(busca_global(outra, ref))
    if not g0:
        print("erro: nenhum par casou por áudio; as duas câmeras gravaram o mesmo ambiente?"); return 3
    ps = pares(outra, ref, g0["deslocamento_s"])
    g = consolidar(ps, outra, ref) or g0
    md, js = relatorio(a.referencia, a.outra, g, ps, outra, a.outra)
    d = g["deslocamento_s"]
    print(f"deslocamento: {_v(abs(d), 3)} s ({'outra atrás' if d > 0 else 'outra à frente'}) | pares fortes: {g['pares_fortes']} | "
          f"dispersão: {_v(g['dispersao_s'][0], 2)} a {_v(g['dispersao_s'][1], 2)} s")
    print(f"relatório: {md}\ndados: {js}")
    if a.resolve:
        from . import sync_resolve
        return sync_resolve.executar(a.referencia, a.outra, js)
    return 0

if __name__ == "__main__":
    sys.exit(main())

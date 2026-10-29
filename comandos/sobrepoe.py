"""sobrepoe PASTA [--take 2.5]: espelha as subpastas como bins e enche os marcadores da timeline com takes colados. Trilha desligada."""
import argparse, os, sys
from . import midia

CABECA, PASSO, FOLGA, MARGEM = 24, 12, 12, 6     # quadros: pula 1 s se sobra; avanço extra por reuso; folga pra usar a cabeça; mínimo além do take

def casar(marcador, subbins):
    """Sub-bin cujo nome começa pelo nome do marcador (sem distinguir maiúsculas), ou None."""
    m = marcador.strip().casefold()
    if not m:
        return None
    for s in subbins:
        if s.casefold().startswith(m):
            return s
    return None

def dividir(L, take):
    """L quadros em n = max(1, round(L/take)) takes iguais; o resto vai um quadro a mais nos primeiros."""
    if L <= 0:
        return []
    n = max(1, round(L / take)); base, resto = divmod(L, n)
    return [base + (1 if i < resto else 0) for i in range(n)]

def entrada(dur, take, vezes):
    """Quadro de entrada no clipe pra um take de `take` quadros, na `vezes`-ésima reutilização; None se curto demais."""
    if dur < take + MARGEM:
        return None
    centro = (dur - take) // 2
    if vezes == 0:
        return CABECA if dur >= take + CABECA + FOLGA else centro
    sin = CABECA + vezes * (take + PASSO)
    return sin if sin + take <= dur - 3 else centro

def _escolhe(nomes, durs, tk, uso):
    for n in nomes:
        sin = entrada(durs[n], tk, uso.get(n, 0))
        if sin is not None:
            return n, sin
    return None

def planejar(trechos, pools, durs, take):
    """trechos = [(ini, fim, subbin)] em quadros; pools = {subbin: [nomes em ordem]}; durs = {nome: quadros}. Takes colados.
    Primeiro os clipes inéditos no trecho; se nenhum cabe, repete pela lista inteira com a entrada avançada."""
    uso, plano = {}, []
    for a, b, sub in trechos:
        ordem = [n for n in pools.get(sub, []) if n in durs]; pos = a; usados = set()
        for tk in dividir(b - a, take):
            escolha = _escolhe([n for n in ordem if n not in usados], durs, tk, uso)
            if not escolha:
                usados = set(); escolha = _escolhe(ordem, durs, tk, uso)      # esgotou (ou nada inédito coube): recomeça do primeiro
            if escolha:
                n, sin = escolha
                plano.append({"clipe": n, "sin": sin, "sout": sin + tk, "rec": pos, "subbin": sub})
                uso[n] = uso.get(n, 0) + 1; usados.add(n)
            pos += tk
    return plano

def trechos_de_marcadores(marcadores, subbins, fim_timeline):
    """marcadores = Timeline.GetMarkers() ({quadro_rel: {name, duration, ...}}). Devolve (trechos ordenados, ignorados).
    Marcador que invade o começo do seguinte é cortado ali (colados, sem sobreposição); o que sobrar com menos de
    2 quadros é descartado."""
    brutos, ignorados = [], []
    for q in sorted(marcadores):
        m = marcadores[q]; nome = (m.get("name") or "").strip(); dur = int(m.get("duration") or 0)
        if dur < 2:
            ignorados.append((q, nome, "sem duração")); continue
        sub = casar(nome, subbins)
        if not sub:
            ignorados.append((q, nome, "sem sub-bin")); continue
        brutos.append((q, min(q + dur, fim_timeline), sub, nome))
    trechos = []
    for i, (q, fim, sub, nome) in enumerate(brutos):
        if i + 1 < len(brutos):
            fim = min(fim, brutos[i + 1][0])
        if fim - q < 2:
            ignorados.append((q, nome, "sobreposto")); continue
        trechos.append((q, fim, sub))
    return trechos, ignorados

def pools_da_pasta(pasta):
    """(subpastas em ordem natural, {subpasta: [nomes em ordem natural]}, {(subpasta, nome): caminho real}, quebrados).
    `reais` é indexado por (subpasta, nome) porque o mesmo nome pode ser um hard link repetido em várias subpastas
    apontando pra arquivos fisicamente distintos. `quebrados` conta apontadores (arquivo ou symlink) com a extensão
    de vídeo cujo destino não existe mais no disco (ex.: cartão da ZR desmontado); esses não entram na pool."""
    subs = sorted((d for d in os.listdir(pasta) if os.path.isdir(os.path.join(pasta, d)) and not d.startswith((".", "_"))), key=midia.chave_natural)
    pools, reais, quebrados = {}, {}, 0
    for s in subs:
        base = os.path.join(pasta, s); pools[s] = []
        for c in midia.listar_clipes(base):
            nome = midia.stem(c); pools[s].append(nome); reais[(s, nome)] = os.path.realpath(c)
        for n in os.listdir(base):
            p = os.path.join(base, n)
            if not n.startswith(".") and os.path.splitext(n)[1].lower() in midia.VIDEO_EXTS and not os.path.exists(p):
                quebrados += 1
    return subs, pools, reais, quebrados

def main(argv=None):
    from . import resolve_api as ra
    ap = argparse.ArgumentParser(prog="sobrepoe", description="Bins por subpasta + trilha desligada de sobreposições a partir dos marcadores da timeline.")
    ap.add_argument("pasta", help="pasta da seleção, com uma subpasta por rubrica")
    ap.add_argument("--take", type=float, default=2.5, help="segundos por take (padrão 2,5)")
    a = ap.parse_args(argv); pasta = os.path.abspath(a.pasta)
    if not os.path.isdir(pasta):
        print(f"erro: pasta não existe: {pasta}"); return 1
    subs, pools, reais, quebrados = pools_da_pasta(pasta)
    if not subs or not any(pools.values()):
        print(f"erro: nenhuma subpasta com clipes em {pasta}"); return 1
    if quebrados:
        print(f"erro: {quebrados} apontadores sem destino (o cartão da ZR está montado?)"); return 1
    try:
        r, pm, proj, tl, mp = ra.conectar()
        pai = ra.sub_bin(mp, mp.GetRootFolder(), os.path.basename(pasta)); itens = {}
        for s in subs:
            b = ra.sub_bin(mp, pai, s); tem = ra.importar(mp, b, [reais[(s, n)] for n in pools[s]])
            for n in pools[s]:
                itens.setdefault((s, n), tem[reais[(s, n)]])
            print(f"  bin '{s}': {len(pools[s])} clipes")
        try:
            fps = float(str(proj.GetSetting("timelineFrameRate")).replace(",", "."))
        except (TypeError, ValueError):
            raise ra.ResolveErro("não consegui ler a taxa de quadros da timeline")
        take = round(a.take * fps); S = tl.GetStartFrame()
        trechos, ignorados = trechos_de_marcadores(tl.GetMarkers() or {}, subs, tl.GetEndFrame() - S)
        if not trechos:
            print("erro: nenhum marcador com duração cujo nome case com uma subpasta (ex.: marcador '03' pra '03 ATO II ...')"); return 3
        durs = {}
        for s, n in {(s, n) for _, _, s in trechos for n in pools[s]}:
            if n in durs:
                continue
            info = midia.probe(reais[(s, n)])
            if not info:
                durs[n] = 0; continue
            durs[n] = round(info["dur"] * (info["fps"] or fps))
            if info["fps"] and abs(info["fps"] - fps) > 0.01:
                print(f"  aviso: '{n}' está a {info['fps']:.3f} fps, timeline está a {fps:.3f} fps")
        plano = planejar(trechos, pools, durs, take)
        if not plano:
            print("erro: nenhum clipe coube nos trechos (todos curtos demais?)"); return 3
        idx = ra.trilha_video(tl, "SOBREPOSIÇÕES"); ok = 0
        for x in plano:
            g = ra.colocar(mp, itens[(x["subbin"], x["clipe"])], x["sin"], x["sout"], idx, S + x["rec"])
            if g:
                ok += 1; g.SetClipColor(ra.cor(subs.index(x["subbin"])))
            else:
                print(f"  falhou: {x['clipe']} em {x['rec'] / fps:.2f}s")
        desligou = ra.desligar_trilha(r, tl, idx); salvou = ra.salvar(pm)
    except ra.ResolveErro as e:
        print(f"erro: {e}"); return 4
    print("\ntrecho (s)        | rubrica                        | takes | clipes")
    for a_, b_, s in trechos:
        ts = [p for p in plano if p["rec"] >= a_ and p["rec"] < b_ and p["subbin"] == s]
        print(f"{a_ / fps:7.1f}-{b_ / fps:7.1f} | {s[:30]:<30} | {len(ts):5d} | {len({p['clipe'] for p in ts})}")
    for q, nome, motivo in ignorados:
        print(f"  ignorado: marcador '{nome}' em {q / fps:.1f}s ({motivo})")
    print(f"\ntrilha 'SOBREPOSIÇÕES' (V{idx}): {ok}/{len(plano)} takes colocados | desligada: {desligou} | salvo: {salvou}")
    return 0 if ok == len(plano) and desligou else 6

if __name__ == "__main__":
    sys.exit(main())

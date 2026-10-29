import numpy as np, pytest
from comandos import alinha

def sinal_falado(seg, semente, fs=8000):
    """Ruído modulado por um envelope lento (parece fala): é o que a correlação de envelope precisa."""
    rng = np.random.default_rng(semente); n = int(seg * fs)
    pontos = rng.uniform(0.05, 1.0, size=max(2, int(seg * 20) + 1))            # 1 ponto a cada 50 ms
    mod = np.interp(np.arange(n), np.linspace(0, n, len(pontos)), pontos)
    return rng.standard_normal(n) * mod

def test_envelope_tamanho_e_normalizacao():
    e = alinha.envelope(sinal_falado(10, 1))
    assert len(e) == 10 * alinha.ER and abs(e.mean()) < 0.2 and abs(e.std() - 1) < 0.1

def test_envelope_curto_demais_vira_vazio():
    assert len(alinha.envelope(np.zeros(100))) == 0

def test_correlacao_acha_lag_conhecido():
    base = sinal_falado(60, 2); ref = alinha.envelope(base)
    trecho = base[int(21.3 * alinha.FS):int(31.3 * alinha.FS)] + 0.3 * np.random.default_rng(3).standard_normal(10 * alinha.FS)
    nc = alinha.correlacao(ref, alinha.envelope(trecho))
    i, p, s = alinha.pico(nc)
    assert abs(i / alinha.ER - 21.3) <= 0.005 and p > 0.6 and alinha.forte(p, s)

def test_forte_exige_pico_e_razao():
    assert alinha.forte(0.5, 0.1) and not alinha.forte(0.25, 0.05) and not alinha.forte(0.5, 0.4)

def test_pico_sem_segundo_e_forte_recusa_none():
    assert alinha.forte(0.9, None) is False
    assert alinha.pico(np.zeros(100))[2] is None

def duas_cameras():
    """REF: 3 clipes (0–40, 45–90, 95–120 s). OUTRA: 4 clipes de 10 s com relógio 810 s ATRÁS. Mesmo ambiente sonoro."""
    base = sinal_falado(120, 7); rng = np.random.default_rng(8); T0 = 1_000_000.0
    def clipe(nome, ini, fim, atraso, ruido):
        x = base[int(ini * alinha.FS):int(fim * alinha.FS)] + ruido * rng.standard_normal(int((fim - ini) * alinha.FS))
        return {"nome": nome, "inicio": T0 + ini - atraso, "dur": float(fim - ini), "env": alinha.envelope(x)}
    ref = [clipe("R1", 0, 40, 0, 0.1), clipe("R2", 45, 90, 0, 0.1), clipe("R3", 95, 120, 0, 0.1)]
    outra = [clipe("S1", 5, 15, 810, 0.4), clipe("S2", 50, 60, 810, 0.4), clipe("S3", 70, 80, 810, 0.4), clipe("S4", 100, 110, 810, 0.4)]
    return ref, outra

def test_busca_global_e_deslocamento():
    ref, outra = duas_cameras()
    res = alinha.busca_global(outra, ref)
    assert all(r["forte"] for r in res)
    g = alinha.deslocamento_global(res)
    assert abs(g["deslocamento_s"] - 810) < 0.05 and g["pares_fortes"] == 4
    assert g["dispersao_s"][1] - g["dispersao_s"][0] < 0.05

def test_deslocamento_global_sem_pares_e_none():
    assert alinha.deslocamento_global([{"forte": False}, {"forte": True, "delta": 1.0}]) is None

def test_pares_lag_por_audio():
    ref, outra = duas_cameras()
    ps = alinha.pares(outra, ref, 810.0)
    por = {(p["outra"], p["ref"]): p for p in ps}
    assert set(por) == {("S1", "R1"), ("S2", "R2"), ("S3", "R2"), ("S4", "R3")}
    assert abs(por[("S1", "R1")]["lag_s"] - 5) < 0.02 and abs(por[("S3", "R2")]["lag_s"] - 25) < 0.02
    assert all(p["fonte"] == "audio" for p in ps)

def test_pares_fraco_cai_no_relogio():
    ref, outra = duas_cameras()
    outra[0]["env"] = alinha.envelope(np.random.default_rng(9).standard_normal(10 * alinha.FS))   # áudio sem relação
    p = [x for x in alinha.pares(outra, ref, 810.0) if x["outra"] == "S1"][0]
    assert p["fonte"] == "relogio" and abs(p["lag_s"] - 5) < 1e-6

def test_consolidar_usa_pares_por_audio():
    ref, outra = duas_cameras()
    g = alinha.consolidar(alinha.pares(outra, ref, 810.0), outra, ref)
    assert g["pares_fortes"] == 4 and abs(g["deslocamento_s"] - 810) < 0.02

import os, json, shutil
from tests.conftest import gerar_clipe

def test_carregar_erros_claros(tmp_path):
    a = tmp_path / "a"; a.mkdir(); gerar_clipe(a / "x.mp4", audio=False)
    with pytest.raises(alinha.Erro, match="não tem áudio"):
        alinha.carregar(str(a), str(tmp_path))
    b = tmp_path / "b"; b.mkdir(); gerar_clipe(b / "y.mp4", inicio=None)
    with pytest.raises(alinha.Erro, match="creation_time"):
        alinha.carregar(str(b), str(tmp_path))

def test_carregar_dedup_por_nome(tmp_path):
    a = tmp_path / "a"; a.mkdir()
    mp4 = gerar_clipe(a / "c1.mp4")
    shutil.copy(mp4, a / "c1.nev")
    out = alinha.carregar(str(a), str(tmp_path))
    assert len(out) == 1 and out[0]["nome"] == "c1"

def test_relatorio_md_e_json(tmp_path):
    ref, outra = duas_cameras(); g = alinha.deslocamento_global(alinha.busca_global(outra, ref)); ps = alinha.pares(outra, ref, g["deslocamento_s"])
    md, js = alinha.relatorio(str(tmp_path / "REF"), str(tmp_path / "OUTRA"), g, ps, outra, str(tmp_path))
    assert os.path.exists(md) and os.path.basename(md) == "ALINHAMENTO_OUTRA.md"
    d = json.load(open(js)); assert d["deslocamento_s"] == g["deslocamento_s"] and len(d["pares"]) == 4
    texto = open(md, encoding="utf-8").read(); assert "810,0" in texto and "S3" in texto


import os
from comandos import sobrepoe as sb

SUBS = ["01 PROLOGO - Praca", "03 ATO II - Praca atual", "08 FUTURO - Orla"]

def test_casar_por_comeco_do_nome():
    assert sb.casar("03", SUBS) == "03 ATO II - Praca atual"
    assert sb.casar("08 futuro - orla", SUBS) == "08 FUTURO - Orla"
    assert sb.casar("02", SUBS) is None and sb.casar("", SUBS) is None

def test_dividir_takes_iguais_com_resto_na_frente():
    assert sb.dividir(343, 60) == [58, 57, 57, 57, 57, 57]        # 343/60 = 5,7 -> 6 takes, resto 1 no primeiro
    assert sb.dividir(30, 60) == [30] and sb.dividir(0, 60) == []
    assert sum(sb.dividir(2000, 60)) == 2000 and all(48 <= t <= 79 for t in sb.dividir(2000, 60))

def test_entrada_cabeca_centro_curto_e_repeticao():
    assert sb.entrada(200, 60, 0) == 24                # tem folga: pula 1 s
    assert sb.entrada(80, 60, 0) == 10                 # sem folga: centralizado
    assert sb.entrada(64, 60, 0) is None               # curto demais (menos que take + 6)
    assert sb.entrada(200, 60, 1) == 24 + 72           # 2ª vez: avança take + 0,5 s
    assert sb.entrada(200, 60, 3) == 70                # não cabe avançando: centralizado

def test_planejar_sem_repetir_e_depois_repete_avancando():
    trechos = [(0, 300, "A")]; pools = {"A": ["x", "y"]}; durs = {"x": 400, "y": 400}
    plano = sb.planejar(trechos, pools, durs, 60)
    assert [p["clipe"] for p in plano] == ["x", "y", "x", "y", "x"]
    assert plano[0]["sin"] == 24 and plano[2]["sin"] == 96 and plano[4]["sin"] == 168
    assert [p["rec"] for p in plano] == [0, 60, 120, 180, 240] and all(p["sout"] - p["sin"] == 60 for p in plano)

def test_planejar_pula_curto_e_trecho_sem_pool():
    plano = sb.planejar([(0, 120, "A"), (200, 260, "B")], {"A": ["curto", "ok"]}, {"curto": 30, "ok": 500}, 60)
    assert [p["clipe"] for p in plano] == ["ok", "ok"] and plano[1]["sin"] > plano[0]["sin"]

def test_planejar_nunca_repete_consecutivo_mesmo_com_clipe_impossivel():
    # "curto" nunca cabe (30 < take + MARGEM); o reset de `usados` tem que disparar mesmo assim.
    trechos = [(0, 300, "A")]; pools = {"A": ["curto", "x", "y"]}; durs = {"curto": 30, "x": 400, "y": 400}
    plano = sb.planejar(trechos, pools, durs, 60)
    clipes = [p["clipe"] for p in plano]
    assert set(clipes) == {"x", "y"} and len(clipes) == 5
    assert all(clipes[i] != clipes[i + 1] for i in range(len(clipes) - 1))

def test_trechos_de_marcadores():
    marcadores = {120: {"name": "03", "duration": 300, "color": "Yellow"}, 900: {"name": "zz", "duration": 100},
                  1500: {"name": "08", "duration": 1}, 2000: {"name": "01 prologo", "duration": 500}}
    trechos, ignorados = sb.trechos_de_marcadores(marcadores, SUBS, fim_timeline=2300)
    assert trechos == [(120, 420, "03 ATO II - Praca atual"), (2000, 2300, "01 PROLOGO - Praca")]    # ordenado; o último cortado no fim
    assert ignorados == [(900, "zz", "sem sub-bin"), (1500, "08", "sem duração")]

def test_trechos_de_marcadores_corta_no_inicio_do_seguinte():
    marcadores = {0: {"name": "03", "duration": 300}, 200: {"name": "08", "duration": 300}}
    trechos, ignorados = sb.trechos_de_marcadores(marcadores, SUBS, fim_timeline=1000)
    assert trechos == [(0, 200, "03 ATO II - Praca atual"), (200, 500, "08 FUTURO - Orla")]

def test_pools_da_pasta(tmp_path):
    (tmp_path / "01 A").mkdir(); (tmp_path / "02 B").mkdir(); (tmp_path / "_folha.jpg").write_bytes(b"")
    alvo = tmp_path / "real.mp4"; alvo.write_bytes(b"x")
    os.symlink(alvo, tmp_path / "01 A" / "ZR_10.mp4"); os.symlink(alvo, tmp_path / "01 A" / "ZR_2.mp4"); (tmp_path / "02 B" / "c.mov").write_bytes(b"y")
    subs, pools, reais, quebrados = sb.pools_da_pasta(str(tmp_path))
    assert subs == ["01 A", "02 B"] and pools["01 A"] == ["ZR_2", "ZR_10"] and pools["02 B"] == ["c"]
    assert reais[("01 A", "ZR_2")] == os.path.realpath(str(alvo)) and reais[("02 B", "c")].endswith("02 B/c.mov")
    assert quebrados == 0

def test_pools_da_pasta_conta_apontadores_quebrados(tmp_path):
    (tmp_path / "01 A").mkdir()
    alvo = tmp_path / "real.mp4"; alvo.write_bytes(b"x")
    os.symlink(alvo, tmp_path / "01 A" / "ZR_1.mp4")                          # aponta pra arquivo que existe
    os.symlink(tmp_path / "sumiu.mp4", tmp_path / "01 A" / "ZR_2.mp4")        # aponta pra arquivo que não existe (cartão desmontado)
    subs, pools, reais, quebrados = sb.pools_da_pasta(str(tmp_path))
    assert quebrados == 1 and pools["01 A"] == ["ZR_1"]                       # o quebrado não entra na pool

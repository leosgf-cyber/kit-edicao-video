from comandos import sync_resolve as sr

def test_trechos_sync_reproduz_c4566_sobre_dsc_4675():
    # V1 de 15/09: pedaço do DSC_4675 de 2261 a 2525 (264 quadros) na posição 462; C4566 começa a 85,48 s dentro do 4675
    v1 = [{"nome": "DSC_4675", "left": 2261, "dur": 264, "pos": 462, "fps": 23.976}]
    pares = {"DSC_4675": [{"outra": "C4566", "lag_s": 85.48, "dur_outra_s": 52.052, "fonte": "audio"}]}
    t = sr.trechos_sync(v1, pares, 23.976)
    assert len(t) == 1 and t[0]["rec"] == 462 and abs(t[0]["sin"] - 212) <= 1 and abs((t[0]["sout"] - t[0]["sin"]) - 264) <= 1

def test_trechos_sync_pula_sobreposicao_curta_e_sem_par():
    v1 = [{"nome": "DSC_1", "left": 0, "dur": 24, "pos": 0, "fps": 24}, {"nome": "DSC_2", "left": 0, "dur": 240, "pos": 24, "fps": 24}]
    pares = {"DSC_1": [{"outra": "C1", "lag_s": 0.8, "dur_outra_s": 10, "fonte": "relogio"}]}   # só 0,2 s de sobreposição
    assert sr.trechos_sync(v1, pares, 24) == []

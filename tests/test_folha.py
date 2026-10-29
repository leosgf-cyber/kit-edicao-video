import os, pytest
from PIL import Image
from comandos import folha, midia

def test_montar_tamanho_e_arquivo(tmp_path):
    itens = [(f"clipe{i}", Image.new("RGB", (640, 360), (i * 20, 0, 0))) for i in range(9)] + [("sem", None)]
    saida = tmp_path / "f.jpg"
    w, h = folha.montar(itens, str(saida))
    assert (w, h) == (8 * 200 + 9 * 4, 2 * 220 + 3 * 4)       # 10 itens = 2 linhas de 8
    assert Image.open(saida).size == (w, h)

def test_celula_rotulo_longo_nao_estoura():
    c = folha.celula(None, "x" * 60, folha._fonte())
    assert c.size == (200, 220)

def test_main_gera_folha_na_pasta(pasta_clipes, capsys):
    assert folha.main([str(pasta_clipes)]) == 0
    assert os.path.exists(pasta_clipes / "_folha.jpg")
    assert "3 clipes" in capsys.readouterr().out

def test_main_pasta_sem_clipe(tmp_path):
    assert folha.main([str(tmp_path)]) == 1

def test_main_saida_e_pasta_da_erro(pasta_clipes, tmp_path):
    assert folha.main([str(pasta_clipes), "--saida", str(tmp_path)]) == 1

def test_main_saida_pasta_pai_ausente_da_erro(pasta_clipes, tmp_path):
    saida = tmp_path / "nao" / "existe.jpg"
    assert folha.main([str(pasta_clipes), "--saida", str(saida)]) == 1
    assert not os.path.exists(pasta_clipes / "_folha.jpg")

def test_encurta_corta_por_largura():
    fonte = folha._fonte()
    r = folha._encurta("W" * 40, fonte)
    assert r.endswith("…")
    assert fonte.getlength(r) <= 192


def test_colunas_multiplo_de_n():
    assert [folha.colunas(n) for n in (1, 2, 3, 4, 5, 9)] == [8, 8, 6, 8, 5, 9]

def test_main_quadros_3(pasta_clipes, capsys):
    saida = pasta_clipes / "f3.jpg"
    assert folha.main([str(pasta_clipes), "--quadros", "3", "--saida", str(saida)]) == 0
    assert Image.open(saida).size == (6 * 200 + 7 * 4, 2 * 220 + 3 * 4)   # 9 quadros, 2 clipes por linha
    assert "3 clipes" in capsys.readouterr().out

def test_quadros_espalhados(pasta_clipes):
    q = midia.quadros(str(pasta_clipes / "c1.mp4"), 3)
    assert [t for t, _ in q] == [0.5, 1.5, 2.5] and all(img is not None for _, img in q)

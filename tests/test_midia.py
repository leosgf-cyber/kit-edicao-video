import os, wave
from comandos import midia
from tests.conftest import gerar_clipe

def test_listar_ordem_natural_e_ignora_nao_video(pasta_clipes):
    nomes = [os.path.basename(p) for p in midia.listar_clipes(str(pasta_clipes))]
    assert nomes == ["c1.mp4", "c2.mp4", "c10.mp4"]

def test_probe_le_duracao_inicio_fps_audio(pasta_clipes):
    info = midia.probe(str(pasta_clipes / "c1.mp4"))
    assert info["nome"] == "c1" and abs(info["dur"] - 3.0) < 0.2
    assert abs(info["fps"] - 24) < 0.01 and info["tem_audio"] is True
    assert int(info["inicio"]) == 1787757412          # 2026-08-26T15:16:52Z em segundos UTC

def test_probe_sem_audio_e_arquivo_invalido(tmp_path):
    mudo = gerar_clipe(tmp_path / "mudo.mp4", audio=False)
    assert midia.probe(mudo)["tem_audio"] is False
    (tmp_path / "lixo.mp4").write_bytes(b"nao e video")
    assert midia.probe(str(tmp_path / "lixo.mp4")) is None

def test_quadro_e_irmao_mp4(tmp_path):
    gerar_clipe(tmp_path / "DSC_0001.MP4")
    (tmp_path / "DSC_0001.NEV").write_bytes(b"raw que o ffmpeg nao abre")
    img = midia.quadro(str(tmp_path / "DSC_0001.NEV"))
    assert img is not None and img.size == (320, 240)     # veio do irmão .MP4
    (tmp_path / "solto.nev").write_bytes(b"sem irmao")
    assert midia.quadro(str(tmp_path / "solto.nev")) is None

def test_audio_wav(pasta_clipes, tmp_path):
    wav = midia.audio_wav(str(pasta_clipes / "c1.mp4"), str(tmp_path / "c1.wav"))
    assert wav and os.path.getsize(wav) > 8000 * 2 * 2      # ≥ 2 s de int16 mono a 8 kHz
    with wave.open(wav, "rb") as w:
        assert w.getnchannels() == 1
        assert w.getframerate() == 8000
        assert w.getsampwidth() == 2

def test_listar_ignora_subpasta_com_nome_de_video(pasta_clipes):
    (pasta_clipes / "subpasta.mov").mkdir()
    nomes = [os.path.basename(p) for p in midia.listar_clipes(str(pasta_clipes))]
    assert nomes == ["c1.mp4", "c2.mp4", "c10.mp4"]

def test_quadro_clipe_curto(tmp_path):
    curto = gerar_clipe(tmp_path / "curto.mp4", dur=0.2)
    assert midia.quadro(curto) is not None

def test_quadro_pasta_inexistente_nao_lanca_excecao():
    assert midia.quadro("/pasta/que/nao/existe/x.nev") is None

def test_creation_time_sem_fuso_e_tratado_como_utc():
    # O ffmpeg normaliza o creation_time do MP4/MOV pro binario do mvhd (sempre UTC, sempre
    # serializado com "Z" pelo ffprobe): nao ha como um clipe gerado por ele carregar uma tag
    # sem fuso. Testa a funcao pura que interpreta a string, o mesmo codigo que o probe() usa.
    assert int(midia._creation_time_utc("2026-08-26T15:16:52")) == 1787757412

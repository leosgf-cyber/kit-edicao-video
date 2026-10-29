import subprocess, pytest

def gerar_clipe(caminho, dur=3.0, inicio="2026-08-26T15:16:52Z", audio=True, fps=24):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size=320x240:rate={fps}:duration={dur}"]
    if audio: cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}"]
    if inicio: cmd += ["-metadata", f"creation_time={inicio}"]
    cmd += ["-shortest", str(caminho)]
    subprocess.run(cmd, check=True)
    return str(caminho)

@pytest.fixture
def pasta_clipes(tmp_path):
    """c1.mp4, c2.mp4, c10.mp4 (ordem natural: 1, 2, 10) + um .txt que deve ser ignorado."""
    for n in ("c2", "c10", "c1"): gerar_clipe(tmp_path / f"{n}.mp4")
    (tmp_path / "nota.txt").write_text("x")
    return tmp_path

#!/usr/bin/env python3
"""Varre um vídeo quadro a quadro atrás da tela "Media Offline" do Resolve (faixa vinho, quase sem verde e azul; tom de pele e luz quente não passam).
Imprime os trechos (quadro inicial, final, tempo) e a cor média. Uso: acha-offline <video>"""
import subprocess, sys, numpy as np
W, H = 27, 48; f = sys.argv[1]
p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", f, "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
n = 0; ruins = []
num, den = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", f],
                        capture_output=True, text=True).stdout.strip().split("/"); FPS = int(num) / int(den)
while True:
    b = p.stdout.read(W * H * 3)
    if len(b) < W * H * 3: break
    a = np.frombuffer(b, np.uint8).reshape(H, W, 3).astype(int)
    r, g, bl = a[..., 0], a[..., 1], a[..., 2]
    verm = ((r > 50) & (r > g * 3) & (r > bl * 3)).mean()   # tela offline do Resolve 21: vinho quase sem verde/azul
    if verm > 0.15: ruins.append((n, verm, a.reshape(-1, 3).mean(0).round()))
    n += 1
print("quadros:", n, "| suspeitos:", len(ruins))
tr = []
for q, v, m in ruins:
    if tr and q == tr[-1][1] + 1: tr[-1][1] = q
    else: tr.append([q, q, m])
for a, b, m in tr: print(f"  quadros {a}-{b} ({(b-a+1)/FPS:.2f}s) em {a/FPS//60:.0f}:{a/FPS%60:05.2f} cor média {m}")

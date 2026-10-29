"""folha PASTA [--saida ARQUIVO] [--quadros N]: folha de contato, nome embaixo.
1 quadro por clipe (padrão, a 40% da duração, 8 colunas) ou N espalhados pelo clipe, com o tempo no rótulo
e cada clipe começando numa linha só dele quando cabe (colunas = múltiplo de N)."""
import argparse, math, os, sys
from PIL import Image, ImageDraw, ImageFont
from . import midia

LADO, FAIXA, GAP, COLS = 200, 20, 4, 8
FUNDO, CINZA, BRANCO = (34, 34, 34), (90, 90, 90), (255, 255, 255)
FONTE = "/System/Library/Fonts/Helvetica.ttc"

def _fonte():
    try:
        return ImageFont.truetype(FONTE, 15)
    except OSError:
        return ImageFont.load_default(size=15)

def _encurta(rotulo, fonte):
    """Corta `rotulo` até caber em LADO - 8 px, acrescentando '…' só se cortou."""
    if fonte.getlength(rotulo) <= LADO - 8:
        return rotulo
    r = rotulo
    while r and fonte.getlength(r + "…") > LADO - 8:
        r = r[:-1]
    return r + "…"

def celula(img, rotulo, fonte):
    """Célula 200×220: quadro encaixado em 200×200 com barras pretas (ou cartão cinza 'sem prévia') + nome."""
    c = Image.new("RGB", (LADO, LADO + FAIXA), FUNDO); d = ImageDraw.Draw(c)
    if img is None:
        d.rectangle([0, 0, LADO - 1, LADO - 1], fill=CINZA)
        d.text((LADO // 2, LADO // 2), "sem prévia", fill=(220, 220, 220), font=fonte, anchor="mm")
    else:
        q = Image.new("RGB", (LADO, LADO), (0, 0, 0)); t = img.copy(); t.thumbnail((LADO, LADO))
        q.paste(t, ((LADO - t.width) // 2, (LADO - t.height) // 2)); c.paste(q, (0, 0))
    d.text((LADO // 2, LADO + FAIXA // 2), _encurta(rotulo, fonte), fill=BRANCO, font=fonte, anchor="mm")
    return c

def colunas(n_quadros):
    """8 colunas com 1 quadro por clipe; com N, o maior múltiplo de N que cabe em 8 (no mínimo N)."""
    return COLS if n_quadros <= 1 else n_quadros * max(1, COLS // n_quadros)

def mmss(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"

def montar(itens, saida, cols=COLS):
    """itens = [(rotulo, PIL.Image ou None)]. Grava JPEG em `saida`; devolve (largura, altura)."""
    n = len(itens); linhas = math.ceil(n / cols)
    w = cols * LADO + (cols + 1) * GAP; h = linhas * (LADO + FAIXA) + (linhas + 1) * GAP
    f = Image.new("RGB", (w, h), FUNDO); fonte = _fonte()
    for i, (rot, img) in enumerate(itens):
        x = GAP + (i % cols) * (LADO + GAP); y = GAP + (i // cols) * (LADO + FAIXA + GAP)
        f.paste(celula(img, rot, fonte), (x, y))
    f.save(saida, "JPEG", quality=85)
    return w, h

def main(argv=None):
    ap = argparse.ArgumentParser(prog="folha", description="Folha de contato de uma pasta de clipes (1 quadro por clipe).")
    ap.add_argument("pasta", nargs="?", default=".", help="pasta com os clipes (padrão: a atual)")
    ap.add_argument("--saida", help="arquivo JPEG de saída (padrão: <pasta>/_folha.jpg)")
    ap.add_argument("--quadros", type=int, default=1, help="quadros por clipe, espalhados (padrão: 1, a 40%%)")
    a = ap.parse_args(argv); pasta = os.path.abspath(a.pasta)
    if a.quadros < 1:
        print("erro: --quadros tem que ser 1 ou mais"); return 1
    if not os.path.isdir(pasta):
        print(f"erro: pasta não existe: {pasta}"); return 1
    clipes = midia.listar_clipes(pasta)
    if not clipes:
        print(f"erro: nenhum clipe de vídeo em {pasta}"); return 1
    saida = os.path.abspath(a.saida) if a.saida else os.path.join(pasta, "_folha.jpg")
    if os.path.isdir(saida):
        print(f"erro: --saida é uma pasta: {saida}"); return 1
    pasta_saida = os.path.dirname(saida)
    if pasta_saida and not os.path.isdir(pasta_saida):
        print(f"erro: pasta de saída não existe: {pasta_saida}"); return 1
    itens, sem = [], 0
    for c in clipes:
        nome = midia.stem(c)
        if a.quadros == 1:
            pares = [(None, midia.quadro(c))]
        else:
            pares = midia.quadros(c, a.quadros) or [(None, None)] * a.quadros
        for t, img in pares:
            if img is not None: img.thumbnail((LADO, LADO))
            itens.append((nome if t is None else f"{mmss(t)} {nome}", img))
        sem += all(img is None for _, img in pares)
        print(f"  {nome}{'' if pares[0][1] else '  (sem prévia)'}", flush=True)
    montar(itens, saida, colunas(a.quadros))
    print(f"pronto: {len(clipes)} clipes ({sem} sem prévia) → {saida}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

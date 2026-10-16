"""GIF do Perfil C em 3D girando (CFI, IMD e CSE × √peso), para o slide do centroide.

Girar o gráfico mostra a profundidade: um município pode parecer perto do centroide
num ângulo e estar longe em outro eixo.

Uso: python figura_centroide_3d_gif.py <arquivo_saida.gif> [quadros]
"""
import io
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline as p  # noqa: E402

AZUL, FUNDO = "#4496CD", "#1E1E1E"  # fundo = cor do cartão do slide
TXT, MUTED, GRID = "#E6E6E6", "#9AA0A6", "#3A3A3A"
plt.rcParams.update({"font.family": "Inter", "text.color": TXT, "axes.labelcolor": TXT,
                     "xtick.color": MUTED, "ytick.color": MUTED})
fmt = lambda v, d=1: f"{v:.{d}f}".replace(".", ",")  # noqa: E731
QUADROS = int(sys.argv[2]) if len(sys.argv) > 2 else 60

d = p.carregar_dados()
e = p.construir_eixos(d)
r, cent, _ = p.montar_resultado(d, e, np.sqrt(p.PESOS), "raiz")
c = r[r.Perfil == "C"]
cc = cent.loc["C"]
ult = c.sort_values("Ranking_Representatividade").iloc[-1]
destaques = [(c[c.municipio == "Barra Bonita"].iloc[0], "1º", "#FFFFFF"),
             (c[c.municipio == "Sorocaba"].iloc[0], "179º", "#F99828"),
             (ult, "180º", "#C0A2C7")]
cmap = matplotlib.colors.LinearSegmentedColormap.from_list("c", ["#1F3A52", "#4496CD", "#BFE0F5"])


def quadro(azim):
    fig = plt.figure(figsize=(8.6, 6.0), dpi=110, facecolor=FUNDO)
    ax = fig.add_subplot(projection="3d", facecolor=FUNDO)
    ax.set_proj_type("ortho")
    ax.view_init(elev=20, azim=azim)
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.set_pane_color((0, 0, 0, 0))
        a._axinfo["grid"].update(color=GRID, linewidth=0.6)
        a.line.set_color(GRID)
        a.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v)))
        a.set_major_locator(matplotlib.ticker.MultipleLocator(0.5))
    ax.scatter(c.CIF_kmeans, c.IMD_kmeans, c.CSE_kmeans, c=-c.Distancia_Centroide, s=24, cmap=cmap,
               depthshade=False, edgecolor=FUNDO, lw=0.3)
    for m, _, cor in destaques:
        ax.plot([cc.CIF, m.CIF_kmeans], [cc.IMD, m.IMD_kmeans], [cc.CSE, m.CSE_kmeans], color=cor, lw=2.2)
        ax.scatter(m.CIF_kmeans, m.IMD_kmeans, m.CSE_kmeans, s=110, facecolor="none", edgecolor=cor,
                   lw=2, depthshade=False)
    ax.scatter(cc.CIF, cc.IMD, cc.CSE, marker="X", s=340, color=AZUL, edgecolor="white", lw=2,
               depthshade=False)
    ax.set_xlabel("CFI × √0,35", fontsize=11, fontweight="bold", labelpad=6)
    ax.set_ylabel("IMD × √0,40", fontsize=11, fontweight="bold", labelpad=6)
    ax.set_zlabel("CSE × √0,25", fontsize=11, fontweight="bold", labelpad=4)
    ax.tick_params(labelsize=8, pad=0)
    lim = lambda s: (s.min() - 0.15, s.max() + 0.15)  # noqa: E731
    ax.set_xlim(*lim(c.CIF_kmeans))
    ax.set_ylim(*lim(c.IMD_kmeans))
    ax.set_zlim(*lim(c.CSE_kmeans))
    ax.set_box_aspect((np.ptp(c.CIF_kmeans), np.ptp(c.IMD_kmeans), np.ptp(c.CSE_kmeans)), zoom=1.05)
    # legenda fixa no topo (não gira junto com o gráfico)
    fig.text(0.02, 0.975, "Perfil C nos três eixos · cor mais clara = mais perto do centroide · linhas = distância d em linha reta",
             fontsize=10, color=MUTED, va="top")
    itens = [("X", "Centroide do Perfil C (−0,20; 0,76; 0,42)", AZUL)] + [
        ("—", f"{m.municipio}: d = {fmt(m.Distancia_Centroide, 3)} · {pos}", cor) for m, pos, cor in destaques]
    for i, (simb, txt, cor) in enumerate(itens):
        x, y = 0.02 + (i % 2) * 0.49, 0.91 - (i // 2) * 0.05
        fig.text(x, y, simb, fontsize=12, fontweight="bold", color=cor, va="center")
        fig.text(x + 0.03, y, txt, fontsize=10.5, fontweight="bold", color=cor, va="center")
    fig.subplots_adjust(left=0.02, right=0.96, bottom=0.04, top=0.88)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=FUNDO)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


azims = np.linspace(-58, -58 + 360, QUADROS, endpoint=False)
frames = [quadro(a) for a in azims]
paleta = frames[0].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
frames = [f.quantize(palette=paleta, dither=Image.Dither.NONE) for f in frames]
frames[0].save(sys.argv[1], save_all=True, append_images=frames[1:], duration=110, loop=0, optimize=True)
print("ok", len(frames))

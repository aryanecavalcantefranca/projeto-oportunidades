"""Centroide do Perfil C em 3D: os três eixos ponderados (CFI, IMD e CSE × √peso).

A distância ao centroide é a linha reta neste espaço; as linhas desenhadas têm
exatamente o comprimento d informado.

Uso: python figura_centroide_3d.py <arquivo_saida.png>
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d import proj3d

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline as p  # noqa: E402

AZUL = "#4496CD"
TXT, MUTED, GRID = "#E6E6E6", "#9AA0A6", "#3A3A3A"
plt.rcParams.update({"font.family": "Inter", "text.color": TXT, "axes.labelcolor": TXT,
                     "xtick.color": MUTED, "ytick.color": MUTED})
fmt = lambda v, d=1: f"{v:.{d}f}".replace(".", ",")  # noqa: E731

d = p.carregar_dados()
e = p.construir_eixos(d)
r, cent, _ = p.montar_resultado(d, e, np.sqrt(p.PESOS), "raiz")
c = r[r.Perfil == "C"]
cc = cent.loc["C"]

fig = plt.figure(figsize=(8.6, 6.0), dpi=220)
ax = fig.add_subplot(projection="3d")
ax.set_proj_type("ortho")
ax.view_init(elev=18, azim=-58)
for a in (ax.xaxis, ax.yaxis, ax.zaxis):
    a.set_pane_color((0, 0, 0, 0))
    a._axinfo["grid"].update(color=GRID, linewidth=0.6)
    a.line.set_color(GRID)
    a.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v)))
    a.set_major_locator(matplotlib.ticker.MultipleLocator(0.5))

ax.scatter(c.CIF_kmeans, c.IMD_kmeans, c.CSE_kmeans, c=-c.Distancia_Centroide, s=26, depthshade=False,
           cmap=matplotlib.colors.LinearSegmentedColormap.from_list("c", ["#1F3A52", "#4496CD", "#BFE0F5"]),
           edgecolor="#1E1E1E", lw=0.3)

ult = c.sort_values("Ranking_Representatividade").iloc[-1]
destaques = [("Barra Bonita", "1º", (-125, -70)), ("Sorocaba", "179º", (-150, 10)),
             (ult.municipio, "180º", (15, 22))]
for nome, _, _ in destaques:
    m = c[c.municipio == nome].iloc[0]
    ax.plot([cc.CIF, m.CIF_kmeans], [cc.IMD, m.IMD_kmeans], [cc.CSE, m.CSE_kmeans], color="white", lw=1.6)
    ax.scatter(m.CIF_kmeans, m.IMD_kmeans, m.CSE_kmeans, s=110, facecolor="none", edgecolor="white",
               lw=1.6, depthshade=False)
ax.scatter(cc.CIF, cc.IMD, cc.CSE, marker="X", s=380, color=AZUL, edgecolor="white", lw=2,
           depthshade=False)
ax.set_xlabel("CFI × √0,35", fontsize=11.5, fontweight="bold", labelpad=8)
ax.set_ylabel("IMD × √0,40", fontsize=11.5, fontweight="bold", labelpad=8)
ax.set_zlabel("CSE × √0,25", fontsize=11.5, fontweight="bold", labelpad=6)
ax.tick_params(labelsize=8.5, pad=1)
lim = lambda s, pad=0.15: (s.min() - pad, s.max() + pad)  # noqa: E731
ax.set_xlim(*lim(c.CIF_kmeans))
ax.set_ylim(*lim(c.IMD_kmeans))
ax.set_zlim(*lim(c.CSE_kmeans))
ax.set_box_aspect((np.ptp(c.CIF_kmeans), np.ptp(c.IMD_kmeans), np.ptp(c.CSE_kmeans)))
fig.canvas.draw()


def rotulo(x, y, z, texto, off, cor="white"):
    x2, y2, _ = proj3d.proj_transform(x, y, z, ax.get_proj())
    ax.annotate(texto, (x2, y2), xytext=off, textcoords="offset points", fontsize=10.5, fontweight="bold",
                color=cor, arrowprops=dict(arrowstyle="-", color=cor, lw=0.8), zorder=10)


for nome, pos, off in destaques:
    m = c[c.municipio == nome].iloc[0]
    rotulo(m.CIF_kmeans, m.IMD_kmeans, m.CSE_kmeans,
           f"{nome}\nd = {fmt(m.Distancia_Centroide, 3)} · {pos}", off)
rotulo(cc.CIF, cc.IMD, cc.CSE, "Centroide C\n(−0,20; 0,76; 0,42)", (70, -60), AZUL)
fig.text(0.02, 0.97, "Perfil C · cada ponto é um município nos três eixos · cor mais clara = mais perto do centroide",
         fontsize=10, color=MUTED, va="top")
fig.text(0.02, 0.925, "Cada linha branca é a distância d em linha reta, considerando CFI, IMD e CSE",
         fontsize=10, color=MUTED, va="top")
fig.subplots_adjust(left=0.0, right=0.97, bottom=0.02, top=0.95)
fig.savefig(sys.argv[1], transparent=True)
print("ok")

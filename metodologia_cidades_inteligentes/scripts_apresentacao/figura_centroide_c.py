"""Figura do slide "Como funciona o ranking pelo centroide" (versão 2): só o Perfil C.

Mostra o centroide do Perfil C, a distância de Barra Bonita (mais típica) e de
Sorocaba, com os componentes ΔCFI e ΔIMD da distância desenhados.

Uso: python figura_centroide_c.py <arquivo_saida.png>
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline as p  # noqa: E402

AZUL, LAR = "#4496CD", "#F99828"
TXT, MUTED, GRID = "#E6E6E6", "#9AA0A6", "#333333"
plt.rcParams.update({"font.family": "Inter", "text.color": TXT, "axes.labelcolor": TXT,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": GRID})
fmt = lambda v, d=2: f"{v:.{d}f}".replace(".", ",")  # noqa: E731

d = p.carregar_dados()
e = p.construir_eixos(d)
r, cent, _ = p.montar_resultado(d, e, np.sqrt(p.PESOS), "raiz")
c = r[r.Perfil == "C"]
cc = cent.loc["C"]

fig, ax = plt.subplots(figsize=(8.6, 6.0), dpi=220)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.grid(color=GRID, lw=0.6)
ax.set_axisbelow(True)
ax.scatter(c.CIF_kmeans, c.IMD_kmeans, s=40, color=AZUL, alpha=0.55, lw=0, zorder=2)
for raio in (0.25, 0.5, 0.75):
    ax.add_patch(plt.Circle((cc.CIF, cc.IMD), raio, fill=False, color=AZUL, lw=0.9, ls=(0, (3, 3)),
                            alpha=0.9, zorder=3))

bb = c[c.municipio == "Barra Bonita"].iloc[0]
so = c[c.municipio == "Sorocaba"].iloc[0]
# Barra Bonita: perto do centroide
ax.plot([cc.CIF, bb.CIF_kmeans], [cc.IMD, bb.IMD_kmeans], color="white", lw=1.6, zorder=4)
ax.scatter(bb.CIF_kmeans, bb.IMD_kmeans, s=100, color=AZUL, edgecolor="white", lw=1.6, zorder=5)
ax.annotate(f"Barra Bonita\nd = {fmt(bb.Distancia_Centroide, 3)} · 1º (mais típica)",
            (bb.CIF_kmeans, bb.IMD_kmeans), (bb.CIF_kmeans - 0.62, bb.IMD_kmeans - 0.62), fontsize=11.5,
            fontweight="bold", color="white", arrowprops=dict(arrowstyle="-", color="white", lw=0.8), zorder=6)
# Sorocaba: longe, com ΔCFI e ΔIMD
ax.plot([cc.CIF, so.CIF_kmeans], [cc.IMD, so.IMD_kmeans], color="white", lw=1.6, zorder=4)
ax.plot([cc.CIF, so.CIF_kmeans], [cc.IMD, cc.IMD], color=LAR, lw=1.8, ls=(0, (4, 3)), zorder=4)
ax.plot([so.CIF_kmeans, so.CIF_kmeans], [cc.IMD, so.IMD_kmeans], color=LAR, lw=1.8, ls=(0, (4, 3)), zorder=4)
ax.text((cc.CIF + so.CIF_kmeans) / 2, cc.IMD - 0.06, f"ΔCFI = {fmt(so.CIF_kmeans - cc.CIF)}", ha="center",
        va="top", fontsize=10.5, color=LAR, fontweight="bold")
ax.text(so.CIF_kmeans - 0.04, (cc.IMD + so.IMD_kmeans) / 2 + 0.35, f"ΔIMD = +{fmt(so.IMD_kmeans - cc.IMD)}",
        ha="right", va="center", fontsize=10.5, color=LAR, fontweight="bold")
ax.scatter(so.CIF_kmeans, so.IMD_kmeans, s=100, color=AZUL, edgecolor="white", lw=1.6, zorder=5)
ax.annotate(f"Sorocaba\nd = {fmt(so.Distancia_Centroide, 3)} · 179º", (so.CIF_kmeans, so.IMD_kmeans),
            (so.CIF_kmeans + 0.25, so.IMD_kmeans - 0.15), fontsize=11.5, fontweight="bold", color="white",
            arrowprops=dict(arrowstyle="-", color="white", lw=0.8), zorder=6)

ax.scatter(cc.CIF, cc.IMD, marker="X", s=380, color=AZUL, edgecolor="white", lw=2, zorder=7)
ax.annotate(f"Centroide C\n({fmt(cc.CIF)}; {fmt(cc.IMD)}; {fmt(cc.CSE)})", (cc.CIF, cc.IMD),
            (cc.CIF + 0.45, cc.IMD - 0.45), fontsize=11.5, fontweight="bold", color=AZUL,
            arrowprops=dict(arrowstyle="-", color=AZUL, lw=0.8), zorder=8)

ax.set_xlabel("Capacidade Fiscal e Institucional (CFI × √0,35)", fontsize=12, fontweight="bold")
ax.set_ylabel("Infraestrutura e Maturidade Digital (IMD × √0,40)", fontsize=12, fontweight="bold")
ax.tick_params(labelsize=10)
for f in (ax.xaxis, ax.yaxis):
    f.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v, 1)))
for f in (ax.xaxis, ax.yaxis):
    f.set_major_locator(matplotlib.ticker.MultipleLocator(0.5))
ax.set_ylim(-0.1, 2.4)
ax.set_aspect("equal", adjustable="datalim")
ax.text(0.01, 0.995, "Perfil C · cada ponto é um município · círculos = mesma distância ao centroide",
        transform=ax.transAxes, fontsize=10, color=MUTED, va="top")
ax.text(0.99, 0.01, "O gráfico mostra 2 eixos; o 3º (CSE) também entra no cálculo da distância",
        transform=ax.transAxes, fontsize=10, color=MUTED, va="bottom", ha="right")
fig.tight_layout()
fig.savefig(sys.argv[1], transparent=True)
print("ok")

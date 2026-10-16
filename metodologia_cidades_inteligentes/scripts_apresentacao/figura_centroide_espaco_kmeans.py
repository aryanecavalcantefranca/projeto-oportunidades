"""Dispersão do Perfil C para o slide do centroide: estrutura visual do gráfico do IAP,
mas no espaço em que a distância é calculada (eixos × √peso), com o centroide e
círculos de mesma distância. A cor indica a distância ao centroide (três eixos).

Uso: python figura_centroide_espaco_kmeans.py <arquivo_saida.png>
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline as p  # noqa: E402

AZUL = "#4496CD"
TXT, MUTED, GRID = "#E6E6E6", "#9AA0A6", "#333333"
plt.rcParams.update({"font.family": "Inter", "text.color": TXT, "axes.labelcolor": TXT,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": GRID})
fmt = lambda v, d=1: f"{v:.{d}f}".replace(".", ",")  # noqa: E731

d = p.carregar_dados()
e = p.construir_eixos(d)
r, _, _ = p.montar_resultado(d, e, np.sqrt(p.PESOS), "raiz")
c = r[r.Perfil == "C"].copy()
c["x"] = c.CIF_kmeans
c["y"] = c.IMD_kmeans
cx, cy = c.x.mean(), c.y.mean()  # centroide do Perfil C (= centroide do K-Means)

fig, ax = plt.subplots(figsize=(8.6, 6.0), dpi=220)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.grid(color=GRID, lw=0.6)
ax.set_axisbelow(True)
x0, x1 = -1.6, 2.35
y0, y1 = -0.4, 2.45
ax.set_xlim(x0, x1)
ax.set_ylim(y0, y1)
ax.set_aspect("equal")
for raio in (0.25, 0.5, 0.75):  # mesma distância no plano dos dois eixos
    ax.add_patch(plt.Circle((cx, cy), raio, fill=False, color=AZUL, lw=0.9, ls=(0, (3, 3)), alpha=0.9,
                            zorder=2))
    ax.text(cx, cy - raio - 0.02, f"d = {fmt(raio, 2)}", fontsize=9, color=AZUL, ha="center", va="top",
            zorder=2, bbox=dict(boxstyle="round,pad=0.1", fc="#1E1E1E", ec="none"))

ax.axvline(0, color=TXT, lw=1, alpha=0.55, zorder=1)
ax.axhline(0, color=TXT, lw=1, alpha=0.55, zorder=1)
ax.text(0.04, y0 + 0.06, "média do Estado", fontsize=9.5, color=MUTED, va="bottom")
ax.text(x1 - 0.03, 0.04, "média do Estado", fontsize=9.5, color=MUTED, va="bottom", ha="right")

# cor = distância ao centroide (mais clara = mais perto = mais típico)
ax.scatter(c.x, c.y, c=-c.Distancia_Centroide, s=50, edgecolor="#1E1E1E", lw=0.5, zorder=3,
           cmap=matplotlib.colors.LinearSegmentedColormap.from_list("c", ["#1F3A52", "#4496CD", "#BFE0F5"]))

ult = c.sort_values("Ranking_Representatividade").iloc[-1]
rot = {"Barra Bonita": ((-0.75, -0.95), "Barra Bonita\nd = {d} · 1º"),
       "Sorocaba": ((-1.05, -0.2), "Sorocaba\nd = {d} · 179º"),
       ult.municipio: ((0.25, -0.05), ult.municipio + "\nd = {d} · 180º")}
for nome, ((dx, dy), texto) in rot.items():
    m = c[c.municipio == nome].iloc[0]
    ax.plot([cx, m.x], [cy, m.y], color="white", lw=1.4, zorder=4)
    ax.scatter(m.x, m.y, s=130, facecolor="none", edgecolor="white", lw=1.6, zorder=5)
    ax.annotate(texto.format(d=fmt(m.Distancia_Centroide, 3)), (m.x, m.y), (m.x + dx, m.y + dy),
                fontsize=11.5, fontweight="bold", color="white",
                arrowprops=dict(arrowstyle="-", color="white", lw=0.8), zorder=6)

ax.scatter(cx, cy, marker="X", s=420, color=AZUL, edgecolor="white", lw=2, zorder=7)
ax.annotate("Centroide do Perfil C\n(−0,20; 0,76; 0,42)", (cx, cy), (cx + 1.25, cy - 0.35),
            fontsize=11.5, fontweight="bold", color=AZUL,
            arrowprops=dict(arrowstyle="-", color=AZUL, lw=0.9), zorder=8)

ax.set_xlabel("Capacidade Fiscal e Institucional (CFI × √0,35)", fontsize=12, fontweight="bold",
              labelpad=22)
ax.set_ylabel("Infraestrutura e Maturidade Digital\n(IMD × √0,40)", fontsize=12, fontweight="bold", labelpad=8)
ax.text(0.0, -0.075, "◀ abaixo da média", transform=ax.transAxes, fontsize=10, color=MUTED, va="top")
ax.text(1.0, -0.075, "acima da média ▶", transform=ax.transAxes, fontsize=10, color=MUTED, va="top",
        ha="right")
ax.tick_params(labelsize=10)
for f in (ax.xaxis, ax.yaxis):
    f.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v)))
ax.text(0.01, 0.995, "Perfil C · cada ponto é um município · cor mais clara = mais perto do centroide",
        transform=ax.transAxes, fontsize=10, color=MUTED, va="top")
ax.text(0.01, 0.945, "Círculos: distância nos 2 eixos do gráfico · d inclui também o CSE", transform=ax.transAxes,
        fontsize=10, color=MUTED, va="top")
fig.tight_layout()
fig.savefig(sys.argv[1], transparent=True)
print("ok")

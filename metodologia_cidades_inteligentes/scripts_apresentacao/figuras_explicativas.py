"""Figuras dos slides explicativos (ranking por IAP e por centroide).

Uso: python figuras_explicativas.py <pasta_saida>
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline as p  # noqa: E402

OUT = Path(sys.argv[1])
COR = {"A": "#F99828", "B": "#7C8EC9", "C": "#4496CD", "D": "#9D4EDD"}
TXT, MUTED, GRID = "#E6E6E6", "#9AA0A6", "#3A3A3A"
plt.rcParams.update({"font.family": "Inter", "font.size": 13, "text.color": TXT,
                     "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.edgecolor": GRID})

d = p.carregar_dados()
e = p.construir_eixos(d)
r, cent, _ = p.montar_resultado(d, e, np.sqrt(p.PESOS), "raiz")


def eixo_base(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(color=GRID, lw=0.6)
    ax.set_axisbelow(True)


# ------------------------------------------------------------------ IAP
c = r[r["Perfil"] == "C"].copy()
c["x"] = c["CIF_z"]
c["y"] = 0.40 * c["IMD_z"] + 0.25 * c["CSE_z"]  # IAP_C = -0,35*CFI + y

fig, ax = plt.subplots(figsize=(8.6, 6.0), dpi=200)
eixo_base(ax)
xs = np.linspace(c.x.min() - 0.3, c.x.max() + 0.3, 50)
for k in np.arange(-0.5, 2.6, 0.5):  # linhas de mesmo IAP
    ax.plot(xs, 0.35 * xs + k, color=GRID, lw=1, ls=(0, (4, 4)), zorder=1)
sc = ax.scatter(c.x, c.y, c=c.IAP, cmap=matplotlib.colors.LinearSegmentedColormap.from_list(
    "c", ["#1F3A52", "#4496CD", "#BFE0F5"]), s=46, edgecolor="#1E1E1E", lw=0.5, zorder=3)
ax.set_xlim(c.x.min() - 0.35, c.x.max() + 0.35)
ax.set_xlabel("Capacidade Fiscal e Institucional (CFI)  →  maior", fontsize=12)
ax.set_ylabel("Digital + socioeconômico (0,40·IMD + 0,25·CSE)  →  maior", fontsize=12)

lbl = {"Sorocaba": "Sorocaba · IAP 1,939 · 1º", "Barra Bonita": "Barra Bonita · IAP 1,040 · 51º"}
ult = c.sort_values("Ranking").iloc[-1]
lbl[ult.municipio] = f"{ult.municipio} · IAP {ult.IAP:.3f} · {ult.Ranking}º".replace(".", ",")
off = {"Sorocaba": (0.25, -0.15), "Barra Bonita": (0.45, -0.25), ult.municipio: (-1.45, -0.55)}
for nome, texto in lbl.items():
    m = c[c.municipio == nome].iloc[0]
    dx, dy = off.get(nome, (0.25, 0.2))
    ax.scatter(m.x, m.y, s=120, facecolor="none", edgecolor="white", lw=1.6, zorder=4)
    ax.annotate(texto, (m.x, m.y), (m.x + dx, m.y + dy), fontsize=12, fontweight="bold", color="white",
                arrowprops=dict(arrowstyle="-", color="white", lw=0.8), zorder=5)
# seta da direção do perfil C (−CFI, +IMD, +CSE)
x0, y0 = c.x.max() - 0.05, c.y.min() - 1.05
v = np.array([-0.35, 1.0]); v = v / np.linalg.norm(v) * 1.15
ax.annotate("", (x0 + v[0], y0 + v[1]), (x0, y0),
            arrowprops=dict(arrowstyle="-|>,head_width=0.4,head_length=0.8", color="#F99828", lw=2.5))
ax.text(x0 - 0.1, y0 + 0.05, "direção do perfil C:\nIAP maior", color="#F99828", fontsize=12,
        fontweight="bold", ha="right", va="bottom")
ax.set_ylim(c.y.min() - 1.35, c.y.max() + 0.5)
ax.text(0.01, 0.99, "Perfil C (180 municípios) · linhas tracejadas = mesmo IAP · cor mais clara = IAP maior", transform=ax.transAxes,
        fontsize=11, color=MUTED, va="top")
fig.tight_layout()
fig.savefig(OUT / "fig_iap.png", transparent=True)
plt.close(fig)

# ------------------------------------------------------------------ Centroide
fig, ax = plt.subplots(figsize=(8.6, 6.0), dpi=200)
eixo_base(ax)
for k in "ABDC":  # C por último (destaque)
    g = r[r.Perfil == k]
    ax.scatter(g.CIF_kmeans, g.IMD_kmeans, s=22 if k != "C" else 30, color=COR[k],
               alpha=0.28 if k != "C" else 0.55, lw=0, zorder=2)
cc = cent.loc["C"]
for raio in (0.25, 0.5, 0.75):
    ax.add_patch(plt.Circle((cc.CIF, cc.IMD), raio, fill=False, color=COR["C"], lw=0.9, ls=(0, (3, 3)),
                            alpha=0.8, zorder=3))
for nome, cor_l in (("Barra Bonita", "#FFFFFF"), ("Sorocaba", "#FFFFFF")):
    m = r[r.municipio == nome].iloc[0]
    ax.plot([cc.CIF, m.CIF_kmeans], [cc.IMD, m.IMD_kmeans], color=cor_l, lw=1.6, zorder=4)
    ax.scatter(m.CIF_kmeans, m.IMD_kmeans, s=90, color=COR["C"], edgecolor="white", lw=1.6, zorder=5)
    txt = (f"{nome}\nd = {m.Distancia_Centroide:.3f} · {m.Ranking_Representatividade}º").replace(".", ",")
    pos = {"Barra Bonita": (cc.CIF - 0.75, cc.IMD - 0.55), "Sorocaba": (m.CIF_kmeans + 0.45, m.IMD_kmeans - 0.2)}[nome]
    ax.annotate(txt, (m.CIF_kmeans, m.IMD_kmeans), pos, fontsize=12, fontweight="bold", color="white",
                arrowprops=dict(arrowstyle="-", color="white", lw=0.8), zorder=6)
for k, row in cent.iterrows():
    ax.scatter(row.CIF, row.IMD, marker="X", s=330, color=COR[k], edgecolor="white", lw=1.8, zorder=7)
    dx, dy, ha = {"A": (-0.12, -0.2, "right"), "B": (0.12, -0.2, "left")}.get(k, (0.15, -0.16, "left"))
    ax.text(row.CIF + dx, row.IMD + dy, f"Centroide {k}", fontsize=12, fontweight="bold", color=COR[k],
            ha=ha, zorder=8)
ax.set_xlabel("Capacidade Fiscal e Institucional (CFI × √0,35)", fontsize=12)
ax.set_ylabel("Infraestrutura e Maturidade Digital (IMD × √0,40)", fontsize=12)
ax.text(0.99, 0.01, "Projeção em dois eixos · a distância é calculada nos três (CFI, IMD e CSE)",
        transform=ax.transAxes, fontsize=11, color=MUTED, va="bottom", ha="right")
ax.set_aspect("equal", adjustable="datalim")
fig.tight_layout()
fig.savefig(OUT / "fig_centroide.png", transparent=True)
plt.close(fig)
print("ok", c.sort_values("Ranking").iloc[-1].municipio)

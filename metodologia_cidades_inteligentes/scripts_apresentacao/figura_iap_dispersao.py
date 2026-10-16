"""Dispersão do Perfil C para o slide "Como funciona o ranking pelo IAP" (versão 2).

Eixos explicados (o que é cada um e onde fica a média do Estado) e linhas de
mesmo IAP rotuladas com o valor, no lugar da seta de direção.

Uso: python figura_iap_dispersao.py <arquivo_saida.png>
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline as p  # noqa: E402

TXT, MUTED, GRID, LINHA = "#E6E6E6", "#9AA0A6", "#333333", "#6B6B6B"
plt.rcParams.update({"font.family": "Inter", "text.color": TXT, "axes.labelcolor": TXT,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": GRID})
fmt = lambda v, d=1: f"{v:.{d}f}".replace(".", ",")  # noqa: E731

d = p.carregar_dados()
e = p.construir_eixos(d)
r, _, _ = p.montar_resultado(d, e, np.sqrt(p.PESOS), "raiz")
c = r[r.Perfil == "C"].copy()
c["x"] = c.CIF_z
c["y"] = 0.40 * c.IMD_z + 0.25 * c.CSE_z  # IAP_C = -0,35·CFI + y

fig, ax = plt.subplots(figsize=(8.6, 6.0), dpi=220)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.grid(color=GRID, lw=0.6)
ax.set_axisbelow(True)
x0, x1 = c.x.min() - 0.35, c.x.max() + 0.55
y0, y1 = c.y.min() - 0.55, c.y.max() + 0.45
ax.set_xlim(x0, x1)
ax.set_ylim(y0, y1)

# linhas de mesmo IAP, rotuladas onde cada uma entra no gráfico
ang = np.degrees(np.arctan(0.35 * (6.0 / 8.6) * (x1 - x0) / (y1 - y0)))
xs = np.linspace(x0, x1, 50)
for k in np.arange(0.0, 2.6, 0.5):
    ax.plot(xs, 0.35 * xs + k, color=LINHA, lw=1, ls=(0, (4, 4)), zorder=1)
    xl = x0 + 0.05 if k > 0 else 1.4  # IAP 0: rótulo à direita, longe dos nomes
    yl = 0.35 * xl + k
    if y0 + 0.05 < yl < y1 - 0.45:
        ax.text(xl, yl + 0.04, f"IAP {fmt(k)}", ha="left", va="bottom", fontsize=9.5, color=MUTED,
                rotation=ang, rotation_mode="anchor", zorder=2)

# média do Estado (escore-z = 0) nos dois eixos
ax.axvline(0, color=TXT, lw=1, alpha=0.55, zorder=1)
ax.axhline(0, color=TXT, lw=1, alpha=0.55, zorder=1)
ax.text(0.04, y0 + 0.06, "média do Estado", fontsize=9.5, color=MUTED, va="bottom")
ax.text(x1 - 0.03, 0.04, "média do Estado", fontsize=9.5, color=MUTED, va="bottom", ha="right")

ax.scatter(c.x, c.y, c=c.IAP, s=50, edgecolor="#1E1E1E", lw=0.5, zorder=3,
           cmap=matplotlib.colors.LinearSegmentedColormap.from_list("c", ["#1F3A52", "#4496CD", "#BFE0F5"]))

ult = c.sort_values("Ranking").iloc[-1]
rot = {"Sorocaba": ((0.3, -0.12), "Sorocaba · IAP 1,939 · 1º"),
       "Barra Bonita": ((0.45, -0.22), "Barra Bonita · IAP 1,040 · 51º"),
       ult.municipio: ((-1.4, -0.4), f"{ult.municipio} · IAP {fmt(ult.IAP, 3)} · {ult.Ranking}º")}
for nome, ((dx, dy), texto) in rot.items():
    m = c[c.municipio == nome].iloc[0]
    ax.scatter(m.x, m.y, s=130, facecolor="none", edgecolor="white", lw=1.6, zorder=4)
    ax.annotate(texto, (m.x, m.y), (m.x + dx, m.y + dy), fontsize=11.5, fontweight="bold", color="white",
                arrowprops=dict(arrowstyle="-", color="white", lw=0.8), zorder=5)

ax.set_xlabel("Capacidade Fiscal e Institucional (CFI)", fontsize=12, fontweight="bold", labelpad=22)
ax.set_ylabel("Infraestrutura digital + condição socioeconômica\n(0,40 × IMD + 0,25 × CSE)", fontsize=12,
              fontweight="bold", labelpad=8)
ax.text(0.0, -0.075, "◀ abaixo da média", transform=ax.transAxes, fontsize=10, color=MUTED, va="top")
ax.text(1.0, -0.075, "acima da média ▶", transform=ax.transAxes, fontsize=10, color=MUTED, va="top",
        ha="right")
ax.tick_params(labelsize=10)
for f in (ax.xaxis, ax.yaxis):
    f.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v)))
ax.text(0.01, 0.995, "Perfil C · cada ponto é um município (escore-z) · cor mais clara = IAP maior",
        transform=ax.transAxes, fontsize=10, color=MUTED, va="top")
fig.tight_layout()
fig.savefig(sys.argv[1], transparent=True)
print("ok")

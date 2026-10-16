"""Figura didática do IAP: o índice como soma de três pedaços (um por eixo).

Uso: python figura_iap_barras.py <arquivo_saida.png>
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline as p  # noqa: E402

TONS = {"CFI": "#2A6E9E", "IMD": "#4496CD", "CSE": "#9CCBEA"}  # Perfil C: escuro, médio, claro
SINAL = {"CFI": -1, "IMD": +1, "CSE": +1}
TXT, MUTED, GRID = "#E6E6E6", "#9AA0A6", "#3A3A3A"
plt.rcParams.update({"font.family": "Inter", "text.color": TXT, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.edgecolor": GRID})
br = lambda v, d=2: f"{v:+.{d}f}".replace(".", ",")  # noqa: E731

d = p.carregar_dados()
e = p.construir_eixos(d)
r, _, _ = p.montar_resultado(d, e, np.sqrt(p.PESOS), "raiz")
c = r[r.Perfil == "C"]
exemplos = [c[c.municipio == m].iloc[0] for m in ("Sorocaba", "Barra Bonita", "Itapevi")]

fig, ax = plt.subplots(figsize=(8.6, 6.0), dpi=220)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.axvline(0, color=MUTED, lw=1.2, zorder=1)
ax.grid(axis="x", color=GRID, lw=0.6)
ax.set_axisbelow(True)

ys = [2.0, 1.0, 0.0]
h = 0.40
for y, m in zip(ys, exemplos):
    pos, neg = 0.0, 0.0
    for eixo in ("CFI", "IMD", "CSE"):
        v = SINAL[eixo] * m[f"{'CIF' if eixo == 'CFI' else eixo}_pond"]
        x0 = pos if v >= 0 else neg + v
        ax.barh(y + 0.12, abs(v), left=x0, height=h, color=TONS[eixo], edgecolor="#1E1E1E", lw=1.2, zorder=2)
        cor = "#1E1E1E" if eixo == "CSE" else "white"
        if abs(v) >= 0.2:
            ax.text(x0 + abs(v) / 2, y + 0.12, f"{eixo}\n{br(v)}", ha="center", va="center", fontsize=11,
                    fontweight="bold", color=cor, zorder=3, linespacing=1.1)
        else:  # pedaço pequeno: rótulo fora, à esquerda
            ax.annotate(f"{eixo} {br(v)}", (x0, y + 0.12), (x0 - 0.05, y + h / 2 + 0.22), ha="right",
                        fontsize=10, fontweight="bold", color=TXT,
                        arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
        if v >= 0:
            pos += v
        else:
            neg += v
    ax.barh(y - 0.23, m.IAP, left=0, height=0.13, color="#F99828", zorder=2)
    ax.text(m.IAP + 0.06, y - 0.23, f"= IAP {m.IAP:.2f}".replace(".", ","), va="center", fontsize=13,
            fontweight="bold", color="#F99828")
    ax.text(-0.62, y + 0.05, f"{m.Ranking}º", ha="right", va="bottom", fontsize=18, fontweight="bold",
            color="white")
    ax.text(-0.62, y - 0.03, m.municipio, ha="right", va="top", fontsize=11, color=MUTED)

ax.set_yticks([])
ax.set_xlim(-1.35, 2.55)
ax.set_ylim(-0.75, 2.6)
ax.set_xticks(np.arange(-0.5, 2.6, 0.5))
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.1f}".replace(".", ",")))
ax.tick_params(axis="x", labelsize=10)
ax.text(-0.04, -0.62, "◀ tira pontos", ha="right", fontsize=11, color=MUTED)
ax.text(0.04, -0.62, "soma pontos ▶", ha="left", fontsize=11, color=MUTED)
ax.text(0.99, 0.995, "Pedaço = peso × escore do eixo, com o sinal do perfil (−CFI, +IMD, +CSE)",
        transform=ax.transAxes, ha="right", va="top", fontsize=10.5, color=MUTED)
fig.tight_layout()
fig.savefig(sys.argv[1], transparent=True)
print("ok")

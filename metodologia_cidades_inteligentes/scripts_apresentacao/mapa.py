import json, sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
sys.path.insert(0, "/home/user/projeto-oportunidades/metodologia_cidades_inteligentes")
import pipeline as p

P = "/tmp/claude-0/-home-user-projeto-oportunidades/400bee1b-8845-51fa-ac8a-89e34a1e2071/scratchpad/ppt/"
COR = {"A": "#F99828", "B": "#263253", "C": "#4496CD", "D": "#9D4EDD"}
W, H = 11692, 8267
BBOX = (245, 590, 11486, 7543)  # área do mapa na imagem original (px)

def desenhar(perfil: dict, saida: str, escala=0.5):
    gj = json.load(open(P + "sp.geojson"))
    polys, cores = [], []
    for f in gj["features"]:
        cod = int(f["properties"]["id"])
        g = f["geometry"]
        partes = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for parte in partes:
            polys.append(np.array(parte[0]))
            cores.append(COR.get(perfil.get(cod), (0, 0, 0, 0)))
    allp = np.vstack(polys)
    x0, y0 = allp.min(0); x1, y1 = allp.max(0)
    w, h = W * escala, H * escala
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    # posiciona o eixo para o mapa ocupar o mesmo BBOX da imagem original
    l, t, r, b = BBOX
    ax = fig.add_axes([l / W, 1 - b / H, (r - l) / W, (b - t) / H])
    ax.add_collection(PolyCollection(polys, facecolors=cores, edgecolors="white",
                                     linewidths=1.1 * escala * 2))
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.axis("off")
    fig.savefig(saida, transparent=True, dpi=100)

d = p.carregar_dados(); e = p.construir_eixos(d)
fator = np.sqrt(p.PESOS) if sys.argv[1] == "raiz" else p.PESOS
r, _, _ = p.montar_resultado(d, e, fator, "x")
desenhar(dict(zip(r.cod_ibge, r.Perfil)), sys.argv[2])

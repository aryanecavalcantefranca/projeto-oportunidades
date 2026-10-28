"""Proposta (em teste): seleção por diversidade dentro dos perfis.

1. Perfis: K-Means (K=4) com pesos 30% CFI / 40% IMD / 30% CSE, aplicados como √peso
   (peso efetivo na distância = peso definido).
2. Subgrupos: em cada perfil, novo K-Means no mesmo espaço ponderado. O número de
   subgrupos (k) é escolhido entre 2 e 5 pela silhueta: descartam-se opções com algum
   subgrupo menor que TAM_MIN municípios e fica-se com o menor k cuja silhueta esteja a
   até TOL da melhor (parcimônia).
3. Vagas: as vagas do perfil são divididas igualmente entre os subgrupos; a sobra vai
   para os subgrupos maiores. Se um subgrupo tiver menos municípios que vagas, o
   excedente é repassado aos demais.
4. Seleção: em cada subgrupo, os municípios mais próximos do centroide do subgrupo
   (os mais representativos daquele "tipo" de município).

Uso:
    python diversidade_subgrupos.py
"""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

import pipeline as p

PESOS = np.array([0.30, 0.40, 0.30])
K_MIN, K_MAX, TOL, TAM_MIN = 2, 5, 0.01, 10
SAIDA = p.RESULTADOS / "diversidade_30_40_30"
EIXOS_K = ["CIF_kmeans", "IMD_kmeans", "CSE_kmeans"]
NOME_EIXO = {"CIF": "CFI", "IMD": "IMD", "CSE": "CSE"}


def escolher_k(X):
    diag = []
    for k in range(K_MIN, K_MAX + 1):
        km = KMeans(n_clusters=k, random_state=42, n_init=50).fit(X)
        tam = np.bincount(km.labels_)
        diag.append({"k": k, "silhueta": silhouette_score(X, km.labels_), "menor_subgrupo": int(tam.min()),
                     "tamanhos": " / ".join(str(t) for t in sorted(tam, reverse=True))})
    diag = pd.DataFrame(diag)
    validos = diag[diag.menor_subgrupo >= TAM_MIN]
    melhor = validos.silhueta.max()
    k = int(validos[validos.silhueta >= melhor - TOL].k.min())
    diag["escolhido"] = diag.k == k
    return k, diag


def dividir_vagas(tamanhos: pd.Series, vagas: int) -> pd.Series:
    """Partes iguais; sobra para os maiores; respeita o tamanho de cada subgrupo."""
    k = len(tamanhos)
    alvo = pd.Series(vagas // k, index=tamanhos.index)
    for s in tamanhos.sort_values(ascending=False).index[: vagas % k]:
        alvo[s] += 1
    excesso = (alvo - tamanhos).clip(lower=0).sum()
    alvo = alvo.clip(upper=tamanhos)
    while excesso > 0:  # repassa a quem ainda tem municípios
        livres = (tamanhos - alvo)[lambda s: s > 0].sort_values(ascending=False)
        alvo[livres.index[0]] += 1
        excesso -= 1
    return alvo


def descrever(sub_z, grupo_z):
    """Traço do subgrupo: eixo em que mais se diferencia da média do próprio perfil."""
    dif = sub_z - grupo_z
    e = dif.abs().idxmax()
    sentido = "mais alto" if dif[e] > 0 else "mais baixo"
    return f"{NOME_EIXO[e.replace('_z', '')]} {sentido} que a média do perfil ({dif[e]:+.2f}σ)".replace(".", ",")


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    d = p.carregar_dados()
    e = p.construir_eixos(d)
    r, cent, met = p.montar_resultado(d, e, np.sqrt(PESOS), "30/40/30", pesos=PESOS)
    vig, _, _ = p.montar_resultado(d, e, np.sqrt(p.PESOS), "vigente")

    diags, subs, partes = [], [], []
    for perfil, g in r.groupby("Perfil"):
        g = g.copy()
        X = g[EIXOS_K].to_numpy()
        k, diag = escolher_k(X)
        diags.append(diag.assign(Perfil=perfil))
        km = KMeans(n_clusters=k, random_state=42, n_init=50).fit(X)
        # numera subgrupos do maior para o menor (A1, A2, ...)
        ordem = pd.Series(km.labels_).value_counts().index
        mapa = {lab: f"{perfil}{i + 1}" for i, lab in enumerate(ordem)}
        g["Subgrupo"] = [mapa[l] for l in km.labels_]
        cent_sub = {mapa[l]: c for l, c in enumerate(km.cluster_centers_)}
        g["Dist_centroide_subgrupo"] = [np.linalg.norm(x - cent_sub[s]) for x, s in zip(X, g.Subgrupo)]
        g["Rank_no_subgrupo"] = g.groupby("Subgrupo").Dist_centroide_subgrupo.rank(method="first").astype(int)
        tam = g.Subgrupo.value_counts().sort_index()
        vagas = dividir_vagas(tam, p.VAGAS[perfil])
        g["Vagas_subgrupo"] = g.Subgrupo.map(vagas)
        g["Selecionado"] = g.Rank_no_subgrupo <= g.Vagas_subgrupo
        grupo_z = g[["CIF_z", "IMD_z", "CSE_z"]].mean()
        for s, gs in g.groupby("Subgrupo"):
            sz = gs[["CIF_z", "IMD_z", "CSE_z"]].mean()
            subs.append({"Perfil": perfil, "Subgrupo": s, "Municipios": len(gs), "Vagas": int(vagas[s]),
                         "CFI_z": round(sz.CIF_z, 2), "IMD_z": round(sz.IMD_z, 2), "CSE_z": round(sz.CSE_z, 2),
                         "Pop_mediana": int(gs.populacao.median()),
                         "Traco": descrever(sz, grupo_z),
                         "Selecionados": ", ".join(gs[gs.Selecionado].sort_values("Rank_no_subgrupo").municipio)})
        partes.append(g)

    base = pd.concat(partes)
    subs = pd.DataFrame(subs)
    diags = pd.concat(diags)[["Perfil", "k", "silhueta", "menor_subgrupo", "tamanhos", "escolhido"]]
    perfis = (base.groupby("Perfil").agg(Municipios=("municipio", "count"), CFI_z=("CIF_z", "mean"),
                                         IMD_z=("IMD_z", "mean"), CSE_z=("CSE_z", "mean"),
                                         Subgrupos=("Subgrupo", "nunique"))
              .round(2).assign(Vagas=lambda t: t.index.map(p.VAGAS)))
    sel = base[base.Selecionado].sort_values(["Perfil", "Subgrupo", "Rank_no_subgrupo"])

    # comparação com a seleção vigente (35/40/25, ranking pelo IAP e por centroide)
    s_iap = set(vig.loc[vig.Ranking <= vig.Perfil.map(p.VAGAS), "cod_ibge"])
    s_rep = set(vig.loc[vig.Ranking_Representatividade <= vig.Perfil.map(p.VAGAS), "cod_ibge"])
    s_nova = set(sel.cod_ibge)
    m = vig[["cod_ibge", "Perfil"]].merge(base[["cod_ibge", "Perfil"]], on="cod_ibge", suffixes=("_vig", "_novo"))
    comp = pd.DataFrame({
        "indicador": ["Municípios no mesmo perfil que a versão vigente (%)",
                      "Selecionados em comum com o IAP vigente (de 50)",
                      "Selecionados em comum com o centroide vigente (de 50)"],
        "valor": [round((m.Perfil_vig == m.Perfil_novo).mean() * 100, 1),
                  len(s_nova & s_iap), len(s_nova & s_rep)]})
    regras = pd.DataFrame({"parametro": [
        "Pesos CFI / IMD / CSE", "Fator no K-Means", "Peso efetivo na distância", "Silhueta dos 4 perfis",
        "Número de subgrupos", "Divisão de vagas", "Seleção no subgrupo"], "valor": [
        "30% / 40% / 30%", " / ".join(f"{v:.3f}" for v in np.sqrt(PESOS)),
        " / ".join(f"{v:.0%}" for v in met["peso_efetivo_distancia"]), f"{met['silhueta']:.3f}",
        f"k entre {K_MIN} e {K_MAX}; subgrupos com ≥ {TAM_MIN} municípios; menor k com silhueta a até {TOL} da melhor",
        "Partes iguais; sobra para os subgrupos maiores",
        "Mais próximos do centroide do subgrupo (eixos × √peso)"]})

    cols = ["cod_ibge", "municipio", "RA", "porte", "populacao", "Perfil", "Subgrupo", "CIF_z", "IMD_z", "CSE_z",
            "Dist_centroide_subgrupo", "Rank_no_subgrupo", "Vagas_subgrupo", "Selecionado"]
    with pd.ExcelWriter(SAIDA / "Selecao_diversidade_30_40_30.xlsx") as w:
        regras.to_excel(w, sheet_name="Regras", index=False)
        perfis.to_excel(w, sheet_name="Perfis")
        diags.round(3).to_excel(w, sheet_name="Escolha do nº de subgrupos", index=False)
        subs.to_excel(w, sheet_name="Subgrupos", index=False)
        sel[cols].round(3).to_excel(w, sheet_name="Selecionados (50)", index=False)
        base.sort_values(["Perfil", "Subgrupo", "Rank_no_subgrupo"])[cols].round(3).to_excel(
            w, sheet_name="Base completa", index=False)
        comp.to_excel(w, sheet_name="Comparacao com vigente", index=False)

    pd.set_option("display.width", 250, "display.max_colwidth", 120)
    print(regras.to_string(index=False), "\n")
    print(perfis, "\n")
    print(diags[diags.escolhido].to_string(index=False), "\n")
    print(subs.drop(columns="Selecionados").to_string(index=False), "\n")
    for _, s in subs.iterrows():
        print(f"{s.Subgrupo} ({s.Vagas}): {s.Selecionados}")
    print("\n", comp.to_string(index=False))


if __name__ == "__main__":
    main()

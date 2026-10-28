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
4. Seleção (regra "diversidade"): em cada subgrupo, o 1º escolhido é o mais típico (mais perto
   do centroide do subgrupo); cada escolhido seguinte é o município mais diferente de todos os já
   escolhidos (maior distância ao escolhido mais próximo). Cobre do típico ao extremo e inclui
   outliers. Para comparação, a regra "típicos" (só os mais próximos do centroide) também é gerada.

Outlier: município cuja distância ao centroide do próprio perfil passa de Q3 + 1,5 × IQR das
distâncias do perfil (critério de Tukey).

Uso:
    python diversidade_subgrupos.py
"""
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
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


def maximin(Xs, v):
    """Índices escolhidos: o mais típico e, depois, sempre o mais diferente dos já escolhidos."""
    sel = [int(np.argmin(np.linalg.norm(Xs - Xs.mean(0), axis=1)))]
    while len(sel) < v:
        dmin = cdist(Xs, Xs[sel]).min(1)
        dmin[sel] = -1
        sel.append(int(np.argmax(dmin)))
    return sel


def metricas(X, sel, out):
    """Diversidade e cobertura de uma seleção dentro do perfil."""
    S = X[sel]
    cob = cdist(X, S).min(1)  # distância de cada município ao escolhido mais próximo
    return {"dist_media_entre_escolhidos": cdist(S, S)[np.triu_indices(len(S), 1)].mean(),
            "cobertura_media": cob.mean(), "cobertura_pior_caso": cob.max(),
            "outliers_incluidos": len(set(sel) & set(out))}


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

    diags, subs, partes, just = [], [], [], []
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
        g["Selecionado_tipicos"] = g.Rank_no_subgrupo <= g.Vagas_subgrupo
        # outliers do perfil (Tukey sobre a distância ao centroide do perfil)
        dc = np.linalg.norm(X - X.mean(0), axis=1)
        q1, q3 = np.percentile(dc, [25, 75])
        g["Dist_centroide_perfil"] = dc
        g["Outlier"] = dc > q3 + 1.5 * (q3 - q1)
        # regra "diversidade" (maximin dentro de cada subgrupo)
        g["Ordem_escolha"] = np.nan
        pos = np.arange(len(g))
        for sgrp in tam.index:
            ii = pos[(g.Subgrupo == sgrp).to_numpy()]
            for ordem, j in enumerate(maximin(X[ii], int(vagas[sgrp])), start=1):
                g.iloc[ii[j], g.columns.get_loc("Ordem_escolha")] = ordem
        g["Selecionado"] = g.Ordem_escolha.notna()
        out = np.where(g.Outlier)[0]
        sel_t, sel_d = np.where(g.Selecionado_tipicos)[0], np.where(g.Selecionado)[0]
        mt, md = metricas(X, sel_t, out), metricas(X, sel_d, out)
        r2 = 1 - km.inertia_ / ((X - X.mean(0)) ** 2).sum()
        just.append({"Perfil": perfil, "Municipios": len(g), "Vagas": p.VAGAS[perfil], "Subgrupos": k,
                     "Divisao_vagas": " / ".join(str(int(vagas[x])) for x in tam.index),
                     "Tamanhos_subgrupos": " / ".join(str(int(tam[x])) for x in tam.index),
                     "Silhueta": round(diag[diag.escolhido].silhueta.iloc[0], 3),
                     "Variacao_explicada_subgrupos_%": round(r2 * 100, 1),
                     "Outliers_no_perfil": len(out),
                     "Outliers_nomes": ", ".join(g.municipio.iloc[out]),
                     **{f"tipicos_{a}": round(b, 2) for a, b in mt.items()},
                     **{f"diversidade_{a}": round(b, 2) for a, b in md.items()}})
        grupo_z = g[["CIF_z", "IMD_z", "CSE_z"]].mean()
        for s, gs in g.groupby("Subgrupo"):
            sz = gs[["CIF_z", "IMD_z", "CSE_z"]].mean()
            subs.append({"Perfil": perfil, "Subgrupo": s, "Municipios": len(gs), "Vagas": int(vagas[s]),
                         "CFI_z": round(sz.CIF_z, 2), "IMD_z": round(sz.IMD_z, 2), "CSE_z": round(sz.CSE_z, 2),
                         "Pop_mediana": int(gs.populacao.median()),
                         "Traco": descrever(sz, grupo_z),
                         "Outliers": int(gs.Outlier.sum()),
                         "Selecionados": ", ".join(gs[gs.Selecionado].sort_values("Ordem_escolha").municipio)})
        partes.append(g)

    base = pd.concat(partes)
    subs = pd.DataFrame(subs)
    diags = pd.concat(diags)[["Perfil", "k", "silhueta", "menor_subgrupo", "tamanhos", "escolhido"]]
    perfis = (base.groupby("Perfil").agg(Municipios=("municipio", "count"), CFI_z=("CIF_z", "mean"),
                                         IMD_z=("IMD_z", "mean"), CSE_z=("CSE_z", "mean"),
                                         Subgrupos=("Subgrupo", "nunique"))
              .round(2).assign(Vagas=lambda t: t.index.map(p.VAGAS)))
    sel = base[base.Selecionado].sort_values(["Perfil", "Subgrupo", "Ordem_escolha"])
    just = pd.DataFrame(just)

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
        "1º = mais típico do subgrupo; seguintes = o mais diferente dos já escolhidos (inclui outliers)"]})

    cols = ["cod_ibge", "municipio", "RA", "porte", "populacao", "Perfil", "Subgrupo", "CIF_z", "IMD_z", "CSE_z",
            "Dist_centroide_perfil", "Outlier", "Dist_centroide_subgrupo", "Rank_no_subgrupo", "Vagas_subgrupo",
            "Ordem_escolha", "Selecionado", "Selecionado_tipicos"]
    with pd.ExcelWriter(SAIDA / "Selecao_diversidade_30_40_30.xlsx") as w:
        regras.to_excel(w, sheet_name="Regras", index=False)
        perfis.to_excel(w, sheet_name="Perfis")
        just.to_excel(w, sheet_name="Justificativa por perfil", index=False)
        base[base.Outlier][cols].round(3).to_excel(w, sheet_name="Outliers", index=False)
        diags.round(3).to_excel(w, sheet_name="Escolha do nº de subgrupos", index=False)
        subs.to_excel(w, sheet_name="Subgrupos", index=False)
        sel[cols].round(3).to_excel(w, sheet_name="Selecionados (50)", index=False)
        base.sort_values(["Perfil", "Subgrupo", "Rank_no_subgrupo"])[cols].round(3).to_excel(
            w, sheet_name="Base completa", index=False)
        comp.to_excel(w, sheet_name="Comparacao com vigente", index=False)

    pd.set_option("display.width", 250, "display.max_colwidth", 120)
    print(regras.to_string(index=False), "\n")
    print(perfis, "\n")
    print(just.T.to_string(), "\n")
    print(diags[diags.escolhido].to_string(index=False), "\n")
    print(subs.drop(columns="Selecionados").to_string(index=False), "\n")
    for _, s in subs.iterrows():
        print(f"{s.Subgrupo} ({s.Vagas}): {s.Selecionados}")
    print("\n", comp.to_string(index=False))


if __name__ == "__main__":
    main()

"""
Matriz de Priorização dos Municípios – Cidades Inteligentes (Anexo III).

Reproduz o notebook original (clusterizacao_2.ipynb) e implementa a revisão
de pesos: o K-Means recebe Z * sqrt(peso), para que a contribuição de cada
eixo à distância euclidiana ao quadrado seja exatamente 35/40/25.

Uso:
    python pipeline.py            # gera os arquivos em resultados/
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

BASE = Path(__file__).resolve().parent
DADOS = BASE / "dados"
RESULTADOS = BASE / "resultados"

EIXOS = ["CIF", "IMD", "CSE"]
PESOS = np.array([0.35, 0.40, 0.25])  # pesos do edital (Anexo III, item 3.2)

# Sinal esperado de cada eixo por perfil (Anexo III, Tabela 1 e Eq. 9-12)
ASSINATURA = {
    "A": np.array([-1, +1, +1]),
    "B": np.array([-1, -1, -1]),
    "C": np.array([+1, +1, +1]),
    "D": np.array([+1, -1, -1]),
}
VAGAS = {"A": 13, "B": 12, "C": 10, "D": 15}  # item 5.1.3 do edital

MAPA_IEGM = {"A": 5, "B+": 4, "B": 3, "C+": 2, "C": 1}


# ------------------------------------------------------------------
# Etapa 1 – Bases
# ------------------------------------------------------------------
def carregar_dados() -> pd.DataFrame:
    iegm = pd.read_excel(DADOS / "IEG-M.xlsx").rename(
        columns={"codigo_municipio": "cod_ibge", "nome": "municipio"})
    ifdm = pd.read_excel(DADOS / "IFDM.xlsx").rename(columns={"COD": "cod_ibge"})
    ibc = pd.read_excel(DADOS / "Indice Brasileiro de Conectividade.xlsx").rename(
        columns={"Código Município": "cod_ibge"})
    smart = pd.read_excel(DADOS / "municipios_sp_inteligente.xlsx").rename(
        columns={"codigo_ibge": "cod_ibge"})
    pop = pd.read_excel(DADOS / "Pop 2022.xlsx").rename(columns={
        "Município": "municipio", "Código": "cod_ibge", "Faixa": "porte",
        "População no último censo - pessoas [2022]": "populacao"})

    dados = (
        pop.merge(iegm[["cod_ibge", "iplanejamento", "ifiscal", "igov"]], on="cod_ibge", how="left")
           .merge(ifdm[["cod_ibge", "IFDM"]], on="cod_ibge", how="left")
           .merge(ibc[["cod_ibge", "IBC"]], on="cod_ibge", how="left")
           .merge(smart[["cod_ibge", "nivel_geral"]], on="cod_ibge", how="left")
    )
    # Capital fora do universo do edital
    dados = dados[dados["cod_ibge"] != 3550308].reset_index(drop=True)

    for col in ["iplanejamento", "ifiscal", "igov"]:
        dados[col] = dados[col].map(MAPA_IEGM)
    return dados


# ------------------------------------------------------------------
# Etapa 2 – Padronização e eixos (Anexo III, itens 2, 3 e 3.1)
# ------------------------------------------------------------------
def construir_eixos(dados: pd.DataFrame) -> pd.DataFrame:
    variaveis = ["iplanejamento", "ifiscal", "igov", "IFDM", "IBC", "nivel_geral"]
    z = pd.DataFrame(StandardScaler().fit_transform(dados[variaveis]),
                     columns=variaveis, index=dados.index)
    eixos = pd.DataFrame(index=dados.index)
    eixos["CIF"] = 0.50 * z["iplanejamento"] + 0.50 * z["ifiscal"]
    eixos["IMD"] = 0.35 * z["IBC"] + 0.25 * z["igov"] + 0.40 * z["nivel_geral"]
    eixos["CSE"] = z["IFDM"]
    eixos[EIXOS] = StandardScaler().fit_transform(eixos[EIXOS])
    return eixos


# ------------------------------------------------------------------
# Etapa 3 – K-Means e nomeação dos perfis
# ------------------------------------------------------------------
def nomear_perfis(centroides: np.ndarray) -> dict:
    """Associa cada cluster a A/B/C/D pela assinatura de sinais do Anexo III.

    Substitui o mapeamento fixo {1:"A", 3:"B", 2:"C", 0:"D"}, que depende do
    número que o K-Means atribui a cada cluster e muda entre execuções/versões.
    """
    letras = list(ASSINATURA)
    # aderência = soma(sinal esperado * centróide); maximiza via Hungarian
    score = np.array([[ASSINATURA[l] @ c for l in letras] for c in centroides])
    linhas, cols = linear_sum_assignment(-score)
    return {int(k): letras[j] for k, j in zip(linhas, cols)}


def clusterizar(eixos: pd.DataFrame, fator: np.ndarray, seed: int = 42):
    X = eixos[EIXOS].to_numpy() * fator
    km = KMeans(n_clusters=4, random_state=seed, n_init=50).fit(X)
    nomes = nomear_perfis(km.cluster_centers_)
    perfil = pd.Series(km.labels_, index=eixos.index).map(nomes)
    centroides = pd.DataFrame(km.cluster_centers_, columns=EIXOS,
                              index=[nomes[k] for k in range(4)]).sort_index()
    return X, km, perfil, centroides


# ------------------------------------------------------------------
# Etapas 4 a 6 – Distância, representatividade e IAP
# ------------------------------------------------------------------
def montar_resultado(dados, eixos, fator, rotulo):
    X, km, perfil, centroides = clusterizar(eixos, fator)

    r = dados[["cod_ibge", "municipio", "RA", "porte", "populacao"]].copy()
    r["Perfil"] = perfil
    for i, e in enumerate(EIXOS):
        r[f"{e}_z"] = eixos[e]                 # eixo padronizado (Eq. 5)
        r[f"{e}_kmeans"] = X[:, i]            # entrada do K-Means
        r[f"{e}_pond"] = eixos[e] * PESOS[i]  # eixo * peso do edital (Eq. 6)

    # IAP (Eq. 9-12). É linear: o peso entra uma única vez, então usa-se
    # Z * peso (35/40/25 exatos) – igual ao notebook original.
    sinais = np.vstack(r["Perfil"].map(ASSINATURA))
    r["IAP"] = (sinais * r[[f"{e}_pond" for e in EIXOS]].to_numpy()).sum(axis=1)

    # Distância euclidiana ao centróide no espaço do K-Means (Eq. 8)
    c = centroides.loc[r["Perfil"]].to_numpy()
    r["Distancia_Centroide"] = np.sqrt(((X - c) ** 2).sum(axis=1))
    g = r.groupby("Perfil")["Distancia_Centroide"]
    r["Representatividade"] = ((g.transform("max") - r["Distancia_Centroide"])
                               / (g.transform("max") - g.transform("min")) * 100).round(1)

    r["Ranking"] = r.groupby("Perfil")["IAP"].rank(ascending=False, method="first").astype(int)
    r["Ranking_Representatividade"] = (
        r.groupby("Perfil")["Distancia_Centroide"].rank(method="first").astype(int))

    metricas = {
        "versao": rotulo,
        "fator_kmeans": np.round(fator, 4).tolist(),
        "peso_efetivo_distancia": np.round(fator**2 / (fator**2).sum(), 4).tolist(),
        "silhueta": silhouette_score(X, km.labels_),
        "inercia": km.inertia_,
        **{f"n_{p}": int((r["Perfil"] == p).sum()) for p in ASSINATURA},
    }
    return r, centroides, metricas


# ------------------------------------------------------------------
# Sensibilidade a variação dos pesos
# ------------------------------------------------------------------
def selecionados(r, criterio):
    col = "Ranking" if criterio == "IAP" else "Ranking_Representatividade"
    return set(r.loc[r[col] <= r["Perfil"].map(VAGAS), "cod_ibge"])


def sensibilidade(dados, eixos, raiz: bool, delta=0.20):
    """Varia cada peso em {-delta, 0, +delta} (26 cenários, renormalizados a 1)
    e compara com o cenário-base: perfil, ranking e lista dos 50 selecionados."""
    fator_base = np.sqrt(PESOS) if raiz else PESOS
    base, _, _ = montar_resultado(dados, eixos, fator_base, "base")
    linhas = []
    for a in (-delta, 0, delta):
        for b in (-delta, 0, delta):
            for c in (-delta, 0, delta):
                if a == b == c == 0:
                    continue
                w = PESOS * (1 + np.array([a, b, c]))
                w = w / w.sum()
                fator = np.sqrt(w) if raiz else w
                r, _, _ = montar_resultado(dados, eixos, fator, "cen")
                m = base.merge(r, on="cod_ibge", suffixes=("_b", "_c"))
                mesmo = m[m["Perfil_b"] == m["Perfil_c"]]
                linhas.append({
                    "esquema": "raiz(peso)" if raiz else "peso (original)",
                    "dCIF": a, "dIMD": b, "dCSE": c,
                    "w_CIF": w[0], "w_IMD": w[1], "w_CSE": w[2],
                    "pct_mesmo_perfil": (m["Perfil_b"] == m["Perfil_c"]).mean() * 100,
                    "ARI": adjusted_rand_score(m["Perfil_b"], m["Perfil_c"]),
                    "spearman_IAP": mesmo["Ranking_b"].corr(mesmo["Ranking_c"], method="spearman"),
                    "spearman_Repr": mesmo["Ranking_Representatividade_b"].corr(
                        mesmo["Ranking_Representatividade_c"], method="spearman"),
                    "sel50_iguais_IAP": len(selecionados(base, "IAP") & selecionados(r, "IAP")),
                    "sel50_iguais_Repr": len(selecionados(base, "Repr") & selecionados(r, "Repr")),
                })
    return pd.DataFrame(linhas)


# ------------------------------------------------------------------
# Exportação
# ------------------------------------------------------------------
COLS_IAP = ["cod_ibge", "municipio", "Perfil", "CIF_z", "IMD_z", "CSE_z",
            "CIF_kmeans", "IMD_kmeans", "CSE_kmeans", "IAP", "Ranking"]
COLS_REP = COLS_IAP + ["Distancia_Centroide", "Representatividade",
                       "Ranking_Representatividade"]


def exportar_versao(r, centroides, metricas, sufixo):
    iap = r.sort_values(["Perfil", "Ranking"])[COLS_IAP]
    rep = r.sort_values(["Perfil", "Ranking_Representatividade"])[COLS_REP]
    resumo = (r.groupby("Perfil")
                .agg(Municipios=("municipio", "count"),
                     Vagas=("Perfil", lambda s: VAGAS[s.iloc[0]]),
                     CIF_z=("CIF_z", "mean"), IMD_z=("IMD_z", "mean"), CSE_z=("CSE_z", "mean"),
                     Pop_mediana=("populacao", "median"))
                .round(3))
    cent = centroides.add_suffix("_centroide_kmeans").round(4)
    meta = pd.DataFrame({"chave": list(metricas), "valor": [str(v) for v in metricas.values()]})

    with pd.ExcelWriter(RESULTADOS / f"Ranking_IAP_Municipios_{sufixo}.xlsx") as w:
        iap.to_excel(w, sheet_name="Ranking IAP", index=False)
        iap.loc[iap["Ranking"] <= iap["Perfil"].map(VAGAS)].to_excel(
            w, sheet_name="Selecionados (vagas)", index=False)
        resumo.join(cent).to_excel(w, sheet_name="Perfis")
        meta.to_excel(w, sheet_name="Parametros", index=False)

    with pd.ExcelWriter(RESULTADOS / f"Ranking_Representatividade_{sufixo}.xlsx") as w:
        rep.to_excel(w, sheet_name="Ranking Representatividade", index=False)
        rep.loc[rep["Ranking_Representatividade"] <= rep["Perfil"].map(VAGAS)].to_excel(
            w, sheet_name="Selecionados (vagas)", index=False)
        resumo.join(cent).to_excel(w, sheet_name="Perfis")
        meta.to_excel(w, sheet_name="Parametros", index=False)


def comparar(orig, nova, sens, metricas):
    m = orig.merge(nova, on=["cod_ibge", "municipio"], suffixes=("_orig", "_raiz"))
    vag_o, vag_n = m["Perfil_orig"].map(VAGAS), m["Perfil_raiz"].map(VAGAS)
    comp = pd.DataFrame({
        "cod_ibge": m["cod_ibge"], "municipio": m["municipio"],
        "Perfil_original": m["Perfil_orig"], "Perfil_raiz": m["Perfil_raiz"],
        "Mudou_perfil": m["Perfil_orig"] != m["Perfil_raiz"],
        "IAP": m["IAP_orig"].round(4),
        "Ranking_IAP_original": m["Ranking_orig"], "Ranking_IAP_raiz": m["Ranking_raiz"],
        "Selec_IAP_original": m["Ranking_orig"] <= vag_o,
        "Selec_IAP_raiz": m["Ranking_raiz"] <= vag_n,
        "Ranking_Repr_original": m["Ranking_Representatividade_orig"],
        "Ranking_Repr_raiz": m["Ranking_Representatividade_raiz"],
        "Selec_Repr_original": m["Ranking_Representatividade_orig"] <= vag_o,
        "Selec_Repr_raiz": m["Ranking_Representatividade_raiz"] <= vag_n,
    })
    migracao = pd.crosstab(comp["Perfil_original"], comp["Perfil_raiz"], margins=True,
                           rownames=["Original (peso)"], colnames=["Revisado (raiz do peso)"])

    def mudancas(col_o, col_n):
        entra = comp[~comp[col_o] & comp[col_n]]
        sai = comp[comp[col_o] & ~comp[col_n]]
        return pd.concat([entra.assign(Movimento="Entra"), sai.assign(Movimento="Sai")])

    resumo_sens = (sens.groupby("esquema")
                       .agg(pct_mesmo_perfil_medio=("pct_mesmo_perfil", "mean"),
                            pct_mesmo_perfil_pior=("pct_mesmo_perfil", "min"),
                            ARI_pior=("ARI", "min"),
                            spearman_IAP_pior=("spearman_IAP", "min"),
                            spearman_Repr_pior=("spearman_Repr", "min"),
                            sel50_IAP_pior=("sel50_iguais_IAP", "min"),
                            sel50_Repr_pior=("sel50_iguais_Repr", "min"),
                            sel50_IAP_medio=("sel50_iguais_IAP", "mean"),
                            sel50_Repr_medio=("sel50_iguais_Repr", "mean"))
                       .round(3))

    with pd.ExcelWriter(RESULTADOS / "Comparacao_Original_vs_RaizPeso.xlsx") as w:
        pd.DataFrame(metricas).to_excel(w, sheet_name="Metricas", index=False)
        migracao.to_excel(w, sheet_name="Migracao de perfis")
        comp.to_excel(w, sheet_name="Municipios", index=False)
        mudancas("Selec_IAP_original", "Selec_IAP_raiz").to_excel(
            w, sheet_name="Selecao IAP - mudancas", index=False)
        mudancas("Selec_Repr_original", "Selec_Repr_raiz").to_excel(
            w, sheet_name="Selecao Repr - mudancas", index=False)
        resumo_sens.to_excel(w, sheet_name="Sensibilidade - resumo")
        sens.round(4).to_excel(w, sheet_name="Sensibilidade - cenarios", index=False)
    return comp, migracao, resumo_sens


def main():
    RESULTADOS.mkdir(exist_ok=True)
    dados = carregar_dados()
    assert dados[["iplanejamento", "ifiscal", "igov", "IFDM", "IBC", "nivel_geral"]].notna().all().all()
    eixos = construir_eixos(dados)

    orig, cent_o, met_o = montar_resultado(dados, eixos, PESOS, "original: Z*peso")
    nova, cent_n, met_n = montar_resultado(dados, eixos, np.sqrt(PESOS), "revisada: Z*raiz(peso)")
    exportar_versao(orig, cent_o, met_o, "original_corrigido")
    exportar_versao(nova, cent_n, met_n, "raiz_peso")

    sens = pd.concat([sensibilidade(dados, eixos, raiz=False),
                      sensibilidade(dados, eixos, raiz=True)])
    comp, migracao, resumo_sens = comparar(orig, nova, sens, [met_o, met_n])

    pd.set_option("display.width", 200)
    for met, cent in ((met_o, cent_o), (met_n, cent_n)):
        print(met)
        print(cent.round(3), "\n")
    print(migracao, "\n")
    print(f"Mesmo perfil: {(~comp['Mudou_perfil']).mean():.1%}")
    print(f"Selecionados IAP em comum: {(comp.Selec_IAP_original & comp.Selec_IAP_raiz).sum()}/50")
    print(f"Selecionados Repr em comum: {(comp.Selec_Repr_original & comp.Selec_Repr_raiz).sum()}/50")
    print(resumo_sens.T)


if __name__ == "__main__":
    main()

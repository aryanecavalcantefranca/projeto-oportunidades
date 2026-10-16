"""Cenário com peso de 20% para a Condição Socioeconômica (CSE).

Compara três formas de redistribuir os 5 p.p. retirados do CSE com a versão
vigente (35/40/25, K-Means com raiz do peso). Gera os rankings de cada cenário
e uma planilha de comparação em resultados/cenario_cse20/.

Uso:
    python cenario_cse20.py
"""
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, silhouette_score

import pipeline as p

SAIDA = p.RESULTADOS / "cenario_cse20"
CENARIOS = {
    "vigente_35_40_25": np.array([0.35, 0.40, 0.25]),
    "proporcional_37_43_20": np.array([0.35, 0.40, 0.0]) / 0.75 * 0.80 + np.array([0, 0, 0.20]),
    "imd_35_45_20": np.array([0.35, 0.45, 0.20]),
    "cfi_40_40_20": np.array([0.40, 0.40, 0.20]),
}


def selec(r, col):
    return set(r.loc[r[col] <= r["Perfil"].map(p.VAGAS), "cod_ibge"])


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    dados = p.carregar_dados()
    eixos = p.construir_eixos(dados)

    res = {}
    for nome, w in CENARIOS.items():
        r, cent, met = p.montar_resultado(dados, eixos, np.sqrt(w), nome, pesos=w)
        res[nome] = (r, cent, met, w)
        if nome != "vigente_35_40_25":
            p.exportar_versao(r, cent, met, f"cse20_{nome}")
            for f in SAIDA.parent.glob(f"*cse20_{nome}.xlsx"):
                f.replace(SAIDA / f.name)

    base, cent_b, _, _ = res["vigente_35_40_25"]
    resumo, migr, mud, cents, sens = [], {}, [], [], []
    for nome, (r, cent, met, w) in res.items():
        m = base.merge(r, on=["cod_ibge", "municipio"], suffixes=("_v", "_c"))
        z = r.groupby("Perfil")[["CIF_z", "IMD_z", "CSE_z"]].mean()
        X = r[["CIF_kmeans", "IMD_kmeans", "CSE_kmeans"]].to_numpy()
        linha = {
            "cenario": nome, "peso_CFI": w[0], "peso_IMD": w[1], "peso_CSE": w[2],
            **{f"n_{k}": int((r.Perfil == k).sum()) for k in "ABCD"},
            "pct_mesmo_perfil_vs_vigente": (m.Perfil_v == m.Perfil_c).mean() * 100,
            "ARI_vs_vigente": adjusted_rand_score(m.Perfil_v, m.Perfil_c),
            "sel50_IAP_iguais": len(selec(base, "Ranking") & selec(r, "Ranking")),
            "sel50_centroide_iguais": len(selec(base, "Ranking_Representatividade")
                                          & selec(r, "Ranking_Representatividade")),
            "silhueta": silhouette_score(X, r.Perfil),
        }
        for k in "ABCD":
            for e in ("CIF", "IMD", "CSE"):
                linha[f"{k}_{e}_z"] = round(z.loc[k, f"{e}_z"], 3)
        resumo.append(linha)
        c = z.round(3).reset_index()
        c.insert(0, "cenario", nome)
        cents.append(c)
        if nome == "vigente_35_40_25":
            continue
        migr[nome] = pd.crosstab(m.Perfil_v, m.Perfil_c, margins=True,
                                 rownames=["Vigente (35/40/25)"], colnames=[nome])
        for col, rot in (("Ranking", "IAP"), ("Ranking_Representatividade", "Centroide")):
            sv, sc = selec(base, col), selec(r, col)
            for cod, mov in [(x, "Entra") for x in sc - sv] + [(x, "Sai") for x in sv - sc]:
                lv = base[base.cod_ibge == cod].iloc[0]
                lc = r[r.cod_ibge == cod].iloc[0]
                mud.append({"cenario": nome, "criterio": rot, "movimento": mov, "municipio": lv.municipio,
                            "perfil_vigente": lv.Perfil, "perfil_cenario": lc.Perfil,
                            f"rank_vigente": lv[col], f"rank_cenario": lc[col]})
        s = p.sensibilidade(dados, eixos, raiz=True, pesos=w)
        sens.append({"cenario": nome,
                     "pct_mesmo_perfil_pior": s.pct_mesmo_perfil.min(),
                     "sel50_IAP_pior": s.sel50_iguais_IAP.min(),
                     "sel50_centroide_pior": s.sel50_iguais_Repr.min()})
    s0 = p.sensibilidade(dados, eixos, raiz=True)
    sens.insert(0, {"cenario": "vigente_35_40_25", "pct_mesmo_perfil_pior": s0.pct_mesmo_perfil.min(),
                    "sel50_IAP_pior": s0.sel50_iguais_IAP.min(),
                    "sel50_centroide_pior": s0.sel50_iguais_Repr.min()})

    resumo = pd.DataFrame(resumo).merge(pd.DataFrame(sens), on="cenario")
    with pd.ExcelWriter(SAIDA / "Comparacao_cenarios_CSE20.xlsx") as wr:
        resumo.round(3).to_excel(wr, sheet_name="Resumo", index=False)
        pd.concat(cents).to_excel(wr, sheet_name="Centroides (z)", index=False)
        for nome, t in migr.items():
            t.to_excel(wr, sheet_name=f"Migracao {nome[:20]}")
        pd.DataFrame(mud).to_excel(wr, sheet_name="Selecionados - mudancas", index=False)
    pd.set_option("display.width", 250)
    print(resumo.round(3).T.to_string())
    for nome, t in migr.items():
        print("\n", t)
    print(pd.DataFrame(mud).groupby(["cenario", "criterio", "movimento"]).municipio.apply(list).to_string())


if __name__ == "__main__":
    main()

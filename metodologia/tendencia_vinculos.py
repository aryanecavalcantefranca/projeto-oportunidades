"""
=============================================================================
TENDÊNCIA DE VÍNCULOS (EMPREGO + RENDA-HORA) — RAIS 2018-2025, SP
=============================================================================
Reconstrução da extração RAIS via basedosdados/BigQuery e do cálculo de
tendência, seguindo a fórmula do Anexo Metodológico Macroplan (pág. 10):

    índice(ano-1,ano) = +raiz(Δrenda² + Δemprego²)   se Δrenda>0 e Δemprego>0
    índice(ano-1,ano) = -raiz(Δrenda² + Δemprego²)   se Δrenda<0 e Δemprego<0
    índice(ano-1,ano) = 0                             se sinais divergem

    índice final = 0,60·índice(t-1,t) + 0,20·índice(t-2,t-1) + 0,10·índice(t-3,t-2)
                 + 0,06·índice(t-4,t-3) + 0,03·índice(t-5,t-4) + 0,01·índice(t-6,t-5)

    (o intervalo 2021→2022 é descartado por orientação do MTE — RAIS não
    comparável antes/depois dessa quebra; os pesos escorregam para o
    próximo intervalo válido, exatamente como no Anexo original quando pula
    2021→2022 e vai de 0,20 direto para 2020→2021)

Diferenças corrigidas em relação às tentativas anteriores (ver
nota_metodologica_atualizacao_2025.md):

  1. RENDA = renda-hora real (massa_salarial_real / horas_contratadas),
     não remuneração média mensal (massa / vínculos). É o que o Anexo pede
     na nota de rodapé da pág. 10, e é a causa mais provável da correlação
     baixa (0,23) no teste de validação anterior.
  2. Winsorização simétrica de Δemprego E Δrenda em ±100% — sem isso o
     índice é dominado por explosões de base pequena (2→40 vínculos =
     +1900%). O seu próprio teste (macroplan_sp_2025 notebook, células
     56-59) mostrou que só clipar Δemprego já derruba o MAE de 0,75 para
     0,11; aqui aplicamos a mesma lógica a Δrenda.
  3. Piso de porte: só existe Δ quando o ano anterior tem >= MIN_VINCULOS_BASE
     vínculos na atividade/município. Evita "tendência" de 1 para 2 vínculos.
  4. Grade completa (ano x município x atividade) preenchida com zero antes
     de calcular os deltas — senão uma atividade que aparece só em alguns
     anos tem seus intervalos silenciosamente pulados.
  5. Renormalização pelo peso efetivamente válido (soma/peso_total) — sem
     isso, séries com histórico incompleto (ex.: 2018-2025, sem os
     intervalos 2016-17/2017-18 do Anexo original) ficam artificialmente
     puxadas para perto de zero. Bug identificado na validação de
     2026-08: caiu no meio do caminho ao reescrever a partir da função
     original `tendencia_emprego_renda`, que já tinha essa correção.
  6. Atividade que desaparece (vínculos caem a zero): a renda-hora fica
     indefinida (0/0), o que descartava o intervalo inteiro mesmo com
     Δemprego = -1 sendo um sinal válido e forte. Convenção adotada:
     tratar o desaparecimento como colapso total (Δrenda = -1 por
     definição), não como dado ausente. Identificado comparando com um
     caso real do painel Macroplan onde a atividade morre em 2023 e a
     tendência publicada é fortemente negativa (-0,62), mas o cálculo sem
     essa correção dava ~0.

Este script é para rodar no Colab, com o projeto de billing "densidade2025"
que você já usa. Ele espera `tabela_cnae.xlsx` no mesmo diretório, com as
colunas Subclasse / Classe / Grupo / Divisão / Seção.

Ordem de execução: configuracao -> extrair_rais -> deflacionar -> juntar_cnae
    -> calcular_tendencia (por nível) -> validar_contra_macroplan
=============================================================================
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# =============================================================================
# 0. CONFIGURAÇÃO
# =============================================================================

UF = "SP"
ANO_MIN, ANO_MAX = 2018, 2025
ANOS_EXCLUIDOS = [2022]          # intervalo 2021->2022 não comparável (MTE)
PESOS_RECENCIA = [0.60, 0.20, 0.10, 0.06, 0.03, 0.01]

MIN_VINCULOS_BASE = 5            # piso de porte p/ gerar delta_emprego/delta_renda
LIMITE_WINSOR = 1.0              # +-100%

NIVEIS = ["secao", "divisao", "grupo", "classe", "subclasse"]

# IPCA (índice de dezembro de cada ano) — ano-base: dezembro de 2025
IPCA = pd.DataFrame({
    "ano": [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
    "indice": [4775.70, 4916.46, 5100.61, 5320.25, 5560.59,
               6120.04, 6474.09, 6773.27, 7100.50, 7403.29],
})
IPCA_ANO_BASE = 2025


# =============================================================================
# 1. EXTRAÇÃO — RAIS via basedosdados/BigQuery, nível subclasse
# =============================================================================

def extrair_rais(billing_project_id="densidade2025", uf=UF,
                  ano_min=ANO_MIN, ano_max=ANO_MAX):
    """
    Uma linha por (ano, município, subclasse). Inclui horas_contratadas —
    é o campo que faltava nas extrações anteriores e que impedia calcular
    renda-hora corretamente.
    """
    import basedosdados as bd

    query = f"""
    SELECT
        ano,
        id_municipio,
        cnae_2_subclasse,
        COUNT(*) AS vinculos,
        SUM(valor_remuneracao_dezembro) AS massa_salarial_dezembro,
        SUM(quantidade_horas_contratadas) AS horas_contratadas
    FROM `basedosdados.br_me_rais.microdados_vinculos`
    WHERE
        sigla_uf = '{uf}'
        AND ano BETWEEN {ano_min} AND {ano_max}
        AND vinculo_ativo_3112 = '1'
        AND valor_remuneracao_dezembro > 0
        AND id_municipio IS NOT NULL
        AND cnae_2_subclasse IS NOT NULL
    GROUP BY ano, id_municipio, cnae_2_subclasse
    ORDER BY ano, id_municipio, cnae_2_subclasse
    """
    rais = bd.read_sql(query, billing_project_id=billing_project_id)

    rais["id_municipio"] = rais["id_municipio"].astype(str)
    rais["cnae_2_subclasse"] = rais["cnae_2_subclasse"].astype(str).str.zfill(7)
    for col in ["vinculos", "massa_salarial_dezembro", "horas_contratadas"]:
        rais[col] = pd.to_numeric(rais[col], errors="coerce")

    rais.to_parquet(f"rais_municipio_cnae_{ano_min}_{ano_max}.parquet", index=False)
    print(f"Base extraída: {len(rais):,} linhas | "
          f"{rais['id_municipio'].nunique()} municípios | "
          f"anos {sorted(rais['ano'].unique())}")
    return rais


# =============================================================================
# 2. DEFLAÇÃO (IPCA, base dezembro/2025)
# =============================================================================

def deflacionar(rais, ipca=IPCA, ano_base=IPCA_ANO_BASE):
    indice_base = ipca.loc[ipca["ano"] == ano_base, "indice"].iloc[0]
    fator = ipca.assign(fator_deflator=indice_base / ipca["indice"])
    d = rais.merge(fator[["ano", "fator_deflator"]], on="ano", how="left")
    d["massa_salarial_real"] = d["massa_salarial_dezembro"] * d["fator_deflator"]
    return d


# =============================================================================
# 3. HIERARQUIA CNAE
# =============================================================================

def juntar_cnae(rais, caminho_tabela_cnae="tabela_cnae.xlsx"):
    cnae = pd.read_excel(caminho_tabela_cnae)
    cnae = cnae.rename(columns={
        "Subclasse": "subclasse", "Classe": "classe",
        "Grupo": "grupo", "Divisão": "divisao", "Seção": "secao",
    })
    cnae["subclasse"] = cnae["subclasse"].astype(str).str.zfill(7)
    cnae["classe"] = cnae["classe"].astype(str).str.zfill(5)
    cnae["grupo"] = cnae["grupo"].astype(str).str.zfill(3)
    cnae["divisao"] = cnae["divisao"].astype(str).str.zfill(2)
    cnae = cnae[["subclasse", "classe", "grupo", "divisao", "secao"]].drop_duplicates()

    d = rais.rename(columns={"cnae_2_subclasse": "subclasse"})
    return d.merge(cnae, on="subclasse", how="left")


# =============================================================================
# 4. PESOS POR RECÊNCIA (intervalos válidos, do mais recente ao mais antigo)
# =============================================================================

def pesos_por_recencia(anos_disponiveis, anos_excluidos=ANOS_EXCLUIDOS,
                        pesos=PESOS_RECENCIA):
    """
    Chave = ano final do intervalo. Ex.: peso[2025] pondera o intervalo
    2024->2025. anos_excluidos remove o(s) ano(s) final(is) de intervalo
    não comparável (2022 = intervalo 2021->2022).

    Réplica exata da lógica do Anexo: quando um intervalo é descartado, o
    peso seguinte "escorrega" para o próximo intervalo válido (0,20 vai
    para 2020->2021 quando 2021->2022 é pulado) — não fica um buraco.
    """
    anos = sorted(a for a in set(anos_disponiveis) if a not in set(anos_excluidos))
    anos = anos[::-1]
    usados = anos[: len(pesos)]
    w = dict(zip(usados, pesos[: len(usados)]))
    total = sum(w.values())
    return {a: p / total for a, p in w.items()}


# =============================================================================
# 5. AGREGAÇÃO POR NÍVEL + GRADE COMPLETA
# =============================================================================

def agregar_nivel(base, nivel):
    dados = (
        base.groupby(["ano", "id_municipio", nivel], observed=True, as_index=False)
        .agg(vinculos=("vinculos", "sum"),
             massa_salarial_real=("massa_salarial_real", "sum"),
             horas_contratadas=("horas_contratadas", "sum"))
        .rename(columns={nivel: "atividade"})
        .dropna(subset=["atividade"])
    )

    anos = sorted(dados["ano"].unique())
    municipios = sorted(dados["id_municipio"].unique())
    atividades = sorted(dados["atividade"].unique())
    grade = pd.MultiIndex.from_product(
        [anos, municipios, atividades], names=["ano", "id_municipio", "atividade"]
    ).to_frame(index=False)

    dados = grade.merge(dados, on=["ano", "id_municipio", "atividade"], how="left")
    dados["vinculos"] = dados["vinculos"].fillna(0)
    dados["massa_salarial_real"] = dados["massa_salarial_real"].fillna(0)
    dados["horas_contratadas"] = dados["horas_contratadas"].fillna(0)

    dados["renda_hora"] = np.where(
        dados["horas_contratadas"] > 0,
        dados["massa_salarial_real"] / dados["horas_contratadas"],
        np.nan,
    )
    return dados


# =============================================================================
# 6. DELTAS, ÍNDICE ANUAL, TENDÊNCIA PONDERADA
# =============================================================================

def _winsor(s, limite=LIMITE_WINSOR):
    return s.clip(-limite, limite)


def calcular_tendencia_nivel(dados, min_vinculos_base=MIN_VINCULOS_BASE,
                              anos_excluidos=ANOS_EXCLUIDOS):
    """
    `dados` = saída de agregar_nivel(): grade completa ano x município x
    atividade, com vinculos, massa_salarial_real, renda_hora.

    Devolve tendência em duas escalas:
      tendencia_bruta -> soma ponderada do índice anual, escala ±raiz(2)
                          (comparável ao índice do Anexo, sem normalização)
      tendencia_norm  -> tendencia_bruta / raiz(2), escala [-1, +1]
    """
    df = dados.sort_values(["id_municipio", "atividade", "ano"]).copy()

    g = df.groupby(["id_municipio", "atividade"], observed=True)
    df["vinculos_ant"] = g["vinculos"].shift(1)
    df["renda_ant"] = g["renda_hora"].shift(1)

    base_valida = df["vinculos_ant"].fillna(0) >= min_vinculos_base

    df["delta_emprego"] = np.where(
        base_valida,
        (df["vinculos"] - df["vinculos_ant"]) / df["vinculos_ant"],
        np.nan,
    )
    df["delta_renda"] = np.where(
        base_valida & (df["renda_ant"].fillna(0) > 0),
        (df["renda_hora"] - df["renda_ant"]) / df["renda_ant"],
        np.nan,
    )

    # Atividade morreu no município (vínculos caem a zero): renda-hora fica
    # indefinida (0/0) e delta_renda vira NaN, o que descartaria o intervalo
    # inteiro mesmo quando delta_emprego = -1 é um sinal claro e válido.
    # Convenção: tratamos o desaparecimento como colapso total (equivalente
    # a delta_renda = -1), não como dado ausente.
    atividade_morreu = base_valida & (df["vinculos"] == 0)
    df.loc[atividade_morreu, "delta_renda"] = -1.0

    df["delta_emprego"] = _winsor(df["delta_emprego"])
    df["delta_renda"] = _winsor(df["delta_renda"])

    modulo = np.sqrt(df["delta_emprego"] ** 2 + df["delta_renda"] ** 2)
    df["indice_anual"] = np.select(
        [
            (df["delta_emprego"] > 0) & (df["delta_renda"] > 0),
            (df["delta_emprego"] < 0) & (df["delta_renda"] < 0),
        ],
        [modulo, -modulo],
        default=0.0,
    )
    df.loc[df["delta_emprego"].isna() | df["delta_renda"].isna(), "indice_anual"] = np.nan

    pesos = pesos_por_recencia(df["ano"].unique(), anos_excluidos)
    df["peso"] = df["ano"].map(pesos).fillna(0.0)
    df["peso_valido"] = np.where(df["indice_anual"].notna(), df["peso"], 0.0)

    out = (
        df.assign(contrib=df["indice_anual"].fillna(0) * df["peso_valido"])
        .groupby(["id_municipio", "atividade"], as_index=False, observed=True)
        .agg(soma=("contrib", "sum"), peso_total=("peso_valido", "sum"))
    )
    # Renormaliza pelo peso efetivamente válido: uma série com histórico
    # incompleto (ex.: começa em 2018, sem os intervalos 2016-17/2017-18 do
    # Anexo original) não pode ser penalizada só por ter menos anos.
    out["tendencia_bruta"] = np.where(
        out["peso_total"] > 0, out["soma"] / out["peso_total"], 0.0
    )
    out["tendencia_norm"] = out["tendencia_bruta"] / np.sqrt(2)
    return out[["id_municipio", "atividade", "tendencia_bruta", "tendencia_norm"]]


# =============================================================================
# 7. ORQUESTRAÇÃO — roda os 5 níveis e salva
# =============================================================================

def gerar_todas_tendencias(base_completa, niveis=NIVEIS, prefixo="tendencia_vinculos_sp"):
    """`base_completa` = saída de juntar_cnae(deflacionar(rais))."""
    resultados = {}
    for nivel in niveis:
        dados = agregar_nivel(base_completa, nivel)
        tendencia = calcular_tendencia_nivel(dados)
        arquivo = f"{prefixo}_{nivel}.xlsx"
        tendencia.to_excel(arquivo, index=False)
        print(f"-> Salvo: {arquivo} ({len(tendencia):,} linhas)")
        resultados[nivel] = tendencia
    return resultados


# =============================================================================
# 8. VALIDAÇÃO — contra os 20 valores reais do Macroplan (2016-2023, nível grupo)
# =============================================================================
# Valores extraídos da sua própria planilha de resultado da metodologia
# original (o notebook de validação já tinha isso na variável `macroplan`).
# Isso reproduz o teste que você já tinha feito, mas com renda-hora em vez
# de remuneração média — é o jeito mais direto de confirmar se a correção
# resolveu o problema de correlação baixa (0,23) do teste anterior.

REFERENCIA_MACROPLAN = pd.DataFrame({
    "id_municipio": ["3502804", "3502705", "3539806", "3529807", "3507506",
                      "3509007", "3500501", "3547304", "3545159", "3550902",
                      "3547908", "3530805", "3515152", "3524501", "3547007",
                      "3503901", "3534203", "3551009", "3506359", "3548807"],
    "atividade": ["581", "562", "823", "931", "873", "813", "869", "370",
                  "431", "021", "949", "234", "012", "478", "331", "522",
                  "493", "702", "781", "661"],
    "macroplan": [-0.688, -0.674, -0.674, -0.669, -0.666, -0.663, -0.653,
                  -0.636, -0.633, -0.627, -0.622, -0.620, -0.617, -0.616,
                  -0.616, -0.611, -0.611, -0.609, -0.608, -0.608],
})


def validar_contra_macroplan(base_completa, referencia=REFERENCIA_MACROPLAN):
    """
    Reconstrói o cálculo tal como no Anexo original: base até 2023, pesos
    2016->2023 (0,01/0,03/0,06/0,10/0,20/0,60 nos intervalos válidos,
    pulando 2021->2022), nível grupo. Compara com os 20 valores publicados.
    """
    base_2023 = base_completa[base_completa["ano"] <= 2023].copy()
    dados = agregar_nivel(base_2023, "grupo")
    tendencia = calcular_tendencia_nivel(dados)

    tendencia["id_municipio"] = tendencia["id_municipio"].astype(str)
    tendencia["atividade"] = tendencia["atividade"].astype(str).str.zfill(3)

    comp = referencia.merge(tendencia, on=["id_municipio", "atividade"], how="left")
    # tendencia_bruta é a escala comparável ao índice do Anexo (sem /raiz(2))
    comp["erro_abs"] = (comp["tendencia_bruta"] - comp["macroplan"]).abs()

    print(f"MAE (bruta vs. Macroplan): {comp['erro_abs'].mean():.4f}")
    print(f"Erro máximo: {comp['erro_abs'].max():.4f}")
    print(f"Correlação: {comp['tendencia_bruta'].corr(comp['macroplan']):.4f}")
    return comp.sort_values("erro_abs", ascending=False)


if __name__ == "__main__":
    print(__doc__)
    print("Pesos 2018-2025 (excluindo intervalo 2021->2022):")
    print(pesos_por_recencia(range(ANO_MIN, ANO_MAX + 1)))


# =============================================================================
# EXEMPLO DE USO NO COLAB
# =============================================================================
# !pip install basedosdados pandas pyarrow db-dtypes openpyxl -q
#
# from google.colab import auth
# auth.authenticate_user()
#
# import tendencia_vinculos as tv
#
# rais = tv.extrair_rais(billing_project_id="densidade2025")   # ~1-2 min
# rais = tv.deflacionar(rais)
# base = tv.juntar_cnae(rais, "tabela_cnae.xlsx")
#
# # 1) valide primeiro contra os 20 valores reais do Macroplan:
# comp = tv.validar_contra_macroplan(base)
# display(comp)
#
# # 2) se a correlação estiver satisfatória, gere as 5 tabelas de tendência:
# resultados = tv.gerar_todas_tendencias(base)
# resultados["grupo"].head()
# =============================================================================

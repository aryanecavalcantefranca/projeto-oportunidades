"""
=============================================================================
TENDÊNCIA DE ESTABELECIMENTOS — RAIS 2018-2025, SP
=============================================================================
Versão univariada da tendência (só Δestabelecimentos, sem componente de
renda), seguindo a mesma lógica validada em tendencia_vinculos.py:

    delta(ano-1,ano) = Δestabelecimentos, truncado em ±100%
    índice final = 0,60·delta(t-1,t) + 0,20·delta(t-2,t-1) + 0,10·delta(t-3,t-2)
                 + 0,06·delta(t-4,t-3) + 0,03·delta(t-5,t-4) + 0,01·delta(t-6,t-5)

Como há um só componente (não dois, como emprego+renda), o índice anual É
a própria variação winsorizada — sem raiz(2), sem regra de sinal
concordante. Com pesos somando 1, o resultado já nasce em [-1, +1]
(ver nota_metodologica_atualizacao_2025.md, seção 2.1).

Diferenças relevantes em relação a tendencia_vinculos.py:

  1. Fonte: `br_me_rais.microdados_estabelecimentos` (uma linha por
     estabelecimento), não `microdados_vinculos`. Contagem = COUNT(*).
  2. Filtro "sem Rais Negativa" = indicador_rais_negativa = 0. Verificado
     por amostragem (SP, 2023): toda linha com indicador_rais_negativa=0
     tem indicador_atividade_ano=1 — não é preciso combinar os dois
     indicadores. O código 2 (categoria residual, 0,16% da base) também
     fica de fora.
  3. Sem o bug de renda-hora indefinida: quando estabelecimentos cai a
     zero, delta = (0-anterior)/anterior = -1 diretamente, sem precisar de
     tratamento especial (esse problema era específico da divisão massa/
     horas na tendência de vínculos).
  4. Sem renormalização por peso_total — mesma decisão validada
     empiricamente em tendencia_vinculos.py: um intervalo ausente ou
     abaixo do piso de porte contribui zero, não redistribui peso.
  5. Piso de porte = 3 estabelecimentos no ano anterior (não 5, como em
     vínculos) — mesmo valor usado no gate `min_estabelecimentos` da
     metodologia (GATES), consistente com a escala menor da série.

Reaproveita de tendencia_vinculos.py: pesos_por_recencia, juntar_cnae,
_winsor, ANOS_EXCLUIDOS, NIVEIS — sem duplicar a lógica já validada.

Ordem de execução: extrair_estabelecimentos -> juntar_cnae (do módulo
tendencia_vinculos) -> gerar_todas_tendencias
=============================================================================
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import tendencia_vinculos as tv

UF = tv.UF
ANO_MIN, ANO_MAX = tv.ANO_MIN, tv.ANO_MAX
ANOS_EXCLUIDOS = tv.ANOS_EXCLUIDOS
NIVEIS = tv.NIVEIS

MIN_ESTABELECIMENTOS_BASE = 3   # piso de porte — mesmo valor do gate min_estabelecimentos


# =============================================================================
# 1. EXTRAÇÃO — RAIS via basedosdados/BigQuery, nível subclasse
# =============================================================================

def extrair_estabelecimentos(billing_project_id="densidade2025", uf=UF,
                              ano_min=ANO_MIN, ano_max=ANO_MAX):
    """Uma linha por (ano, município, subclasse) = nº de estabelecimentos."""
    import basedosdados as bd

    query = f"""
    SELECT
        ano,
        id_municipio,
        cnae_2_subclasse,
        COUNT(*) AS estabelecimentos
    FROM `basedosdados.br_me_rais.microdados_estabelecimentos`
    WHERE
        sigla_uf = '{uf}'
        AND ano BETWEEN {ano_min} AND {ano_max}
        AND indicador_rais_negativa = 0
        AND id_municipio IS NOT NULL
        AND cnae_2_subclasse IS NOT NULL
    GROUP BY ano, id_municipio, cnae_2_subclasse
    ORDER BY ano, id_municipio, cnae_2_subclasse
    """
    estab = bd.read_sql(query, billing_project_id=billing_project_id)

    estab["id_municipio"] = estab["id_municipio"].astype(str)
    estab["cnae_2_subclasse"] = estab["cnae_2_subclasse"].astype(str).str.zfill(7)
    estab["estabelecimentos"] = pd.to_numeric(estab["estabelecimentos"], errors="coerce")

    estab.to_parquet(f"estabelecimentos_municipio_cnae_{ano_min}_{ano_max}.parquet", index=False)
    print(f"Base extraída: {len(estab):,} linhas | "
          f"{estab['id_municipio'].nunique()} municípios | "
          f"anos {sorted(estab['ano'].unique())}")
    return estab


# =============================================================================
# 2. AGREGAÇÃO POR NÍVEL + GRADE COMPLETA
# =============================================================================

def agregar_nivel(base, nivel):
    dados = (
        base.groupby(["ano", "id_municipio", nivel], observed=True, as_index=False)
        .agg(estabelecimentos=("estabelecimentos", "sum"))
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
    dados["estabelecimentos"] = dados["estabelecimentos"].fillna(0)
    return dados


# =============================================================================
# 3. DELTA, ÍNDICE ANUAL (UNIVARIADO), TENDÊNCIA PONDERADA
# =============================================================================

def calcular_tendencia_nivel(dados, min_base=MIN_ESTABELECIMENTOS_BASE,
                              anos_excluidos=ANOS_EXCLUIDOS):
    """
    `dados` = saída de agregar_nivel(): grade completa ano x município x
    atividade, com estabelecimentos.

    Univariado: o índice anual já é a variação winsorizada, sem raiz(2).
    Pesos somam 1 -> tendencia já nasce em [-1, +1] (não precisa de
    tendencia_norm separado, ao contrário de tendencia_vinculos.py).
    """
    df = dados.sort_values(["id_municipio", "atividade", "ano"]).copy()

    g = df.groupby(["id_municipio", "atividade"], observed=True)
    df["estab_ant"] = g["estabelecimentos"].shift(1)

    base_valida = df["estab_ant"].fillna(0) >= min_base
    df["delta"] = np.where(
        base_valida,
        (df["estabelecimentos"] - df["estab_ant"]) / df["estab_ant"],
        np.nan,
    )
    df["delta"] = tv._winsor(df["delta"])
    df["indice_anual"] = df["delta"]   # univariado: índice = delta, sem combinação

    pesos = tv.pesos_por_recencia(df["ano"].unique(), anos_excluidos)
    df["peso"] = df["ano"].map(pesos).fillna(0.0)
    df["peso_valido"] = np.where(df["indice_anual"].notna(), df["peso"], 0.0)

    out = (
        df.assign(contrib=df["indice_anual"].fillna(0) * df["peso_valido"])
        .groupby(["id_municipio", "atividade"], as_index=False, observed=True)
        .agg(soma=("contrib", "sum"), peso_total=("peso_valido", "sum"))
    )
    # Sem renormalização por peso_total — mesma decisão validada em
    # tendencia_vinculos.py (intervalo ausente/abaixo do piso contribui
    # zero, não redistribui peso).
    out["tendencia_estabelecimentos"] = out["soma"]
    return out[["id_municipio", "atividade", "tendencia_estabelecimentos"]]


# =============================================================================
# 4. ORQUESTRAÇÃO — roda os 5 níveis e salva
# =============================================================================

def gerar_todas_tendencias(base_completa, niveis=NIVEIS,
                            prefixo="tendencia_estabelecimentos_sp"):
    """`base_completa` = saída de tv.juntar_cnae(estab)."""
    resultados = {}
    for nivel in niveis:
        dados = agregar_nivel(base_completa, nivel)
        tendencia = calcular_tendencia_nivel(dados)
        arquivo = f"{prefixo}_{nivel}.xlsx"
        tendencia.to_excel(arquivo, index=False)
        print(f"-> Salvo: {arquivo} ({len(tendencia):,} linhas)")
        resultados[nivel] = tendencia
    return resultados


if __name__ == "__main__":
    print(__doc__)


# =============================================================================
# EXEMPLO DE USO NO COLAB
# =============================================================================
# !wget -q -O tendencia_vinculos.py https://raw.githubusercontent.com/aryanecavalcantefranca/projeto-oportunidades/claude/vocacoes-municipais-2025-ikllz9/metodologia/tendencia_vinculos.py
# !wget -q -O tendencia_estabelecimentos.py https://raw.githubusercontent.com/aryanecavalcantefranca/projeto-oportunidades/claude/vocacoes-municipais-2025-ikllz9/metodologia/tendencia_estabelecimentos.py
#
# import sys
# sys.modules.pop("tendencia_vinculos", None)
# sys.modules.pop("tendencia_estabelecimentos", None)
# import tendencia_estabelecimentos as te
#
# estab = te.extrair_estabelecimentos(billing_project_id="densidade2025")   # ~1-2 min
# base_estab = te.tv.juntar_cnae(estab, "tabela_cnae.xlsx")
#
# resultados = te.gerar_todas_tendencias(base_estab)
# resultados["grupo"].head()
# =============================================================================

"""
=============================================================================
TENDÊNCIA DE MEI + QL_MEI — Receita Federal/Simples Nacional, 2019-2025, SP
=============================================================================
Reconstrói a extração de MEIs ativos (Receita Federal via basedosdados)
e recalcula a tendência com a mesma fórmula univariada já validada em
tendencia_estabelecimentos.py — reaproveitando agregar_nivel e
calcular_tendencia_nivel de lá (parametrizados por coluna) em vez de
duplicar a lógica pela terceira vez.

Por que recalcular em vez de aproveitar o notebook de MEI que você já
tinha: o cálculo antigo (tendencia_mei_sp_nivel_*.csv) não tem
winsorização, não tem piso de porte, e quando o ano anterior tem 0 MEIs
faz `(atual - anterior) / 1` em vez de tratar como caso especial — isso
transforma a variação numa contagem absoluta em vez de percentual,
distorcendo o índice exatamente como o bug de explosão de base pequena
que já corrigimos em vínculos.

Sem quebra de série (a fonte é Receita Federal/Simples, não RAIS) — por
isso NÃO se exclui o intervalo 2021-2022 aqui, ao contrário de vínculos e
estabelecimentos (ver nota_metodologica_atualizacao_2025.md, seção 2.1).

QL_MEI: mesma fórmula do QL tradicional (calcular_ql em
metodologia_vocacoes_2025.py), mas sobre número de MEIs ativos em vez de
massa salarial, referência estado de São Paulo, ano mais recente (2025).

Cautela documentada na nota metodológica (item 9, "itens em aberto"):
existem subclasses vedadas ao MEI (atividades que não podem ser MEI) —
isso gera zeros legítimos em boa parte da base fina (subclasse), não é
erro.

Ordem de execução: extrair_mei_historico -> juntar_cnae (de
tendencia_vinculos) -> calcular_tendencia_mei / calcular_ql_mei
=============================================================================
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import tendencia_vinculos as tv
import tendencia_estabelecimentos as te

UF = tv.UF
ANOS_MEI = range(2019, 2026)   # sem quebra de série -> usa todos os intervalos
NIVEIS = tv.NIVEIS

MIN_MEI_BASE = 3   # mesmo piso usado em estabelecimentos


# =============================================================================
# 1. EXTRAÇÃO — MEIs ativos em 31/12 de cada ano, por município x subclasse
# =============================================================================

def extrair_mei_ano(ano, billing_project_id="densidade2025", uf=UF):
    """Retrato de MEIs ativos em 31/12/`ano`. Mesma query do seu notebook."""
    import basedosdados as bd

    query = f"""
    SELECT
        e.id_municipio,
        e.cnae_fiscal_principal AS cnae_2_subclasse,
        COUNT(*) AS numero_de_meis
    FROM `basedosdados.br_me_cnpj.estabelecimentos` e
    INNER JOIN `basedosdados.br_me_cnpj.simples` s
        ON e.cnpj_basico = s.cnpj_basico
    WHERE e.sigla_uf = '{uf}'
      AND s.opcao_mei = 1
      AND s.data_opcao_mei <= '{ano}-12-31'
      AND (s.data_exclusao_mei > '{ano}-12-31' OR s.data_exclusao_mei IS NULL)
    GROUP BY e.id_municipio, e.cnae_fiscal_principal
    """
    df = bd.read_sql(query, billing_project_id=billing_project_id)
    df["ano"] = ano
    df["id_municipio"] = df["id_municipio"].astype(str)
    df["cnae_2_subclasse"] = (
        df["cnae_2_subclasse"].astype(str).str.replace(r"[^0-9]", "", regex=True).str.zfill(7)
    )
    df["numero_de_meis"] = pd.to_numeric(df["numero_de_meis"], errors="coerce")
    return df


def extrair_mei_historico(anos=ANOS_MEI, billing_project_id="densidade2025", uf=UF):
    partes = []
    for ano in anos:
        print(f"Extraindo retrato de MEIs ativos em 31/12/{ano}...")
        partes.append(extrair_mei_ano(ano, billing_project_id, uf))
    mei = pd.concat(partes, ignore_index=True)
    mei.to_parquet(f"mei_municipio_cnae_{min(anos)}_{max(anos)}.parquet", index=False)
    print(f"Base MEI extraída: {len(mei):,} linhas | anos {sorted(mei['ano'].unique())}")
    return mei


# =============================================================================
# 2. TENDÊNCIA DE MEI — reaproveita agregar_nivel/calcular_tendencia_nivel
# =============================================================================

def calcular_tendencia_mei(base_completa, niveis=NIVEIS, min_base=MIN_MEI_BASE):
    """`base_completa` = saída de tv.juntar_cnae(mei_historico)."""
    resultados = {}
    for nivel in niveis:
        dados = te.agregar_nivel(base_completa, nivel, coluna="numero_de_meis")
        tendencia = te.calcular_tendencia_nivel(
            dados, coluna="numero_de_meis", min_base=min_base,
            anos_excluidos=(), nome_saida="tendencia_mei",
        )
        resultados[nivel] = tendencia
    return resultados


# =============================================================================
# 3. QL_MEI — mesma fórmula do QL tradicional, sobre número de MEIs, ref. SP
# =============================================================================

def calcular_ql_mei(base_ano_recente, niveis=NIVEIS):
    """`base_ano_recente` = fatia de um único ano (ex.: 2025) de
    tv.juntar_cnae(mei_historico), já com a hierarquia CNAE."""
    resultados = {}
    for nivel in niveis:
        d = (
            base_ano_recente.groupby(["id_municipio", nivel], observed=True, as_index=False)
            ["numero_de_meis"].sum()
            .rename(columns={nivel: "atividade"})
            .dropna(subset=["atividade"])
        )
        tot_mun = d.groupby("id_municipio", observed=True)["numero_de_meis"].transform("sum")
        tot_ativ = d.groupby("atividade", observed=True)["numero_de_meis"].transform("sum")
        tot = d["numero_de_meis"].sum()
        d["QL_MEI"] = (d["numero_de_meis"] / tot_mun) / (tot_ativ / tot)
        d["QL_MEI"] = d["QL_MEI"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        resultados[nivel] = d[["id_municipio", "atividade", "QL_MEI"]]
    return resultados


# =============================================================================
# 4. ORQUESTRAÇÃO — junta tendência + QL_MEI por nível e salva
# =============================================================================

def gerar_tudo(base_completa, ano_referencia_ql=2025, niveis=NIVEIS,
               prefixo="mei_sp"):
    tendencias = calcular_tendencia_mei(base_completa, niveis)
    base_recente = base_completa[base_completa["ano"] == ano_referencia_ql]
    qls = calcular_ql_mei(base_recente, niveis)

    resultados = {}
    for nivel in niveis:
        out = tendencias[nivel].merge(
            qls[nivel], on=["id_municipio", "atividade"], how="outer"
        )
        out["tendencia_mei"] = out["tendencia_mei"].fillna(0.0)
        out["QL_MEI"] = out["QL_MEI"].fillna(0.0)
        arquivo = f"{prefixo}_{nivel}.xlsx"
        out.to_excel(arquivo, index=False)
        print(f"-> Salvo: {arquivo} ({len(out):,} linhas)")
        resultados[nivel] = out
    return resultados


if __name__ == "__main__":
    print(__doc__)


# =============================================================================
# EXEMPLO DE USO NO COLAB
# =============================================================================
# !wget -q -O tendencia_vinculos.py https://raw.githubusercontent.com/aryanecavalcantefranca/projeto-oportunidades/claude/vocacoes-municipais-2025-ikllz9/metodologia/tendencia_vinculos.py
# !wget -q -O tendencia_estabelecimentos.py https://raw.githubusercontent.com/aryanecavalcantefranca/projeto-oportunidades/claude/vocacoes-municipais-2025-ikllz9/metodologia/tendencia_estabelecimentos.py
# !wget -q -O tendencia_mei.py https://raw.githubusercontent.com/aryanecavalcantefranca/projeto-oportunidades/claude/vocacoes-municipais-2025-ikllz9/metodologia/tendencia_mei.py
#
# import sys
# for m in ["tendencia_vinculos", "tendencia_estabelecimentos", "tendencia_mei"]:
#     sys.modules.pop(m, None)
# import tendencia_mei as tm
#
# mei_hist = tm.extrair_mei_historico(billing_project_id="densidade2025")   # ~2-3 min (7 anos)
# base_mei = tm.tv.juntar_cnae(mei_hist, "tabela_cnae.xlsx")
#
# resultados = tm.gerar_tudo(base_mei)
# resultados["grupo"].head()
# =============================================================================

"""
=============================================================================
ÍNDICE DE OPORTUNIDADE, CATEGORIA E POSIÇÃO NO MUNICÍPIO
=============================================================================
Consolida os pilares já validados (QL massa salarial, relevância, densidade,
tendência composta, empreendedorismo) num Índice de Oportunidade único por
nível de CNAE, aplica os filtros de elegibilidade, seleciona até TOP_N
oportunidades por município (sem misturar níveis), categoriza e marca as
seções produtivas — preenchendo os campos do painel "Mapeamento de
oportunidades estratégicas" e "Detalhamento: oportunidades estratégicas
produtivas", exceto a caixa de oportunidade turística.

Reaproveita tudo que já foi validado nas etapas anteriores:
  - tendencia_vinculos.py: QL oficial (massa salarial) e tendência de vínculos
  - tendencia_estabelecimentos.py: contagem, QL e tendência de estabelecimentos
  - tendencia_mei.py: contagem, QL_MEI e tendência de MEI
  - densidade_{nivel}.xlsx / densidade_classe_corrigida.xlsx: densidade validada
  - renda_vinculos_relevancia_{nivel}_2025.xlsx: vínculos, renda média, relevância

Índice de Oportunidade (IV): média geométrica ponderada de 5 pilares em
[0,1] — especialização (0,30), relevância (0,25), tendência (0,20),
densidade (0,15), empreendedorismo (0,10). Geométrica, não aritmética: exige
desempenho razoável em todas as dimensões, evita que relevância altíssima
com especialização zero vire "oportunidade" sozinha.

Empreendedorismo (MEI) — tratamento especial: nem toda atividade tem perfil
de MEI (indústria pesada, por exemplo, é estruturalmente incompatível — em
muitos casos nem é elegível para MEI por lei). Penalizar uma vocação
industrial forte por não ter MEI seria injusto. Por isso: se o total de
MEIs de uma atividade em SP inteiro (soma de todos os municípios) for menor
que MEI_MIN_TOTAL_ESTADO, o pilar de empreendedorismo é marcado como
NÃO APLICÁVEL (NaN) para essa atividade em todo município — não como zero.
Pilar ausente é excluído da média geométrica e os pesos dos outros 4 pilares
são renormalizados proporcionalmente (mesma lógica de
`metodologia_vocacoes_2025.py::indice_vocacao`, que a primeira versão deste
arquivo tinha perdido ao reescrever — corrigido em 2026-08).

Seleção — corte duplo, mas com registro do "quase":
  1. Elegibilidade (gates de porte: vínculos, estabelecimentos, relevância, QL).
  2. Posição <= TOP_N dentro do mesmo nível e mesmo município, entre as
     elegíveis — SEMPRE calculada, mesmo se o IV não bate o mínimo. Isso
     preenche as TOP_N caixas do painel mesmo quando o corte absoluto deixaria
     alguma vazia.
  3. Dentro do top-N, `status_oportunidade` distingue "Confirmada" (IV >=
     IV_MINIMO) de "Potencial" (no top-N, elegível, mas abaixo do corte
     absoluto) — o painel pode estilizar as duas de forma diferente em vez de
     esconder a caixa.
Um município pode ter zero oportunidades confirmadas; nenhum passa de TOP_N
no total (confirmadas + potenciais).

Categoria: quadro 2x2 do Anexo (QL massa x tendência de vínculos), aplicado
a QUALQUER atividade elegível (não só as do top-N) — é uma propriedade da
atividade, não do corte de prioridade. Mais os dois marcadores
não-excludentes (empreendedorismo especializado, abertura líquida de
estabelecimentos) que alimentam os blocos "Caracterização
empresas"/"empreendedorismo" do painel.

Posição no município: ranking por IV, feito SEPARADAMENTE para cada um dos
5 níveis — nunca misture posição de Grupo com posição de Classe (Anexo,
seção 7 da nota metodológica).

Ordem de execução: montar_todos_os_niveis(base_rais_completa) -> ajuste
IV_MINIMO/GATES com diagnostico() se a mediana de oportunidades por
município fugir de 4-7.
=============================================================================
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import tendencia_vinculos as tv

NIVEIS = tv.NIVEIS
LARGURA_CODIGO = {"secao": 1, "divisao": 2, "grupo": 3, "classe": 5, "subclasse": 7}

# Arquivos esperados no diretório de trabalho, por nível.
RENDA_CONFIG = {n: (f"renda_vinculos_relevancia_{n}_2025.xlsx", n) for n in NIVEIS}
DENSIDADE_CONFIG = {
    "secao": ("densidade_secao.xlsx", "Seção"),
    "divisao": ("densidade_divisao.xlsx", "Divisão"),
    "grupo": ("densidade_grupo.xlsx", "Grupo"),
    "classe": ("densidade_classe_corrigida.xlsx", "Classe"),
    "subclasse": ("densidade_subclasse.xlsx", "Subclasse"),
}

PESOS_IV = {
    "especializacao": 0.30,
    "relevancia": 0.25,
    "tendencia": 0.20,
    "densidade": 0.15,
    "empreendedorismo": 0.10,
}
GATES = {
    "min_vinculos": 20,
    "min_estabelecimentos": 3,
    "min_relevancia": 0.005,
    "min_ql": 0.5,
}
IV_MINIMO = 0.35
TOP_N = 6   # nº de caixas do painel "Mapeamento de oportunidades estratégicas"
EPS = 0.01

MEI_MIN_TOTAL_ESTADO = 10   # abaixo disso, empreendedorismo não é aplicável à atividade

SECOES_PRODUTIVAS = ["A", "B", "C", "D", "E", "F", "H", "J", "Q"]


# =============================================================================
# 0. PADRONIZAÇÃO — os arquivos vêm de notebooks diferentes, com formatos de
# código de atividade e de município inconsistentes entre si (int, float do
# Excel, string zero-padded, string sem padding). Normaliza tudo pra um
# formato único antes de qualquer merge.
# =============================================================================

def normalizar_codigo(serie, nivel):
    largura = LARGURA_CODIGO[nivel]
    s = serie.astype(str).str.strip()
    s = s.str.replace(r"\.0$", "", regex=True)
    if nivel != "secao":
        s = s.str.zfill(largura)
    return s


def normalizar_municipio(serie):
    return serie.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)


# =============================================================================
# 1. CARREGAMENTO E JUNÇÃO — um nível por vez
# =============================================================================

def mapa_secao_por_nivel(base_rais_completa, nivel):
    """Deriva {atividade -> seção} da mesma hierarquia CNAE usada em todo o
    resto do pipeline (tv.juntar_cnae) — não depende de arquivo à parte."""
    if nivel == "secao":
        m = base_rais_completa[["secao"]].drop_duplicates().rename(columns={"secao": "atividade"})
        m["secao_letra"] = m["atividade"]
    else:
        m = base_rais_completa[[nivel, "secao"]].drop_duplicates(subset=[nivel])
        m = m.rename(columns={nivel: "atividade", "secao": "secao_letra"})
    m["atividade"] = normalizar_codigo(m["atividade"].astype(str), nivel)
    return m[["atividade", "secao_letra"]]


def carregar_nivel(nivel, base_rais_completa, ano=2025):
    arq_renda, col_renda = RENDA_CONFIG[nivel]
    arq_dens, col_dens = DENSIDADE_CONFIG[nivel]

    renda = pd.read_excel(arq_renda).rename(columns={col_renda: "atividade"})
    renda["id_municipio"] = normalizar_municipio(renda["id_municipio"])
    renda["atividade"] = normalizar_codigo(renda["atividade"], nivel)
    renda = renda[["id_municipio", "atividade", "vinculos", "renda_media", "indice_relevancia"]]

    dens = pd.read_excel(arq_dens).rename(columns={col_dens: "atividade"})
    dens["id_municipio"] = normalizar_municipio(dens["id_municipio"])
    dens["atividade"] = normalizar_codigo(dens["atividade"], nivel)
    dens = dens[["id_municipio", "atividade", "densidade"]].drop_duplicates(["id_municipio", "atividade"])

    tend_v = pd.read_excel(f"tendencia_vinculos_sp_{nivel}.xlsx")
    tend_v["id_municipio"] = normalizar_municipio(tend_v["id_municipio"])
    tend_v["atividade"] = normalizar_codigo(tend_v["atividade"], nivel)
    tend_v = tend_v[["id_municipio", "atividade", "tendencia_norm"]].rename(
        columns={"tendencia_norm": "tendencia_vinculos"}
    )

    estab = pd.read_excel(f"estabelecimentos_sp_{nivel}.xlsx")
    estab["id_municipio"] = normalizar_municipio(estab["id_municipio"])
    estab["atividade"] = normalizar_codigo(estab["atividade"], nivel)
    estab = estab.rename(columns={"QL": "QL_estabelecimentos"})
    estab = estab[["id_municipio", "atividade", "estabelecimentos", "QL_estabelecimentos",
                    "tendencia_estabelecimentos"]]

    mei = pd.read_excel(f"mei_sp_{nivel}.xlsx")
    mei["id_municipio"] = normalizar_municipio(mei["id_municipio"])
    mei["atividade"] = normalizar_codigo(mei["atividade"], nivel)
    mei = mei[["id_municipio", "atividade", "numero_de_meis", "QL_MEI", "tendencia_mei"]]

    ql_massa = tv.calcular_ql_massa(base_rais_completa, ano=ano, niveis=[nivel])[nivel]
    ql_massa["id_municipio"] = normalizar_municipio(ql_massa["id_municipio"])
    ql_massa["atividade"] = normalizar_codigo(ql_massa["atividade"], nivel)
    ql_massa = ql_massa.rename(columns={"QL": "QL_massa"})

    secao_map = mapa_secao_por_nivel(base_rais_completa, nivel)

    # `renda` é a base: só entram atividades com vínculos formais observados
    # em 2025 — sem isso não há como calcular relevância nem QL de qualquer
    # jeito, então não faz sentido como candidata a oportunidade.
    d = renda.merge(ql_massa, on=["id_municipio", "atividade"], how="left")
    d = d.merge(dens, on=["id_municipio", "atividade"], how="left")
    d = d.merge(tend_v, on=["id_municipio", "atividade"], how="left")
    d = d.merge(estab, on=["id_municipio", "atividade"], how="left")
    d = d.merge(mei, on=["id_municipio", "atividade"], how="left")
    d = d.merge(secao_map, on="atividade", how="left")

    for c in ["QL_massa", "densidade", "tendencia_vinculos", "estabelecimentos",
              "QL_estabelecimentos", "tendencia_estabelecimentos", "numero_de_meis",
              "QL_MEI", "tendencia_mei"]:
        d[c] = d[c].fillna(0.0)

    d["nivel"] = nivel
    return d


# =============================================================================
# 2. PILARES -> [0, 1]  (mesmas transformações de metodologia_vocacoes_2025.py)
# =============================================================================

def pilar_especializacao(ql):
    return (ql / (1.0 + ql)).clip(0, 1)


def pilar_relevancia(share, escala=100.0):
    return (np.log1p(escala * share) / np.log1p(escala)).clip(0, 1)


def pilar_densidade(dens):
    return pd.Series(dens).clip(0, 1).values


def pilar_tendencia(t):
    return ((pd.Series(t).clip(-1, 1) + 1.0) / 2.0).values


def pilar_empreendedorismo(ql_mei, tend_mei):
    e = pilar_especializacao(pd.Series(ql_mei).fillna(0))
    t = pilar_tendencia(pd.Series(tend_mei).fillna(0))
    return np.sqrt(e * t)


def marcar_mei_aplicavel(df, minimo_estadual=MEI_MIN_TOTAL_ESTADO):
    """Uma atividade só disputa o pilar de empreendedorismo se tiver MEI em
    volume plausível em SP inteiro — evita punir vocação industrial forte só
    por o setor ser estruturalmente incompatível com MEI."""
    d = df.copy()
    total_estado = d.groupby("atividade")["numero_de_meis"].transform("sum")
    d["mei_aplicavel"] = total_estado >= minimo_estadual
    return d


# =============================================================================
# 3. TENDÊNCIA COMPOSTA E ÍNDICE DE OPORTUNIDADE
# =============================================================================

def calcular_indice_oportunidade(df, pesos=PESOS_IV, eps=EPS):
    """
    Média geométrica ponderada. Pilar ausente (NaN) é excluído da conta e os
    pesos dos demais são renormalizados — não é tratado como zero. Hoje só
    pilar_empreendedorismo pode ficar NaN (ver marcar_mei_aplicavel), mas a
    lógica é genérica para qualquer pilar futuro.
    """
    d = df.copy()

    tend_composta = (
        2 * d["tendencia_vinculos"] + 1 * d["tendencia_estabelecimentos"] + 1 * d["tendencia_mei"]
    ) / 4.0
    d["tendencia_composta"] = tend_composta.clip(-1, 1)

    d["pilar_especializacao"] = pilar_especializacao(d["QL_massa"])
    d["pilar_relevancia"] = pilar_relevancia(d["indice_relevancia"])
    d["pilar_densidade"] = pilar_densidade(d["densidade"])
    d["pilar_tendencia"] = pilar_tendencia(d["tendencia_composta"])
    d["pilar_empreendedorismo"] = pilar_empreendedorismo(d["QL_MEI"], d["tendencia_mei"])
    d.loc[~d["mei_aplicavel"], "pilar_empreendedorismo"] = np.nan

    log_soma = np.zeros(len(d))
    peso_soma = np.zeros(len(d))
    for nome, w in pesos.items():
        v = pd.to_numeric(d[f"pilar_{nome}"], errors="coerce")
        valido = v.notna().values
        v = v.fillna(eps).clip(eps, 1.0).values
        log_soma += np.where(valido, w * np.log(v), 0.0)
        peso_soma += np.where(valido, w, 0.0)
    d["indice_oportunidade"] = np.where(peso_soma > 0, np.exp(log_soma / peso_soma), 0.0)
    return d


# =============================================================================
# 4. GATES DE ELEGIBILIDADE
# =============================================================================

def aplicar_gates(df, gates=GATES):
    d = df.copy()
    d["gate_porte"] = d["vinculos"] >= gates["min_vinculos"]
    d["gate_estab"] = d["estabelecimentos"] >= gates["min_estabelecimentos"]
    d["gate_relev"] = d["indice_relevancia"] >= gates["min_relevancia"]
    d["gate_ql"] = d["QL_massa"] >= gates["min_ql"]
    d["elegivel"] = d["gate_porte"] & d["gate_estab"] & d["gate_relev"] & d["gate_ql"]
    return d


# =============================================================================
# 5. SELEÇÃO — top-N sempre preenchido, com status Confirmada/Potencial
# =============================================================================

def selecionar_oportunidades(df, iv_minimo=IV_MINIMO, top_n=TOP_N):
    """
    posicao_municipio é calculada para qualquer atividade elegível dentro do
    top_n — não só as que passam do IV_MINIMO. Isso preenche as TOP_N caixas
    do painel mesmo quando o corte absoluto deixaria alguma vazia.

    status_oportunidade distingue, dentro do top_n:
      "Confirmada" -> IV >= iv_minimo (oportunidade "de verdade")
      "Potencial"  -> elegível e no top_n, mas abaixo do corte absoluto
                      (ex.: município pequeno onde nada bate 0,35, mas ainda
                      há uma atividade relativamente melhor que as outras)
    e_oportunidade fica True só para "Confirmada" — mantém compatível com
    quem já usa esse campo (ex.: categorizar()).
    """
    d = df.copy()
    d["posicao_municipio"] = (
        d.where(d["elegivel"])
        .groupby("id_municipio", observed=True)["indice_oportunidade"]
        .rank(ascending=False, method="first")
    )

    no_top_n = d["elegivel"] & (d["posicao_municipio"] <= top_n)
    confirmada = no_top_n & (d["indice_oportunidade"] >= iv_minimo)
    potencial = no_top_n & ~confirmada

    d["status_oportunidade"] = np.select([confirmada, potencial], ["Confirmada", "Potencial"], default="")
    d["e_oportunidade"] = confirmada
    d.loc[~no_top_n, "posicao_municipio"] = np.nan
    return d


# =============================================================================
# 6. CATEGORIZAÇÃO — propriedade da atividade elegível, independe do top-N
# =============================================================================

def categorizar(df):
    """
    Baseado em `elegivel` (passou nos gates de porte), não em `e_oportunidade`
    (top-N + IV mínimo) — a categoria descreve a atividade, o status de
    Confirmada/Potencial descreve a prioridade dela no ranking. Uma atividade
    pode ser "Vocação promissora" e ainda assim ficar fora do top-N do
    município (perdeu de outras 6 melhores).
    """
    d = df.copy()
    cond = [
        (~d["elegivel"]),
        (d["QL_massa"] > 1) & (d["tendencia_vinculos"] > 0),
        (d["QL_massa"] > 1) & (d["tendencia_vinculos"] <= 0),
        (d["QL_massa"] <= 1) & (d["QL_massa"] >= 0.5) & (d["tendencia_vinculos"] > 0),
    ]
    rotulo = [
        "Não elegível",
        "Vocação promissora",
        "Vocação sem crescimento",
        "Vocação potencial",
    ]
    d["categoria_oportunidade"] = np.select(cond, rotulo, default="Sem classificação")

    d["marcador_empreendedorismo"] = np.where(
        d["QL_MEI"] > 1,
        np.where(d["tendencia_mei"] > 0,
                 "Empreendedorismo especializado e em expansão",
                 "Empreendedorismo especializado"),
        "",
    )
    d["marcador_empresarial"] = np.where(
        d["tendencia_estabelecimentos"] > 0, "Abertura líquida de estabelecimentos", ""
    )
    return d


def marcar_produtiva(df, secoes=SECOES_PRODUTIVAS):
    d = df.copy()
    d["produtiva"] = d["secao_letra"].astype(str).str.upper().isin(secoes)
    return d


# =============================================================================
# 7. ORQUESTRAÇÃO
# =============================================================================

def montar_oportunidades(nivel, base_rais_completa, ano=2025,
                          pesos=PESOS_IV, gates=GATES, iv_minimo=IV_MINIMO, top_n=TOP_N,
                          mei_min_total_estado=MEI_MIN_TOTAL_ESTADO):
    d = carregar_nivel(nivel, base_rais_completa, ano=ano)
    d = marcar_mei_aplicavel(d, minimo_estadual=mei_min_total_estado)
    d = calcular_indice_oportunidade(d, pesos=pesos)
    d = aplicar_gates(d, gates=gates)
    d = selecionar_oportunidades(d, iv_minimo=iv_minimo, top_n=top_n)
    d = categorizar(d)
    d = marcar_produtiva(d)
    return d.sort_values(["id_municipio", "indice_oportunidade"], ascending=[True, False])


def montar_todos_os_niveis(base_rais_completa, niveis=NIVEIS, ano=2025, prefixo="oportunidades_sp"):
    resultados = {}
    for nivel in niveis:
        d = montar_oportunidades(nivel, base_rais_completa, ano=ano)
        arquivo = f"{prefixo}_{nivel}.xlsx"
        d.to_excel(arquivo, index=False)
        print(f"-> Salvo: {arquivo} ({len(d):,} linhas)")
        resultados[nivel] = d
    return resultados


# =============================================================================
# 8. DIAGNÓSTICO — para calibrar IV_MINIMO e os gates
# =============================================================================

def diagnostico(df, col_mun="id_municipio"):
    """Alvo razoável: mediana de Confirmadas entre a metade e o total do
    TOP_N por município, com uma cauda de municípios sem nenhuma
    confirmada (mas ainda com Potenciais preenchendo as caixas do painel)."""
    conf = df[df["status_oportunidade"] == "Confirmada"]
    pot = df[df["status_oportunidade"] == "Potencial"]
    por_mun_conf = conf.groupby(col_mun, observed=True).size()
    por_mun_top = df[df["status_oportunidade"] != ""].groupby(col_mun, observed=True).size()
    todos = df[col_mun].nunique()

    print(f"Municípios na base .................................. {todos}")
    print(f"Municípios com >= 1 Confirmada ...................... {por_mun_conf.size} ({por_mun_conf.size/todos:.1%})")
    print(f"Municípios só com Potencial (nenhuma Confirmada) .... {por_mun_top.size - por_mun_conf.size}")
    print(f"Municípios sem nada no top-N (nem Potencial) ........ {todos - por_mun_top.size}")
    print("\nConfirmadas por município:")
    print(por_mun_conf.describe().round(2).to_string())
    print(f"\nTotal Confirmada: {len(conf):,} | Total Potencial: {len(pot):,}")
    print("\nDistribuição por categoria (só elegíveis):")
    print(df[df["elegivel"]]["categoria_oportunidade"].value_counts().to_string())
    return por_mun


if __name__ == "__main__":
    print(__doc__)


# =============================================================================
# EXEMPLO DE USO NO COLAB
# =============================================================================
# !wget -q -O tendencia_vinculos.py https://raw.githubusercontent.com/aryanecavalcantefranca/projeto-oportunidades/claude/vocacoes-municipais-2025-ikllz9/metodologia/tendencia_vinculos.py
# !wget -q -O indice_oportunidade.py https://raw.githubusercontent.com/aryanecavalcantefranca/projeto-oportunidades/claude/vocacoes-municipais-2025-ikllz9/metodologia/indice_oportunidade.py
#
# import sys
# for m in ["tendencia_vinculos", "indice_oportunidade"]:
#     sys.modules.pop(m, None)
# import tendencia_vinculos as tv
# import indice_oportunidade as io
#
# # reconstrói a base RAIS completa (2018-2025, com hierarquia CNAE) a
# # partir do parquet já extraído — não precisa consultar o BigQuery de novo
# rais = pd.read_parquet("rais_municipio_cnae_2018_2025.parquet")
# rais = tv.deflacionar(rais)
# base = tv.juntar_cnae(rais, "tabela_cnae.xlsx")
#
# # os outros arquivos (renda_vinculos_relevancia_*, densidade_*,
# # tendencia_vinculos_sp_*, estabelecimentos_sp_*, mei_sp_*) precisam estar
# # no mesmo diretório do Colab
# resultados = io.montar_todos_os_niveis(base)
#
# io.diagnostico(resultados["grupo"])
# resultados["grupo"].head()
# =============================================================================

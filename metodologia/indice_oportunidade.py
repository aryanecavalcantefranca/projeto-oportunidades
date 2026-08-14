"""
=============================================================================
ÍNDICE DE ADERÊNCIA ECONÔMICA, CATEGORIA E POSIÇÃO NO MUNICÍPIO
=============================================================================
Consolida os pilares já validados (QL massa salarial, relevância, densidade,
tendência composta, empreendedorismo) num Índice de Aderência Econômica
único por nível de CNAE, aplica os filtros de elegibilidade, monta um
ranking GERAL por município (sem misturar níveis, sem limite de tamanho),
categoriza e marca as seções produtivas — preenchendo os campos do painel
"Mapeamento de oportunidades estratégicas" e "Detalhamento: oportunidades
estratégicas produtivas", exceto a caixa de oportunidade turística.

O nome do índice mudou de "Índice de Oportunidade" para "Índice de
Aderência Econômica" em 2026-08, a pedido do usuário: mede o quanto uma
atividade combina com o perfil econômico já existente no município
(especialização + relevância + tendência + densidade), não uma promessa de
mercado — "oportunidade" segue existindo só como conceito do painel
(categoria_oportunidade, exibir_mapeamento, montar_oportunidades), não como
nome do índice em si. A palavra "vocação" foi descartada explicitamente
pelo usuário como alternativa.

Reaproveita tudo que já foi validado nas etapas anteriores:
  - tendencia_vinculos.py: QL oficial (massa salarial) e tendência de vínculos
  - tendencia_estabelecimentos.py: contagem, QL e tendência de estabelecimentos
  - tendencia_mei.py: contagem, QL_MEI e tendência de MEI
  - densidade_{nivel}.xlsx / densidade_classe_corrigida.xlsx: densidade validada
  - renda_vinculos_relevancia_{nivel}_2025.xlsx: vínculos, renda média, relevância

Índice de Aderência Econômica (IAE) = núcleo + bônus:

  núcleo = média geométrica ponderada de 4 pilares em [0,1] — especialização
           (0,30), relevância (0,25), tendência (0,20), densidade (0,15).
           Geométrica, não aritmética: exige desempenho razoável em todas as
           dimensões do núcleo, evita que relevância altíssima com
           especialização zero vire "oportunidade" sozinha.

  bônus_empreendedorismo = 0,10 × pilar_empreendedorismo (aditivo, não entra
           na geométrica). Empreendedorismo (MEI) é setorialmente muito
           específico — concentrado em serviços, ausente por razões
           estruturais em setores inteiros (indústria pesada, em muitos
           casos nem elegível para MEI por lei). Se ele fosse um pilar
           multiplicativo como os outros 4, um valor baixo (não precisa ser
           zero) já derrubaria o índice inteiro por causa de como a
           geométrica reage a números perto de zero — puniria vocação
           industrial forte só por não ter perfil de microempreendedor.
           Como bônus aditivo, só soma quando presente, nunca subtrai
           (decisão de 2026-08, depois de discussão sobre esse ponto).

  índice = mín(1,0, núcleo + bônus_empreendedorismo)

marcar_mei_aplicavel() ainda existe, mas com outro papel: não é mais para
evitar punição (o bônus aditivo já resolve isso), é para evitar que 2-3
MEIs por acaso gerem um QL_MEI artificialmente alto e um bônus espúrio numa
atividade onde o total de MEIs em SP inteiro é irrelevante.

Seleção — ranking geral, TOP_N é só filtro de exibição (mudou em 2026-08 a
pedido do usuário: "a classificação precisa ser geral, os 6 eu preciso só
naquela parte do mapeamento"):
  1. Elegibilidade (gates de porte: vínculos, estabelecimentos, relevância, QL).
  2. `posicao_municipio`: ranking 1..N sobre TODAS as atividades do
     município com indice_aderencia_economica > 0, elegíveis ou não (mudou de novo
     em 2026-08, a pedido do usuário: "nos casos em que o índice seja maior
     que 0, haja uma posição entre todas as atividades de cada nível") — uma
     atividade com sinal positivo mas que não passou nos gates de porte
     ainda ganha uma posição no ranking, só não fica elegível.
  3. `exibir_mapeamento`: True só para atividades elegíveis dentro das TOP_N
     posições — é o filtro que a tela de Mapeamento usa pra decidir quais
     das 6 caixas preencher. Não limita a base, só marca o que aparece
     naquela tela específica.
Um município pode ter zero atividades elegíveis; o ranking geral não tem
teto, só `exibir_mapeamento` tem.

`status_oportunidade` (Confirmada/Potencial) e `e_oportunidade` foram
REMOVIDOS em 2026-08 a pedido do usuário — variáveis demais para o uso real
do painel, sem necessidade de uma segunda camada de corte além de
`elegivel` (gates) e `categoria_oportunidade` (seção de categorização,
abaixo). `IV_MINIMO` deixou de existir por causa disso.

Categoria: quadro 2x2 do Anexo (QL massa x tendência de vínculos), aplicado
a QUALQUER atividade elegível (não só as do top-N) — é uma propriedade da
atividade, não do corte de prioridade. Mais os dois marcadores
não-excludentes (empreendedorismo especializado, abertura líquida de
estabelecimentos) que alimentam os blocos "Caracterização
empresas"/"empreendedorismo" do painel.

Posição no município: ranking por IAE, feito SEPARADAMENTE para cada um dos
5 níveis — nunca misture posição de Grupo com posição de Classe (Anexo,
seção 7 da nota metodológica).

Ordem de execução: montar_todos_os_niveis(base_rais_completa) -> ajuste
GATES com diagnostico() se a mediana de atividades elegíveis por município
fugir de 4-7.
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

# Núcleo: média geométrica, entra na conta multiplicativa (exige desempenho
# mínimo em todas). Empreendedorismo NÃO está aqui — ver PESO_BONUS abaixo.
PESOS_NUCLEO = {
    "especializacao": 0.30,
    "relevancia": 0.25,
    "tendencia": 0.20,
    "densidade": 0.15,
}
# Bônus aditivo: soma até PESO_BONUS_EMPREENDEDORISMO ao núcleo, nunca
# subtrai. Perfil de MEI é setorialmente muito específico (concentrado em
# serviços) para forçar como exigência multiplicativa como os outros 4.
PESO_BONUS_EMPREENDEDORISMO = 0.10
GATES = {
    "min_vinculos": 20,
    "min_estabelecimentos": 3,
    "min_relevancia": 0.005,
    "min_ql": 0.5,
}
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
    """Filtro de ruído: com o bônus aditivo (ver calcular_indice_aderencia_economica)
    a ausência de MEI já não penaliza nada, então isso não protege mais
    contra punição — protege contra RECOMPENSA espúria (2-3 MEIs por acaso
    gerando um QL_MEI enorme e um bônus artificial)."""
    d = df.copy()
    total_estado = d.groupby("atividade")["numero_de_meis"].transform("sum")
    d["mei_aplicavel"] = total_estado >= minimo_estadual
    return d


# =============================================================================
# 3. TENDÊNCIA COMPOSTA E ÍNDICE DE ADERÊNCIA ECONÔMICA
# =============================================================================

def calcular_indice_aderencia_economica(df, pesos_nucleo=PESOS_NUCLEO,
                                         peso_bonus_empreendedorismo=PESO_BONUS_EMPREENDEDORISMO, eps=EPS):
    """
    índice = núcleo (média geométrica de especialização/relevância/tendência/
    densidade) + bônus de empreendedorismo (aditivo, 0 a peso_bonus, nunca
    subtrai). Perfil de MEI é setorialmente específico demais (concentrado
    em serviços) pra forçar como exigência multiplicativa como os outros 4
    pilares — um setor sem MEI relevante não perde nada, só não ganha o
    bônus.

    Pilar do núcleo ausente (NaN) é excluído da conta e os pesos dos demais
    são renormalizados — não é tratado como zero. Nenhum dos 4 pilares do
    núcleo fica NaN hoje, mas a lógica é genérica para o caso futuro.
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
    d.loc[~d["mei_aplicavel"], "pilar_empreendedorismo"] = 0.0

    log_soma = np.zeros(len(d))
    peso_soma = np.zeros(len(d))
    for nome, w in pesos_nucleo.items():
        v = pd.to_numeric(d[f"pilar_{nome}"], errors="coerce")
        valido = v.notna().values
        v = v.fillna(eps).clip(eps, 1.0).values
        log_soma += np.where(valido, w * np.log(v), 0.0)
        peso_soma += np.where(valido, w, 0.0)
    d["indice_nucleo"] = np.where(peso_soma > 0, np.exp(log_soma / peso_soma), 0.0)

    d["bonus_empreendedorismo"] = peso_bonus_empreendedorismo * d["pilar_empreendedorismo"]
    d["indice_aderencia_economica"] = (d["indice_nucleo"] + d["bonus_empreendedorismo"]).clip(0, 1)
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
# 5. SELEÇÃO — ranking geral + filtro de exibição do Mapeamento
# =============================================================================

def selecionar_oportunidades(df, top_n=TOP_N):
    """
    posicao_municipio é um ranking GERAL — 1..N sobre TODAS as atividades do
    município com indice_aderencia_economica > 0, elegíveis ou não, sem
    limite de tamanho. O corte de TOP_N não vive aqui: é um filtro de
    exibição (a tela de Mapeamento, que só tem TOP_N caixas), não uma
    restrição da base de dados (decidido em 2026-08, a pedido do usuário:
    "a classificação precisa ser geral, os 6 eu preciso só naquela parte do
    mapeamento").

    A base do ranking é `indice_aderencia_economica > 0`, não `elegivel` —
    uma atividade pode ter índice positivo e ainda não passar nos gates de
    porte; antes ela ficava sem posição nenhuma (NaN), agora entra no
    ranking geral como qualquer outra (mudou em 2026-08, a pedido do
    usuário: "nos casos em que o índice seja maior que 0, haja uma posição
    entre todas as atividades de cada nível").

    exibir_mapeamento: conveniência para a tela de Mapeamento no Power BI —
    True só para atividades elegíveis dentro das top_n posições do
    município. Filtra só a visual das TOP_N caixas; não afeta
    posicao_municipio.

    status_oportunidade (Confirmada/Potencial) e e_oportunidade foram
    REMOVIDOS em 2026-08 a pedido do usuário — variáveis demais para o uso
    real do painel. `elegivel` (gates de porte, seção 4) e
    `categoria_oportunidade` (categorizar(), seção 6) já cobrem a
    distinção que interessa.
    """
    d = df.copy()
    d["posicao_municipio"] = (
        d.where(d["indice_aderencia_economica"] > 0)
        .groupby("id_municipio", observed=True)["indice_aderencia_economica"]
        .rank(ascending=False, method="first")
    )
    d["exibir_mapeamento"] = d["elegivel"] & (d["posicao_municipio"] <= top_n)
    return d


# =============================================================================
# 6. CATEGORIZAÇÃO — propriedade da atividade elegível, independe do top-N
# =============================================================================

def categorizar(df):
    """
    Baseado em `elegivel` (passou nos gates de porte) — a categoria descreve
    a atividade, independente da posição dela no ranking. Uma atividade pode
    ser "Oportunidade promissora" e ainda assim ficar fora do top-N do
    município (perdeu de outras 6 melhores em posicao_municipio).

    Rótulos usam "Oportunidade", não "Vocação" — alinhado com o nome do
    painel ("Mapeamento de Oportunidades Estratégicas") e com o pedido do
    usuário em 2026-08 de padronizar a terminologia.
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
        "Oportunidade promissora",
        "Oportunidade sem crescimento",
        "Oportunidade potencial",
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
                          pesos_nucleo=PESOS_NUCLEO, peso_bonus_empreendedorismo=PESO_BONUS_EMPREENDEDORISMO,
                          gates=GATES, top_n=TOP_N,
                          mei_min_total_estado=MEI_MIN_TOTAL_ESTADO):
    d = carregar_nivel(nivel, base_rais_completa, ano=ano)
    d = marcar_mei_aplicavel(d, minimo_estadual=mei_min_total_estado)
    d = calcular_indice_aderencia_economica(d, pesos_nucleo=pesos_nucleo,
                                             peso_bonus_empreendedorismo=peso_bonus_empreendedorismo)
    d = aplicar_gates(d, gates=gates)
    d = selecionar_oportunidades(d, top_n=top_n)
    d = categorizar(d)
    d = marcar_produtiva(d)
    return d.sort_values(["id_municipio", "indice_aderencia_economica"], ascending=[True, False])


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
# 8. DIAGNÓSTICO — para calibrar os gates
# =============================================================================

def diagnostico(df, col_mun="id_municipio"):
    """
    Sem status_oportunidade (Confirmada/Potencial) — removido em 2026-08 a
    pedido do usuário. `elegivel` (gates de porte, sem teto) e
    `exibir_mapeamento` (elegível + teto TOP_N, para a tela de Mapeamento)
    são as duas métricas de referência para calibrar GATES.
    """
    eleg = df[df["elegivel"]]
    por_mun_eleg = eleg.groupby(col_mun, observed=True).size()
    por_mun_mapa = df[df["exibir_mapeamento"]].groupby(col_mun, observed=True).size()
    todos = df[col_mun].nunique()

    print(f"Municípios na base .................................. {todos}")
    print(f"Municípios com >= 1 atividade elegível .............. {por_mun_eleg.size} ({por_mun_eleg.size/todos:.1%})")
    print(f"Municípios sem nada elegível ......................... {todos - por_mun_eleg.size}")
    print("\nAtividades elegíveis por município (ranking geral, sem teto):")
    print(por_mun_eleg.describe().round(2).to_string())
    print("\nCaixas preenchidas na tela de Mapeamento (exibir_mapeamento, teto TOP_N):")
    print(por_mun_mapa.describe().round(2).to_string())
    print(f"\nTotal de atividades elegíveis: {len(eleg):,}")
    print("\nDistribuição por categoria (só elegíveis):")
    print(eleg["categoria_oportunidade"].value_counts().to_string())
    return por_mun_eleg


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

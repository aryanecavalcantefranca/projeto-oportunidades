# Revisão da metodologia – Matriz de Priorização dos Municípios (Anexo III)

Base: notebook `clusterização_2.ipynb`, bases do `Indicadores.zip`, arquivos
`Ranking_IAP_Municipios_2.xlsx` / `Ranking_IAP_Representatividade_2.xlsx` e
Anexo III do Edital de Chamamento Público – Cidades Inteligentes.

Tudo aqui é reproduzível com `python pipeline.py` (gera os arquivos de `resultados/`).
A reprodução da versão original bate exatamente com o notebook
(181 / 145 / 78 / 240 municípios, mesmos centroides e silhueta 0,312) e com os
dois arquivos entregues (mesmo IAP, mesma distância e mesmos rankings).

---

## 1. A correção da raiz do peso já foi feita?

**Não.** No notebook (célula 18) os eixos padronizados são multiplicados pelo peso:

```python
dados_z["CIF_kmeans"] = dados_z["CIF"] * 0.35
dados_z["IMD_kmeans"] = dados_z["IMD"] * 0.40
dados_z["CSE_kmeans"] = dados_z["CSE"] * 0.25
```

e o item 3.2 / Equação (6) do Anexo III descreve exatamente isso.

**O comentário está correto.** Com eixos de variância 1, a contribuição de cada eixo
para a distância euclidiana ao quadrado (que é o que o K-Means minimiza, Eq. 7) é
proporcional a `peso²`:

| Eixo | Peso do edital | Peso efetivo hoje (`w² / Σw²`) | Fator com a correção (`√w`) | Peso efetivo corrigido |
|---|---|---|---|---|
| CIF | 35% | 35,5% | 0,592 | 35% |
| IMD | 40% | **46,4%** | 0,632 | 40% |
| CSE | 25% | **18,1%** | 0,500 | 25% |

Ou seja, hoje o IMD ganha ~6 p.p. e o socioeconômico perde ~7 p.p. em relação ao
que o Anexo III afirma ("a influência de cada eixo na formação dos perfis passou a
refletir a ponderação estabelecida").

## 2. Achado importante: as letras dos perfis nos arquivos entregues estão trocadas

Os arquivos `Ranking_IAP_*_2.xlsx` **não** seguem a Tabela 1 do Anexo III.
Comparando os centroides de cada letra do arquivo com a definição do edital:

| Letra no arquivo | Centroide (CIF, IMD, CSE) | Corresponde no Anexo III a | Fórmula de IAP efetivamente usada |
|---|---|---|---|
| A | (−0,36; −0,26; −0,13) – tudo abaixo | **B** | IAP_B |
| B | (+0,09; −0,25; −0,08) | **D** | IAP_D |
| C | (−0,12; +0,48; +0,20) | **A** | IAP_A |
| D | (+0,66; +0,14; +0,03) | **C** | IAP_C |

O IAP de cada município foi calculado com a fórmula certa para o formato do grupo
(as equações estão amarradas ao número do cluster), mas a **letra exportada** está
errada. Consequência prática: aplicar as vagas do item 5.1.3 (A=13, B=12, C=10,
D=15) sobre esses arquivos seleciona, por exemplo, 13 municípios do grupo "tudo
abaixo da média" no lugar do Perfil A. A distribuição de vagas só é coerente com a
nomenclatura do Anexo III (A=181, B=145, C=78, D=240 municípios).

Causa: o mapeamento é fixo (`{1:"A", 3:"B", 2:"C", 0:"D"}`), mas o número que o
K-Means dá a cada cluster é arbitrário e pode mudar com a versão do scikit-learn,
a ordem das linhas ou a reexecução de células. No `pipeline.py` a letra passa a ser
atribuída automaticamente pela **assinatura de sinais** da Tabela 1 (atribuição
ótima pelo método húngaro), então não depende mais da numeração.

> Isso também explica o comentário "a mudança é quase toda entre A e B": nas letras
> do arquivo, A e B são, pelo Anexo III, os perfis **B e D**. É exatamente onde
> ocorre a migração (ver item 3).

Todos os arquivos novos estão com as letras do Anexo III.

## 3. Resultado da correção (`Z × √peso`)

| | Original (`Z × peso`) | Revisada (`Z × √peso`) |
|---|---|---|
| Peso efetivo na distância | 35,5 / 46,4 / 18,1 | **35 / 40 / 25** |
| Municípios A / B / C / D | 181 / 145 / 78 / 240 | 180 / 156 / 72 / 236 |
| Silhueta | 0,312 | 0,290 |

Centroides em desvios-padrão (média de `Z` de cada eixo no perfil):

| Perfil | Original CIF / IMD / CSE | Revisada CIF / IMD / CSE |
|---|---|---|
| A | −0,33 / +1,20 / +0,80 | −0,34 / +1,20 / +0,83 |
| B | −1,03 / −0,65 / −0,51 | −0,80 / −0,79 / −0,97 |
| C | +1,88 / +0,35 / +0,11 | +1,97 / +0,35 / **+0,03** |
| D | +0,26 / −0,63 / −0,33 | +0,19 / −0,50 / **−0,00** |

Migração entre perfis (linhas = original, colunas = revisada):

| | A | B | C | D | Total |
|---|---|---|---|---|---|
| A | 175 | 1 | 0 | 5 | 181 |
| B | 3 | 115 | 0 | 27 | 145 |
| C | 2 | 0 | 71 | 5 | 78 |
| D | 0 | 40 | 1 | 199 | 240 |

- **87,0%** dos municípios ficam no mesmo perfil (o colega obteve 88%; a diferença é
  de inicialização/versão do K-Means). A troca é quase toda **B ↔ D** (67 dos 84).
  Faz sentido: B e D diferem principalmente em CSE, que é o eixo que ganha peso.
- O perfil B fica mais "socioeconômico" (CSE −0,97σ) e o D passa a ter CSE na média.
- A queda da silhueta é esperada e não é critério para escolher pesos (os pesos são
  definição normativa; a silhueta só mede separação no espaço deformado pelos pesos).

### Efeito sobre os 50 selecionados (vagas 13/12/10/15)

| Critério de ordenação | Selecionados em comum (original × revisada) |
|---|---|
| IAP (regra do edital) | **42 / 50** – todas as 8 trocas no Perfil D |
| Representatividade (distância ao centroide) | 27 / 50 |

No IAP, 7 dos 15 primeiros do Perfil D original (Arco-Íris, São João das Duas
Pontes, Ribeira, Salmourão, Riversul, Piquete, Ribeirão Branco) migram para o
Perfil B, e 1 (Pilar do Sul) para o C. Ou seja, os "mais alinhados" ao D pelo IAP
original eram municípios na fronteira com o B – ver item 5.2.

### Estabilidade frente à variação dos pesos (±20% em cada eixo, 26 cenários)

| Indicador (pior cenário) | `Z × peso` | `Z × √peso` |
|---|---|---|
| % no mesmo perfil | 33,1% | **53,7%** |
| ARI (concordância da partição) | 0,29 | **0,55** |
| Spearman do ranking IAP | 0,61 | **0,77** |
| Spearman do ranking por centroide | −0,00 | **0,71** |
| Selecionados (de 50) mantidos – IAP | 20 | **28** |
| Selecionados (de 50) mantidos – centroide | 1 | **25** |

Confirma o comentário: o ranking pelo centroide, que na versão original
praticamente se desfaz no pior cenário, fica estável com `√peso`. Em média
(todos os cenários) a revisada também é melhor (88,0% vs 84,0% no mesmo perfil).

## 4. Ponto de atenção: o IAP deve continuar com o peso "cheio"

O K-Means é quadrático, o IAP é **linear**. Se, depois da correção, o IAP for
calculado sobre as colunas `*_kmeans` (já multiplicadas por `√peso`), o peso efetivo
do IAP passa a ser 0,59/0,63/0,50 → **34% / 37% / 29%**, e o erro migra de lugar.

Regra adotada no `pipeline.py`:

| Etapa | Operação | Por quê |
|---|---|---|
| K-Means e distância ao centroide (Eq. 7 e 8) | `Z × √peso` | distância euclidiana eleva ao quadrado |
| IAP (Eq. 9–12) | `Z × peso` | combinação linear: o peso entra uma vez |

Com isso o IAP de cada município é **idêntico** ao da versão original; o que muda é
apenas o perfil a que ele pertence (e, portanto, com quem compete).

## 5. Outras propostas de melhoria

### 5.1 Ajustar o texto do Anexo III (necessário se a correção for adotada)
- Item 3.2 / Eq. (6): `CIF* = √0,35 × Z_CIF`, `IMD* = √0,40 × Z_IMD`,
  `CSE* = √0,25 × Z_CSE`, com a justificativa: "como o K-Means minimiza a soma dos
  quadrados das distâncias, os eixos são multiplicados pela raiz quadrada dos pesos,
  de modo que a contribuição de cada eixo à distância seja exatamente 35%, 40% e 25%".
- Item 6 / Eq. (9)–(12): explicitar que o IAP usa os eixos padronizados
  **multiplicados pelos pesos** (`0,35·Z_CIF`, …). Hoje o texto fala apenas em
  "escore padronizado", mas o código usa os ponderados.
- Uniformizar nomes: o item 6 chama os eixos de "Índice de Maturidade Digital" e
  "Complexidade Socioeconômica"; nos itens 3 e 5 são "Infraestrutura e Maturidade
  Digital" e "Condição Socioeconômica".
- A Eq. (6) está com a formatação quebrada no .docx (três equações coladas).
- Tabela 1: com a correção, o CSE de C (+0,03σ) e de D (−0,00σ) fica **na média**;
  descrever como "próximo da média" em vez de "acima/abaixo".
- Atualizar os testes de Kruskal-Wallis/Qui-quadrado do item 5 com os novos perfis.

### 5.2 Sinal de eixo "neutro" no IAP
O IAP usa apenas o **sinal** do centroide (±1). Quando o perfil está na média de um
eixo, o sinal é arbitrário mas pesa igual aos demais: com a correção, o IAP_D
(`CIF − IMD − CSE`) passa a privilegiar municípios com **pior** socioeconômico num
perfil cujo CSE é 0,00σ. Isso empurra o topo do ranking para a fronteira com o
Perfil B – foi exatamente o que aconteceu nas 8 trocas do item 3.

Duas alternativas, em ordem de simplicidade:
1. **Sinal neutro**: atribuir sinal 0 ao eixo quando `|centroide| < 0,25σ`.
2. **IAP direcional**: `IAP_k = Σ_e w_e · Z_e · μ_ke / ‖μ_k‖` (projeção na direção do
   centroide). Generaliza a regra atual: eixos marcantes pesam mais, eixos na média
   pesam ~0. Teste rápido na versão revisada: B mantém 12/12 selecionados, A 7/13,
   C 7/10, D 8/15.

Como o item 5.1.2 do edital fixa as Eq. 9–12, isso exigiria retificação; fica como
recomendação para o próximo ciclo.

### 5.3 IAP × representatividade medem coisas diferentes
A correlação de Spearman entre o ranking IAP e o ranking por distância ao centroide
é ≈ 0 em todos os perfis (−0,16 a +0,03). O IAP premia os municípios mais
**extremos** na direção do perfil; a distância premia os mais **típicos**. Os
selecionados pelo IAP têm representatividade média de 35 a 50 (escala 0–100).
São critérios legítimos, mas com objetivos diferentes – a escolha precisa ser
explícita. O edital (5.1.2 e 5.1.4) prevê o IAP; a representatividade pode servir
como critério de desempate ou como diagnóstico.

### 5.4 Robustez da partição
- Silhueta ~0,30: a estrutura de grupos é fraca; no pior cenário de ±20% nos pesos
  quase metade dos municípios muda de perfil mesmo com a correção. Recomenda-se
  registrar no Anexo III a análise de sensibilidade e, se possível, uma verificação
  por bootstrap (ARI médio entre reamostragens).
- Escolha de K = 4 é normativa; vale documentar o cotovelo/silhueta para K=2..8.

### 5.5 Indicadores muito discretos
- `iplanejamento`: 83% dos municípios com nota C; `nivel_geral`: 99% em 3 ou 4;
  CIF assume só 16 valores distintos. Na prática, 40% do IMD e 50% do CIF funcionam
  como variáveis quase binárias, e as fronteiras dos perfis seguem os degraus
  dessas notas. Para o próximo ciclo, avaliar usar a nota numérica do IEG-M (em vez
  da faixa A–C) e os subíndices contínuos do IMCI.

### 5.6 Higiene do código
- Rótulos por assinatura de sinais (feito no `pipeline.py`).
- Células duplicadas e um "Score"/"Ranking" alternativo (células 58–60, média
  simples dos eixos) que não entra no arquivo final – remover para evitar confusão.
- O IAP é calculado sobre `base_cluster` (mesmo índice de `dados`); manter o
  `merge` por `cod_ibge` em vez de atribuição por índice (`dados_z["Perfil"] = ...`).

---

## Mudança mínima no notebook

```python
# Célula 18 – entrada do K-Means
pesos = np.array([0.35, 0.40, 0.25])
dados_z[["CIF_kmeans", "IMD_kmeans", "CSE_kmeans"]] = dados_z[["CIF", "IMD", "CSE"]] * np.sqrt(pesos)

# Célula 62 – IAP continua com o peso cheio (linear)
for e, w in zip(["CIF", "IMD", "CSE"], pesos):
    ranking[f"{e}_pond"] = ranking[e] * w        # usar *_pond nas Eq. 9-12
```

e substituir o `mapa_perfis` fixo pela função `nomear_perfis` do `pipeline.py`.

## Arquivos gerados (`resultados/`)

| Arquivo | Conteúdo |
|---|---|
| `Ranking_IAP_Municipios_raiz_peso.xlsx` | **Proposta**: perfis com `√peso`, ordenação por IAP; abas de selecionados (vagas), perfis e parâmetros |
| `Ranking_Representatividade_raiz_peso.xlsx` | **Proposta**: perfis com `√peso`, ordenação por distância ao centroide |
| `Ranking_IAP_Municipios_original_corrigido.xlsx` | Versão original (`peso`) com as letras corrigidas conforme o Anexo III |
| `Ranking_Representatividade_original_corrigido.xlsx` | Idem, por representatividade |
| `Comparacao_Original_vs_RaizPeso.xlsx` | Migração de perfis, município a município, entradas/saídas dos 50 selecionados e cenários de sensibilidade |

Colunas: `*_z` = eixo padronizado; `*_kmeans` = entrada do K-Means (`Z × √peso` na
proposta); `IAP` = Eq. 9–12 com `Z × peso`; `Distancia_Centroide` no espaço do K-Means;
`Representatividade` = 0–100 dentro do perfil (100 = mais próximo do centroide).

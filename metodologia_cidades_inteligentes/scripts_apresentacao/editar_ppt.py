"""Atualiza o deck de metodologia para a versão com pesos via raiz quadrada."""
import copy
import re
import sys
from pathlib import Path

import openpyxl
from lxml import etree

ED = Path(sys.argv[1])  # pasta descompactada (já com o slide novo adicionado)
NOVO = sys.argv[2]      # nome do xml do slide novo (ex.: slide36.xml)
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"a": A, "c": "http://schemas.openxmlformats.org/drawingml/2006/chart"}


def load(name):
    path = ED / "ppt/slides" / name
    return path, etree.parse(str(path))


def save(path, tree):
    tree.write(str(path), xml_declaration=True, encoding="UTF-8", standalone=True)


def ts(tree):
    return tree.findall(".//a:t", NS)


def sub_seq(tree, pairs):
    """Substitui textos de <a:t> em ordem de documento (cada par casa uma vez)."""
    i = 0
    for t in ts(tree):
        if i < len(pairs) and t.text == pairs[i][0]:
            t.text = pairs[i][1]
            i += 1
    assert i == len(pairs), f"casou {i}/{len(pairs)}; parou em {pairs[i] if i < len(pairs) else ''}"


def para_por_texto(tree, inicio):
    ps = [p for p in tree.findall(".//a:p", NS)
          if "".join(t.text or "" for t in p.findall(".//a:t", NS)).startswith(inicio)]
    assert len(ps) == 1, (inicio, len(ps))
    return ps[0]


def set_para(p, runs):
    """Reescreve o parágrafo com runs [(texto, negrito)], reaproveitando a formatação."""
    rs = p.findall("a:r", NS)
    normal = next((r for r in rs if r.find("a:rPr", NS).get("b") != "1"), rs[0])
    bold = next((r for r in rs if r.find("a:rPr", NS).get("b") == "1"), None)
    for r in rs:
        p.remove(r)
    for br in p.findall("a:br", NS):
        p.remove(br)
    end = p.find("a:endParaRPr", NS)
    for texto, b in runs:
        modelo = bold if (b and bold is not None) else normal
        r = copy.deepcopy(modelo)
        rpr = r.find("a:rPr", NS)
        if b:
            rpr.set("b", "1")
        elif "b" in rpr.attrib:
            del rpr.attrib["b"]
        r.find("a:t", NS).text = texto
        if end is not None:
            end.addprevious(r)
        else:
            p.append(r)


def editar(name, fn):
    path, tree = load(name)
    fn(tree)
    save(path, tree)


# ---------------------------------------------------------------- slide 6
def s6(t):
    set_para(para_por_texto(t, "Nova padronização dos eixos"), [
        ("Nova padronização dos eixos e aplicação dos pesos ", False),
        ("35%, 40% e 25%", True),
        (", via raiz quadrada no agrupamento.", False)])


# ---------------------------------------------------------------- slide 12
def s12(t):
    set_para(para_por_texto(t, "Variáveis de entrada"), [
        ("Variáveis de entrada: ", True),
        ("exclusivamente os três eixos padronizados (CFI, IMD e CSE), multiplicados pela ", False),
        ("raiz quadrada dos pesos", True),
        (".", False)])


# ---------------------------------------------------------------- slide 13
def s13(t):
    sub_seq(t, [("181", "180"), ("28,1%", "28,0%"), ("145", "156"), ("22,5%", "24,2%"),
                ("78", "72"), ("12,1%", "11,2%"), ("240 ", "236 "), ("37,3%", "36,6%")])


# ---------------------------------------------------------------- slide 14 / 15
def s14(t):
    sub_seq(t, [("145", "156"), ("22,5% ", "24,2% "), ("240", "236"), ("37,3% ", "36,6% ")])
    set_para(para_por_texto(t, "Municípios com capacidade fiscal e institucional"), [
        ("Municípios com ", False),
        ("capacidade fiscal e institucional ", True),
        ("acima da média ", True),
        ("estadual, porém com infraestrutura digital abaixo da média e condição "
         "socioeconômica muito próxima da média. É o agrupamento mais numeroso do Estado.", False)])


def s15(t):
    sub_seq(t, [("181", "180"), ("78", "72"), ("28,1%", "28,0%"), ("12,1% ", "11,2% ")])


# ---------------------------------------------------------------- slide 17
def s17(t):
    sub_seq(t, [("Valor médio de cada eixo por perfil, em escala padronizada e ponderada",
                 "Valor médio de cada eixo por perfil, em escala padronizada e ponderada (eixo × √peso)")])
    set_para(para_por_texto(t, "PERFIL A:"), [
        ("PERFIL A: ", True), ("os três eixos abaixo da média, em magnitudes semelhantes.", False)])
    set_para(para_por_texto(t, "PERFIL B:"), [
        ("PERFIL B: ", True),
        ("capacidade fiscal e institucional acima da média; infraestrutura digital abaixo da "
         "média; condição socioeconômica praticamente na média.", False)])
    set_para(para_por_texto(t, "PERFIL D:"), [
        ("PERFIL D: ", True),
        ("os três eixos acima da média, com destaque para a capacidade fiscal e institucional; "
         "condição socioeconômica próxima da média.", False)])


# ---------------------------------------------------------------- slide 18
RA = {  # (RA, n, %)
    "A": [("São José do Rio Preto", 26, "16,7"), ("Presidente Prudente", 21, "13,5")],
    "B": [("São José do Rio Preto", 48, "20,3"), ("Araçatuba", 26, "11,0")],
    "C": [("Campinas", 46, "25,6"), ("São Paulo", 22, "12,2")],
    "D": [("São José do Rio Preto", 10, "13,9"), ("Marília", 10, "13,9")],
}


def s18(t):
    sub_seq(t, [("POP MEDIANA", "POP MÉDIA"),
                ("  2.806.941  ", "  2.277.841  "), ("(6,30%)", "(5,1%)"),
                (" 3.632.819 ", " 3.872.584 "), ("(8,2%)", "(8,7%)"),
                (" 23.673.011 ", " 24.235.453 "), ("(53,3%)", "(54,6%)"),
                (" 2.846.468 ", " 2.573.361 "), ("(6,4%)", "(5,8%)"),
                (" 19.358", " 14.602"), (" 15.137", " 16.409"),
                (" 130.790", " 134.641"), (" 36.493", " 35.741"),
                (" 151.564.598.271 ", " 82.199.119.718 "), ("(4,40%)", "(2,39%)"),
                (" 166.072.195.649 ", " 216.829.556.785 "), ("(4,82%)", "(6,29%)"),
                (" 1.824.934.454.960 ", " 1.860.265.769.453 "), ("(52,98%)", "(54,00%)"),
                (" 235.417.679.080 ", " 218.694.482.004 "), ("(6,83%)", "(6,35%)")])
    # Composição por RA: parágrafos de nome e de contagem, na ordem A, B, C, D
    antigos = ["São José do Rio Preto ", "29 municípios (20%)", "Presidente Prudente ", "11 municípios (7,6%)",
               "São José do Rio Preto ", "43 municípios (17,9%)", "Araçatuba", "27 municípios (11,3%)",
               "Campinas", "46 municípios (25,4%)", "São Paulo", "21 municípios (11,6%)",
               "Marília", "11 municípios (14,1%)", "Campinas", "9 municípios (11,5%)"]
    novos = []
    for k in "ABCD":
        for nome, n, pct in RA[k]:
            novos += [(nome + " ",), (f"{n} municípios ", f"({pct}%)")]
    i = 0
    for p in t.findall(".//a:p", NS):
        if i == len(antigos):
            break
        tt = p.findall(".//a:t", NS)
        if "".join(x.text or "" for x in tt) == antigos[i]:
            for x in tt:
                x.text = ""
            tt[0].text = novos[i][0]
            if len(novos[i]) > 1:
                if len(tt) > 1:
                    tt[-1].text = novos[i][1]
                else:
                    tt[0].text += novos[i][1]
            i += 1
    assert i == len(antigos), i


# ---------------------------------------------------------------- slide 20
def s20(t):
    sub_seq(t, [("São João das Duas Pontes", "Mesópolis"), ("1,191", "1,145"),
                ("Mesópolis", "Luiziânia"), ("1,145", "1,072")])


# ---------------------------------------------------------------- slide 21
def s21(t):
    sub_seq(t, [("CF1", "CFI"),
                ("−0,361", "−0,473"), ("−0,258", "−0,498"), ("−0,127", "−0,485"),
                ("0,091", "0,111"), ("−0,252", "−0,318"), ("−0,082", "−0,002"),
                ("−0,116", "−0,202"), ("0,480", "0,761"), ("0,199", "0,417"),
                ("0,659", "1,167"), ("0,142", "0,220"), ("0,028", "0,016")])
    set_para(para_por_texto(t, "Os três eixos entram com"), [
        ("Os eixos entram ponderados pela ", False), ("raiz quadrada dos pesos", True),
        (" (35%, 40% e 25% na distância).", False)])


# ---------------------------------------------------------------- slide 22
def s22(t):
    old = ["Pedregulho", "0,129", "Ribeirão do Sul", "0,140", "Catiguá", "0,147", "Turiúba", "0,149",
           "Pedranópolis", "0,150",
           "Caconde", "0,066", "Itaju", "0,067", "Ipaussu", "0,070", "Aspásia", "0,071", "Sarutaiá", "0,072",
           "Barra Bonita", "0,148", "Franca", "0,151", "Santa Rita do Passa Quatro", "0,158", "Orlândia",
           "0,159", "Ourinhos", "0,162",
           "Oriente", "0,071", "Jumirim", "0,078", "Piratininga", "0,133", "Itatinga", "0,167", "Gália", "0,185"]
    new = ["Uchoa", "0,099", "Mira Estrela", "0,108", "Queluz", "0,127", "Palmares Paulista", "0,145",
           "Vera Cruz", "0,150",
           "Santa Cruz das Palmeiras", "0,051", "Nipoã", "0,084", "Onda Verde", "0,122", "Pindorama", "0,126",
           "Auriflama", "0,128",
           "Barra Bonita", "0,243", "Franca", "0,244", "Orlândia", "0,267", "Santa Rita do Passa Quatro",
           "0,273", "Ourinhos", "0,279",
           "Oriente", "0,122", "Jumirim", "0,123", "Piratininga", "0,194", "Itatinga", "0,263", "Itararé", "0,304"]
    sub_seq(t, list(zip(old, new)))


# ---------------------------------------------------------------- slide 23
def s23(t):
    sub_seq(t, [("Distância do centroide = 0,831 ", "Distância ao centroide = 1,339 "),
                ("Ranking de representatividade = 180º", "Ranking de representatividade = 179º (de 180)"),
                ("Distância ao centroide = 0,148 ", "Distância ao centroide = 0,243 ")])


# ---------------------------------------------------------------- slide 28 (oculto)
def s28(t):
    sub_seq(t, [("181", "156"), ("28,1%", "24,2%"), ("13", "12"), ("6", "6"),
                ("145", "236"), ("22,5%", "36,6%"), ("12", "15"), ("6", "8"),
                ("78", "180"), ("12,1%", "28,0%"), ("10", "13"), ("5", "6"),
                ("240", "72"), ("37,3%", "11,2%"), ("15", "10"), ("8", "5")])


# ---------------------------------------------------------------- slide 35 (oculto)
def s35(t):
    sub_seq(t, [("H = 220,55", "H = 247,70"), ("χ² = 280,31", "χ² = 314,51"), ("0,381", "0,403")])


# ---------------------------------------------------------------- slide novo
def novo(t):
    sub_seq(t, [("PROPOSTA 2 - ", ""), ("PROXIMIDADE AO CENTROIDE", "PONDERAÇÃO DOS EIXOS NO AGRUPAMENTO"),
                ("Nova métrica de ordenação ", "Os pesos entram no K-Means pela raiz quadrada, para que a "
                 "influência de cada eixo seja exatamente 35%, 40% e 25%"),
                ("intraperfil", ""), (": distância de cada município ao centroide do seu perfil", ""),
                ("O QUE MUDA EM RELAÇÃO À VERSÃO ANTERIOR", "O PROBLEMA CORRIGIDO"),
                ("O QUE O ÍNDICE MEDE — E O QUE NÃO MEDE", "EFEITO DA CORREÇÃO"),
                ("CENTROIDE", "EIXO"), ("CFI", "PESO DEFINIDO"), ("IMD", "INFLUÊNCIA ANTES"),
                ("CSE", "INFLUÊNCIA AGORA"),
                ("A", "CFI"), ("−0,361", "35%"), ("−0,258", "35,5%"), ("−0,127", "35%"),
                ("B", "IMD"), ("0,091", "40%"), ("−0,252", "46,4%"), ("−0,082", "40%"),
                ("C", "CSE"), ("−0,116", "25%"), ("0,480", "18,1%"), ("0,199", "25%"),
                ("D", "Total"), ("0,659", "100%"), ("0,142", "100%"), ("0,028", "100%")])
    # tabela: valores em branco (sem cor de sinal)
    for tc in t.findall(".//a:tc", NS):
        for rpr in tc.findall(".//a:rPr", NS):
            sf = rpr.find("a:solidFill", NS)
            if sf is not None and sf.find("a:srgbClr", NS) is not None:
                sf.remove(sf[0])
                etree.SubElement(sf, f"{{{A}}}schemeClr").set("val", "bg1")
    set_para(para_por_texto(t, "A proposta 1"), [
        ("O K-Means agrupa os municípios pela ", False), ("distância euclidiana ao quadrado", True),
        (". Ao multiplicar cada eixo diretamente pelo peso, o peso também entra ao quadrado: a "
         "influência efetiva era de 35,5% (CFI), 46,4% (IMD) e 18,1% (CSE), e a condição "
         "socioeconômica perdia força.", False)])
    set_para(para_por_texto(t, "Mede a representatividade"), [
        ("87% dos municípios permanecem no mesmo perfil", True),
        ("; as mudanças concentram-se entre A e B, que se diferenciam sobretudo pela condição "
         "socioeconômica.", False)])
    set_para(para_por_texto(t, "Utiliza as mesmas"), [
        ("Mais estabilidade: ", True),
        ("com variação de ±20% nos pesos, no pior cenário 54% dos municípios mantêm o perfil "
         "(antes, 33%).", False)])
    set_para(para_por_texto(t, "Não é comparável"), [
        ("O IAP não muda: ", True),
        ("por ser uma soma linear, continua calculado com os pesos de 35%, 40% e 25%.", False)])
    set_para(para_por_texto(t, "Para cada perfil calcula-se"), [
        ("Antes do agrupamento, cada eixo padronizado é multiplicado pela ", False),
        ("raiz quadrada do seu peso", True),
        (": CFI × 0,59, IMD × 0,63 e CSE × 0,50. A contribuição de cada eixo para a distância "
         "passa a corresponder exatamente ao peso definido.", False)])
    set_para(para_por_texto(t, "Os três eixos entram com"), [
        ("√peso no K-Means e na distância ao centroide; ", False), ("peso cheio no IAP", True), (".", False)])


for nome, fn in [("slide6.xml", s6), ("slide12.xml", s12), ("slide13.xml", s13), ("slide14.xml", s14),
                 ("slide15.xml", s15), ("slide17.xml", s17), ("slide18.xml", s18), ("slide20.xml", s20),
                 ("slide21.xml", s21), ("slide22.xml", s22), ("slide23.xml", s23), ("slide28.xml", s28),
                 ("slide35.xml", s35), (NOVO, novo)]:
    editar(nome, fn)
    print("ok", nome)


# ---------------------------------------------------------------- gráficos
def chart(n, valores, extra=None):
    path = ED / f"ppt/charts/chart{n}.xml"
    x = path.read_text(encoding="utf8")
    sers = re.findall(r"<c:val>.*?</c:val>", x, flags=re.S)
    assert len(sers) == len(valores)
    for s, vals in zip(sers, valores):
        novo_s = s
        pts = re.findall(r'<c:pt idx="(\d)"><c:v>[^<]*</c:v></c:pt>', s)
        for idx, v in zip(pts, vals):
            novo_s = re.sub(rf'(<c:pt idx="{idx}"><c:v>)[^<]*(</c:v>)', rf"\g<1>{v}\g<2>", novo_s)
        x = x.replace(s, novo_s)
    for a, b in (extra or []):
        assert a in x
        x = x.replace(a, b)
    path.write_text(x, encoding="utf8")
    rel = (ED / f"ppt/charts/_rels/chart{n}.xml.rels").read_text()
    emb = ED / "ppt/embeddings" / re.search(r"embeddings/([^\"]+)", rel).group(1)
    wb = openpyxl.load_workbook(emb)
    ws = wb.active
    for j, vals in enumerate(valores):
        for i, v in enumerate(vals):
            ws.cell(row=2 + i, column=2 + j, value=v)
    wb.save(emb)


chart(3, [[156, 236, 180, 72]])
chart(4, [[-0.47, 0.11, -0.20, 1.17], [-0.50, -0.32, 0.76, 0.22], [-0.49, -0.00, 0.42, 0.02]],
      extra=[('<c:max val="0.8"/>', '<c:max val="1.4"/>')])
print("graficos ok")

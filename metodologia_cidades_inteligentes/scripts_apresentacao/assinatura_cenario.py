"""Slide "Assinatura estatística" para o cenário de pesos 35/45/20.

Uso: python assinatura_cenario.py <pasta_descompactada_com_o_slide>
"""
import re
import sys
from pathlib import Path

import openpyxl
from lxml import etree

ED = Path(sys.argv[1])
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"a": A}
VAL = [[-0.61, 0.15, -0.20, 1.11], [-0.44, -0.42, 0.80, 0.24], [-0.24, -0.15, 0.36, 0.05]]

slide = next((ED / "ppt/slides").glob("slide*.xml"))
tree = etree.parse(str(slide))


def para(inicio, runs):
    ps = [p for p in tree.iter(f"{{{A}}}p") if "".join(p.itertext()).startswith(inicio)]
    assert len(ps) == 1, inicio
    rs = ps[0].findall("a:r", NS)
    for r in rs[1:]:
        ps[0].remove(r)
    import copy
    base = rs[0]
    novos = []
    for txt, b in runs:
        r = copy.deepcopy(base)
        rp = r.find("a:rPr", NS)
        rp.set("b", "1") if b else rp.attrib.pop("b", None)
        r.find("a:t", NS).text = txt
        novos.append(r)
    for r in novos:
        base.addprevious(r)
    ps[0].remove(base)


para("Valor médio de cada eixo", [("Valor médio de cada eixo por perfil, em escala padronizada e ponderada "
                                   "(eixo × √peso) · cenário de pesos 35% / 45% / 20%", False)])
para("PERFIL A:", [("PERFIL A: ", True), ("os três eixos abaixo da média, com maior distância em capacidade "
                                          "fiscal e institucional.", False)])
para("PERFIL B:", [("PERFIL B: ", True), ("capacidade fiscal e institucional acima da média; infraestrutura "
                                          "digital e condição socioeconômica abaixo da média.", False)])
tree.write(str(slide), xml_declaration=True, encoding="UTF-8", standalone=True)

chart = next(f for f in (ED / "ppt/charts").glob("chart*.xml") if "Condição Socioeconômica" in f.read_text("utf8"))
x = chart.read_text(encoding="utf8")
for ser, vals in zip(re.findall(r"<c:val>.*?</c:val>", x, flags=re.S), VAL):
    novo = ser
    for i, v in enumerate(vals):
        novo = re.sub(rf'(<c:pt idx="{i}"><c:v>)[^<]*(</c:v>)', rf"\g<1>{v}\g<2>", novo)
    x = x.replace(ser, novo)
assert '<c:min val="-0.6"/>' in x
x = x.replace('<c:min val="-0.6"/>', '<c:min val="-0.8"/>')
chart.write_text(x, encoding="utf8")
rel = (ED / "ppt/charts/_rels" / f"{chart.name}.rels").read_text()
emb = ED / "ppt/embeddings" / re.search(r"embeddings/([^\"]+)", rel).group(1)
wb = openpyxl.load_workbook(emb)
ws = wb.active
for j, vals in enumerate(VAL):
    for i, v in enumerate(vals):
        ws.cell(row=2 + i, column=2 + j, value=v)
wb.save(emb)
print("ok")

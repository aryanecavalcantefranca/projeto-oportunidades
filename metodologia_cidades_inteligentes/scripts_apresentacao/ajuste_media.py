"""Marca o CSE dos Perfis B e D como "≈ na média" e explica o caso no slide do IAP.

Uso: python ajuste_media.py <pasta_descompactada>
"""
import copy
import sys
from pathlib import Path

from lxml import etree

ED = Path(sys.argv[1])
NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
NEUTRO, BORDA = "9AA0A6", "5A5F66"


def shape(tree, nome, contem):
    """Forma pelo nome e por um texto que contém (os nomes se repetem no slide)."""
    achados = [sp for sp in tree.iter("{%s}sp" % NS["p"])
               if sp.find(".//p:cNvPr", NS).get("name") == nome and contem in "".join(sp.itertext())]
    assert len(achados) == 1, (nome, contem, len(achados))
    return achados[0]


def pilula(arquivo, texto_nome, borda_nome, antigo):
    path = ED / "ppt/slides" / arquivo
    tree = etree.parse(str(path))
    txt = shape(tree, texto_nome, antigo)
    t = [x for x in txt.iter("{%s}t" % NS["a"]) if x.text == antigo]
    assert len(t) == 1, (arquivo, antigo)
    t[0].text = "≈ na média"
    t[0].getparent().find("a:rPr/a:solidFill/a:srgbClr", NS).set("val", NEUTRO)
    off = txt.find(".//a:off", NS)
    tx, ty = int(off.get("x")), int(off.get("y"))
    bordas = [sp for sp in tree.iter("{%s}sp" % NS["p"])
              if sp.find(".//p:cNvPr", NS).get("name") == borda_nome
              and int(sp.find(".//a:off", NS).get("y")) == ty
              and abs(int(sp.find(".//a:off", NS).get("x")) - tx) < 200000]
    assert len(bordas) == 1, (arquivo, len(bordas))
    bordas[0].find("p:spPr/a:ln/a:solidFill/a:srgbClr", NS).set("val", BORDA)
    tree.write(str(path), xml_declaration=True, encoding="UTF-8", standalone=True)


pilula("slide14.xml", "Text 19", "Shape 18", "▼ abaixo")  # Perfil B
pilula("slide15.xml", "Text 36", "Shape 35", "▲ acima")   # Perfil D

# ---- slide do IAP: asterisco na tabela + nota explicativa
path = ED / "ppt/slides/slide19.xml"
tree = etree.parse(str(path))
tbl = tree.find(".//a:tbl", NS)
linhas = tbl.findall("a:tr", NS)
for tr in linhas:
    cel = tr.findall("a:tc", NS)
    rot = "".join(cel[0].itertext()).strip()
    if rot in ("B", "D"):
        t = cel[3].find(".//a:t", NS)
        t.text = t.text + "*"

alvo = None
for p in tree.iter("{%s}p" % NS["a"]):
    if "".join(p.itertext()).startswith("Não é comparável entre perfis"):
        alvo = p
nova = copy.deepcopy(alvo)
rs = nova.findall("a:r", NS)
for r in rs[1:]:
    nova.remove(r)
rpr = rs[0].find("a:rPr", NS)
rpr.attrib.pop("b", None)
bold = copy.deepcopy(rs[0])
bold.find("a:rPr", NS).set("b", "1")
bold.find("a:t", NS).text = "* CSE de B e D ≈ na média: "
rs[0].find("a:t", NS).text = ("o sinal segue a fórmula do edital, mas esse eixo "
                              "praticamente não diferencia esses perfis.")
rs[0].addprevious(bold)
alvo.addnext(nova)
tree.write(str(path), xml_declaration=True, encoding="UTF-8", standalone=True)
print("ajuste média ok")

# ---- texto do cartão do Perfil D, coerente com "CSE ≈ na média"
path = ED / "ppt/slides/slide15.xml"
tree = etree.parse(str(path))
ps = [p for p in tree.iter("{%s}p" % NS["a"])
      if "".join(p.itertext()).startswith("Municípios com desempenho acima da média estadual nos três eixos")]
assert len(ps) == 1
ts = ps[0].findall(".//a:t", NS)
novos = ["Municípios com capacidade fiscal e institucional e infraestrutura digital acima da média "
         "estadual, com ", "destaque para a capacidade ", "fiscal e ", "institucional. ",
         "A condição socioeconômica fica na média do Estado."]
assert len(ts) == len(novos), [t.text for t in ts]
for t, n in zip(ts, novos):
    t.text = n
tree.write(str(path), xml_declaration=True, encoding="UTF-8", standalone=True)
print("texto do Perfil D ok")

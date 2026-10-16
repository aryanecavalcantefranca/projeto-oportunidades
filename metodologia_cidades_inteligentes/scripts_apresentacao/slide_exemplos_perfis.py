"""Slide "Um exemplo por perfil": 1º pelo IAP × 1º pela representatividade (centroide).

Uso: python slide_exemplos_perfis.py <pasta_descompactada> <slide.xml>
O slide deve ser uma cópia de um slide com faixas, título ("Text 4") e subtítulo ("Text 5").
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline as p  # noqa: E402

ED, SLIDE = Path(sys.argv[1]), sys.argv[2]
NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
DECL = " ".join(f'xmlns:{k}="{v}"' for k, v in NS.items())
COR = {"A": "C0A2C7", "B": "263253", "C": "4496CD", "D": "7A8BC6"}  # cores dos perfis (mapa)
LETRA = {"A": "1E1E1E", "B": "FFFFFF", "C": "FFFFFF", "D": "1E1E1E"}
LAR, BRA, CINZA, CARD, BORDA = "F99828", "E6E6E6", "9AA0A6", "1E1E1E", "3A3A3A"
FRASE = {
    "A": "{a} está abaixo da média nos três eixos com muito mais intensidade que o grupo; "
         "{b} tem valores próximos aos da média do Perfil A.",
    "B": "{a} é o caso extremo do perfil (CFI muito alto, IMD e CSE muito baixos) e, por isso, "
         "o menos típico; {b} está praticamente no centro do grupo.",
    "C": "{a} tem forte alinhamento às direções do Perfil C, mas se afasta da combinação média; "
         "{b} é o que mais se aproxima do padrão do grupo.",
    "D": "{a} é extrema em CFI e IMD: 1ª no IAP e a mais distante do centro; "
         "{b} reproduz o padrão médio do Perfil D.",
}
fmt = lambda v, d=3: f"{v:.{d}f}".replace(".", ",")  # noqa: E731

_id = [700]


def nid():
    _id[0] += 1
    return _id[0]


def forma(x, y, cx, cy, fill, prst="roundRect", adj=3500, linha=None):
    ln = (f'<a:ln w="9525"><a:solidFill><a:srgbClr val="{linha}"/></a:solidFill></a:ln>' if linha
          else "<a:ln><a:noFill/></a:ln>")
    av = f'<a:avLst><a:gd name="adj" fmla="val {adj}"/></a:avLst>' if prst == "roundRect" else "<a:avLst/>"
    i = nid()
    return (f'<p:sp {DECL}><p:nvSpPr><p:cNvPr id="{i}" name="Forma {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{int(x)}" y="{int(y)}"/><a:ext cx="{int(cx)}" cy="{int(cy)}"/></a:xfrm>'
            f'<a:prstGeom prst="{prst}">{av}</a:prstGeom><a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>'
            f'{ln}</p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="pt-BR"/></a:p>'
            f"</p:txBody></p:sp>")


def texto(x, y, cx, cy, pars, anchor="t", algn="l"):
    """pars: lista de parágrafos; cada um é lista de runs (texto, tamanho, negrito, cor)."""
    ps = []
    for runs in pars:
        rs = "".join(
            f'<a:r><a:rPr lang="pt-BR" sz="{sz}"{" b=\"1\"" if b else ""} noProof="0"><a:solidFill>'
            f'<a:srgbClr val="{cor}"/></a:solidFill><a:latin typeface="Montserrat" pitchFamily="2" '
            f'charset="0"/></a:rPr><a:t>{escape(t)}</a:t></a:r>' for t, sz, b, cor in runs)
        ps.append(f'<a:p><a:pPr marL="0" indent="0" algn="{algn}"><a:lnSpc><a:spcPct val="100000"/>'
                  f'</a:lnSpc><a:spcAft><a:spcPts val="200"/></a:spcAft><a:buNone/></a:pPr>{rs}</a:p>')
    i = nid()
    return (f'<p:sp {DECL}><p:nvSpPr><p:cNvPr id="{i}" name="Texto {i}"/><p:cNvSpPr txBox="1"/><p:nvPr/>'
            f'</p:nvSpPr><p:spPr><a:xfrm><a:off x="{int(x)}" y="{int(y)}"/><a:ext cx="{int(cx)}" '
            f'cy="{int(cy)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" rtlCol="0" '
            f'anchor="{anchor}"/><a:lstStyle/>{"".join(ps)}</p:txBody></p:sp>')


# ------------------------------------------------------------------ dados
d = p.carregar_dados()
e = p.construir_eixos(d)
r, _, _ = p.montar_resultado(d, e, np.sqrt(p.PESOS), "raiz")
ex = {}
for k, g in r.groupby("Perfil"):
    ex[k] = (len(g), g.sort_values("Ranking").iloc[0], g.sort_values("Ranking_Representatividade").iloc[0])

# ------------------------------------------------------------------ slide
path = ED / "ppt/slides" / SLIDE
tree = etree.parse(str(path))
sptree = tree.find(".//p:spTree", NS)
manter = {"Shape 0", "Shape 1", "Shape 2", "Shape 3", "Text 4", "Text 5"}
for ch in list(sptree)[2:]:
    nm = ch.find(".//p:cNvPr", NS)
    if nm is None or nm.get("name") not in manter:
        sptree.remove(ch)
for nm, txt in (("Text 4", "UM EXEMPLO POR PERFIL: IAP × CENTROIDE"),
                ("Text 5", "Em cada perfil, o 1º colocado pelo IAP e o 1º pela proximidade ao centroide "
                           "(representatividade)")):
    sp = next(s for s in sptree if s.find(".//p:cNvPr", NS) is not None
              and s.find(".//p:cNvPr", NS).get("name") == nm)
    ts = sp.findall(".//a:t", NS)
    ts[0].text = txt
    for t in ts[1:]:
        t.text = ""

X0, LARG, GAP = 548640, 11091672, 137160
W = (LARG - 3 * GAP) / 4
Y0, H = 1554480, 4206240
PAD = 182880
novos = []
for i, k in enumerate("ABCD"):
    n, a, b = ex[k]
    x = X0 + i * (W + GAP)
    novos.append(forma(x, Y0, W, H, CARD))
    # cabeçalho: selo com a letra + nº de municípios
    novos.append(forma(x + PAD, Y0 + PAD, 420000, 420000, COR[k], adj=18000))
    novos.append(texto(x + PAD, Y0 + PAD, 420000, 420000, [[(k, 1800, True, LETRA[k])]], "ctr", "ctr"))
    novos.append(texto(x + PAD + 520000, Y0 + PAD, W - 2 * PAD - 520000, 420000,
                       [[(f"PERFIL {k}", 1300, True, BRA)], [(f"{n} municípios", 1000, False, CINZA)]], "ctr"))
    yb = Y0 + PAD + 600000
    blocos = [
        ("1º NO IAP", a.municipio, [f"IAP = {fmt(a.IAP)}",
                                    f"Representatividade: {a.Ranking_Representatividade}º de {n}"]),
        ("1º EM REPRESENTATIVIDADE", b.municipio, [f"Distância ao centroide = {fmt(b.Distancia_Centroide)}",
                                                    f"IAP: {b.Ranking}º de {n}"]),
    ]
    for rot, nome, linhas in blocos:
        novos.append(forma(x + PAD, yb, W - 2 * PAD, 1010000, "262626", adj=6000, linha=BORDA))
        novos.append(texto(x + PAD + 110000, yb + 90000, W - 2 * PAD - 220000, 900000,
                           [[(rot, 900, True, LAR)], [(nome, 1250, True, BRA)]]
                           + [[(l, 1000, False, BRA)] for l in linhas]))
        yb += 1010000 + 110000
    frase = FRASE[k].format(a=a.municipio, b=b.municipio)
    novos.append(texto(x + PAD, yb + 40000, W - 2 * PAD, Y0 + H - yb - 140000, [[(frase, 1000, False, CINZA)]]))

# faixa de conclusão
yc = Y0 + H + 137160
novos.append(forma(X0, yc, LARG, 560000, CARD, adj=50000, linha=LAR))
novos.append(texto(X0 + 228600, yc, LARG - 457200, 560000, [[
    ("O líder do IAP nunca é o mais típico: ", 1100, True, LAR),
    ("em B e D, o 1º no IAP é justamente o último em representatividade. O IAP premia quem vai mais longe "
     "na direção do perfil; o centroide premia quem mais se parece com o grupo.", 1100, False, BRA)]], "ctr"))
for xml in novos:
    sptree.append(etree.fromstring(xml))
tree.write(str(path), xml_declaration=True, encoding="UTF-8", standalone=True)
print("ok", {k: (v[1].municipio, v[2].municipio) for k, v in ex.items()})

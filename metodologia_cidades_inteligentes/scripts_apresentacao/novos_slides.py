"""Cria os slides explicativos (IAP e centroide) e troca a cor do Perfil D.

Uso: python novos_slides.py <pasta_descompactada> <slide_iap.xml> <slide_centroide.xml> <pasta_figuras>
Os dois slides devem ser cópias de slide19.xml (título + subtítulo + faixas).
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree

ED, S_IAP, S_CEN, FIG = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])
NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
DECL = " ".join(f'xmlns:{k}="{v}"' for k, v in NS.items())
VERMELHO, ROXO = "EA3234", "9D4EDD"  # nova cor do Perfil D

_id = [900]


def nid():
    _id[0] += 1
    return _id[0]


def rpr(sz=1200, b=False, cor="E6E6E6"):
    return (f'<a:rPr lang="pt-BR" sz="{sz}"{" b=\"1\"" if b else ""} noProof="0"><a:solidFill>'
            f'<a:srgbClr val="{cor}"/></a:solidFill><a:latin typeface="Montserrat" pitchFamily="2" '
            f'charset="0"/><a:ea typeface="Arial" pitchFamily="34" charset="-122"/>'
            f'<a:cs typeface="Arial" pitchFamily="34" charset="-120"/></a:rPr>')


def card(x, y, cx, cy):
    i = nid()
    return (f'<p:sp {DECL}><p:nvSpPr><p:cNvPr id="{i}" name="Cartao {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val 2791"/></a:avLst></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="1E1E1E"/></a:solidFill><a:ln w="12700"><a:solidFill>'
            f'<a:srgbClr val="1E1E1E"/></a:solidFill></a:ln></p:spPr><p:txBody><a:bodyPr/><a:lstStyle/>'
            f'<a:p><a:endParaRPr lang="pt-BR"/></a:p></p:txBody></p:sp>')


def texto(x, y, cx, cy, paragrafos, anchor="t"):
    """paragrafos: lista de listas de runs (texto, negrito, cor, tamanho)."""
    ps = []
    for runs in paragrafos:
        rs = "".join(f'<a:r>{rpr(sz, b, cor)}<a:t>{escape(t)}</a:t></a:r>' for t, b, cor, sz in runs)
        ps.append(f'<a:p><a:pPr marL="0" indent="0"><a:lnSpc><a:spcPct val="105000"/></a:lnSpc>'
                  f'<a:spcAft><a:spcPts val="400"/></a:spcAft><a:buNone/></a:pPr>{rs}</a:p>')
    i = nid()
    return (f'<p:sp {DECL}><p:nvSpPr><p:cNvPr id="{i}" name="Texto {i}"/><p:cNvSpPr txBox="1"/><p:nvPr/>'
            f'</p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr><p:txBody>'
            f'<a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" rtlCol="0" anchor="{anchor}"/>'
            f'<a:lstStyle/>{"".join(ps)}</p:txBody></p:sp>')


def imagem(rid, x, y, cx, cy, descr):
    i = nid()
    return (f'<p:pic {DECL}><p:nvPicPr><p:cNvPr id="{i}" name="Figura {i}" descr="{escape(descr)}"/>'
            f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
            f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')


LAR, BRA, CINZA = "F99828", "E6E6E6", "9AA0A6"


def montar(nome_slide, titulo, subtitulo, fig, descr, cab_esq, passos):
    path = ED / "ppt/slides" / nome_slide
    tree = etree.parse(str(path))
    sptree = tree.find(".//p:spTree", NS)
    manter = {"Shape 0", "Shape 1", "Shape 2", "Shape 3", "Text 4", "Text 5"}
    for ch in list(sptree)[2:]:
        nm = ch.find(".//p:cNvPr", NS)
        if nm is None or nm.get("name") not in manter:
            sptree.remove(ch)
    for nm, txt in (("Text 4", titulo), ("Text 5", subtitulo)):
        sp = next(s for s in sptree if s.find(".//p:cNvPr", NS) is not None
                  and s.find(".//p:cNvPr", NS).get("name") == nm)
        ts = sp.findall(".//a:t", NS)
        ts[0].text = txt
        for t in ts[1:]:
            t.text = ""

    # figura: copia para media e cria relação
    media = ED / "ppt/media" / f"explic_{fig.stem}.png"
    media.write_bytes(fig.read_bytes())
    rels = ED / "ppt/slides/_rels" / f"{nome_slide}.rels"
    rt = etree.parse(str(rels))
    rid = "rId90"
    el = etree.SubElement(rt.getroot(), "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
    el.set("Id", rid)
    el.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image")
    el.set("Target", f"../media/{media.name}")
    rt.write(str(rels), xml_declaration=True, encoding="UTF-8", standalone=True)

    # geometria (EMU)
    y0, h = 1645920, 4565098
    xl, wl = 548640, 6309360
    xr, wr = 7040880, 11640312 - 7040880
    pad, gap = 228600, 137160
    novos = [card(xl, y0, wl, h),
             texto(xl + pad, y0 + 150000, wl - 2 * pad, 274320, [[(cab_esq, True, LAR, 1200)]], "ctr")]
    ih = h - 457200 - 91440
    iw = int(ih * 8.6 / 6.0)
    novos.append(imagem(rid, xl + (wl - iw) // 2, y0 + 457200, iw, ih, descr))
    hc = (h - 2 * gap) // 3
    for k, (cab, corpo) in enumerate(passos):
        y = y0 + k * (hc + gap)
        novos += [card(xr, y, wr, hc),
                  texto(xr + pad, y + 150000, wr - 2 * pad, 274320, [[(cab, True, LAR, 1200)]], "ctr"),
                  texto(xr + pad, y + 500000, wr - 2 * pad, hc - 600000, [corpo])]
    for xml in novos:
        sptree.append(etree.fromstring(xml))
    tree.write(str(path), xml_declaration=True, encoding="UTF-8", standalone=True)


def r(t, b=False, cor=BRA):
    return (t, b, cor, 1200)


montar(S_IAP,
       "COMO FUNCIONA O RANKING PELO IAP",
       "Cada perfil tem uma direção característica: quanto mais o município avança nela, maior o IAP",
       FIG / "fig_iap.png",
       "Dispersão dos municípios do Perfil C com linhas de mesmo IAP e destaque para Sorocaba, "
       "Barra Bonita e Itapevi",
       "EXEMPLO VISUAL — PERFIL C",
       [("1 · O SINAL VEM DO PERFIL",
         [r("Cada eixo entra com "), r("+", True), r(" se o perfil está acima da média nele e "),
          r("−", True), r(" se está abaixo. No Perfil C: "), r("CFI (−), IMD (+) e CSE (+)", True), r(".")]),
        ("2 · SOMA PONDERADA PELOS PESOS",
         [r("IAP = −0,35·CFI + 0,40·IMD + 0,25·CSE", True),
          r(" (eixos em escore-z). Sorocaba: 0,234 + 1,267 + 0,438 = "), r("1,939", True), r(".")]),
        ("3 · ORDENAÇÃO DENTRO DO PERFIL",
         [r("Do maior para o menor IAP. Sorocaba é a "), r("1ª", True),
          r(" do Perfil C; Barra Bonita (1,040), a "), r("51ª", True),
          r(". As vagas vão aos primeiros colocados.")])])

montar(S_CEN,
       "COMO FUNCIONA O RANKING PELO CENTROIDE",
       "O centroide é o “município médio” de cada perfil: quanto mais perto dele, mais típico é o município",
       FIG / "fig_centroide.png",
       "Municípios dos quatro perfis com seus centroides e as distâncias de Barra Bonita e Sorocaba "
       "ao centroide do Perfil C",
       "OS QUATRO CENTROIDES E AS DISTÂNCIAS NO PERFIL C",
       [("1 · O QUE É O CENTROIDE",
         [r("É o "), r("ponto médio do perfil", True),
          r(": a média de CFI, IMD e CSE dos seus municípios, calculada pelo K-Means. "
            "Perfil C: (−0,20; 0,76; 0,42).")]),
        ("2 · DISTÂNCIA AO CENTROIDE",
         [r("Quanto o município se afasta do padrão do grupo nos três eixos: "),
          r("d = √(ΔCFI² + ΔIMD² + ΔCSE²)", True), r(", com os eixos ponderados por √peso.")]),
        ("3 · ORDENAÇÃO DENTRO DO PERFIL",
         [r("Do mais próximo (mais típico) ao mais distante. Barra Bonita (d = 0,243) é a "),
          r("1ª", True), r(" do Perfil C; Sorocaba (d = 1,339) fica em "), r("179º", True), r(".")])])
print("slides explicativos ok")

# ------------------------------------------------------------------ cor do Perfil D
SLIDES_PERFIL = ["slide12.xml", "slide13.xml", "slide15.xml", "slide16.xml", "slide17.xml",
                 "slide18.xml", "slide20.xml", "slide22.xml"]
n = 0
for nome in SLIDES_PERFIL:
    path = ED / "ppt/slides" / nome
    tree = etree.parse(str(path))
    for top in tree.find(".//p:spTree", NS)[2:]:
        nm = top.find(".//p:cNvPr", NS)
        if nm is not None and nm.get("name") == "Shape 1":  # faixa decorativa do topo
            continue
        for c in top.iter("{%s}srgbClr" % NS["a"]):
            if c.get("val") == VERMELHO:
                c.set("val", ROXO)
                n += 1
    tree.write(str(path), xml_declaration=True, encoding="UTF-8", standalone=True)
ch = ED / "ppt/charts/chart3.xml"
x = ch.read_text(encoding="utf8")
assert x.count(VERMELHO) == 1
ch.write_text(x.replace(VERMELHO, ROXO), encoding="utf8")
print("cor do Perfil D trocada em", n + 1, "elementos")

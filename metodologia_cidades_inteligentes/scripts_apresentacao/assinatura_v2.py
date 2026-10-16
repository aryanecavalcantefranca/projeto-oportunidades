"""Assinatura estatística (versão 2): novas cores dos perfis + nome do eixo em cada barra.

Cores dos perfis (como no mapa): A lilás, B marinho, C azul, D lavanda. Cada perfil
em três tons (CFI escuro, IMD médio, CSE claro). Os rótulos CFI/IMD/CSE são caixas
de texto posicionadas sobre as barras; para isso a área de plotagem do gráfico
recebe um layout fixo.

Uso: python assinatura_v2.py <pasta_descompactada_com_o_slide> <slide.xml> <chart.xml>
"""
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree

ED, SLIDE, CHART = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
EMU_IN = 914400
TONS = {  # (CFI, IMD, CSE)
    "A": ("8E6A98", "C0A2C7", "E3D3E7"),
    "B": ("263253", "34457A", "4A5C94"),
    "C": ("2A6E9E", "4496CD", "9CCBEA"),
    "D": ("6576B8", "7A8BC6", "B3BEE4"),
}
CLAROS = {"E3D3E7", "C0A2C7", "9CCBEA", "B3BEE4"}  # rótulo escuro sobre tom claro
EIXOS = ("CFI", "IMD", "CSE")

# ------------------------------------------------------------------ gráfico
cpath = ED / "ppt/charts" / CHART
x = cpath.read_text(encoding="utf8")
vals = []
for s_idx, ser in enumerate(re.findall(r"<c:ser>.*?</c:ser>", x, flags=re.S)):
    novo = ser
    for i, p in enumerate("ABCD"):
        novo = re.sub(rf'(<c:dPt><c:idx val="{i}"/>.*?<a:srgbClr val=")\w+("/></a:solidFill>)',
                      rf"\g<1>{TONS[p][s_idx]}\g<2>", novo, count=1, flags=re.S)
    x = x.replace(ser, novo)
    val = re.search(r"<c:val>.*?</c:val>", ser, flags=re.S).group()
    vals.append([float(v) for v in re.findall(r"<c:v>([^<]+)</c:v>", val)])
LX, LY, LW, LH = 0.075, 0.07, 0.905, 0.72  # área de plotagem interna (fração do gráfico)
assert x.count("<c:plotArea><c:layout/>") == 1
x = x.replace("<c:plotArea><c:layout/>",
              f'<c:plotArea><c:layout><c:manualLayout><c:layoutTarget val="inner"/><c:xMode val="edge"/>'
              f'<c:yMode val="edge"/><c:x val="{LX}"/><c:y val="{LY}"/><c:w val="{LW}"/><c:h val="{LH}"/>'
              f"</c:manualLayout></c:layout>")
vmax = float(re.search(r'<c:max val="([^"]+)"', x).group(1))
vmin = float(re.search(r'<c:min val="([^"]+)"', x).group(1))
gap = int(re.search(r'<c:gapWidth val="(\d+)"', x).group(1)) / 100
cpath.write_text(x, encoding="utf8")

# ------------------------------------------------------------------ rótulos
spath = ED / "ppt/slides" / SLIDE
tree = etree.parse(str(spath))
NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
gf = tree.find(".//p:graphicFrame", NS)
off, ext = gf.find("p:xfrm/a:off", NS), gf.find("p:xfrm/a:ext", NS)
fx, fy, fw, fh = (int(off.get("x")), int(off.get("y")), int(ext.get("cx")), int(ext.get("cy")))
px, py, pw, ph = fx + LX * fw, fy + LY * fh, LW * fw, LH * fh
cat_w = pw / 4
bar_w = cat_w / (3 + gap)
y_of = lambda v: py + (vmax - v) / (vmax - vmin) * ph  # noqa: E731

LBL_H = int(0.20 * EMU_IN)
VAL_H = int(0.20 * EMU_IN)  # espaço ocupado pelo rótulo de valor nativo
sptree = tree.find(".//p:spTree", NS)
nid = 950
for j, eixo in enumerate(EIXOS):
    for i, p in enumerate("ABCD"):
        v = vals[j][i]
        cx = px + i * cat_w + gap / 2 * bar_w + (j + 0.5) * bar_w
        y0, y1 = y_of(0), y_of(v)
        altura = abs(y1 - y0)
        tom = TONS[p][j]
        if altura >= LBL_H + 0.04 * EMU_IN:  # cabe dentro da barra, junto à ponta
            y = y1 + 0.03 * EMU_IN if v > 0 else y1 - LBL_H - 0.03 * EMU_IN
            cor = "1E1E1E" if tom in CLAROS else "FFFFFF"
        else:  # barra curta: acima/abaixo do rótulo de valor
            y = (y1 - VAL_H - LBL_H) if v >= 0 else (y1 + VAL_H)
            cor = "FFFFFF"
        w = int(bar_w)
        nid += 1
        xml = (f'<p:sp xmlns:p="{NS["p"]}" xmlns:a="{NS["a"]}"><p:nvSpPr><p:cNvPr id="{nid}" '
               f'name="Rotulo {eixo} {p}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm>'
               f'<a:off x="{int(cx - w / 2)}" y="{int(y)}"/><a:ext cx="{w}" cy="{LBL_H}"/></a:xfrm>'
               f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr><p:txBody>'
               f'<a:bodyPr wrap="none" lIns="0" tIns="0" rIns="0" bIns="0" anchor="ctr"/><a:lstStyle/>'
               f'<a:p><a:pPr algn="ctr"/><a:r><a:rPr lang="pt-BR" sz="1000" b="1"><a:solidFill>'
               f'<a:srgbClr val="{cor}"/></a:solidFill><a:latin typeface="Montserrat" pitchFamily="2" '
               f'charset="0"/></a:rPr><a:t>{escape(eixo)}</a:t></a:r></a:p></p:txBody></p:sp>')
        sptree.append(etree.fromstring(xml))
tree.write(str(spath), xml_declaration=True, encoding="UTF-8", standalone=True)
print("assinatura v2 ok")

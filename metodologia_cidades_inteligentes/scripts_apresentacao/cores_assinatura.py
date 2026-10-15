"""Gráfico "Assinatura estatística dos perfis": cada perfil em tons da sua cor.

Séries = eixos (CFI, IMD, CSE); categorias = perfis (A..D). Cada barra recebe
um tom do perfil (CFI escuro, IMD médio, CSE claro) e a legenda mostra a
mesma ordem de tons em cinza.

Uso: python cores_assinatura.py <pasta_descompactada>
"""
import re
import sys
from pathlib import Path

ED = Path(sys.argv[1])
TONS = {  # perfil: (CFI, IMD, CSE) — do escuro ao claro
    "A": ("C2700F", "F99828", "FCC27E"),
    "B": ("34467F", "5A6DB0", "9EABDA"),
    "C": ("2A6E9E", "4496CD", "9CCBEA"),
    "D": ("6E2FA6", "9D4EDD", "C9A2EE"),
}
LEGENDA = ("6B6B6B", "9A9A9A", "D0D0D0")

path = ED / "ppt/charts/chart4.xml"
x = path.read_text(encoding="utf8")
series = re.findall(r"<c:ser>.*?</c:ser>", x, flags=re.S)
assert len(series) == 3
for s_idx, ser in enumerate(series):
    novo = re.sub(r'(<c:tx>.*?</c:tx><c:spPr><a:solidFill><a:srgbClr val=")\w+(")',
                  rf"\g<1>{LEGENDA[s_idx]}\g<2>", ser, count=1, flags=re.S)
    dpts = "".join(
        f'<c:dPt><c:idx val="{i}"/><c:invertIfNegative val="0"/><c:bubble3D val="0"/>'
        f'<c:spPr><a:solidFill><a:srgbClr val="{TONS[p][s_idx]}"/></a:solidFill></c:spPr></c:dPt>'
        for i, p in enumerate("ABCD"))
    assert novo.count('<c:invertIfNegative val="0"/>') == 1
    novo = novo.replace('<c:invertIfNegative val="0"/>', '<c:invertIfNegative val="0"/>' + dpts, 1)
    x = x.replace(ser, novo)
path.write_text(x, encoding="utf8")
print("cores da assinatura ok")

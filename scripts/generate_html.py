#!/usr/bin/env python3
"""
Trin 5: HTML-genereringsfase
Modtager analyseret JSON fra Trin 4, udfylder marked-template.html
og skriver færdig HTML til stdout eller en fil.

Brug: python analyze.py | python generate_html.py
  eller: python generate_html.py analyze_output.json
  eller: python generate_html.py analyze_output.json output/optik/index.html
Output: HTML til stdout (eller fil hvis angivet)
"""

import sys
import json
import pathlib
import html as html_module
from datetime import date

SCRIPT_DIR = pathlib.Path(__file__).parent
TEMPLATE_PATH = SCRIPT_DIR.parent / "templates" / "marked-template.html"

H = html_module.escape  # HTML-escape hjælper


# ─── HTML-byggeblokke ──────────────────────────────────────────────────────────

def kpi_items(data: list) -> str:
    parts = []
    for item in data:
        parts.append(
            f'<div class="kpi-item">'
            f'<div class="kpi-value">{H(item["value"])}</div>'
            f'<div class="kpi-label">{H(item["label"])}</div>'
            f'</div>'
        )
    return "\n".join(parts)


def bar_chart_items(items: list) -> str:
    parts = []
    for item in items:
        andel = item.get("andel", 0)
        parts.append(
            f'<div class="bar-row">'
            f'<div class="bar-label">{H(item["navn"])}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{andel}%"></div></div>'
            f'<div class="bar-pct">{andel}%</div>'
            f'</div>'
        )
    return "\n".join(parts)


def marked_stats_4(stats: dict) -> str:
    items = [
        ("Vækstrate", stats.get("vaeкstrate", "N/A")),
        ("Virksomheder", stats.get("antal_virksomheder", "N/A")),
        ("Beskæftigelse", stats.get("beskæftigelse", "N/A")),
        ("Gns. margin", stats.get("gennemsnitlig_margin", "N/A")),
    ]
    parts = []
    for label, value in items:
        parts.append(
            f'<div style="background:var(--white);padding:20px">'
            f'<div style="font-size:11px;color:var(--grey-500);margin-bottom:4px">{H(label)}</div>'
            f'<div style="font-size:20px;font-weight:800;letter-spacing:-0.03em">{H(str(value))}</div>'
            f'</div>'
        )
    return "\n".join(parts)


def insight_items(items: list, key_titel="titel", key_desc="beskrivelse") -> str:
    parts = []
    for item in items:
        parts.append(
            f'<div class="insight-item">'
            f'<div class="insight-title">{H(item.get(key_titel, ""))}</div>'
            f'<div class="insight-desc">{H(item.get(key_desc, ""))}</div>'
            f'</div>'
        )
    return "\n".join(parts)


def kundelandskab_items(items: list) -> str:
    parts = []
    for item in items:
        andel = item.get("andel", "")
        andel_html = f' <span style="color:var(--grey-500);font-weight:400">({H(andel)})</span>' if andel else ""
        parts.append(
            f'<div class="insight-item">'
            f'<div class="insight-title">{H(item.get("segment", ""))}{andel_html}</div>'
            f'<div class="insight-desc">{H(item.get("karakteristika", ""))}</div>'
            f'</div>'
        )
    return "\n".join(parts)


def aktor_tabel_rows(aktorer: list, konkurrenter: list) -> str:
    # Byg et opslag fra konkurrent-navn til SWOT
    swot = {k["navn"]: k for k in konkurrenter}
    parts = []
    for a in aktorer:
        navn = a.get("navn", "")
        k = swot.get(navn, {})
        styrke = k.get("styrker", ["N/A"])[0] if k.get("styrker") else a.get("position", "N/A")
        svaghed = k.get("svagheder", ["N/A"])[0] if k.get("svagheder") else "N/A"
        retning = k.get("seneste_bevaegelser", "N/A")
        parts.append(
            f'<tr>'
            f'<td><strong>{H(navn)}</strong><br><span style="color:var(--grey-500);font-size:12px">{H(a.get("omsaetning",""))}</span></td>'
            f'<td>{H(a.get("type",""))}</td>'
            f'<td>{H(styrke)}</td>'
            f'<td>{H(svaghed)}</td>'
            f'<td>{H(retning)}</td>'
            f'</tr>'
        )
    return "\n".join(parts)


def konkurrent_tabs(konkurrenter: list) -> str:
    parts = []
    for i, k in enumerate(konkurrenter):
        active = ' active' if i == 0 else ''
        slug = k["navn"].lower().replace(" ", "-")
        parts.append(
            f'<button class="pill{active}" onclick="showSwot(\'{slug}\')">{H(k["navn"])}</button>'
        )
    return "\n".join(parts)


def swot_list(items: list) -> str:
    return "".join(f'<li>{H(x)}</li>' for x in items)


def konkurrent_blocks(konkurrenter: list) -> str:
    parts = []
    for i, k in enumerate(konkurrenter):
        display = 'block' if i == 0 else 'none'
        slug = k["navn"].lower().replace(" ", "-")
        pris_labels = {"premium": "Premium", "mid": "Mid-market", "value": "Value"}
        pris = pris_labels.get(k.get("prissaetning", "mid"), k.get("prissaetning", ""))
        parts.append(f'''
<div id="swot-{slug}" class="swot-block fade-up" style="display:{display}">
  <div class="swot-header">
    <div>
      <h3 class="display-md" style="margin-bottom:4px">{H(k["navn"])}</h3>
      <p class="body-md" style="color:var(--grey-500)">{H(k.get("tagline",""))}</p>
    </div>
    <div style="text-align:right">
      <div class="label-tag">{H(pris)}</div>
      <p style="font-size:12px;color:var(--grey-500);margin-top:4px">{H(k.get("omsaetning",""))}{" · " + H(k.get("ansatte","")) + " ansatte" if k.get("ansatte") else ""}</p>
    </div>
  </div>
  <p class="body-md" style="margin-bottom:24px">{H(k.get("profil",""))}</p>
  <div class="swot-grid">
    <div class="swot-cell strengths">
      <div class="swot-cell-title">Styrker</div>
      <ul>{swot_list(k.get("styrker",[]))}</ul>
    </div>
    <div class="swot-cell weaknesses">
      <div class="swot-cell-title">Svagheder</div>
      <ul>{swot_list(k.get("svagheder",[]))}</ul>
    </div>
    <div class="swot-cell opportunities">
      <div class="swot-cell-title">Muligheder</div>
      <ul>{swot_list(k.get("muligheder",[]))}</ul>
    </div>
    <div class="swot-cell threats">
      <div class="swot-cell-title">Trusler</div>
      <ul>{swot_list(k.get("trusler",[]))}</ul>
    </div>
  </div>
  <div style="margin-top:20px;padding:16px;background:var(--grey-100);border-radius:var(--radius-sm)">
    <span style="font-size:12px;font-weight:700;color:var(--grey-600)">Seneste bevægelser: </span>
    <span style="font-size:12px;color:var(--grey-700)">{H(k.get("seneste_bevaegelser",""))}</span>
  </div>
</div>''')
    return "\n".join(parts)


MODENHED_EMOJI = {"emerging": "🌱", "growing": "📈", "mature": "✅"}
MODENHED_DK = {"emerging": "Emerging", "growing": "Voksende", "mature": "Moden"}

def trend_cards(trends: list) -> str:
    parts = []
    for t in trends:
        mod = t.get("modenhed", "growing")
        emoji = MODENHED_EMOJI.get(mod, "📊")
        label = MODENHED_DK.get(mod, mod)
        impact_color = {"høj": "var(--blue)", "medium": "var(--grey-600)", "lav": "var(--grey-400)"}
        color = impact_color.get(t.get("paavirkningsgrad", "medium"), "var(--grey-600)")
        parts.append(
            f'<div class="trend-card fade-up">'
            f'<div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:12px">'
            f'<span style="font-size:24px">{emoji}</span>'
            f'<span style="font-size:11px;font-weight:700;color:{color}">{H(t.get("paavirkningsgrad","").upper())}</span>'
            f'</div>'
            f'<div style="font-size:11px;color:var(--grey-500);margin-bottom:6px">{H(label)} · {H(t.get("tidshorisont",""))}</div>'
            f'<h4 style="font-size:18px;font-weight:800;margin-bottom:8px;letter-spacing:-0.02em">{H(t.get("titel",""))}</h4>'
            f'<p style="font-size:13px;color:var(--grey-600);line-height:1.5">{H(t.get("beskrivelse",""))}</p>'
            f'</div>'
        )
    return "\n".join(parts)


def trend_modenhed_headers(trends: list) -> str:
    return "".join(f'<th>{H(t["titel"])}</th>' for t in trends)


def trend_modenhed_rows(aktorer: list, trends: list) -> str:
    mod_map = {"emerging": "🌱", "growing": "📈", "mature": "✅"}
    parts = []
    for a in aktorer[:5]:  # max 5 aktører i tabellen
        cells = "".join(
            f'<td style="text-align:center">{mod_map.get(t.get("modenhed","growing"), "📊")}</td>'
            for t in trends
        )
        parts.append(f'<tr><td>{H(a.get("navn",""))}</td>{cells}</tr>')
    return "\n".join(parts)


def opp_rows(muligheder: list) -> str:
    parts = []
    for i, m in enumerate(muligheder, 1):
        parts.append(
            f'<div class="opp-row fade-up" style="display:grid;grid-template-columns:40px 1fr auto;gap:16px;align-items:start;padding:24px;border-bottom:1px solid var(--grey-200)">'
            f'<div style="font-size:32px;font-weight:900;color:var(--grey-200);letter-spacing:-0.03em">{i:02d}</div>'
            f'<div>'
            f'<h4 style="font-size:17px;font-weight:800;margin-bottom:4px">{H(m.get("titel",""))}</h4>'
            f'<p style="font-size:13px;color:var(--grey-600);line-height:1.5">{H(m.get("beskrivelse",""))}</p>'
            f'</div>'
            f'<div style="text-align:right;white-space:nowrap">'
            f'<div style="font-size:11px;font-weight:700;color:var(--blue);margin-bottom:2px">{H(m.get("timing",""))}</div>'
            f'<div style="font-size:11px;color:var(--grey-500)">{H(m.get("potentiale",""))}</div>'
            f'</div>'
            f'</div>'
        )
    return "\n".join(parts)


def strategisk_3col(anbefaling_1: dict, anbefaling_2: dict, anbefaling_3: dict) -> str:
    cols = []
    for a in [anbefaling_1, anbefaling_2, anbefaling_3]:
        cols.append(
            f'<div>'
            f'<div style="font-size:13px;font-weight:800;color:white;margin-bottom:8px">{H(a.get("titel",""))}</div>'
            f'<p style="font-size:13px;color:var(--grey-400);line-height:1.5">{H(a.get("beskrivelse",""))}</p>'
            f'</div>'
        )
    return "\n".join(cols)


def kilde_items(kilder: list) -> str:
    parts = []
    for k in kilder:
        url = k.get("url", "")
        titel = H(k.get("titel", ""))
        dato = k.get("dato", "")
        if url and url != "ikke tilgængeligt":
            link = f'<a href="{H(url)}" target="_blank" rel="noopener">{titel}</a>'
        else:
            link = titel
        parts.append(
            f'<div class="insight-item">'
            f'<div class="insight-title">{link}</div>'
            f'<div class="insight-desc">{H(dato)}</div>'
            f'</div>'
        )
    return "\n".join(parts)


def definition_items(definitioner: list) -> str:
    parts = []
    for d in definitioner:
        parts.append(
            f'<div class="insight-item">'
            f'<div class="insight-title">{H(d.get("term",""))}</div>'
            f'<div class="insight-desc">{H(d.get("definition",""))}</div>'
            f'</div>'
        )
    return "\n".join(parts)


def marked_navn_split(navn: str) -> tuple[str, str, str]:
    """Fordel markedsnavn over op til tre linjer baseret på orddeling."""
    ord_liste = navn.split()
    if len(ord_liste) == 1:
        return navn, "", ""
    mid = len(ord_liste) // 2
    return " ".join(ord_liste[:mid]), " ".join(ord_liste[mid:]), ""


# ─── Hovedfunktion ─────────────────────────────────────────────────────────────

def generate(data: dict, gate_password: str = "") -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    marked = data.get("marked_navn", "Marked")
    linje1, linje2, linje3 = marked_navn_split(marked)
    konkurrenter = data.get("konkurrenter", [])
    aktorer = data.get("aktorer", [])
    trends = data.get("trends", [])
    muligheder = data.get("muligheder", [])
    tam = data.get("tam", {})
    sam = data.get("sam", {})
    som = data.get("som", {})

    replacements = {
        "{{MARKED_NAVN}}": H(marked),
        "{{MARKED_NAVN_LINJE1}}": H(linje1),
        "{{MARKED_NAVN_LINJE2}}": H(linje2),
        "{{MARKED_NAVN_LINJE3}}": H(linje3),
        "{{MARKED_HEADLINE}}": H(f"Det danske {marked.lower()}marked"),
        "{{AAR}}": H(data.get("aar", str(date.today().year))),
        "{{DATO}}": H(data.get("dato", str(date.today()))),
        "{{KLIENT_NAVN}}": H(data.get("klient_navn", "Analyse")),
        "{{EXECUTIVE_SUMMARY}}": H(data.get("executive_summary", "")),
        "{{KPI_ITEMS}}": kpi_items(data.get("kpi_items", [])),
        "{{BAR_CHART_ITEMS}}": bar_chart_items(data.get("bar_chart_items", [])),
        "{{MARKEDSANDEL_METRIK}}": H(data.get("markedsandel_metrik", "")),
        "{{BAR_CHART_KILDE}}": H(data.get("bar_chart_kilde", "")),
        "{{MARKEDSTILSTAND_CITAT}}": H(data.get("markedstilstand_citat", "")),
        "{{MARKED_STATS_4}}": marked_stats_4(data.get("marked_stats", {})),
        "{{TAM_NUM}}": H(tam.get("num", "")),
        "{{TAM_BESKRIVELSE}}": H(tam.get("beskrivelse", "")),
        "{{TAM_KILDE}}": H(tam.get("kilde", "")),
        "{{SAM_NUM}}": H(sam.get("num", "")),
        "{{SAM_BESKRIVELSE}}": H(sam.get("beskrivelse", "")),
        "{{SAM_KILDE}}": H(sam.get("kilde", "")),
        "{{SOM_NUM}}": H(som.get("num", "")),
        "{{SOM_BESKRIVELSE}}": H(som.get("beskrivelse", "")),
        "{{SOM_KILDE}}": H(som.get("kilde", "")),
        "{{DRIVERE_ITEMS}}": insight_items(data.get("drivere", [])),
        "{{BARRIERER_ITEMS}}": insight_items(data.get("barrierer", [])),
        "{{KUNDELANDSKAB_ITEMS}}": kundelandskab_items(data.get("kundelandskab", [])),
        "{{AKTOR_TABEL_ROWS}}": aktor_tabel_rows(aktorer, konkurrenter),
        "{{KONKURRENT_TABS}}": konkurrent_tabs(konkurrenter),
        "{{KONKURRENT_BLOCKS}}": konkurrent_blocks(konkurrenter),
        "{{ANTAL_TRENDS}}": str(len(trends)),
        "{{TREND_CARDS}}": trend_cards(trends),
        "{{TREND_MODENHED_HEADERS}}": trend_modenhed_headers(trends),
        "{{TREND_MODENHED_ROWS}}": trend_modenhed_rows(aktorer, trends),
        "{{TREND_MODENHED_NOTE}}": H(data.get("usikkerhed_note", "")),
        "{{MULIGHEDER_CITAT}}": H(data.get("strategisk_paradigme", "")),
        "{{OPP_ROWS}}": opp_rows(muligheder),
        "{{STRATEGISK_PARADIGME}}": H(data.get("strategisk_paradigme", "")),
        "{{STRATEGISK_3COL}}": strategisk_3col(
            data.get("strategisk_anbefaling_1", {}),
            data.get("strategisk_anbefaling_2", {}),
            data.get("strategisk_anbefaling_3", {}),
        ),
        "{{METODE_BESKRIVELSE}}": H(data.get("metode_beskrivelse", "")),
        "{{KILDE_ITEMS}}": kilde_items(data.get("kilder", [])),
        "{{DEFINITION_ITEMS}}": definition_items(data.get("definitioner", [])),
        "{{USIKKERHED_NOTE}}": H(data.get("usikkerhed_note", "")),
        "{{DATA_DATO}}": H(data.get("data_dato", "")),
        "{{GATE_PASSWORD}}": gate_password,  # ikke HTML-escaped — bruges i JS-streng
    }

    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)

    # Injicér showSwot JS-funktion hvis ikke allerede til stede
    if "function showSwot" not in result:
        swot_js = """
<script>
function showSwot(slug) {
  document.querySelectorAll('.swot-block').forEach(el => el.style.display = 'none');
  document.querySelectorAll('#swot-tabs .pill').forEach(el => el.classList.remove('active'));
  const target = document.getElementById('swot-' + slug);
  if (target) target.style.display = 'block';
  event.target.classList.add('active');
}
</script>"""
        result = result.replace("</body>", swot_js + "\n</body>")

    return result


def main():
    # Input: fil-argument eller stdin
    if len(sys.argv) >= 2:
        input_path = pathlib.Path(sys.argv[1])
        print(f"Indlæser analyse fra: {input_path}", file=sys.stderr)
        data = json.loads(input_path.read_text(encoding="utf-8"))
    else:
        print("Indlæser analyse fra stdin ...", file=sys.stderr)
        data = json.load(sys.stdin)

    import os
    gate_password = os.environ.get("GATE_PASSWORD", "")

    marked_navn = data.get("marked_navn", "ukendt")
    print(f"Genererer HTML for: {marked_navn} ...", file=sys.stderr)

    html_output = generate(data, gate_password)

    # Output: fil-argument eller stdout
    if len(sys.argv) >= 3:
        out_path = pathlib.Path(sys.argv[2])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html_output, encoding="utf-8")
        print(f"HTML skrevet til: {out_path}", file=sys.stderr)
    else:
        print(html_output)

    print(f"HTML-generering færdig: {len(html_output):,} tegn", file=sys.stderr)


if __name__ == "__main__":
    main()

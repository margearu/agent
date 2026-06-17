#!/usr/bin/env python3
"""
Trin 3: Research-fase
Indsamler rå markedsdata via Claude Sonnet + web search og returnerer struktureret JSON
til analysefasen (Trin 4).

Brug: python research.py "optik"
Output: JSON til stdout
"""

import sys
import io
import json
import traceback
import anthropic

# Tving UTF-8 på stdout/stderr uanset terminal-locale
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Workaround: httpx bruger ASCII til headers men platform-info på dansk macOS
# kan indeholde ikke-ASCII. Patch normalize-funktionen til at bruge latin-1.
try:
    import httpx._models as _httpx_models
    _orig_normalize = _httpx_models._normalize_header_value
    def _safe_normalize(value, encoding):
        if isinstance(value, str):
            try:
                value.encode(encoding or "ascii")
            except (UnicodeEncodeError, LookupError):
                value = value.encode("ascii", "replace").decode("ascii")
        return _orig_normalize(value, encoding)
    _httpx_models._normalize_header_value = _safe_normalize
except Exception:
    pass  # Nyere httpx-versioner har ikke dette problem

RESEARCH_SYSTEM_PROMPT = """Du er en erfaren markedsresearcher specialiseret i det danske marked.
Din opgave er at indsamle faktuelle data om et givet marked via websøgning.

KILDEBEGRÆNSNING — du må KUN bruge følgende offentligt tilgængelige danske kilder:
- Årsrapporter og virksomhedshjemmesider
- Danmarks Statistik (dst.dk)
- CVR / Erhvervsstyrelsen (cvr.dk, virk.dk)
- Brancheorganisationer: Dansk Erhverv (danskerhverv.dk), DI (di.dk)
- Konkurrence- og Forbrugerstyrelsen (kfst.dk)
- Finanstilsynet (finanstilsynet.dk) — ved relevante brancher

Ingen interne dokumenter, betalte databaser eller udenlandske kilder.

Svar ALTID på dansk. Vær præcis med tal og kildehenvisninger.
Angiv tydeligt skellet mellem faktabaserede oplysninger og kvalificerede vurderinger.
"""

RESEARCH_PROMPT_TEMPLATE = """Udfør en grundig markedsresearch om det danske {marked_navn}-marked.

VIGTIG INSTRUKTION — KONKURRENTER:
Søg systematisk efter ALLE relevante aktører i markedet, inddelt i kategorier:
1. Store kæder / kapitalkæder (søg specifikt på de 5-8 største)
2. Frivillige kæder og indkøbsfællesskaber
3. Danske producenter og designbrands
4. Online-spillere og nichespillere
5. Internationale aktører med dansk tilstedeværelse

Lever MINIMUM 8 konkurrenter i JSON-outputtet — hellere 12 end 4.
For hvert marked: søg brancheorganisationernes hjemmesider, CVR-udtræk og Optikerforeningen/brancheorganisationen.

Søg efter og indsaml data til alle nedenstående felter. Brug web search aktivt (brug alle 30 søgninger).
Returner et JSON-objekt med PRÆCIS disse felter — udfyld alle felter, brug "N/A" eller estimater med usikkerhedsangivelse hvis data ikke kan verificeres.

{{
  "marked_navn": "{marked_navn}",
  "aar": "2025",
  "dato": "<dagens dato>",
  "executive_summary": "<3-5 sætninger: markedets størrelse, vækstrate, vigtigste driver, topanbefaling>",

  "kpi_items": [
    {{"label": "<KPI-navn>", "value": "<tal + enhed>", "kilde": "<kilde>"}},
    {{"label": "<KPI-navn>", "value": "<tal + enhed>", "kilde": "<kilde>"}},
    {{"label": "<KPI-navn>", "value": "<tal + enhed>", "kilde": "<kilde>"}},
    {{"label": "<KPI-navn>", "value": "<tal + enhed>", "kilde": "<kilde>"}}
  ],

  "bar_chart_items": [
    {{"navn": "<Aktørnavn>", "andel": <tal som heltal 0-100>, "kilde": "<kilde>"}},
    {{"navn": "<Aktørnavn>", "andel": <tal som heltal 0-100>, "kilde": "<kilde>"}},
    {{"navn": "<Aktørnavn>", "andel": <tal som heltal 0-100>, "kilde": "<kilde>"}},
    {{"navn": "Øvrige", "andel": <resterende>, "kilde": "<kilde>"}}
  ],
  "bar_chart_kilde": "<kilde til markedsandelsoversigt>",

  "markedstilstand_citat": "<kort karakteristik af markedet i ét slående citat/sætning>",

  "marked_stats": {{
    "vaeкstrate": "<% CAGR eller årsændring>",
    "antal_virksomheder": "<antal>",
    "beskæftigelse": "<antal ansatte>",
    "gennemsnitlig_margin": "<% eller 'ikke tilgængeligt'>"
  }},

  "markedsandel_metrik": "<kort label til markedsandelsdiagram, f.eks. 'Markedsandel efter omsætning 2024'>",

  "tam": {{
    "num": "<tal + enhed, f.eks. '4,2 mia. kr.'>",
    "beskrivelse": "<hvad TAM dækker>",
    "kilde": "<kilde>"
  }},
  "sam": {{
    "num": "<tal + enhed>",
    "beskrivelse": "<hvad SAM dækker>",
    "kilde": "<kilde>"
  }},
  "som": {{
    "num": "<tal + enhed>",
    "beskrivelse": "<hvad SOM dækker>",
    "kilde": "<kilde>"
  }},

  "drivere": [
    {{"titel": "<Drivernavn>", "beskrivelse": "<2-3 sætninger>"}},
    {{"titel": "<Drivernavn>", "beskrivelse": "<2-3 sætninger>"}},
    {{"titel": "<Drivernavn>", "beskrivelse": "<2-3 sætninger>"}}
  ],

  "barrierer": [
    {{"titel": "<Barriernavn>", "beskrivelse": "<2-3 sætninger>"}},
    {{"titel": "<Barriernavn>", "beskrivelse": "<2-3 sætninger>"}},
    {{"titel": "<Barriernavn>", "beskrivelse": "<2-3 sætninger>"}}
  ],

  "kundelandskab": [
    {{"segment": "<Segmentnavn>", "karakteristika": "<beskrivelse>", "andel": "<% af marked>"}},
    {{"segment": "<Segmentnavn>", "karakteristika": "<beskrivelse>", "andel": "<% af marked>"}},
    {{"segment": "<Segmentnavn>", "karakteristika": "<beskrivelse>", "andel": "<% af marked>"}}
  ],

  "aktorer": [
    {{
      "navn": "<Virksomhedsnavn>",
      "type": "<dansk/international/offentlig>",
      "omsaetning": "<kr. eller mia. kr.>",
      "markedsandel": "<%>",
      "position": "<markedsposition kort>"
    }}
  ],

  "konkurrenter": [
    {{
      "navn": "<Virksomhedsnavn>",
      "tagline": "<kort positionering>",
      "profil": "<2-3 sætninger om virksomheden>",
      "prissaetning": "premium|mid|value",
      "styrker": ["<styrke 1>", "<styrke 2>", "<styrke 3>"],
      "svagheder": ["<svaghed 1>", "<svaghed 2>", "<svaghed 3>"],
      "muligheder": ["<mulighed 1>", "<mulighed 2>"],
      "trusler": ["<trussel 1>", "<trussel 2>"],
      "seneste_bevaegelser": "<hvad har de gjort senest>",
      "omsaetning": "<kr.>",
      "ansatte": "<antal>"
    }}
  ],

  "trends": [
    {{
      "titel": "<Trendnavn>",
      "beskrivelse": "<2-3 sætninger>",
      "modenhed": "emerging|growing|mature",
      "tidshorisont": "<1-2 år|3-5 år|5+ år>",
      "paavirkningsgrad": "høj|medium|lav"
    }}
  ],

  "muligheder": [
    {{
      "titel": "<Mulighedsnavn>",
      "beskrivelse": "<2-3 sætninger>",
      "timing": "<hvornår>",
      "potentiale": "<estimeret størrelse eller vækstpotentiale>"
    }}
  ],

  "strategisk_paradigme": "<overordnet strategisk karakteristik af markedet i ét udsagn>",
  "strategisk_anbefaling_1": {{"titel": "<Anbefalingsnavn>", "beskrivelse": "<konkret anbefaling>"}},
  "strategisk_anbefaling_2": {{"titel": "<Anbefalingsnavn>", "beskrivelse": "<konkret anbefaling>"}},
  "strategisk_anbefaling_3": {{"titel": "<Anbefalingsnavn>", "beskrivelse": "<konkret anbefaling>"}},

  "metode_beskrivelse": "<beskrivelse af dataindsamlingsmetode og kildekritik>",

  "kilder": [
    {{"titel": "<Kildetitel>", "url": "<URL eller 'ikke tilgængeligt'>", "dato": "<tilgangsdato>"}},
    {{"titel": "<Kildetitel>", "url": "<URL eller 'ikke tilgængeligt'>", "dato": "<tilgangsdato>"}}
  ],

  "definitioner": [
    {{"term": "<Fagterm>", "definition": "<definition>"}},
    {{"term": "<Fagterm>", "definition": "<definition>"}}
  ],

  "usikkerhed_note": "<vigtigste forbehold og usikkerheder i analysen>",
  "data_dato": "<dato for seneste data>"
}}

Udfyld alle felter med reelle data.
Søgerækkefølge: 1) markedsstørrelse og omsætning, 2) alle aktører systematisk pr. kategori,
3) SWOT pr. aktør, 4) trends og drivere.
Returner KUN det rene JSON-objekt, ingen forklarende tekst.
"""


def research_market(marked_navn: str) -> dict:
    # Høj timeout + max 3 forsøg ved netværksfejl
    client = anthropic.Anthropic(
        timeout=600.0,
        max_retries=3,
    )

    prompt = RESEARCH_PROMPT_TEMPLATE.format(marked_navn=marked_navn)

    # Brug create() i stedet for stream() — mere robust over dårlige forbindelser
    # da svaret buffereres server-side og returneres samlet.
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        system=RESEARCH_SYSTEM_PROMPT,
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}],
        messages=[{"role": "user", "content": prompt}],
    )

    print(f"Stop reason: {response.stop_reason}", file=sys.stderr)

    json_text = ""
    for block in response.content:
        if block.type == "text":
            json_text += block.text

    if not json_text.strip():
        types = [b.type for b in response.content]
        raise ValueError(f"Intet tekst-output fra Claude. Bloktyper: {types}")

    start = json_text.find("{")
    end = json_text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"Intet JSON-objekt i svaret. Første 500 tegn:\n{json_text[:500]}")

    return json.loads(json_text[start:end])


TEST_DATA = {
  "marked_navn": "optik",
  "aar": "2025",
  "dato": "2025-06-17",
  "executive_summary": "Det danske optikmarked omsætter for ca. 3,5 mia. kr. årligt og domineres af to store kæder. Markedet vokser 2-3% om året drevet af en aldrende befolkning og øget skærmforbrug.",
  "kpi_items": [
    {"label": "Markedsstørrelse", "value": "3,5 mia. kr.", "kilde": "Optikerforeningen 2024"},
    {"label": "Vækstrate", "value": "2-3% p.a.", "kilde": "Dansk Erhverv"},
    {"label": "Antal butikker", "value": "ca. 900", "kilde": "CVR 2024"},
    {"label": "Beskæftigelse", "value": "ca. 4.500", "kilde": "DST"}
  ],
  "bar_chart_items": [
    {"navn": "Louis Nielsen", "andel": 35, "kilde": "Brancheestimater"},
    {"navn": "Synoptik", "andel": 25, "kilde": "Brancheestimater"},
    {"navn": "Øvrige", "andel": 40, "kilde": "Brancheestimater"}
  ],
  "bar_chart_kilde": "Brancheestimater 2024",
  "markedstilstand_citat": "Konsolideret marked med to dominerende kæder og et langt felt af uafhængige optikere.",
  "marked_stats": {
    "vaeкstrate": "2-3% CAGR",
    "antal_virksomheder": "ca. 450",
    "beskæftigelse": "ca. 4.500",
    "gennemsnitlig_margin": "ca. 40%"
  },
  "markedsandel_metrik": "Markedsandel efter omsætning 2024",
  "tam": {"num": "3,5 mia. kr.", "beskrivelse": "Samlet dansk optikmarked inkl. kontaktlinser", "kilde": "Optikerforeningen"},
  "sam": {"num": "2,5 mia. kr.", "beskrivelse": "Brilleoptik og synsprøver", "kilde": "Brancheestimater"},
  "som": {"num": "500 mio. kr.", "beskrivelse": "Tilgængeligt for ny aktør inden for 3 år", "kilde": "Vurdering"},
  "drivere": [
    {"titel": "Aldrende befolkning", "beskrivelse": "Stigende andel af danskere over 50 øger efterspørgslen på briller og linser markant."},
    {"titel": "Skærmforbrug", "beskrivelse": "Øget digitalt forbrug accelererer synsproblemer i alle aldersgrupper."},
    {"titel": "Modetrend", "beskrivelse": "Briller er blevet et modeobjekt — forbrugerne køber flere stel."}
  ],
  "barrierer": [
    {"titel": "Høj konkurrence", "beskrivelse": "To store kæder med stordriftsfordele presser marginer for mindre aktører."},
    {"titel": "Online pres", "beskrivelse": "Udenlandske onlinebutikker underminerer priserne på standardglas."},
    {"titel": "Krav til uddannelse", "beskrivelse": "Optikere kræver 4-årig uddannelse — begrænser hurtig skalering."}
  ],
  "kundelandskab": [
    {"segment": "Seniorer (55+)", "karakteristika": "Hyppige brugere, loyale over for lokal optiker, pris-tolerante", "andel": "40%"},
    {"segment": "Arbejdsaktive (30-54)", "karakteristika": "Kombinerer arbejds- og fritidsbriller, modebevidste", "andel": "35%"},
    {"segment": "Unge (under 30)", "karakteristika": "Pris-sensitive, online-åbne, kontaktlinsebrugere", "andel": "25%"}
  ],
  "aktorer": [
    {"navn": "Louis Nielsen", "type": "international", "omsaetning": "ca. 1,2 mia. kr.", "markedsandel": "35%", "position": "Markedsleder på volumen"},
    {"navn": "Synoptik", "type": "international", "omsaetning": "ca. 875 mio. kr.", "markedsandel": "25%", "position": "Premium-positioneret"}
  ],
  "konkurrenter": [
    {
      "navn": "Louis Nielsen",
      "tagline": "Danmarks største optikerkæde",
      "profil": "Ejet af Specsavers. Stærk volumenposition med aggressive priser og bred tilstedeværelse i hele landet.",
      "prissaetning": "value",
      "styrker": ["Stordriftsfordele", "Stærk brand-kendskab", "Bred geografisk dækning"],
      "svagheder": ["Lavt premium-image", "Standardiseret oplevelse", "Afhængig af britisk moderkoncern"],
      "muligheder": ["Digital synsprøve", "Abonnementsmodeller"],
      "trusler": ["Online-konkurrence", "Premium-segmentet vokser fra dem"],
      "seneste_bevaegelser": "Øget digital markedsføring og online booking.",
      "omsaetning": "ca. 1,2 mia. kr.",
      "ansatte": "ca. 800"
    },
    {
      "navn": "Synoptik",
      "tagline": "Premium optik med bred service",
      "profil": "Ejet af EssilorLuxottica via GrandVision. Premium-positioneret med fokus på kvalitet og rådgivning.",
      "prissaetning": "premium",
      "styrker": ["Stærkt premium-image", "Internationalt netværk", "Bred sortiment"],
      "svagheder": ["Høje priser begrænser markedsandel", "Kompleks koncernstruktur"],
      "muligheder": ["Voksende premium-segment", "Luksusbrilletrend"],
      "trusler": ["Prisbevidste forbrugere", "Direkte onlinesalg fra brands"],
      "seneste_bevaegelser": "Lanceret Smarteyes som discountkoncept.",
      "omsaetning": "ca. 875 mio. kr.",
      "ansatte": "ca. 600"
    }
  ],
  "trends": [
    {"titel": "Digitale synsprøver", "beskrivelse": "Fjernsynsprøver via app og teleoptik vinder frem.", "modenhed": "emerging", "tidshorisont": "1-2 år", "paavirkningsgrad": "høj"},
    {"titel": "Bæredygtige stel", "beskrivelse": "Forbrugere efterspørger bionedbrydelige og genbrugsmaterialer.", "modenhed": "growing", "tidshorisont": "3-5 år", "paavirkningsgrad": "medium"}
  ],
  "muligheder": [
    {"titel": "Abonnementsmodel", "beskrivelse": "Månedligt abonnement på briller og linser — lav adgangsbarriere for forbrugeren.", "timing": "1-2 år", "potentiale": "500 mio. kr. TAM"},
    {"titel": "B2B arbejdsbriller", "beskrivelse": "Virksomhedsaftaler om arbejds- og skærmbriller til ansatte.", "timing": "Nu", "potentiale": "200 mio. kr."}
  ],
  "strategisk_paradigme": "Skalér eller specialisér — midterfeltet er under pres fra kæder nedefra og premium oppe fra.",
  "strategisk_anbefaling_1": {"titel": "Differentiér på service", "beskrivelse": "Investér i rådgivningskvalitet og oplevelse som discount-kæderne ikke kan matche."},
  "strategisk_anbefaling_2": {"titel": "Byg B2B-pipeline", "beskrivelse": "Indgå aftaler med virksomheder om skærmbriller — stabilt og margen-stærkt segment."},
  "strategisk_anbefaling_3": {"titel": "Digital synsprøve", "beskrivelse": "Lancér app-baseret forsøgsprøve for at nå unge og distante kunder."},
  "metode_beskrivelse": "TEST-DATA — ikke baseret på reel websøgning. Bruges til at validere pipeline.",
  "kilder": [
    {"titel": "Optikerforeningen", "url": "https://optikerforeningen.dk", "dato": "2024"},
    {"titel": "Danmarks Statistik", "url": "https://dst.dk", "dato": "2024"}
  ],
  "definitioner": [
    {"term": "TAM", "definition": "Total Addressable Market — det samlede marked hvis man havde 100% markedsandel."},
    {"term": "Optiker", "definition": "Uddannet fagperson med 4-årig professionsbacheloruddannelse i optometri."}
  ],
  "usikkerhed_note": "TEST-DATA. Tal er estimater til pipeline-validering og må ikke bruges analytisk.",
  "data_dato": "2025-06-17"
}


def main():
    if len(sys.argv) < 2:
        print("Brug: python research.py <marked-navn> [--test]", file=sys.stderr)
        print('Eksempel: python research.py "optik"', file=sys.stderr)
        sys.exit(1)

    marked_navn = sys.argv[1]
    test_mode = "--test" in sys.argv

    if test_mode:
        print(f"TEST-TILSTAND: springer API over, returnerer dummy-data for '{marked_navn}'", file=sys.stderr)
        data = TEST_DATA.copy()
        data["marked_navn"] = marked_navn
        print(json.dumps(data, ensure_ascii=False, indent=2))
        print("Research færdig (test). Fundet 2 konkurrenter, 2 trends.", file=sys.stderr)
        return

    print(f"Starter research: {marked_navn} ...", file=sys.stderr)

    try:
        data = research_market(marked_navn)
    except Exception as e:
        print(f"FEJL i research: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"Research færdig. Fundet {len(data.get('konkurrenter', []))} konkurrenter, "
          f"{len(data.get('trends', []))} trends.", file=sys.stderr)


if __name__ == "__main__":
    main()

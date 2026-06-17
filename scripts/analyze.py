#!/usr/bin/env python3
"""
Trin 4: Analysefase
Modtager rå research-JSON fra Trin 3, kører Claude Opus med strategisk
konsulent-system-prompt og returnerer beriget, kvalitetssikret JSON.

Brug: python research.py "optik" | python analyze.py
  eller: python analyze.py research_output.json
Output: JSON til stdout
"""

import sys
import io
import json
import pathlib
import anthropic

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Indlæs system-prompt fra fil (relativ til dette scripts placering)
SCRIPT_DIR = pathlib.Path(__file__).parent
SYSTEM_PROMPT_PATH = SCRIPT_DIR.parent / "prompts" / "strategisk_konsulent_system_prompt.md"


def load_system_prompt() -> str:
    if not SYSTEM_PROMPT_PATH.exists():
        raise FileNotFoundError(f"System-prompt ikke fundet: {SYSTEM_PROMPT_PATH}")
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


ANALYSIS_PROMPT = """Du modtager rå research-data om et dansk marked som JSON.
Din opgave er at:

1. **Kvalitetssikre og berige dataene** — ret åbenlyse fejl, udfyld huller med kvalificerede vurderinger (mærk dem tydeligt som "vurdering"), og sørg for intern konsistens.

2. **Skærpe den strategiske analyse** — gør executive summary præcis og handlingsorienteret (max 5 sætninger), styrk SWOT-analysen for hvert konkurrent, identificér "white space" og de vigtigste strategiske implikationer.

3. **MECE-tjek** — sørg for at drivere, barrierer og kundelandskab ikke overlapper og er udtømmende.

4. **Verificér TAM/SAM/SOM-logikken** — tallene skal hænge sammen (SAM ≤ TAM, SOM ≤ SAM). Ret hvis nødvendigt og angiv kilden til dine korrektioner.

5. **Strategisk syntese** — `strategisk_paradigme` skal opsummere markedets grundvilkår i ét præcist udsagn. De tre `strategisk_anbefaling_x`-felter skal være konkrete, prioriterede og handlingsorienterede — ikke generiske.

Returner det berigede JSON-objekt med PRÆCIS samme struktur og feltnavn som input.
Tilføj et nyt felt `"analyse_noter"` med dine vigtigste kvalitetsobservationer (max 5 punkter).
Returner KUN det rene JSON-objekt, ingen forklarende tekst uden for JSON.

Her er research-dataene:
"""


def analyze(research_data: dict) -> dict:
    system_prompt = load_system_prompt()
    client = anthropic.Anthropic()

    user_message = ANALYSIS_PROMPT + json.dumps(research_data, ensure_ascii=False, indent=2)

    with client.messages.stream(
        model="claude-opus-4-8",
        max_tokens=16000,
        system=system_prompt,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        response = stream.get_final_message()

    json_text = ""
    for block in response.content:
        if block.type == "text":
            json_text += block.text

    start = json_text.find("{")
    end = json_text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"Intet JSON fundet i analyse-svar. Svar: {json_text[:500]}")

    return json.loads(json_text[start:end])


def main():
    # Læs input: fra fil-argument eller stdin
    if len(sys.argv) >= 2:
        input_path = pathlib.Path(sys.argv[1])
        print(f"Indlæser research fra: {input_path}", file=sys.stderr)
        research_data = json.loads(input_path.read_text(encoding="utf-8"))
    else:
        print("Indlæser research fra stdin ...", file=sys.stderr)
        research_data = json.load(sys.stdin)

    marked_navn = research_data.get("marked_navn", "ukendt marked")
    print(f"Analyserer: {marked_navn} ...", file=sys.stderr)

    result = analyze(research_data)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Analyse færdig for: {marked_navn}", file=sys.stderr)


if __name__ == "__main__":
    main()

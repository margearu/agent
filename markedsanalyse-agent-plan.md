# Markedsanalyse-Agent — Projektspecifikation til Claude Code

Status: Plan låst efter afklaring med CEO/bruger. Klar til implementering.
Dato: 2026-06-17

## 1. Formål

CEO skal kunne indtaste et vilkårligt marked (f.eks. "optik", "telekommunikation") på en
landingpage, trykke "Begynd markedsanalyse", og få genereret en dyb, struktureret
markedsanalyse som et publiceret website — uden at nogen rører kode eller en chat-session
efter opsætning.

Eksisterende materiale (i `/Agent`-mappen) definerer kvalitetsbar og format:

- `Dansk_pension_marked_2026.html` — målformatet. Single-page app med tabs: Marked,
  Konkurrenter+SWOT, Trends, Muligheder, Analyser/UX. Bruges som skabelon (CSS-tokens,
  layout, interaktionsmønster) for alle fremtidige markeder.
- `Nord ID_Danske Byggemarkeder E-handel Markedanalyse.pdf` — eksempel på det analytiske
  skema: Executive Summary → Markedet → Trends → Muligheder → Appendix.

## 2. Systemarkitektur — tre dele

Dette er IKKE et enkelt script. Det er tre samvirkende dele:

1. **Landing page** (statisk, GitHub Pages) — grid/liste med links til alle genererede
   markedsanalyser + inputfelt + knap "Begynd markedsanalyse".
2. **Trigger-lag** (serverless function) — modtager input fra formularen, holder
   GitHub-token sikkert server-side, kalder GitHub API (`repository_dispatch`) for at
   starte pipelinen. **Token må aldrig ligge i frontend-kode** — statisk GitHub Pages kan
   ikke i sig selv modtage og behandle formular-submits sikkert.
3. **Pipeline** (GitHub Actions workflow, trigget af `repository_dispatch`) — kører
   research → analyse → HTML-generering → commit → push til `main`, hvorefter GitHub
   Pages publicerer automatisk.

```
[Bruger] → [Landing page form] → [Serverless function] → [GitHub repository_dispatch]
                                                                    ↓
                                          [GitHub Actions: research → analyse → HTML → commit/push]
                                                                    ↓
                                                         [GitHub Pages publicerer]
```

## 3. Pipeline — faser, modeller, ansvar

| Fase | Model | Ansvar | Kildebegrænsning |
|------|-------|--------|-------------------|
| Research | Claude Sonnet + websøgning | Indsaml rå data om markedet | Kun offentligt tilgængeligt i Danmark: årsrapporter, virksomhedshjemmesider, dst.dk, CVR/Erhvervsstyrelsen, brancheorganisationer (Dansk Erhverv, DI), Konkurrence- og Forbrugerstyrelsen. **Ingen interne dokumenter.** |
| Analyse/syntese | Claude Opus | SWOT, markedsdrivere/-barrierer, kundelandskab, strategiske implikationer, MECE-kvalitetstjek | Bruger system-prompt fra `senior-strategisk-konsulent`-skillen (se §4) |
| HTML-generering | Claude Sonnet | Udfyld parametriseret skabelon med analyseoutput | — |

Model-rationale: Sonnet er tilstrækkelig og billigere til bredde-opgaver (websøgning,
formattering). Opus er forbeholdt det trin hvor analysekvaliteten reelt afgøres
(tolkning, strategisk syntese) — det er her "dyb markedsanalyse" lever eller dør.

## 4. System-prompt for analysefasen

Kilde: `senior-strategisk-konsulent` SKILL.md (allerede gennemlæst i planlægningen).
Indeholder:

- Persona: senior strategisk konsulent, 15+ års erfaring, dansk/nordisk kontekst
- Strukturelle træk ved det danske marked (skala, digitalisering, trepartsmodel,
  offentlig sektor som aktør, prisfølsomhed)
- Branchespecifikke noter (bygge & anlæg, retail/e-commerce, professional services,
  tech/SaaS) — udvid med flere brancher efter behov når nye markeder testes
- Nordisk ekspansionsmønstre (DK→SE/NO/FI)
- Regulatorisk kontekst og kildehenvisninger (Konkurrence- og Forbrugerstyrelsen,
  Finanstilsynet, Erhvervsstyrelsen/CVR, Danmarks Statistik, Dansk Erhverv/DI)
- Markedsanalyserapport-skabelon: Executive Summary → Markedsoverblik (TAM/SAM/SOM) →
  Markedsdrivere/-barrierer → Kundelandskab → Konkurrentlandskab → Strategiske
  implikationer → Appendiks (metode, kilder, definitioner)
- Kvalitetstjek inden levering: klar konklusion i én sætning, evidensbaseret
  (fakta/vurdering/antagelse skilt ad), handlingsorienteret, MECE, niveau-tilpasset,
  nordisk kontekst korrekt anvendt

**Implementeringsnote:** Dette er en chat-skill (Cowork/claude.ai-koncept), IKKE noget
der automatisk følger med et rent API-kald. For at få samme effekt i pipelinen skal hele
indholdet kopieres ind som en statisk system-prompt-streng i koden (f.eks.
`prompts/strategisk_konsulent_system_prompt.md`, indlæst af analysefasens script). Den
fulde tekst findes i Cowork-skill-cachen under `senior-strategisk-konsulent/SKILL.md` —
kopiér den derfra ved implementering, eller bed Claude Code om at hente den fra denne
samtales kontekst.

## 5. HTML-skabelon

Udled en parametriseret template fra `Dansk_pension_marked_2026.html`:

- Bevar CSS-tokens (`--black`, `--blue`, `--font-display` osv.), pill-tabs-navigation,
  fade-up-animationer, sektionsstruktur.
- Map skillens analytiske skema ind i eksisterende tab-struktur:
  - **Marked**-tab ← Markedsoverblik + Markedsdrivere/-barrierer + Kundelandskab
  - **Konkurrenter**-tab ← Konkurrentlandskab + SWOT pr. aktør
  - **Trends**-tab ← uændret
  - **Muligheder**-tab ← Strategiske implikationer
  - Overvej en **Executive Summary**-sektion på hjemmesiden/landing-tab, da skillens
    skema kræver det og pension-eksemplet ikke har en tydelig tab for det
- Placeholders for: markedsnavn, dato, alle tekstsektioner, aktør-data (navn, profil,
  SWOT), trends, muligheder. Generér via templating (f.eks. simple `{{placeholder}}`
  eller en JS-byggefunktion der injicerer JSON-data i en fast HTML-skal).

## 6. Landing page

- Statisk side på repo-rod, hostes via GitHub Pages.
- Grid/liste over alle genererede markeder, hver med link til `/marked-slug/index.html`.
- Listen opdateres automatisk af pipelinen (workflowet skriver et nyt link til en
  manifest-fil eller direkte til landing page's HTML ved hver succesfuld kørsel).
- Inputfelt ("indtast marked") + knap "Begynd markedsanalyse" → poster til
  serverless-function-endpointet.
- Ingen password på selve knappen/formularen (bekræftet valg).

## 7. Sikkerhed og misbrugsbeskyttelse

Da formularen er helt åben (ingen login), er der reel risiko for ukontrolleret
API-forbrug, hvis linket deles eller indekseres. Indbygget, ikke bruger-facing:

- **Rate-limiting** på trigger-endpointet: f.eks. maks. 1 kørsel/time pr. IP.
- **Samtidighedscap** i GitHub Actions workflow: forhindre at flere kørsler overlapper
  og spammer API'et eller repoet.
- GitHub-token opbevares kun i serverless-functionens miljøvariabler (secrets), aldrig i
  frontend-kode eller committed filer.

## 8. Password-gating af indhold (ikke-kritisk)

- Aftalt: client-side JavaScript-gating af udvalgte sektioner i de genererede analyser.
- **Vigtigt forbehold:** dette er IKKE reel adgangskontrol. Enhver kan læse kildekoden
  eller password'et i browser-DevTools, eller hente HTML'en direkte. Det fungerer som en
  speedbump for almindelige besøgende, ikke som sikkerhed mod en motiveret aktør. Hvis
  kravet ændrer sig til reel beskyttelse, kræver det i stedet en hosting-løsning med
  server-side auth (f.eks. Cloudflare Access, Netlify password-protected sites) — ikke
  ren GitHub Pages.

## 9. Repo-struktur (forslag)

```
/                          → landing page (index.html)
/manifest.json             → liste over genererede markeder (navn, slug, dato)
/<marked-slug>/index.html  → genereret analyse
/templates/marked-template.html
/prompts/strategisk_konsulent_system_prompt.md
/scripts/research.(py|js)  → Sonnet + websøgning
/scripts/analyze.(py|js)   → Opus, bruger system-prompt
/scripts/generate_html.(py|js) → Sonnet, fylder skabelon
/.github/workflows/generate-analysis.yml → trigget af repository_dispatch
/functions/trigger.(py|js) → serverless endpoint, kalder GitHub API
```

## 10. Implementeringsrækkefølge (task-liste)

1. Omsæt `senior-strategisk-konsulent`-skillen til en statisk system-prompt-fil i repoet.
2. Parametriser HTML-skabelonen fra `Dansk_pension_marked_2026.html`.
3. Byg research-fasen (Sonnet + websøgning, afgrænset til offentlige danske kilder).
4. Byg analysefasen (Opus, bruger system-prompten fra trin 1).
5. Byg HTML-genereringsfasen (Sonnet, udfylder skabelonen fra trin 2).
6. Byg landing page (grid + formular).
7. Byg serverless trigger-function (sikker token-håndtering, kalder
   `repository_dispatch`).
8. Byg GitHub Actions workflow (kæder trin 3–5 sammen, committer, pusher).
9. Tilføj rate-limiting og samtidighedscap.
10. Tilføj client-side password-gating af udvalgt indhold.
11. End-to-end test: kør for et testmarked (f.eks. "optik"), verificér kvalitet,
    landing-page-opdatering, rate-limit, og gating. Tag screenshots af resultatet.

## 11. Åbne tekniske valg til Claude Code-sessionen

Disse er ikke afklaret med CEO endnu — bevidste implementeringsvalg, ikke
forretningsbeslutninger:

- Valg af serverless-platform (Vercel Functions, Netlify Functions, Cloudflare Workers,
  AWS Lambda) — afhænger af hvor I allerede har infrastruktur/konti.
- Konkret rate-limit-tærskel (forslag: 1/time/IP, men bør tilpasses forventet trafik).
- Hvordan manifest.json/landing page opdateres atomisk uden race conditions, hvis to
  kørsler afsluttes samtidigt.
- Fejlhåndtering: hvad sker der på landing page, hvis en pipeline-kørsel fejler
  (timeout, API-fejl, dårlig websøgningsdata)? Bør vise en fejlstatus, ikke bare intet.

## 12. Eksempelfiler brugt som reference

- `/Agent/Dansk_pension_marked_2026.html` — HTML-skabelon-kilde
- `/Agent/Nord ID_Danske Byggemarkeder E-handel Markedanalyse.pdf` — analytisk
  skema-reference

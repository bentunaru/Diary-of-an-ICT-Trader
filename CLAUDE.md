# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal ICT (Inner Circle Trader) trading journal for NQM26 / ESM26 futures on a Sierra Chart Sim1 account. There is no build system, no package manager, and no test suite — the deliverables are self-contained HTML files opened directly in a browser, plus one Python script that regenerates data.

The language of the content (UI text, comments, commit messages, docs) is **French**. Match it when editing.

## Key files

- `ICT_Dashboard.html` — the main deliverable. A single-file, data-driven dashboard (~350KB). All trade data lives in a `const DATA = {}` object near the top of the inline `<script>` (around line 499). Rendering regenerates from `DATA`; tabs (`overview`, `sessions`, `rules`, `concepts`, `errors`, `performance`, `backtest`, `plan`) are driven by `data-view` buttons. Chart.js is loaded via CDN — the file otherwise has zero external dependencies.
- `tools/update_dashboard.py` — regenerates the quantitative data (equity, trades, meta) from a Sierra Chart export. Stdlib only, no dependencies.
- `tools/annotations.json` — setups déclarés par Ben **en session** (skill de trading, voir "Workflow de session" ci-dessous) et rapprochés automatiquement des fills par `reconcile_declarations()` (`tools/trade_validation.py`). Ben n'édite jamais ce fichier à la main.
- `ICT_Knowledge.md` — the trader's methodology reference (setups, Kill Zones, range/Fib framework, top-down Weekly→4H→15m). Read this to annotate trades or understand domain terms; it is a living document, enriched as concepts are explained.
- `topstep_rules_config.json` / `topstep_rules_reference.md` — the Topstep rulebook (verified 2026-06-17): MLL, profit targets, consistency, optional DLL, scaling, payouts per account size (50K/100K/150K) and type (TC/XFA/LFA). The `.json` is the source of truth; the `.md` documents the formulas. The dashboard's `meta.propFirms` (Combine 50/100/150K) must stay in sync with these — note the Combine DLL is **optional** (`dllOptional` in the dashboard) and winning days are a **funded-account payout** criterion, not a Combine pass condition.
- `ict-arcade.html` — a standalone retro-arcade game ("Liquidity Hunter"), unrelated to the dashboard data pipeline.
- `plans/`, `backtests/`, `logos/` — image assets. `.gitignore` blocks all `*.png`/`*.txt`/`*.pdf` except whitelisted icons and `plans/*.png`.

## Updating dashboard data (the one real workflow)

```bash
python3 tools/update_dashboard.py path/to/TradeActivityLogExport_YYYY-MM-DD.txt
# no arg → uses the most recent TradeActivityLogExport_*.txt in cwd / repo root
```

The pipeline (`reconstruct` → `build_data` → `inject`):
1. Parses the TSV log, keeps `Fills` rows.
2. Reconstructs flat→flat trades per symbol via FIFO lot matching.
3. Computes real P/L (NQ $20/pt, ES $50/pt), daily equity, and best trade.
4. Derives each trade's Kill Zone from its open time. **The Sierra log is UTC; the script converts to ET via `UTC_TO_ET_OFFSET = -4` (EDT).** This offset is hardcoded and must change for non-DST dates.
5. Merges `tools/annotations.json` by trade-id (`YYYY-MM-DD_HH:MM:SS`, the UTC open time).
6. Injects only `equity[]` and `trades[]` into the HTML, plus `meta.fills`, `periodEnd`, and `bestTrade`.

### Critical constraints

- **The script rewrites the HTML in place between marker comments** (`// <EQUITY>`…`// </EQUITY>`, `// <TRADES>`…`// </TRADES>`). Never delete or reformat these markers, and do not hand-edit the data between them — it gets overwritten on the next run. Everything outside the markers (sessions, rules, errors, performance — authored HTML in `DATA`) is left untouched and must be edited by hand.
- **Annotations survive regeneration**; raw Sierra exports do not (they are gitignored). `annotations.json` has two blocks: `declarations[]` (setup déclaré en session, voir "Workflow de session" ci-dessous — `date`, `declared_at` heure ET, `setup`, `direction` optionnelle, `note` optionnelle, `screenshot` optionnelle, `source`) and `overrides{}` (correction a posteriori, clé `"<date_iso UTC>|<openTime UTC>"`, prime sur tout). `reconcile_declarations()` (`tools/trade_validation.py`) rapproche chaque déclaration d'un fill : tolérance ±15 min en heure ET (avec gestion du changement de jour), même direction si déclarée. Aucun match → `setup: "Non documenté"`, `taggedBy: "auto"` — **jamais bloquant** pour la régénération.

## Workflow de session (déclarations en direct)

Pendant qu'il trade, Ben envoie des screenshots et déclare son setup/son
attente dans le chat — texte libre, pas de format imposé côté Ben. À chaque
déclaration de ce type, Claude doit :

1. **Écrire l'entrée dans `tools/annotations.json` (`declarations[]`)**, en plus
   du narratif ajouté à l'onglet Session (`DATA.sessions[]` dans le HTML, édité
   à la main — pas de marqueur automatique pour cette section) :
   - `date` : date du jour au format ISO (`YYYY-MM-DD`).
   - `declared_at` : heure ET au moment de la déclaration (`HH:MM:SS`), pas
     l'heure du fill Sierra — c'est le rapprochement (`reconcile_declarations()`)
     qui fera le lien avec le fill au moment de l'import de l'export.
   - `setup` : un terme du vocabulaire fermé `VALID_SETUPS`
     (`tools/trade_validation.py`) — jamais de texte libre, sous peine de faire
     échouer la régénération (setup hors vocabulaire = bloquant).
   - `direction` (si Ben l'a précisée) : `"Long"` ou `"Short"`.
   - `note` (si Ben a donné un commentaire notable) : reprise telle quelle
     dans le champ `notes` du trade une fois rapproché.
   - `screenshot` (si un chemin/nom de fichier a été fourni) : référence
     informative, non exploitée par le rapprochement.
   - `source: "session"`.
2. **Ne jamais écrire dans `annotations.json` à la main pour Ben** — Ben ne
   saisit jamais rien lui-même dans ce fichier. Une correction a posteriori
   ("finalement c'était tel setup") va dans `overrides{}`, clé
   `"<date_iso UTC>|<openTime UTC>"` — nécessite de connaître l'openTime UTC du
   fill concerné (visible dans le dashboard une fois le journal régénéré).
3. Le rapprochement fills↔déclarations est **automatique et non bloquant** :
   en fin de journée, l'import de l'export Sierra
   (`python3 tools/update_dashboard.py ...`) rapproche chaque fill de la
   déclaration la plus proche (±15 min ET, même direction si déclarée). Un
   fill sans déclaration proche devient `"Non documenté"` — ça ne bloque rien,
   mais ça fait baisser le taux de documentation (KPI qualité du journal,
   affiché par `update_dashboard.py` et dans `trade_validation.stats()`).

## Domain notes that affect the code

- Point multipliers `MULT = {"NQ": 20.0, "ES": 50.0}` and Kill Zone windows (London 2–5 ET, NY AM 8:30–11 ET, London Close 10–12 ET) are encoded in the script and documented in `ICT_Knowledge.md` — keep them in sync if either changes.
- Fill prices in the log are in integer cents (`FillPrice / 100.0`).

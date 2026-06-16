# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal ICT (Inner Circle Trader) trading journal for NQM26 / ESM26 futures on a Sierra Chart Sim1 account. There is no build system, no package manager, and no test suite — the deliverables are self-contained HTML files opened directly in a browser, plus one Python script that regenerates data.

The language of the content (UI text, comments, commit messages, docs) is **French**. Match it when editing.

## Key files

- `ICT_Dashboard.html` — the main deliverable. A single-file, data-driven dashboard (~350KB). All trade data lives in a `const DATA = {}` object near the top of the inline `<script>` (around line 499). Rendering regenerates from `DATA`; tabs (`overview`, `sessions`, `rules`, `concepts`, `errors`, `performance`, `backtest`, `plan`) are driven by `data-view` buttons. Chart.js is loaded via CDN — the file otherwise has zero external dependencies.
- `tools/update_dashboard.py` — regenerates the quantitative data (equity, trades, meta) from a Sierra Chart export. Stdlib only, no dependencies.
- `tools/annotations.json` — manual ICT context per trade, keyed by trade-id.
- `ICT_Knowledge.md` — the trader's methodology reference (setups, Kill Zones, range/Fib framework, top-down Weekly→4H→15m). Read this to annotate trades or understand domain terms; it is a living document, enriched as concepts are explained.
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
- **Annotations survive regeneration**; raw Sierra exports do not (they are gitignored). To enrich the journal, add/edit entries in `annotations.json` keyed by trade-id, then re-run the script. Fields: `setupType`, `mood`, `processClean`, `setup`, `notes`, `rr`, `kz` (kz overrides the auto-derived Kill Zone).

## Domain notes that affect the code

- Point multipliers `MULT = {"NQ": 20.0, "ES": 50.0}` and Kill Zone windows (London 2–5 ET, NY AM 8:30–11 ET, London Close 10–12 ET) are encoded in the script and documented in `ICT_Knowledge.md` — keep them in sync if either changes.
- Fill prices in the log are in integer cents (`FillPrice / 100.0`).

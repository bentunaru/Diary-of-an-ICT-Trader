# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal ICT (Inner Circle Trader) trading journal for NQM26 / ESM26 futures on a Sierra Chart Sim1 account. There is no build system, no package manager, and no test suite — the deliverables are self-contained HTML files opened directly in a browser, plus one Python script that regenerates data.

**Language convention (décision Ben, 20 juillet 2026)** : l'**interface du
dashboard est en anglais** (nav, titres de sections, libellés KPI, boutons,
états vides, footer — tout ce que le renderer génère) ; **tout le contenu
reste en français** (narratifs de sessions, notes de trades, rules/concepts/
backtests, commentaires de code, messages de commit, docs). Les valeurs
produites par le pipeline (`classify_kz` → "Hors KZ", violations) restent
telles quelles pour ne pas casser la validation.

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
# no arg → merges everything already persisted in imports/ (Sierra + TradingView)
```

**Two fill sources, one journal.** The pipeline merges chronologically:
- **Sierra Chart** (compte Sim1, PC) : l'export TSV passé en argument est **copié dans `imports/sierra/`** puis tous les exports persistés y sont relus et dédoublonnés — les exports bruts hors repo sont volatils (supprimés/écrasés par Sierra ou OneDrive), `imports/` est la mémoire durable qui rend le journal régénérable. Timestamps UTC.
- **TradingView Paper Trading** (Mac, backtests/trades) : dépose les `paper-trading-order-history-all-*.csv` dans `imports/tradingview/` — lus automatiquement à chaque run, dédoublonnés par Order ID. Seuls NQ/ES/MNQ/MES sont retenus (autres symboles = warning). **Timestamps en heure locale Paris, convertis via `TV_LOCAL_TO_UTC_H = -2`** (à ajuster hors DST, comme `UTC_TO_ET_OFFSET`). Trades tagués `(TV)` dans l'instrument et `src: "TradingView"`.

The pipeline (`reconstruct` → `build_data` → `inject`):
1. Parses Sierra TSV logs (rows `Fills`) + TradingView order-history CSVs (orders `Filled`).
2. Reconstructs flat→flat trades per symbol via FIFO lot matching, all sources merged.
3. Computes real P/L (NQ $20/pt, ES $50/pt, micros 1/10e), daily equity, and best trade.
4. Derives each trade's Kill Zone from its open time. **Sierra logs are UTC; the script converts to ET via `UTC_TO_ET_OFFSET = -4` (EDT).** This offset is hardcoded and must change for non-DST dates.
5. Merges `tools/annotations.json` by trade-id (`YYYY-MM-DD_HH:MM:SS`, the UTC open time).
6. Injects only `equity[]` and `trades[]` into the HTML, plus `meta.fills`, `periodEnd`, and `bestTrade`.

### Critical constraints

- **The script rewrites the HTML in place between marker comments** (`// <EQUITY>`…`// </EQUITY>`, `// <TRADES>`…`// </TRADES>`). Never delete or reformat these markers, and do not hand-edit the data between them — it gets overwritten on the next run. Everything outside the markers (sessions, rules, errors, performance — authored HTML in `DATA`) is left untouched and must be edited by hand.
- **`imports/` est committé et fait foi** : ne jamais supprimer un fichier de `imports/sierra/` ou `imports/tradingview/` — c'est la seule copie durable des fills (les exports bruts sont gitignorés partout ailleurs). Un fichier corrompu se corrige, ne se supprime pas.
- **Annotations survive regeneration**. `annotations.json` has two blocks: `declarations[]` (setup déclaré en session, voir "Workflow de session" ci-dessous — `date`, `declared_at` heure ET, `setup`, `direction` optionnelle, `note` optionnelle, `screenshot` optionnelle, `source`) and `overrides{}` (correction a posteriori, clé `"<date_iso UTC>|<openTime UTC>"`, prime sur tout). `reconcile_declarations()` (`tools/trade_validation.py`) rapproche chaque déclaration d'un fill : tolérance ±15 min en heure ET (avec gestion du changement de jour), même direction si déclarée. Aucun match → `setup: "Non documenté"`, `taggedBy: "auto"` — **jamais bloquant** pour la régénération.

## « Session ouverte » — routine automatisée (Mac, boîte de dépôt locale)

**Tout se gère depuis le Mac** (`/Users/benjamin/Trading Journal`) — un seul
clone, plus de synchro PC↔Mac via GitHub. Sierra Chart continue de tourner
sur le PC (c'est là qu'est le compte Sim1) mais son export brut est transféré
par Ben lui-même (peu importe le moyen) dans `inbox/` en local sur le Mac,
au même titre que les exports TradingView et les screenshots. `inbox/` n'est
pas versionné (sauf `.gitkeep`) : c'est une zone de travail en vrac, jamais
une source de vérité — les copies durables vivent dans `imports/` et `plans/`.

Quand Ben dit **« session ouverte »** (ou dépose des fichiers dans `inbox/`
en vrac), Claude déroule :

1. **`git pull` d'abord** — vérifier qu'il n'y a pas de PR en attente côté
   GitHub à récupérer avant d'empiler du nouveau travail.
2. **Scanner `inbox/`** pour les fichiers non encore traités :
   - `TradeActivityLogExport_*.txt` (Sierra — **le nom de fichier ment
     souvent**, regarder les dates des fills dedans, pas le nom) ;
   - `paper-trading-order-history-all-*.csv` (TradingView — priorité à
     Sierra si TradingView est absent, ce n'est pas bloquant) ;
   - screenshots TradingView (`NQU2026_YYYY-MM-DD_*.png`), captures Sierra
     (`Screenshot YYYY-MM-DD *.png`), notes iPad (`IMG_*.PNG`).
3. **Lancer le pipeline** (`python3 tools/update_dashboard.py <export Sierra>` ;
   sans argument si seuls les CSV TV sont présents). Le script copie et
   persiste automatiquement l'export Sierra dans `imports/sierra/` et relit
   tout `imports/tradingview/` — copier d'abord les CSV TV neufs depuis
   `inbox/` vers `imports/tradingview/`.
4. **Lire chaque screenshot/note** et classer dans `plans/YYYY-MM-DD/` avec la
   numérotation en place (`01-` pré-marché top-down … `NN-tX-…` par trade),
   rédiger/mettre à jour le narratif de session (`DATA.sessions[]`, style
   `.rich` : `h3/p/strong/img`, pas de callouts) et documenter les setups via
   `overrides{}` si Ben ne les a pas déclarés en direct (demander confirmation
   du setup si l'inférence depuis les screenshots n'est pas évidente).
   **Ordre anté-chronologique dans chaque session** (décision Ben, 21 juillet
   2026) : le bloc le plus récent (dernier trade, setup surveillé, mise à
   jour) s'écrit EN HAUT du `html`, l'analyse pré-marché descend en bas —
   le lecteur voit d'abord la dernière info sans scroller. (La numérotation
   des fichiers dans `plans/` reste chronologique, elle.)
5. **Valider avant commit** (parse JS + rendu navigateur, cf. workflow de
   validation habituel), puis branche → PR — merge après OK de Ben.
6. Les violations détectées (sizing, hors-KZ, stop quotidien) se **signalent
   dans le narratif**, jamais en les masquant : le résultat ne valide pas le
   process.
7. Une fois les fichiers de `inbox/` traités (copiés dans `imports/`/`plans/`),
   ils peuvent être nettoyés de `inbox/` — les copies versionnées font foi.

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

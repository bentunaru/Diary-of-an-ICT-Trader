# Diary of an ICT Trader

Journal de trading ICT — NQM26 / ESM26 · Compte Sim1

## Dashboard

`ICT_Dashboard.html` — application single-file, data-driven.

Ouvrir directement dans un navigateur, aucune dépendance externe requise (Chart.js chargé via CDN).

### Fonctionnalités

- **Vue d'ensemble** — KPIs cumulés (P/L, Win Rate, Expectancy, Profit Factor), courbe equity, bar chart P/L journalier, journal des trades avec filtres et détail dépliable
- **Sessions** — accordéon par session : analyse pré-marché, détail des trades T1/T2/T3, management, bilan clôture
- **Erreurs** — résumé hebdomadaire des erreurs critiques / avertissements, compliance des règles ICT (barre de progression par règle)
- **Performance** — breakdown par setup ICT, par Kill Zone, streak process propre, analyse mood/état émotionnel, évolution violations par session
- **Règles ICT** — référentiel des concepts clés (OB, FVG, Unicorn, SMT, Kill Zones, Macro…)

### Architecture

Toute la donnée est centralisée dans `const DATA = {}` en tête de script.  
Pour ajouter une session : un point dans `equity[]`, les trades dans `trades[]`, une entrée dans `sessions[]`. Le rendu se régénère automatiquement.

```
DATA.meta          — période, compte, fills totaux
DATA.equity[]      — courbe P/L cumulé (un point par session)
DATA.trades[]      — tous les trades (setupType, kz, mood, processClean…)
DATA.sessions[]    — HTML complet de chaque session
DATA.rules[]       — règles ICT de référence
DATA.weeklyErrors[]   — erreurs documentées de la semaine
DATA.ruleCompliance[] — compliance par règle ICT
DATA.weeklyStats      — performance par setup / KZ / mood / streak
```

### Période couverte

3 juin → 12 juin 2026 · NQM26 / ESM26 · Sim1  
P/L cumulé : **+$86,172** · 29 trades réels · Win Rate 45%  
Source : reconstruction flat→flat du Trade Activity Log Sierra Chart.

## Automatisation — mise à jour depuis Sierra Chart

Les données quantitatives (equity, trades, stats) sont générées automatiquement
depuis un export `TradeActivityLogExport_*.txt` de Sierra Chart :

```bash
python3 tools/update_dashboard.py chemin/vers/TradeActivityLogExport_AAAA-MM-JJ.txt
```

Le script :
- parse le log (TSV), garde les lignes `Fills`
- reconstruit les trades flat→flat par symbole (matching FIFO)
- calcule le P/L réel (NQ $20/pt, ES $50/pt), l'equity journalier et les stats
- déduit la Kill Zone de l'heure (log en UTC → ET)
- fusionne les annotations ICT (`tools/annotations.json`) par trade-id
- injecte `equity[]` + `trades[]` dans `ICT_Dashboard.html` entre marqueurs `// <EQUITY>` / `// <TRADES>`

Le reste du dashboard (sessions, règles, erreurs) n'est pas touché.

### Annotations ICT

`tools/annotations.json` associe le contexte ICT (setup, mood, processClean, notes)
à chaque trade par son id `AAAA-MM-JJ_HH:MM:SS` (heure UTC d'ouverture). Ces annotations
survivent aux régénérations — il suffit de les compléter pour enrichir le journal.

## Méthodologie

ICT (Inner Circle Trader) — concepts principaux appliqués :

- Order Block (OB) 15min / 4H
- Fair Value Gap (FVG) · BISI / SIBI
- Unicorn Model (FVG + Breaker Block)
- SMT Divergence NQ / ES
- SSL / BSL (Sell-Side / Buy-Side Liquidity)
- Kill Zones : London 2h–5h ET · NY AM 8h30–11h ET
- FIB Range : 0% SSL · 25% best buys · 50% EQL · 75% best sells · 100% BSL
- Macro ICT : fenêtres algorithmiques :50–:10

## Instruments

| Instrument | Valeur du point | Tick |
|-----------|----------------|------|
| NQM26 (Nasdaq futures) | $20 / pt | 0.25 pt = $5 |
| ESM26 (S&P 500 futures) | $50 / pt | 0.25 pt = $12.50 |

Compte : **Sim1** · Sierra Chart · Données P/L vérifiées via `TradeStatisticsForCharts` export.

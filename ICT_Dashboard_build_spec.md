# Cahier des charges — « Diary of an ICT Trader » (journal de trading pro)
> Prompt de reproduction à donner à Claude Code. Objectif : reconstruire à l'identique un dashboard
> de journal de trading ICT, monofichier HTML, design institutionnel épuré, clair + sombre.
> Langue : **interface en anglais, contenus/commentaires en français.**

---

## 0. Principes généraux
- **Un seul fichier HTML autonome** (`ICT_Dashboard.html`), ouvrable par double-clic. Pas de framework.
  Vanilla HTML/CSS/JS. Une seule lib externe : **Chart.js v4** (CDN) avec **fallback canvas natif** si absente.
- **Polices** : IBM Plex Sans (texte) + IBM Plex Mono (tous les chiffres, classe `.num` avec `font-variant-numeric: tabular-nums`). Repli système : `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` et `'SF Mono', Menlo, monospace`.
- **Source unique de vérité** : tout le rendu (KPIs, courbes, journal, sessions…) est généré en JS depuis un seul objet `DATA`. Aucun chiffre dupliqué dans le HTML.
- **Pipeline de données** : les blocs `equity` et `trades` de `DATA` sont délimités par des commentaires marqueurs `// <EQUITY> … // </EQUITY>` et `// <TRADES> … // </TRADES>` pour qu'un script externe puisse les réécrire. **Conserver ces marqueurs.**
- **Accessibilité** : `role="tablist"/"tab"`, `aria-selected`, `aria-expanded`, focus visibles (`:focus-visible` outline accent), `@media (prefers-reduced-motion: reduce)`.
- **Style 100% via variables CSS** → un simple changement de palette recolore tout, y compris les graphes (qui lisent les variables au runtime).

---

## 1. Système de design

### 1.1 Palette (institutionnelle : neutres slate froids + accent indigo UNIQUE + vert/rouge P&L maîtrisés)
La couleur ne porte que le **sens** : vert = gain, rouge = perte, indigo = structurel (onglet actif, focus, liens, pastilles neutres). Tout le reste est neutre.

**Thème clair `:root`**
```
--bg:#f3f5f9; --bg2:#ffffff; --bg3:#eceff5; --bg-hover:#e3e8f0;
--border:rgba(15,23,42,.09); --border-strong:rgba(15,23,42,.16);
--text:#0f172a; --muted:#647189;
--green:#0c8f63; --red:#d4364c; --accent:#3a55d9; --blue:#2f6feb; --violet:#7458e8;
--green-bg:rgba(12,143,99,.09); --red-bg:rgba(212,54,76,.08); --accent-bg:rgba(58,85,217,.08);
--grid:rgba(15,23,42,.055);
--shadow:0 1px 2px rgba(15,23,42,.04),0 2px 8px rgba(15,23,42,.04);
--shadow-lg:0 4px 16px rgba(15,23,42,.08),0 1px 3px rgba(15,23,42,.06);
--topbar-bg:rgba(255,255,255,.9); --radius:12px;
```
**Thème sombre `[data-theme="dark"]`**
```
--bg:#0a0e16; --bg2:#131926; --bg3:#1a2130; --bg-hover:#222b3c;
--border:rgba(255,255,255,.08); --border-strong:rgba(255,255,255,.15);
--text:#e8ecf4; --muted:#8893a8;
--green:#2bbd7a; --red:#f2546b; --accent:#7088ff; --blue:#5b89ff; --violet:#9a86f5;
--green-bg:rgba(43,189,122,.13); --red-bg:rgba(242,84,107,.12); --accent-bg:rgba(112,136,255,.14);
--grid:rgba(255,255,255,.06);
--shadow:0 1px 2px rgba(0,0,0,.4),0 2px 8px rgba(0,0,0,.3);
--shadow-lg:0 6px 22px rgba(0,0,0,.5),0 1px 3px rgba(0,0,0,.4);
--topbar-bg:rgba(10,14,22,.9);
```

### 1.2 Thème clair/sombre
- Bouton toggle (icône lune/soleil SVG) dans la topbar. État mémorisé en `localStorage` clé `ict-theme`.
- Script **dans le `<head>`** appliquant le thème avant rendu (anti-flash) : lit `localStorage`, sinon `prefers-color-scheme`.
- Au toggle : set `data-theme` + persiste + **reconstruit les graphes** (`buildCharts()`) pour recolorer.
- `body { transition: background-color .25s, color .25s; }`.

### 1.3 Typographie & échelles
- Hero P&L : 42px/600. Titres de section (`h2`) : 12px, 600, UPPERCASE, letter-spacing .7px, couleur `--muted`.
- Valeurs KPI 22px/600 ; labels KPI 11px UPPERCASE muted. Petit texte 11–12.5px.
- Classes sémantiques de couleur : `.pos{color:var(--green)} .neg{color:var(--red)} .acc{color:var(--accent)}`.

### 1.4 Rayons (3 niveaux, cohérents partout)
- **Cartes & sections** : `12px` (`--radius`). **Panneaux/callouts internes** : `10px`. **Mini-éléments/chips** : `8px`. **Pills/chips ronds** : `20px`.

### 1.5 Pattern « soft semantic » (PAS de trait latéral)
> Remplace l'ancienne convention « bordure-gauche colorée » (datée). À utiliser pour tout élément porteur de sens.
- Carte : fond **légèrement teinté** (`--green-bg`/`--red-bg`/`--accent-bg`) + bordure teintée via `color-mix(in srgb, var(--green) 26%, transparent)` + **pastille ronde colorée** devant le label (`::before`, 7px) ou pastille inline `.idot`.
- Variantes : `--green` (positif), `--red` (critique/perte), `--accent` (avertissement/structurel).
- **Aucune** `border-left` épaisse nulle part.
- Pastille inline réutilisable : `.idot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:7px}` + `.idot.green/.red/.accent/.muted`.

### 1.6 Survol des cartes (identique partout)
`transform:translateY(-2px); box-shadow:var(--shadow-lg); border-color:var(--border-strong);` sur `.kpi, .stat-card, .error-card, .rule, .concept, .bt-entry, .plan-tf` (transition .15s).

### 1.7 En-tête de page cohérent
Chaque onglet ouvre sur un élément de contexte du même type :
- Overview → hero. Performance/Errors/Rules/Backtest → ligne d'intro `.view-intro` (13px muted, max 74ch).
- Sessions → rail sticky. Plan → bannière. Concepts → barre de recherche.
- En-tête de section optionnel `.section-head` = `<h2>` + `.section-hint` (11px muted) aligné à droite.

---

## 2. Structure & navigation

### 2.1 Topbar (sticky, blur)
- Logo SVG « DI » + titre **Diary of an ICT Trader**.
- Badges : `NQM26 · ESM26`, `Sierra Chart`, et badge **`SIM · réel`** (accent) avec **infobulle** au survol : « Compte démo Sierra (Sim1) — P/L = valeurs réelles exportées du Trade Activity Log, sans estimation ».
- À droite : `Period` (dates) + **bouton toggle thème**.

### 2.2 Onglets (8, regroupés logiquement)
Ordre + séparateurs visuels (`.tab-sep`) :
`Overview · Performance · Errors  |  Sessions · Backtest · Plan  |  ICT Rules · Concepts`
- **Scroll horizontal** sur mobile (pas de wrap), scrollbar masquée.
- **Persistance** : onglet actif sauvegardé en `localStorage` (`ict-tab`) + **hash d'URL** (`#performance`) → deep-link et survie au rechargement.
- **Navigation clavier** (pattern ARIA tablist) : flèches gauche/droite, Home, End ; roving `tabindex`.
- Transition d'entrée de vue : `@keyframes viewIn` (fade + translateY 6px).

---

## 3. Modèle de données `DATA`
```
meta: { periodStart, periodEnd, account:"Sim1", fills:Number,
        riskMaxDay:{value,label,sub}, maxDrawdownLimit:-20000 /* éditable, jauge prop firm */ }
equity: [ { date:"03 juin", cum:12010 }, … ]        // P/L cumulé réel, entre marqueurs <EQUITY>
trades: [ {                                          // cycles flat→flat, entre marqueurs <TRADES>
   date,instr,dir:"Long|Short",entry,exit,rr,
   pl:"+$13,020",plClass:"pos|neg",plNum:13020,result:"Win|Perte",
   setup,notes,kz:"London|NY AM|Hors KZ",
   setupType,mood:"Confiant|Neutre|Impatient|FOMO|Revenge",processClean:Boolean   // annotations ICT manuelles (optionnelles)
}, … ]
bestTrade:{value,sub}
rules:[ {label,text,critical?:true} ]               // ~14
concepts:[ {label,text} ]                            // glossaire
weeklyErrors:[ {type:"critical|warning",title,occurrences,days,description,rule,costStr} ]
ruleCompliance:[ {label,violations,ok} ]
backtests:[ {date,instrument,timeframe,setup,result:"valid|invalid|neutral",title,comment,
             lessons:[{type:"pos|neg|note",text}],images:[{caption,src(dataURI)}]} ]
weekPlan:{ date,instrument,bias,summary,timeframes:[{tf,title,img,note,levels:[{name,val}]}] }
```

## 4. Métriques calculées (formules exactes)
- `plOf(t)` : utilise `plNum`, sinon parse `pl`.
- wins/losses/closedTrades, **winRate** = wins/closed.
- avgWin, avgLoss (valeur absolue), **expectancy** = winRate·avgWin − (1−winRate)·avgLoss.
- totalWins, totalLosses, **profitFactor** = totalWins/totalLosses.
- **oneR** = avgLoss (proxy de risque = 1R). **payoff** = avgWin/avgLoss. **rExpectancy** = expectancy/oneR. `rOf(t)` = plOf/oneR.
- **Equity trade-par-trade** : somme cumulée de `plNum` dans l'ordre ; suivi du `peak` ; `dd = cum − peak` (≤0). **maxDrawdown** = |min(dd)|. **currentDD** = |dernier dd|.
- **clean/dirty** : sur trades annotés (`processClean` booléen) → cleanNet, dirtyNet, dirtyLossSum (somme des dirty perdants).
- **largestWin/largestLoss**, **concentration** = largestWin/totalWins (% du gain brut issu du meilleur trade).
- **maxLosingStreak** = plus longue série de pertes consécutives (chronologique).
- **processAdherence** = clean / annotés (%).
- Groupes Performance : par `setupType`, par `kz`, par `mood`, et **par jour de semaine** (dérivé de `date` via `new Date(2026,5,jour).getDay()`, libellés Mon→Fri).
- **Process streak** (annotés) : current, longest. **violationEvolution** : nb de dirty par session.
- **Distribution R** : bins `<−2R, −2..−1, −1..0, 0..1, 1..2, 2..3, 3..5, >5R` (négatifs rouges, positifs verts).

## 5. Graphes (Chart.js, theme-aware, reconstruits au toggle)
Helper `cssVar(name)` lit les variables CSS au runtime (couleurs des charts = `--green/--red/--muted/--grid/--green-bg/--red-bg`). Fonction unique `buildCharts()` qui **détruit puis recrée** toutes les instances (tableau `chartInstances`), appelée **en fin de script** (tous les canvases existent) et à chaque toggle de thème. Fallback `drawFallbackChart()` (canvas natif) si `Chart` indéfini.
1. **Net P&L curve** — ligne cumulée par session, remplie.
2. **Daily P&L by session** — barres vert/rouge.
3. **Trade-by-trade equity & drawdown** — 2 datasets : `peak` (ligne pointillée muted) + `equity` (ligne verte, `fill:'-1'` rempli en `--red-bg` = zone de drawdown). **Points rouges plus gros = trades hors-process (dirty)**. Tooltip : equity, P/L du trade, drawdown, ⚠ hors-process.
4. **Drawdown underwater** — aire rouge du `dd` (≤0) au fil des trades, axe Y plafonné à 0.
5. **R-multiple distribution** — barres par bin (rouges négatifs / verts positifs).

---

## 6. Contenu par onglet

### 6.1 Overview
- **Bande hero (`.overview-top`, 2 colonnes)** :
  - Gauche `.hero-pl` (léger wash radial accent) : label « Net P&L » + infobulle, **valeur 42px**, **sparkline SVG** inline (indépendante de Chart.js) générée depuis `equity`, et pied à 3 stats : *Last session*, *Avg R / trade*, *Max drawdown*.
  - Droite `.story-card` : « **Your edge · win rate × payoff = expectancy** » avec 3 termes (Win rate × Payoff = Expectancy) + phrase explicative FR sur l'asymétrie.
- **Scorecard KPI (`.kpis`, auto-fit minmax 160px)**, ordre = priorité d'un pro :
  `Expectancy ($ + R)` · `Profit Factor` · `Win rate (W/L)` · `Payoff ratio` · `Max drawdown (+ current DD)` · `Max losing streak` · `Process adherence (%)`. Infobulles `.info` sur les métriques techniques.
- **Section graphes** : Net P&L curve + Daily P&L.
- **Section equity** : Trade-by-trade equity & drawdown + **Drawdown underwater** + **jauge drawdown vs limite** (`#dd-gauge` : barre de progression `maxDrawdown / |maxDrawdownLimit|`, classes ok/warn/danger à 50/80%, % utilisé + buffer restant).
- **Period statistics** (`.stat-card`) : Avg win, Avg loss, Largest win, Largest loss, **Concentration** (accent si ≥40%), Max risk engaged, Total fills.
- **Trade log** :
  - En-tête avec hint + bouton **Export CSV** (SVG download) → génère un CSV (BOM UTF-8) : Date, Instrument, Direction, Entry, Exit, P/L, R, Result, Setup, Kill Zone, Process, Notes ; téléchargement via Blob.
  - **Filtres groupés** (chips pill) : Instrument · Result (Win/Loss avec `.idot`) · Kill Zone · Process (Clean/Dirty) + compteur « X / N trades affichés ».
  - **Tableau triable** (clic en-tête Date / R / P/L, flèche qui pivote) ; colonnes : caret, Date, Instr, Dir (tag), Entry, Exit, **R** (pill `.r-pill` vert/rouge), **P/L** (valeur + mini-barre `.pl-bar` proportionnelle), Result (tag + **pastille process**). Lignes **dépliables** (détail : setup, notes, setupType, KZ, mood, process). Enveloppé dans `.table-scroll` (défilement horizontal mobile, min-width 600px).

### 6.2 Performance
Intro `.view-intro`. KPIs : *Process adherence*, *Current streak (✓)*, *Best streak*, *Most reliable setup*.
- **R-multiple distribution** (chart).
- Grille `.perf-grid` (2 col) : **Setup performance** (table : setup, trades, win-rate barre, total P/L), **Kill Zone performance** (pastille `.idot` colorée par win-rate + W/L), **Performance by weekday** (table P/L par jour), **Process discipline streak** (pastilles `.streak-dot` ✓/✗ par trade), **Psychology** (barres par mood, couleurs : Confiant=green, Neutre=blue, Impatient/FOMO=red, Revenge=violet — toutes en variables).
- Section pleine largeur : **ICT violations trend** (barres de violations par session, cible 0).

### 6.3 Errors
Intro. KPIs : Critical errors, Warnings, Rules respected, Dominant pattern.
- **Coût des violations de process** (`.cost-grid` 3 cartes teintées + pastille) : *Trades hors-process* (nb + net), *Pertes encaissées hors-process* (dont revenge sizing), *P/L net process propre*. + **barre « what-if »** (`.whatif-bar`) : segment vert « $X réel » + segment accent « +$Y récupérables » et phrase « potentiel $Z sans les pertes hors-process… la marge est comportementale ».
- **Documented errors** : cartes `.error-card` **teintées** (critical=rouge, warning=accent) avec pastille `.idot`, badge occurrences, description, encart **« Correct rule »** vert doux, coût.
- **ICT rule compliance** : tracker (label + barre ok/warn/bad + badge violations).

### 6.4 Sessions
- **Rail sticky** `.session-rail` : chips « Aller à » (date + P/L, pastille colorée, état `live`) → clic = ouvre + scroll vers la session ; **scrollspy** (surligne le chip de la session la plus proche du haut) ; bouton **« Tout déplier / replier »**.
- Accordéon `<details class="session">` (la plus récente ouverte). En-tête : date, statut (live/closed), P/L. Corps : titres `h3` en **séparateurs propres** (marqueur accent 3px + hairline bas), panneaux/callouts en pattern soft semantic.

### 6.5 Backtest
Intro avec compteur de setups validés. Cartes `.bt-entry` : en-tête (date en chip + tags instrument/timeframe/setup/résultat coloré), titre, **commentaire** teinté selon résultat, **lessons** (cartes teintées + pastille : Strength/Error/Note), **galerie** d'images (dataURI) avec **lightbox** (clic = plein écran, Échap/clic = ferme).

### 6.6 Plan
Bannière `.plan-head` (wash accent) : titre « Weekly Plan · date · instruments », **bias** en pill, résumé. Cartes `.plan-tf` par timeframe : badge + titre, image (ou placeholder), note + **niveaux** alignés (nom ↔ valeur mono). Lightbox partagée.

### 6.7 ICT Rules
Intro. Cartes `.rule` groupées : **« Non-négociables »** (critiques, fond rouge doux, pastille rouge) puis **« Règles opérationnelles »** (pastille accent). Titres de groupe `.group-title` avec pastille + compteur + hairline. Bloc citation `.quote` en bas.

### 6.8 Concepts (glossaire)
**Barre de recherche** (input + icône loupe SVG) filtrant en temps réel (titre + texte) + compteur « X / N concepts ». Cartes `.concept` en **colonne unique large** (lecture des définitions longues) : terme + **icône-initiale** (carré accent avec 1re lettre, mono) + définition. **État vide** si aucun résultat.

---

## 7. Terminologie (UI anglaise)
`Net P&L` (pas « Cumulative P/L ») · `Largest win/loss` (pas « Best trade ») · `Process adherence` (pas « Clean process ») · `Psychology` (pas « Mood analysis ») · `Payoff ratio`, `Expectancy (+R)`, `Profit Factor`, `Max losing streak`, `Concentration`, `R-multiple distribution`, `Drawdown underwater`.

## 8. Version autonome hors-ligne (build)
Pour produire un fichier autonome partageable (zéro dépendance réseau) :
1. Retirer les `<link>` favicon/apple-touch-icon et les polices Google (repli système). 
2. Neutraliser les `<img src="plans/…">` (captures privées) → placeholder « Capture disponible dans la version connectée ».
3. Inliner Chart.js (le bundler le transforme en blob). Les images de backtest sont déjà en dataURI base64.
4. Garder le tout dans un seul `.html` ; viser ~480 Ko.
5. Si l'outil de bundling injecte un bandeau d'erreur global (`#__bundler_err`), ajouter un petit script qui le retire en continu (MutationObserver + interval) — l'app étant fonctionnelle.

## 9. À NE PAS faire
- Pas de trait latéral coloré (`border-left` épais). Pas d'emoji dans le *chrome* (utiliser pastilles `.idot`/labels) ; emoji tolérés uniquement dans la prose de session.
- Pas plus de 2 fonds de couleur ; l'accent indigo reste réservé au structurel. Pas de dégradés agressifs.
- Ne pas dupliquer de chiffres en dur dans le HTML : tout vient de `DATA`.
- Ne pas casser les marqueurs `<EQUITY>` / `<TRADES>`.

— Fin du cahier des charges.

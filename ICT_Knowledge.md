# ICT Knowledge Base — Méthodologie du trader

> Document vivant. Enrichi à chaque explication. Sert de référence pour reconnaître
> les setups du trader sans réexplication, et pour annoter les futurs screenshots.

---

## 1. Principe fondamental

Un trader ICT **n'attend pas le prix, il l'anticipe**. Le marché est algorithmique :
l'algorithme prend de la liquidité (SSL/BSL) puis cherche une efficience (comble un FVG).
Tout setup se construit **avant** le mouvement, pas pendant.

---

## 2. Setup principal — Sweep de liquidité → Retracement → Target Range

### Logique (apprise le 13 juin 2026, backtest NQM26 15min)

1. **Sweep d'un niveau de liquidité** (ex : Asian Low / Asian High) **avant la Kill Zone**
   → c'est le signal d'anticipation. Le sweep = l'algorithme est allé chercher la
   liquidité côté opposé avant de repartir.
   - Sweep de l'**Asian Low** → on anticipe un mouvement **haussier** (long)
   - Sweep de l'**Asian High** → on anticipe un mouvement **baissier** (short)

2. **Formation d'un PDA dans la zone de discount/premium** après le sweep :
   - **OB** (Order Block) — la dernière bougie opposée avant le déplacement
   - **Breaker Block** — OB qui a été invalidé puis re-respecté
   - **FVG / BISI / SIBI** — déséquilibre laissé par le déplacement

3. **Retracement dans le PDA** (l'OB en priorité) → **entrée en ordre limite**.

4. **Target** — voir section 5 (gestion des targets selon la taille du range).

### Règle de liquidité épuisée (importante)

Un **FVG déjà utilisé par le Stop Run** est considéré comme **consommé** :
la liquidité y a déjà été prise, donc on **ne s'attend pas à un retour** sur ce niveau.
→ Ne pas placer d'entrée ni de stop en référence à un FVG déjà traversé/utilisé.

Ex (13 juin) : le FVG (BISI) bas ~28,880 avait déjà servi au Stop Run qui a pris
l'Asian Low → pas de raison que le prix y revienne. L'entrée se fait sur l'OB plus haut.

---

## 3. Hiérarchie des PDAs (zone de discount)

Ordre de priorité pour poser un ordre limite :

1. **GAP** — premier PDA, le plus bas (bottom de la zone)
2. **FVG / Unicorn** — déséquilibre
3. **OB** — Order Block

Poser un ordre limite à chaque niveau **dès la planification pré-marché**.

---

## 4. Modèle Unicorn

**Displacement → FVG créé → prix revient dans le FVG → Breaker Block à l'intérieur
ou adjacent.** La confluence **FVG + Breaker** = setup à exécuter sans hésitation.

---

## 5. Framework Range (FIB) + gestion des targets

| Niveau | Rôle |
|--------|------|
| 0% | SSL · Stop invalide |
| 25% | Best buys (zone discount) |
| 50% | EQL · Pivot · premier objectif |
| 75% | Best sells (zone premium) · **target préféré** |
| 100% | BSL · Target complet |

### Gestion des targets (apprise le 13 juin 2026)

- Le **50% du Range n'est en général PAS le TP final** — c'est un premier objectif.
- **Exception** : si le range est **très grand**, les 50% suffisent largement (le move
  en absolu est déjà conséquent).
- **Niveau préféré : 75% du Range Fib.**
- **Les meilleurs setups se situent entre 25% et 75% du range** — c'est la zone de
  travail privilégiée (entrées en discount 25%, sorties en premium 75%).

---

## 6. Kill Zones (heures algorithmiques)

| KZ | Horaire (ET) |
|----|--------------|
| London | 2h00 – 5h00 |
| NY AM | 8h30 – 11h00 |
| London Close | 10h00 – 12h00 |

Un retour dans un FVG **pendant une Kill Zone** = confluence ICT forte.
Le sweep qui précède la KZ (ex : Asian Low pris avant 2:00 ET) confirme le biais.

### Macro ICT (fenêtre algorithmique)

Chaque heure, entre **:50 et :10** (7:50–8:10, 9:50–10:10…), l'algorithme prend de la
liquidité ou atteint une efficience. Pattern typique : **Run-Stop-Run**.
Instrument préféré pour les macros : **ES** (plus propre que NQ).

---

## 7. Règles de gestion (process propre)

- **Stop structurel obligatoire** — jamais le stop Sierra par défaut. Placer manuellement
  sous le low 15min / OB / FVG. Désactiver le stop par défaut avant toute entrée.
- **Sizing fixe = 3 contrats.** Jamais modifier en réaction à un résultat (pas de revenge sizing).
- **Biais pré-marché tenu** jusqu'à une close 15min structurelle hors range. Pas de décision émotionnelle intra-session.
- **TP du plan = sell limits posées d'avance**, ne pas les baisser. Laisser le setup se dérouler.
- **News / IPO = ordres limites uniquement.**
- **Valider le sweep** : un corps de bougie doit fermer au-delà du niveau (pas seulement une mèche).

---

## 8. Instruments

| Instrument | Valeur point | Tick |
|-----------|--------------|------|
| NQM26 (Nasdaq) | $20 / pt | 0.25 pt = $5 |
| ESM26 (S&P 500) | $50 / pt | 0.25 pt = $12.50 |

Roll NQM26 → NQU26 vers le 17–18 juin (contrat dominant = plus de volume).

---

## 9. Méthodologie Top-Down (Weekly → 4H → 15m)

Lecture multi-timeframe systématique avant chaque semaine / session. Chaque
timeframe a un rôle précis :

**Weekly — définir le range macro et la position premium/discount.**
On marque le range hebdo (high / low). Si le prix est en **premium** (moitié haute),
le biais directionnel de fond est **short** : si le prix doit continuer vers le bas,
c'est de la zone premium que viendra le **setup short parfait**. En discount, biais long.

**4H — l'objectif directionnel à court terme.**
On reporte le range et les Fib (0 / 25 / 50 / 75 / 100). En premium du 4H, l'attente
typique est une **prise du high du range (Fib 100 = BSL)** avant tout retournement.
→ On laisse d'abord le prix aller chercher la liquidité au-dessus (Fib 100).

**15m — la zone d'entrée intraday.**
On marque le range 15m courant. Pour un **long intraday**, on attend un **retour en
discount** (sous les niveaux rouges = 50% et equilibrium du range 15m). La présence
d'un **15m Breaker** dans la zone renforce le point d'entrée.

**Synthèse de l'arbitrage des timeframes :**
- Biais de fond (Weekly premium) = chercher les shorts en haut.
- Mais d'abord (4H premium) = laisser le prix prendre le high / Fib 100 (BSL).
- Entrée intraday (15m) = long sur retour en discount + Breaker, en visant le Fib 100 4H.
- Le grand short Weekly ne se travaille qu'**après** la prise de liquidité du high.

---

## Plan de la semaine — 14 juin 2026 (NQM26)

Lecture top-down du dimanche soir (prix ~29,662) :

- **Weekly** : range macro **28,250 → 30,800**. Prix en **premium**. Biais de fond short
  si continuation baissière — le setup short parfait se formera dans le premium.
- **4H** : range **28,227.75 (Fib 0) → 29,848.25 (Fib 100)**. Niveaux : 0.25 ≈ 28,632 ·
  0.5 ≈ 29,038 · 0.75 ≈ 29,443 · 1.0 = 29,848.25. Prix en premium (entre 0.75 et 1.0).
  **Attente : prise du high du range, Fib 100 ≈ 29,848 (BSL).**
- **15m** : range intraday courant. **15m Breaker ≈ 29,560.** Pour un **long intraday**,
  attendre un retour en **discount sous les traits rouges (~29,500 / equilibrium ~29,440)**.

**Scénario privilégié :** long intraday sur retour en discount 15m (+ Breaker) → cible
le Fib 100 4H (~29,848 / BSL). Puis surveiller le premium Weekly pour le short de fond.

---

## Journal d'apprentissage

| Date | Source | Concept appris |
|------|--------|----------------|
| 13 juin 2026 | Backtest NQM26 15min | Sweep Asian Low avant KZ → OB retracement → Target Range · Règle FVG consommé par Stop Run |
| 13 juin 2026 | Précision targets | 50% rarement le TP final (sauf très grand range) · 75% = niveau préféré · meilleurs setups entre 25% et 75% du range |
| 14 juin 2026 | Méthodologie Top-Down (4 charts) | Weekly = range macro + premium/discount · 4H = objectif (Fib 100 BSL si premium) · 15m = entrée intraday (retour discount + Breaker). Plan semaine 14 juin documenté. |

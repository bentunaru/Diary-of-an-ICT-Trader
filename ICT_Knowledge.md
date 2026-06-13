# ICT Knowledge Base — Méthodologie de Benjamin

> Document vivant. Enrichi à chaque explication. Sert de référence pour reconnaître
> les setups de Benjamin sans réexplication, et pour annoter les futurs screenshots.

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

4. **Target = 50% du Range 4H** (niveau d'équilibre EQL/pivot).

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

## 5. Framework Range (FIB)

| Niveau | Rôle |
|--------|------|
| 0% | SSL · Stop invalide |
| 25% | Best buys (zone discount) |
| 50% | EQL · Pivot · **Target par défaut du sweep** |
| 75% | Best sells (zone premium) |
| 100% | BSL · Target haussier complet |

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

## Journal d'apprentissage

| Date | Source | Concept appris |
|------|--------|----------------|
| 13 juin 2026 | Backtest NQM26 15min | Sweep Asian Low avant KZ → OB retracement → Target 50% 4H · Règle FVG consommé par Stop Run |

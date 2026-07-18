# Topstep — Règles complètes (référence dashboard)

> Source : help.topstep.com — Vérifié le **17 juin 2026**, mise à jour plateforme le **1er juillet 2026**.
> Toutes les heures en **CT (America/Chicago)**. Devise : **USD**.
> Fichier compagnon : `topstep_rules_config.json` (config machine-readable à importer).

---

## 0. Architecture du programme (3 étapes)

`Trading Combine (TC)` → `Express Funded Account (XFA, simulé)` → `Live Funded Account (LFA, réel)`

- **TC** : compte simulé d'évaluation. Atteindre le Profit Target sans toucher le MLL.
- **XFA** : compte funded simulé. Payouts réels. Démarre à **$0** (le label = buying power, pas le solde).
- **LFA** : compte réel, capital Topstep. Call-up discrétionnaire par la Risk Team.

Tailles : **50K / 100K / 150K**.

---

## 1. La règle unique : Maximum Loss Limit (MLL)

| Taille | MLL (TC & XFA) | MLL liquidation (LFA) |
|--------|----------------|------------------------|
| 50K    | $2,000         | $1,000                 |
| 100K   | $3,000         | $1,000                 |
| 150K   | $4,500         | $1,000                 |

**Comportement (TC & XFA) :**
- Trailing : monte avec le solde EOD, **ne redescend jamais**.
- Verrouille une fois revenu au solde de départ (TC) / à **$0** (XFA).
- Calculé en **temps réel sur Net P&L (réalisé + non réalisé)**. Si le seuil est touché en intra-day, liquidation immédiate — même si le solde final repasse au-dessus (slippage).
- **Non ajustable. Aucune exception.**

**XFA spécifique :** MLL démarre négatif (-$2,000 / -$3,000 / -$4,500), trail jusqu'à $0 puis lock. **Après le 1er payout → MLL = $0 définitif**, le solde restant devient le plancher.

**LFA spécifique :** seuil unique de **$1,000** toutes tailles. Sous $1,000 → liquidation + fermeture en fin de journée, solde restant en payout final, réserve non débloquée perdue.

---

## 2. Trading Combine — paramètres

| Taille | Profit Target | MLL    | Max contrats | Max micros | Meilleur jour max | DLL (option) |
|--------|---------------|--------|--------------|------------|-------------------|--------------|
| 50K    | $3,000        | $2,000 | 5            | 50         | < $1,500          | $1,000       |
| 100K   | $6,000        | $3,000 | 10           | 100        | < $3,000          | $2,000       |
| 150K   | $9,000        | $4,500 | 15           | 150        | < $4,500          | $3,000       |

- **Passage possible en 2 jours minimum** (pas en 1 seul jour).
- **Consistency Target 50%** : `best_day / total_profit ≤ 50%`. Si dépassé → le Profit Target augmente : `nouveau_PT = best_day / 0.50`.
- Le meilleur jour se **verrouille à 15:10 CT**. Les pertes ne réinitialisent pas le best day.
- Micros comptés **10:1** (10 micros = 1 mini) — **sans exception depuis le 28 février 2026** : ProjectX (moteur tiers utilisé pour NinjaTrader/Tradovate) a coupé le support des prop firms tierces ce jour-là, donc **TopstepX est désormais la seule plateforme** Topstep (plus de compte legacy non-TopstepX, plus de ratio 1:1 alternatif).

---

## 3. Express Funded Account — 2 chemins de payout

| | **Standard** | **Consistency** |
|---|---|---|
| Éligibilité payout | 5 jours gagnants $150+ | 3 jours tradés + consistency ≤ 40% |
| Cap payout 50K | $2,000 | $3,000 |
| Cap payout 100K | $3,000 | $4,000 |
| Cap payout 150K | $5,000 | $6,000 |
| Max par demande | 50% du solde | 50% du solde |
| Split | 90/10 | 90/10 |
| Consistency formula | — | `largest_day / total_net_profit ≤ 40%` |

**Règles payout XFA :**
- Min payout **$125**, max **50% du solde** (plafonné par cap ci-dessus).
- Profit requis depuis dernier payout (min $0.01) — 1er payout exempté.
- Jours gagnants = **$150+ net**, verrouillés à **16:00 CT**, non consécutifs.
- Après payout : **MLL → $0**, compteurs (jours / consistency) reset, jour de la demande exclu du cycle suivant.
- Jusqu'à **5 XFA actifs**, **$750K buying power max** via trade copier.
- Inactivité **30 jours** → fermeture.

> ⚠️ Clause legacy : traders inscrits **avant le 12 jan 2026** → 100% des $10,000 premiers profits à vie, puis 90/10.

---

## 4. Scaling Plan (TC max position + XFA)

- Définit le **nombre max de contrats** selon le **solde courant** (XFA part de $0).
- **N'augmente pas en cours de session** : nouveau palier appliqué à la session suivante (rebill 17:00 CT).
- Ne s'applique **pas au LFA** (remplacé par Dynamic Live Risk Expansion).
- Tolérance erreur : position excédentaire corrigée **< 10 s** ignorée ; ≥ 10 s → review.
- Plafonds : **5 / 10 / 15** contrats (50K / 100K / 150K).
- 50K XFA démarre à **2 contrats** et scale 2 → 3 → 4 → 5.

> 🔴 **À VÉRIFIER** : les seuils de solde intermédiaires de chaque palier sont publiés dans une **image** sur la page Scaling Plan de Topstep et ont été ajustés occasionnellement. Scraper/vérifier l'image avant mise en prod plutôt que coder des valeurs supposées. Marqué `TO_VERIFY` dans le JSON.

**Pondérations spéciales :** Micro Silver (SIL) = ratio 5:1 (compte comme 2 micros) ; Micro Bitcoin (MBT) et Micro Ether (MET) plafonnés à l'équivalent mini.

---

## 5. Live Funded Account

- **Taille** = moyenne des XFA éligibles (≥ 1 payout), arrondie au palier supérieur.
- **Solde de départ = 20%** des soldes XFA combinés (min **$10,000**), **80% en réserve**.
- Réserve débloquée par tranches de **25%** à chaque atteinte du Profit Target :

| Taille LFA | Profit Target (débloque 25% réserve) | DLL standard |
|------------|--------------------------------------|--------------|
| 50K        | $3,000                               | $2,000       |
| 100K       | $6,000                               | $3,000       |
| 150K       | $9,000                               | $4,500       |

**DLL dynamique selon solde tradable :**

| Solde tradable ≤ | DLL    | Max position |
|------------------|--------|--------------|
| $10,000          | $2,000 | 5            |
| $5,000           | $1,000 | 3            |

(Ajustement le vendredi ; retour au standard quand le solde remonte.)

**Payout LFA :** 5 jours gagnants $150+, jusqu'à **50% sans cap**. Après **30 jours gagnants** → **payouts quotidiens jusqu'à 100%** (min $125). Payout uniquement depuis le solde débloqué, pas la réserve. 100% ferme le compte.

- Capital expansion review **lundi matin** ; pas de multi-palier sur un seul gros gain.

---

## 6. Horaires & produits

- **Journée de trading** : 17:00 CT → 15:10 CT le lendemain. Ordre passé après 17:00 CT = session suivante.
- **Flat obligatoire à 15:10 CT** (Risk commence à flatten à 15:08). Réouverture 17:00 CT.
- Vendredi : clôture 15:10 CT, fermé jusqu'au dimanche 17:00 CT.
- **Pas de swing / overnight.** Tous les ordres en attente annulés à la clôture.
- **Futures uniquement** (CME, COMEX, NYMEX, CBOT). Interdits : actions, options, **Forex spot**, **crypto spot**, CFD.
- Produits clés Ben : **NQ, ES (CME)** · **GC (COMEX)**.
- Horaires spéciaux : grains CBOT (ZC/ZW/ZS/ZM/ZL) et ag CME (HE/LE) ont des plages distinctes — voir JSON.

---

## 7. Conformité (à intégrer dans la logique de validation)

- **Single Profile Policy** : tous les comptes sous 1 profil. Multi-profil = violation ToU.
- **MLL/DLL temps réel** sur Net P&L (réalisé + non réalisé) — un breach intra-day reste un breach.
- **Stratégies automatisées** autorisées sous conditions ; **ProjectX API interdite en LFA** ; copier autorisé ; **hedging inter-comptes interdit**.
- Refs : [Prohibited Conduct](https://help.topstep.com/en/articles/10296582-prohibited-conduct) · [Prohibited Strategies](https://help.topstep.com/en/articles/10305426-prohibited-trading-strategies-at-topstep) · [Terms of Use](https://www.topstep.com/terms-of-use).

---

## Notes d'intégration pour Claude Code

1. **Source de vérité = `topstep_rules_config.json`.** Ce `.md` documente la logique/formules.
2. Indexer toute la config par **taille de compte** (`50K`/`100K`/`150K`) et **type** (`TC`/`XFA`/`LFA`).
3. Implémenter le MLL/DLL en **temps réel sur Net P&L non réalisé**, pas seulement à la clôture des trades.
4. Le **best day** (consistency) se verrouille à 15:10 CT ; le **winning day** payout à 16:00 CT — deux horloges distinctes.
5. Le **Scaling Plan XFA** a des seuils `TO_VERIFY` (image) : prévoir un champ de config éditable, pas de hardcode.
6. Gérer la bascule **DLL dynamique LFA** sur événement du vendredi (recalcul hebdo).

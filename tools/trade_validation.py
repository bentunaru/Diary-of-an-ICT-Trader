#!/usr/bin/env python3
"""
trade_validation.py — Rapprochement des déclarations de session + validation
des règles de discipline pour le ICT Dashboard.

Deux modes :
  1. Standalone : python3 trade_validation.py ICT_Dashboard.html
     → parse le bloc <TRADES> (déjà enrichi par update_dashboard.py), applique
       les règles de discipline, affiche le rapport (dont le taux de documentation).
  2. Import (depuis tools/update_dashboard.py) :
         from trade_validation import reconcile_declarations, validate_trades, RULES
         tags = reconcile_declarations(trades, annotations)   # setup + taggedBy par trade
         trades = validate_trades(trades, rules=...)          # enrichit `violations`
     → setup manquant = tagué "Non documenté" (tagged_by "auto"), JAMAIS bloquant.
     → seul un setup HORS VOCABULAIRE (VALID_SETUPS) fait échouer la régénération
       (garde-fou contre une faute de frappe dans une déclaration/override).

Le setup ne vient plus d'une saisie manuelle de Ben dans ce fichier : il est
déclaré en session (skill ict-trading-journal) et rapproché automatiquement des
fills par reconcile_declarations(). Voir tools/annotations.json pour le schéma
(declarations[] / overrides{}).
"""
import json
import re
import sys
from collections import defaultdict
from datetime import date, timedelta

# ── Règles (source unique — alignées sur le plan de risque) ──────────────────
RULES = {
    "MAX_CONTRACTS": 7,          # sizing standard MNQ (5+2 SwissFirmUp)
    "MAX_TRADES_PER_DAY": 2,     # ≤ 2 trades perdants/jour → 2 trades max
    "DAILY_STOP": -500.0,        # stop quotidien perso ($)
    # Décalage (minutes) pour convertir l'openTime du log → heure ET.
    # Le TradeActivityLogExport Sierra est en UTC ; ET été = UTC−4 → −240.
    # ⚠ À passer à −300 après le retour à l'heure d'hiver (début novembre),
    #   ou mettre 0 si l'export Sierra est reconfiguré directement en ET.
    "OPENTIME_SHIFT_MIN": -240,
}

# Fenêtres d'exécution (heure ET, bornes [début, fin) en minutes depuis minuit).
# SOURCE UNIQUE de la définition des KZ — update_dashboard.py doit importer
# classify_kz() au lieu de sa propre classification, sinon deux vérités.
KZ_WINDOWS = [
    # (nom, début, fin, live) — heures ET, bornes [début, fin).
    # Alignées sur la config TradingView de Ben (20 juil. 2026).
    # live=False : fenêtre reconnue pour tagging/backtest ; trade réel = violation.
    ("Asia",        20 * 60,      24 * 60,       False),  # 20:00–00:00
    ("London",       2 * 60,       5 * 60,       True),   # 02:00–05:00
    ("NY pré-open",  7 * 60,       9 * 60 + 30,  False),  # 07:00–09:30 — OBSERVATION seulement
    #   (lecture des setups en formation, pas d'entrée ; couvre l'embargo news 08:30)
    ("NY AM",        9 * 60 + 30, 11 * 60,       True),   # 09:30–11:00 (exécution dès l'open equities)
    ("NY late",     11 * 60,      11 * 60 + 30,  True),   # 11:00–11:30 (fin du périmètre live)
    ("NY Lunch",    12 * 60,      13 * 60,       False),  # 12:00–13:00
    ("NY PM",       13 * 60 + 30, 16 * 60,       False),  # 13:30–16:00 (backtest)
]
ALLOWED_KZ = {name for name, _, _, live in KZ_WINDOWS if live}
# tout le reste (00–02, 05–07, 11:30–12, 13–13:30, 16–20) = "Hors KZ" → violation

# Silver Bullets (ET) — overlay : un trade porte kz ET sb (ou sb absent).
SB_WINDOWS = [
    ("SB London", 2 * 60,      3 * 60),       # 02:00–03:00
    ("SB NY AM", 10 * 60,     11 * 60),       # 10:00–11:00
    ("SB NY PM", 14 * 60,     15 * 60),       # 14:00–15:00
]


def _to_et_minutes(open_time, shift_min=None):
    if shift_min is None:
        shift_min = RULES["OPENTIME_SHIFT_MIN"]
    h, m = open_time.split(":")[:2]
    return (int(h) * 60 + int(m) + shift_min) % (24 * 60)


def _to_et_date_minutes(date_iso, open_time, shift_min=None):
    """(date_iso UTC, 'HH:MM:SS' UTC) -> (date_iso ET, minutes depuis minuit ET).

    Gère le changement de jour calendaire (ex. Asia 20:00–00:00 ET tombe le
    lendemain en UTC) — nécessaire pour rapprocher un fill d'une déclaration de
    session, qui est datée en ET.
    """
    if shift_min is None:
        shift_min = RULES["OPENTIME_SHIFT_MIN"]
    h, m = open_time.split(":")[:2]
    total = int(h) * 60 + int(m) + shift_min
    day_shift, mins = divmod(total, 24 * 60)
    et_date = date.fromisoformat(date_iso) + timedelta(days=day_shift)
    return et_date.isoformat(), mins


def classify_sb(open_time, shift_min=None):
    """openTime du log → nom du Silver Bullet, ou None."""
    try:
        mins = _to_et_minutes(open_time, shift_min)
    except (ValueError, AttributeError):
        return None
    for name, start, end in SB_WINDOWS:
        if start <= mins < end:
            return name
    return None


def classify_kz(open_time, shift_min=None):
    """openTime du log ('05:26:00') → fenêtre ET, via OPENTIME_SHIFT_MIN."""
    try:
        mins = _to_et_minutes(open_time, shift_min)
    except (ValueError, AttributeError):
        return "Hors KZ"
    for name, start, end, _live in KZ_WINDOWS:
        if start <= mins < end:
            return name
    return "Hors KZ"

VALID_SETUPS = {
    # Vocabulaire fermé — un setup hors liste = faute de frappe à corriger.
    "Sweep SSL → FVG 5m", "Sweep BSL → FVG 5m",
    "OB 15m → Displacement 1m → FVG 1m",
    "IFVG 5m", "Breaker 5m", "OTE 0.677–0.788",
    "FVG multi-TF",   # confluence de FVG/BISI validée étage par étage (1h→15m→5m→1m)
    "MMXM", "Judas Swing", "SMT divergence",
    "Hors modèle",   # tag explicite : trade pris SANS setup (à assumer, pas à cacher)
}

# Sentinelle posée par reconcile_declarations() quand aucune déclaration de
# session ne rapproche le fill — pas une faute de vocabulaire, donc exemptée
# du check VALID_SETUPS. Le taux de documentation (stats()) l'isole.
AUTO_SETUP = "Non documenté"

# Tolérance de rapprochement déclaration ↔ fill (minutes, heure ET).
MATCH_TOLERANCE_MIN = 15


class ValidationError(Exception):
    pass


def trade_key(t):
    return f"{t.get('date', '?')}|{t.get('openTime', '?')}"


# ── Rapprochement déclarations de session ↔ fills reconstruits ──────────────
def reconcile_declarations(trades, annotations, shift_min=None):
    """Associe à chaque trade reconstruit (flat→flat) un setup + sa provenance.

    `trades` : liste interne de update_dashboard.reconstruct() — chaque élément a
    au moins `id`, `date_iso` (UTC), `open_time` ('HH:MM:SS' UTC), `dir`.

    Priorité :
      1. overrides["<date_iso>|<open_time>"] (saisie a posteriori) → tagged_by "override".
      2. Déclaration de session la plus proche en ET, ±MATCH_TOLERANCE_MIN,
         même direction si la déclaration en porte une → tagged_by "declaration".
      3. Aucun match → setup AUTO_SETUP, tagged_by "auto".

    Un scale-in (plusieurs fills avant retour à plat) est déjà fusionné en UN
    seul trade logique par reconstruct() — une déclaration ne matche donc jamais
    plus d'un fill par trade, mais peut matcher plusieurs trades logiques distincts
    si Ben a ré-exécuté le même setup dans la fenêtre de tolérance.

    Retourne { trade_id: {"setup": str, "taggedBy": "override"|"declaration"|"auto",
                           "note": str|None} }.
    """
    overrides = annotations.get("overrides", {})
    by_date = defaultdict(list)
    for d in annotations.get("declarations", []):
        if d.get("date") and d.get("declared_at"):
            by_date[d["date"]].append(d)

    tags = {}
    for t in trades:
        override_key = f"{t['date_iso']}|{t['open_time']}"
        ov = overrides.get(override_key)
        if ov and ov.get("setup"):
            tags[t["id"]] = {"setup": ov["setup"], "taggedBy": "override", "note": None}
            continue

        et_date, et_min = _to_et_date_minutes(t["date_iso"], t["open_time"], shift_min)
        best, best_delta = None, None
        for d in by_date.get(et_date, []):
            try:
                dh, dm = d["declared_at"].split(":")[:2]
                d_min = int(dh) * 60 + int(dm)
            except (ValueError, KeyError):
                continue
            delta = abs(d_min - et_min)
            if delta > MATCH_TOLERANCE_MIN:
                continue
            if d.get("direction") and t.get("dir") and d["direction"] != t["dir"]:
                continue
            if best is None or delta < best_delta:
                best, best_delta = d, delta

        if best:
            tags[t["id"]] = {"setup": best.get("setup") or AUTO_SETUP,
                              "taggedBy": "declaration", "note": best.get("note")}
        else:
            tags[t["id"]] = {"setup": AUTO_SETUP, "taggedBy": "auto", "note": None}
    return tags


# ── Cœur : flags automatiques de discipline ──────────────────────────────────
def validate_trades(trades, rules=RULES, strict=True):
    """Enrichit chaque trade avec `violations`. Le `setup` doit déjà être posé
    (par reconcile_declarations, en amont). Ordre chronologique requis."""
    unknown = []
    per_day_count = defaultdict(int)
    per_day_pl = defaultdict(float)
    last_result_by_day = {}   # (plNum du trade précédent du jour)
    last_size_by_day = {}

    for t in trades:
        day = t.get("date", "?")
        v = []

        # 1) Vocabulaire du setup — jamais bloquant si "Non documenté" (aucune
        #    déclaration rapprochée), bloquant en mode strict si c'est une
        #    valeur hors VALID_SETUPS (faute de frappe dans une déclaration/override).
        setup = t.get("setup", AUTO_SETUP)
        if setup != AUTO_SETUP and setup not in VALID_SETUPS:
            unknown.append((trade_key(t), setup))

        # 2) Sizing.
        c = int(t.get("contracts", 0))
        if c > rules["MAX_CONTRACTS"]:
            v.append(f"SIZING {c}>{rules['MAX_CONTRACTS']}")

        # 3) Kill Zone — recalculée depuis openTime (source unique : KZ_WINDOWS),
        #    on ignore la valeur kz éventuellement présente dans le log.
        kz = classify_kz(t.get("openTime", ""))
        t["kz"] = kz
        sb = classify_sb(t.get("openTime", ""))
        if sb:
            t["sb"] = sb
        if kz not in ALLOWED_KZ:
            v.append(f"HORS KZ ({kz})")

        # 4) Nombre de trades/jour.
        per_day_count[day] += 1
        if per_day_count[day] > rules["MAX_TRADES_PER_DAY"]:
            v.append(f"TRADE #{per_day_count[day]} DU JOUR (max {rules['MAX_TRADES_PER_DAY']})")

        # 5) Escalade post-perte (pattern récupération) : taille ↑ après un trade perdant du même jour.
        prev_pl = last_result_by_day.get(day)
        prev_sz = last_size_by_day.get(day)
        if prev_pl is not None and prev_pl < 0 and prev_sz is not None and c > prev_sz:
            v.append(f"ESCALADE POST-PERTE {prev_sz}→{c}")

        # 6) Entrée alors que le stop quotidien est déjà dépassé.
        if per_day_pl[day] <= rules["DAILY_STOP"]:
            v.append(f"ENTRÉE APRÈS STOP QUOTIDIEN ({per_day_pl[day]:+.0f}$)")

        pl = float(t.get("plNum", 0.0))
        per_day_pl[day] += pl
        last_result_by_day[day] = pl
        last_size_by_day[day] = c

        t["violations"] = v

    if strict and unknown:
        lst = "\n".join(f"    {k}: '{s}'" for k, s in unknown)
        raise ValidationError(f"SETUP HORS VOCABULAIRE (VALID_SETUPS) :\n{lst}")
    return trades


# ── Stats par modèle / KZ / discipline ───────────────────────────────────────
def stats(trades):
    def agg(sub):
        if not sub:
            return None
        wins = [t for t in sub if t["plNum"] > 0]
        gp = sum(t["plNum"] for t in wins)
        gl = abs(sum(t["plNum"] for t in sub if t["plNum"] < 0))
        return {
            "n": len(sub), "wins": len(wins),
            "winrate": round(100 * len(wins) / len(sub)),
            "net": round(sum(t["plNum"] for t in sub), 1),
            "pf": round(gp / gl, 2) if gl else float("inf"),
        }

    by_setup = defaultdict(list)
    by_kz = defaultdict(list)
    by_sb = defaultdict(list)
    clean, dirty = [], []
    documented = 0
    for t in trades:
        by_setup[t.get("setup", AUTO_SETUP)].append(t)
        by_kz[t.get("kz", "?")].append(t)
        by_sb[t.get("sb", "hors SB")].append(t)
        (dirty if t.get("violations") else clean).append(t)
        if t.get("taggedBy") in ("declaration", "override"):
            documented += 1

    return {
        "global": agg(trades),
        "par_setup": {k: agg(v) for k, v in sorted(by_setup.items())},
        "par_kz": {k: agg(v) for k, v in sorted(by_kz.items())},
        "par_sb": {k: agg(v) for k, v in sorted(by_sb.items())},
        "trades_propres": agg(clean),          # zéro violation → l'edge réel du modèle
        "trades_en_violation": agg(dirty),     # le P/L de l'indiscipline
        # KPI qualité journal — doit tendre vers 100 % (déclarer en session, pas a posteriori).
        "taux_documentation": round(100 * documented / len(trades)) if trades else None,
    }


# ── Standalone : parse le bloc <TRADES> du HTML ──────────────────────────────
def parse_dashboard(html_path):
    src = open(html_path, encoding="utf-8").read()
    m = re.search(r"//\s*<TRADES>(.*?)//\s*</TRADES>", src, re.S)
    if not m:
        sys.exit("Bloc <TRADES> introuvable dans le HTML.")
    block = m.group(1)
    trades = []
    for obj in re.finditer(r"\{(.*?)\}(?=\s*,?\s*(?:\{|$))", block, re.S):
        body = obj.group(1)
        t = {}
        for k, val in re.findall(r'(\w+):\s*(".*?"|[−+\-\d.]+)', body):
            t[k] = val.strip('"').rstrip(",")
        t["plNum"] = float(t.get("plNum", "0").replace("−", "-"))
        t["contracts"] = int(float(t.get("contracts", "0")))
        trades.append(t)
    return trades


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    trades = parse_dashboard(sys.argv[1])
    try:
        validate_trades(trades, strict=True)
    except ValidationError as e:
        print(f"❌ {e}")
        print(json.dumps(stats(trades), ensure_ascii=False, indent=2))
        sys.exit(1)
    print("✅ Aucun setup hors vocabulaire.")
    print(json.dumps(stats(trades), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

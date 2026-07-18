#!/usr/bin/env python3
"""
trade_validation.py — Validation obligatoire des trades du ICT Dashboard.

Deux modes :
  1. Standalone : python3 trade_validation.py ICT_Dashboard.html [annotations.json]
     → parse le bloc <TRADES>, applique les règles, affiche le rapport.
     → exit 1 si un trade n'a pas de setup taggé (bloque la régénération en CI).
  2. Import (depuis tools/update_dashboard.py) :
         from trade_validation import validate_trades, RULES
         trades = validate_trades(trades, annotations)   # enrichit chaque trade
     → chaque trade reçoit `setup` (depuis annotations.json) et `violations: [...]`.
     → lève ValidationError si un setup manque → le dashboard ne se régénère PAS
       tant que chaque trade n'est pas taggé.

Clé de trade stable : "<date>|<openTime>" (ex. "29 juin|05:26:00").

Schéma annotations.json attendu :
{
  "trades": {
    "29 juin|05:26:00": { "setup": "Sweep SSL → FVG 5m", "grade": "A" },
    ...
  }
}
"""
import json
import re
import sys
from collections import defaultdict

# ── Règles (source unique — alignées sur le plan de risque) ──────────────────
RULES = {
    "MAX_CONTRACTS": 7,          # sizing standard MNQ (5+2 SwissFirmUp)
    "MAX_TRADES_PER_DAY": 2,     # ≤ 2 trades perdants/jour → 2 trades max
    # Stop quotidien : FALLBACK uniquement (MLL 3500 ÷ 5, SwissFirmUp 300K).
    # La valeur réelle est dérivée de mm + challenge actif par update_dashboard.py
    # (compute_daily_stop) et passée en override via le paramètre rules.
    "DAILY_STOP": -700.0,
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
    ("London",       2 * 60,       5 * 60),        # 02:00–05:00
    ("NY pré-open",  7 * 60,       8 * 60 + 30),   # 07:00–08:30 (traverse les news 08:30)
    ("NY AM",        8 * 60 + 30, 11 * 60),        # 08:30–11:00 (KZ ICT canonique)
    ("NY late",     11 * 60,      11 * 60 + 30),   # 11:00–11:30 (début lunch)
]
ALLOWED_KZ = {name for name, _, _ in KZ_WINDOWS}   # tout le reste = "Hors KZ" → violation


def classify_kz(open_time, shift_min=None):
    """openTime du log ('05:26:00') → fenêtre ET, via OPENTIME_SHIFT_MIN."""
    if shift_min is None:
        shift_min = RULES["OPENTIME_SHIFT_MIN"]
    try:
        h, m = open_time.split(":")[:2]
        mins = (int(h) * 60 + int(m) + shift_min) % (24 * 60)
    except (ValueError, AttributeError):
        return "Hors KZ"
    for name, start, end in KZ_WINDOWS:
        if start <= mins < end:
            return name
    return "Hors KZ"

VALID_SETUPS = {
    # Vocabulaire fermé — un setup hors liste = faute de frappe à corriger.
    "Sweep SSL → FVG 5m", "Sweep BSL → FVG 5m",
    "OB 15m → Displacement 1m → FVG 1m",
    "IFVG 5m", "Breaker 5m", "OTE 0.677–0.788",
    "MMXM", "Judas Swing", "SMT divergence",
    "Hors modèle",   # tag explicite : trade pris SANS setup (à assumer, pas à cacher)
}


class ValidationError(Exception):
    pass


def trade_key(t):
    return f"{t.get('date', '?')}|{t.get('openTime', '?')}"


# ── Cœur : enrichissement + flags automatiques ───────────────────────────────
def validate_trades(trades, annotations, rules=RULES, strict=True):
    """Enrichit chaque trade avec `setup` et `violations`. Ordre chronologique requis."""
    ann = annotations.get("trades", {})
    missing, unknown = [], []
    per_day_count = defaultdict(int)
    per_day_pl = defaultdict(float)
    last_result_by_day = {}   # (plNum du trade précédent du jour)
    last_size_by_day = {}

    for t in trades:
        key = trade_key(t)
        day = t.get("date", "?")
        v = []

        # 1) Setup obligatoire — vient d'annotations.json, jamais du log Sierra.
        a = ann.get(key)
        if a and a.get("setup"):
            t["setup"] = a["setup"]
            if a.get("grade"):
                t["grade"] = a["grade"]
            if a["setup"] not in VALID_SETUPS:
                unknown.append((key, a["setup"]))
        else:
            missing.append(key)

        # 2) Sizing.
        c = int(t.get("contracts", 0))
        if c > rules["MAX_CONTRACTS"]:
            v.append(f"SIZING {c}>{rules['MAX_CONTRACTS']}")

        # 3) Kill Zone — recalculée depuis openTime (source unique : KZ_WINDOWS),
        #    on ignore la valeur kz éventuellement présente dans le log.
        kz = classify_kz(t.get("openTime", ""))
        t["kz"] = kz
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

    if strict and missing:
        raise ValidationError(
            "SETUP MANQUANT — dashboard NON régénéré. Tagger dans annotations.json :\n"
            + "\n".join(f'    "{k}": {{ "setup": "…" }},' for k in missing)
        )
    if unknown:
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
    clean, dirty = [], []
    for t in trades:
        by_setup[t.get("setup", "NON TAGGÉ")].append(t)
        by_kz[t.get("kz", "?")].append(t)
        (dirty if t.get("violations") else clean).append(t)

    return {
        "global": agg(trades),
        "par_setup": {k: agg(v) for k, v in sorted(by_setup.items())},
        "par_kz": {k: agg(v) for k, v in sorted(by_kz.items())},
        "trades_propres": agg(clean),          # zéro violation → l'edge réel du modèle
        "trades_en_violation": agg(dirty),     # le P/L de l'indiscipline
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
    annotations = {}
    if len(sys.argv) > 2:
        annotations = json.load(open(sys.argv[2], encoding="utf-8"))
    try:
        validate_trades(trades, annotations, strict=True)
    except ValidationError as e:
        print(f"❌ {e}")
        # On calcule quand même les stats (setups partiels), mais exit 1.
        for t in trades:
            t.setdefault("setup", "NON TAGGÉ")
        print(json.dumps(stats(trades), ensure_ascii=False, indent=2))
        sys.exit(1)
    print("✅ Tous les trades taggés — aucune régénération bloquée.")
    print(json.dumps(stats(trades), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

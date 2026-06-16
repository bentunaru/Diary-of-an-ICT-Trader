#!/usr/bin/env python3
"""
update_dashboard.py — Régénère les données quantitatives du dashboard ICT
à partir d'un export Sierra Chart "TradeActivityLogExport".

Usage:
    python3 tools/update_dashboard.py [chemin_export.txt]

Si aucun chemin n'est fourni, prend le TradeActivityLogExport_*.txt le plus
récent dans le dossier courant.

Ce que fait le script :
  1. Parse le log (TSV), garde les lignes "Fills"
  2. Reconstruit les trades flat→flat par symbole (matching FIFO)
  3. Calcule P/L réel (NQ $20/pt, ES $50/pt), equity journalier, stats
  4. Fusionne les annotations ICT (annotations.json) par trade-id
  5. Injecte equity[] + trades[] dans ICT_Dashboard.html entre marqueurs

Le script ne touche PAS au reste du dashboard (sessions, règles, etc.).
"""
import csv, json, sys, os, glob, re
from collections import deque, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DASHBOARD = os.path.join(ROOT, "ICT_Dashboard.html")
ANNOTATIONS = os.path.join(HERE, "annotations.json")

MULT = {"NQ": 20.0, "ES": 50.0}
MONTHS_FR = {1:"janvier",2:"février",3:"mars",4:"avril",5:"mai",6:"juin",
             7:"juillet",8:"août",9:"septembre",10:"octobre",11:"novembre",12:"décembre"}


def sym_short(s):
    if "NQ" in s: return "NQ"
    if "ES" in s: return "ES"
    return "?"


def instr_full(s):
    if "NQ" in s: return "NQM26"
    if "ES" in s: return "ESM26"
    return s


def fr_date(iso):  # "2026-06-08" -> "08 juin"
    y, m, d = iso.split("-")
    return f"{d} {MONTHS_FR[int(m)]}"


# Le log Sierra est en UTC. ET (EDT en juin) = UTC - 4h.
UTC_TO_ET_OFFSET = -4

def to_et_minutes(hhmmss):
    """'07:28:57' UTC -> minutes depuis minuit en ET."""
    h, m, s = map(int, hhmmss.split(":"))
    et_h = (h + UTC_TO_ET_OFFSET) % 24
    return et_h * 60 + m

def kill_zone(hhmmss):
    """Kill Zone ICT déduite de l'heure d'ouverture (ET)."""
    t = to_et_minutes(hhmmss)
    if 2 * 60 <= t < 5 * 60:        return "London"        # 02:00–05:00 ET
    if 8 * 60 + 30 <= t < 11 * 60:  return "NY AM"         # 08:30–11:00 ET
    if 10 * 60 <= t < 12 * 60:      return "London Close"  # 10:00–12:00 ET
    return "Hors KZ"


def parse_log(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            rows.append(row)
    fills = [x for x in rows if x["ActivityType"] == "Fills"]
    fills.sort(key=lambda x: x["DateTime"])
    return rows, fills


def reconstruct(fills):
    """Reconstruit les trades flat→flat avec matching FIFO."""
    trades = []
    state = defaultdict(lambda: {"lots": deque(), "pos": 0, "open_time": None,
                                 "realized": 0.0, "dir": None, "entry_px": None,
                                 "maxq": 0, "fills": 0})
    for fl in fills:
        sym = fl["Symbol"]; short = sym_short(sym); mult = MULT[short]
        qty = int(fl["FilledQuantity"]); px = float(fl["FillPrice"]) / 100.0
        side = 1 if fl["BuySell"] == "Buy" else -1
        t = fl["DateTime"]; st = state[sym]
        # Un fill peut à la fois fermer la position et en ouvrir une opposée (flip).
        # On le traite par tranches bornées au retour à plat, pour ne jamais
        # mélanger deux trades dans une même position reconstruite.
        remaining = qty
        while remaining > 0:
            if st["pos"] == 0:
                st.update(open_time=t, dir=("Long" if side == 1 else "Short"),
                          realized=0.0, entry_px=px, maxq=0, fills=0)
                st["lots"].clear()
            # Si ce fill réduit la position, on s'arrête au flat ; sinon on prend tout.
            if st["pos"] != 0 and st["pos"] * side < 0:
                chunk = min(remaining, abs(st["pos"]))
            else:
                chunk = remaining
            st["fills"] += 1
            q = chunk
            while q > 0 and st["lots"] and (st["lots"][0][0] * side < 0):
                lot_side, lot_qty, lot_px = st["lots"][0]
                m = min(q, lot_qty)
                pl = (px - lot_px) * m * mult if lot_side == 1 else (lot_px - px) * m * mult
                st["realized"] += pl
                q -= m
                if m == lot_qty:
                    st["lots"].popleft()
                else:
                    st["lots"][0] = (lot_side, lot_qty - m, lot_px)
            if q > 0:
                st["lots"].append((side, q, px))
            st["pos"] += side * chunk
            st["maxq"] = max(st["maxq"], abs(st["pos"]))
            if st["pos"] == 0:
                trades.append({
                    "id": f"{st['open_time'][:10]}_{st['open_time'][12:20]}",
                    "symbol": short, "instr": instr_full(sym),
                    "date_iso": st["open_time"][:10], "date": fr_date(st["open_time"][:10]),
                    "open_time": st["open_time"][12:20], "close_time": t[12:20],
                    "dir": st["dir"], "entry": round(st["entry_px"], 2),
                    "exit": round(px, 2), "maxq": st["maxq"],
                    "pl": round(st["realized"], 2), "fills": st["fills"],
                })
            remaining -= chunk
    return trades


def fmt_pl(v):
    return ("+$" if v >= 0 else "−$") + f"{abs(v):,.0f}"


def fmt_px(p):
    return f"{p:,.2f}"


def build_data(trades, annotations):
    # Equity journalier
    daily = defaultdict(float)
    for t in trades:
        daily[t["date_iso"]] += t["pl"]
    equity = []
    cum = 0
    for d in sorted(daily):
        cum += daily[d]
        equity.append({"date": fr_date(d), "cum": round(cum)})

    # Best trade (None si aucun trade)
    best = max(trades, key=lambda t: t["pl"]) if trades else None

    # Render trades JS
    trade_objs = []
    for t in trades:
        a = annotations.get(t["id"], {})
        pos = t["pl"] >= 0
        notes = a.get("notes") or f"{t['maxq']} contrat(s) max · {t['fills']} fills · {t['open_time']}→{t['close_time']} · P/L réel Sierra."
        setup = a.get("setup") or "—"
        obj = {
            "date": t["date"], "instr": t["instr"], "dir": t["dir"],
            "entry": fmt_px(t["entry"]), "exit": fmt_px(t["exit"]),
            "rr": a.get("rr", "—"), "pl": fmt_pl(t["pl"]),
            "plClass": "pos" if pos else "neg", "plNum": t["pl"],
            "result": "Win" if pos else "Perte",
            "setup": setup, "notes": notes,
        }
        # Kill Zone : dérivée de l'heure ET, sauf override explicite dans l'annotation
        obj["kz"] = a.get("kz") or kill_zone(t["open_time"])
        for k in ("setupType", "mood"):
            if a.get(k): obj[k] = a[k]
        if "processClean" in a: obj["processClean"] = a["processClean"]
        trade_objs.append(obj)

    return equity, best, trade_objs


def js_render(obj, indent=6):
    """Rend un dict JS sur une ligne, ordre stable, échappe les backticks."""
    parts = []
    for k, v in obj.items():
        if isinstance(v, bool):
            parts.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            parts.append(f"{k}: {v}")
        else:
            s = str(v).replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'{k}: "{s}"')
    return "    { " + ", ".join(parts) + " }"


def inject(html, marker, content):
    pat = re.compile(rf"(// <{marker}>\n).*?(\n\s*// </{marker}>)", re.DOTALL)
    if not pat.search(html):
        raise SystemExit(f"Marqueur <{marker}> introuvable dans le HTML.")
    return pat.sub(lambda m: m.group(1) + content + m.group(2), html)


def main():
    if len(sys.argv) > 1:
        export = sys.argv[1]
    else:
        cands = sorted(glob.glob(os.path.join(ROOT, "TradeActivityLogExport_*.txt")) +
                       glob.glob(os.path.join(os.getcwd(), "TradeActivityLogExport_*.txt")))
        if not cands:
            raise SystemExit("Aucun TradeActivityLogExport_*.txt trouvé. Donne le chemin en argument.")
        export = cands[-1]
    print(f"Export : {export}")

    rows, fills = parse_log(export)
    trades = reconstruct(fills)
    print(f"Fills : {len(fills)} · Trades reconstruits : {len(trades)}")
    if not trades:
        raise SystemExit("Aucun trade flat→flat reconstruit : le dashboard n'est pas modifié.")

    annotations = {}
    if os.path.exists(ANNOTATIONS):
        with open(ANNOTATIONS, encoding="utf-8") as f:
            annotations = json.load(f)
        print(f"Annotations chargées : {len(annotations)}")

    equity, best, trade_objs = build_data(trades, annotations)
    total = sum(t["pl"] for t in trades)
    wins = sum(1 for t in trades if t["pl"] > 0)
    losses = sum(1 for t in trades if t["pl"] < 0)
    closed = wins + losses
    wr = round(100 * wins / closed) if closed else 0
    print(f"P/L total : {fmt_pl(total)} · {wins}W / {losses}L · WR {wr}%")

    # Render blocks
    equity_js = ",\n".join(
        f'    {{ date: "{e["date"]}", cum: {e["cum"]} }}' for e in equity)
    trades_js = ",\n".join(js_render(o) for o in trade_objs)

    with open(DASHBOARD, encoding="utf-8") as f:
        html = f.read()

    html = inject(html, "EQUITY", equity_js)
    html = inject(html, "TRADES", trades_js)

    # meta : fills + periodEnd + bestTrade
    html = re.sub(r"(fills:\s*)\d+", rf"\g<1>{len(fills)}", html, count=1)
    last_date = equity[-1]["date"] + " 2026"
    html = re.sub(r'(periodEnd:\s*")[^"]*"', rf'\g<1>{last_date}"', html, count=1)
    best_sub = f'{best["symbol"]} · {best["date"]} · réel Sierra'
    html = re.sub(r'bestTrade:\s*\{[^}]*\}',
                  f'bestTrade: {{ value: "{fmt_pl(best["pl"])}", sub: "{best_sub}" }}',
                  html, count=1)

    with open(DASHBOARD, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Dashboard mis à jour : {DASHBOARD}")


if __name__ == "__main__":
    main()

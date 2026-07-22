#!/usr/bin/env python3
"""
update_dashboard.py — Régénère les données quantitatives du dashboard ICT
à partir d'un export Sierra Chart "TradeActivityLogExport" et des exports
TradingView Paper Trading déposés dans imports/tradingview/.

Usage:
    python3 tools/update_dashboard.py [chemin_export.txt]

Si aucun chemin n'est fourni, prend le TradeActivityLogExport_*.txt le plus
récent dans le dossier courant. Les CSV TradingView (paper-trading-order-
history-all-*.csv) sont TOUJOURS lus depuis imports/tradingview/ en plus de
l'export Sierra — commités dans le repo pour que la régénération reste
reproductible sur les deux machines (Mac + PC).

Ce que fait le script :
  1. Parse le log Sierra (TSV, lignes "Fills") + les order-history TradingView
     (CSV, ordres "Filled" sur NQ/ES/MNQ/MES — autres symboles ignorés avec
     warning). Heures Sierra = UTC ; heures TradingView = heure locale Paris,
     converties en UTC (TV_LOCAL_TO_UTC_H) pour un référentiel unique.
  2. Reconstruit les trades flat→flat par symbole (matching FIFO), toutes
     sources confondues, chronologiquement.
  3. Calcule P/L réel (NQ $20/pt, ES $50/pt, micros 1/10e), equity journalier
  4. Rapproche chaque trade des déclarations de session (annotations.json,
     ±15 min ET) via reconcile_declarations() — setup "Non documenté" si
     aucune déclaration ne matche (voir tools/trade_validation.py)
  5. Injecte equity[] + trades[] dans ICT_Dashboard.html entre marqueurs

Le script ne touche PAS au reste du dashboard (sessions, règles, etc.).
"""
import csv, json, sys, os, glob, re
from collections import deque, defaultdict
from datetime import datetime, timedelta

from trade_validation import (
    validate_trades, ValidationError, classify_kz, RULES, reconcile_declarations,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DASHBOARD = os.path.join(ROOT, "ICT_Dashboard.html")
ANNOTATIONS = os.path.join(HERE, "annotations.json")
TV_IMPORTS = os.path.join(ROOT, "imports", "tradingview")
SIERRA_IMPORTS = os.path.join(ROOT, "imports", "sierra")

# Les exports TradingView sont horodatés en heure LOCALE de la machine (Paris,
# UTC+2 en été) — à convertir vers l'UTC des fills Sierra. Comme UTC_TO_ET_OFFSET
# (trade_validation), à ajuster hors DST.
TV_LOCAL_TO_UTC_H = -2

# Journal remis à zéro le 18 juillet 2026 (tag journal-v1-pre-reset) : les fills
# antérieurs à cette date sont IGNORÉS — un ancien export ne repeuple pas le journal.
JOURNAL_START = "2026-07-18"

# Multiplicateurs par point. Micros (MNQ/MES) = 1/10e des minis. Détection MNQ/MES avant NQ/ES.
MULT = {"MNQ": 2.0, "MES": 5.0, "NQ": 20.0, "ES": 50.0}
MONTHS_FR = {1:"janvier",2:"février",3:"mars",4:"avril",5:"mai",6:"juin",
             7:"juillet",8:"août",9:"septembre",10:"octobre",11:"novembre",12:"décembre"}


def sym_short(s):
    if "MNQ" in s: return "MNQ"
    if "MES" in s: return "MES"
    if "NQ" in s: return "NQ"
    if "ES" in s: return "ES"
    return "?"


def instr_full(s):
    short = sym_short(s)
    if short == "?":
        return s
    m = re.search(re.escape(short) + r"([A-Z]\d{2})", s)
    return f"{short}{m.group(1)}" if m else s


def fr_date(iso):  # "2026-06-08" -> "08 juin"
    y, m, d = iso.split("-")
    return f"{d} {MONTHS_FR[int(m)]}"


# La classification Kill Zone (UTC→ET compris) vit dans trade_validation.py
# (KZ_WINDOWS + classify_kz) — source unique, pas de duplication ici.


def parse_log(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            rows.append(row)
    fills = [x for x in rows if x["ActivityType"] == "Fills"]
    fills.sort(key=lambda x: x["DateTime"])
    return rows, fills


def tv_instr(symbol):
    """'CME_MINI:NQU2026' -> 'NQU26 (TV)' — label contrat + source visible."""
    tail = symbol.split(":")[-1]
    m = re.match(r"([A-Z]+?)([HMUZ])(?:20)?(\d{2})$", tail)
    return (f"{m.group(1)}{m.group(2)}{m.group(3)}" if m else tail) + " (TV)"


def parse_tv_orders(directory):
    """Lit les paper-trading-order-history-all-*.csv de imports/tradingview/.

    Retourne des fills au format Sierra (mêmes clés que parse_log) : les ordres
    'Filled' sur NQ/ES/MNQ/MES uniquement, horodatage converti Paris→UTC au
    format 'YYYY-MM-DD  HH:MM:SS' (double espace, comme Sierra). Dédoublonne
    par Order ID à travers plusieurs exports (le dernier fichier gagne).
    """
    paths = sorted(glob.glob(os.path.join(directory, "*order-history*.csv")))
    by_id, skipped_syms = {}, set()
    for path in paths:
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("Status") != "Filled" or not row.get("Fill price"):
                    continue
                symbol = row["Symbol"].strip()
                short = sym_short(symbol.split(":")[-1])
                if short == "?":
                    skipped_syms.add(symbol)
                    continue
                ts = (row.get("Closing time") or row["Placing time"]).strip()
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") + timedelta(hours=TV_LOCAL_TO_UTC_H)
                by_id[row["Order ID"]] = {
                    "ActivityType": "Fills",
                    "Symbol": symbol,
                    "DateTime": dt.strftime("%Y-%m-%d  %H:%M:%S"),
                    "FilledQuantity": row["Quantity"],
                    "FillPrice": str(float(row["Fill price"]) * 100.0),
                    "BuySell": row["Side"],
                    "_instr": tv_instr(symbol),
                    "_src": "TradingView",
                }
    for s in sorted(skipped_syms):
        print(f"⚠️  TradingView : symbole hors périmètre ignoré — {s}")
    fills = sorted(by_id.values(), key=lambda x: x["DateTime"])
    return fills, len(paths)


def reconstruct(fills):
    """Reconstruit les trades flat→flat avec matching FIFO.

    Retourne (trades, intraday) où `intraday` est la courbe de P/L cumulé RÉALISÉ
    échantillonnée à chaque fill qui réalise du P/L (clôture/réduction). Beaucoup plus
    fidèle que l'equity fin-de-journée pour détecter un franchissement DLL/MLL intraday.
    Limite : l'excursion NON réalisée à l'intérieur d'un trade ouvert reste invisible
    (le log ne contient pas les ticks) — c'est l'étape suivante (MAE via barres).
    """
    trades = []
    intraday = []
    gcum = 0.0
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
        fill_realized = 0.0
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
                fill_realized += pl
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
                    "symbol": short, "instr": fl.get("_instr") or instr_full(sym),
                    "src": fl.get("_src", "Sierra"),
                    "date_iso": st["open_time"][:10], "date": fr_date(st["open_time"][:10]),
                    "open_time": st["open_time"][12:20], "close_time": t[12:20],
                    "dir": st["dir"], "entry": round(st["entry_px"], 2),
                    "exit": round(px, 2), "maxq": st["maxq"],
                    "pl": round(st["realized"], 2), "fills": st["fills"],
                })
            remaining -= chunk
        if fill_realized:
            gcum += fill_realized
            intraday.append({"date_iso": t[:10], "time": t[12:20], "cum": round(gcum)})
    return trades, intraday


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

    # Rapprochement des déclarations de session (skill ict-trading-journal) + overrides
    # a posteriori — source unique du setup, voir tools/annotations.json.
    tags = reconcile_declarations(trades, annotations)

    # Render trades JS
    trade_objs = []
    for t in trades:
        tag = tags.get(t["id"], {})
        pos = t["pl"] >= 0
        notes = tag.get("note") or f"{t['maxq']} contrat(s) max · {t['fills']} fills · {t['open_time']}→{t['close_time']} · P/L réel {t['src']}."
        obj = {
            "date": t["date"], "instr": t["instr"], "dir": t["dir"],
            "entry": fmt_px(t["entry"]), "exit": fmt_px(t["exit"]),
            "rr": "—", "pl": fmt_pl(t["pl"]),
            "plClass": "pos" if pos else "neg", "plNum": t["pl"],
            "result": "Win" if pos else "Perte",
            "setup": tag.get("setup", "Non documenté"), "notes": notes,
            "taggedBy": tag.get("taggedBy", "auto"),
            # Champs exposés (quick win) : exploités par l'audit de discipline et l'onglet Prop Firm.
            "contracts": t["maxq"], "openTime": t["open_time"], "closeTime": t["close_time"],
        }
        # Kill Zone : source unique = classify_kz (KZ_WINDOWS de trade_validation)
        obj["kz"] = classify_kz(t["open_time"])
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
        elif isinstance(v, list):  # violations: [...] (trade_validation)
            parts.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        else:
            s = str(v).replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'{k}: "{s}"')
    return "    { " + ", ".join(parts) + " }"


def compute_daily_stop(html):
    """Stop quotidien dérivé du dashboard : min(40 % × DLL si DLL, MLL ÷ minBufferDays).

    Lit mm (dailyStopPctOfDLL, minBufferDays) et le challenge actif → son entrée
    propFirms (mll, dailyLossLimit). Retourne un montant négatif ;
    fallback RULES["DAILY_STOP"] (avec warning) si le parsing échoue.
    """
    try:
        pct = float(re.search(r"dailyStopPctOfDLL:\s*([\d.]+)", html).group(1))
        buf = int(re.search(r"minBufferDays:\s*(\d+)", html).group(1))
        firm_id = re.search(r'propFirmId:\s*"([^"]+)"[^}]*?status:\s*"active"',
                            html, re.S).group(1)
        entry = re.search(
            rf'id:\s*"{re.escape(firm_id)}"[^}}]*?mll:\s*([\d.]+)[^}}]*?dailyLossLimit:\s*(null|[\d.]+)',
            html, re.S)
        mll, dll = float(entry.group(1)), entry.group(2)
        candidates = [mll / buf]
        if dll != "null":
            candidates.append(pct * float(dll))
        return -min(candidates)
    except (AttributeError, ValueError, ZeroDivisionError):
        print(f"⚠️  Stop quotidien introuvable dans le dashboard — fallback {RULES['DAILY_STOP']:+.0f}$")
        return RULES["DAILY_STOP"]


def inject(html, marker, content):
    pat = re.compile(rf"(// <{marker}>\n).*?(\n\s*// </{marker}>)", re.DOTALL)
    if not pat.search(html):
        raise SystemExit(f"Marqueur <{marker}> introuvable dans le HTML.")
    return pat.sub(lambda m: m.group(1) + content + m.group(2), html)


def main():
    export = None
    if len(sys.argv) > 1:
        export = sys.argv[1]
    else:
        cands = sorted(glob.glob(os.path.join(ROOT, "TradeActivityLogExport_*.txt")) +
                       glob.glob(os.path.join(os.getcwd(), "TradeActivityLogExport_*.txt")))
        if cands:
            export = cands[-1]

    # Sources Sierra : l'export CLI (copié dans imports/sierra/ pour persistance —
    # les exports bruts hors repo sont volatils) + tous les exports déjà persistés.
    # Dédoublonnage par (DateTime, Symbol, BuySell, FillPrice, FilledQuantity).
    if export:
        print(f"Export Sierra : {export}")
        os.makedirs(SIERRA_IMPORTS, exist_ok=True)
        dest = os.path.join(SIERRA_IMPORTS, os.path.basename(export))
        if os.path.abspath(export) != os.path.abspath(dest):
            with open(export, encoding="utf-8") as src, open(dest, "w", encoding="utf-8") as out:
                out.write(src.read())
            print(f"Export persisté : {dest}")

    seen, fills = set(), []
    for path in sorted(glob.glob(os.path.join(SIERRA_IMPORTS, "*.txt"))):
        _, part = parse_log(path)
        for f in part:
            key = (f["DateTime"], f["Symbol"], f["BuySell"], f["FillPrice"], f["FilledQuantity"])
            if key not in seen:
                seen.add(key)
                fills.append(f)

    tv_fills, tv_files = parse_tv_orders(TV_IMPORTS) if os.path.isdir(TV_IMPORTS) else ([], 0)
    if tv_files:
        print(f"TradingView : {tv_files} fichier(s) order-history · {len(tv_fills)} fills retenus")
    if not fills and not tv_fills:
        raise SystemExit("Aucun fill : ni export Sierra (CLI ou imports/sierra/), "
                         "ni CSV TradingView (imports/tradingview/).")

    n_sierra = len(fills)
    fills = sorted(fills + tv_fills, key=lambda x: x["DateTime"])
    skipped = len(fills)
    fills = [f for f in fills if f["DateTime"][:10] >= JOURNAL_START]
    skipped -= len(fills)
    if skipped:
        print(f"Fills antérieurs au {JOURNAL_START} ignorés : {skipped} (reset du journal)")
    trades, intraday = reconstruct(fills)
    print(f"Fills : {len(fills)} (Sierra {n_sierra} + TV {len(tv_fills)}) · "
          f"Trades reconstruits : {len(trades)} · Points intraday : {len(intraday)}")
    if not trades:
        print("Aucun trade flat→flat reconstruit : le dashboard n'est pas modifié.")
        return

    annotations = {}
    if os.path.exists(ANNOTATIONS):
        with open(ANNOTATIONS, encoding="utf-8") as f:
            annotations = json.load(f)
        print(f"Déclarations de session : {len(annotations.get('declarations', []))} · "
              f"Overrides : {len(annotations.get('overrides', {}))}")

    equity, best, trade_objs = build_data(trades, annotations)

    with open(DASHBOARD, encoding="utf-8") as f:
        html = f.read()

    # Validation des règles de discipline (setup = "Non documenté" si aucune
    # déclaration rapprochée, non bloquant). Échec ⇒ sortie AVANT toute écriture
    # : le dashboard n'est pas régénéré (uniquement si un setup est hors vocabulaire).
    daily_stop = compute_daily_stop(html)
    print(f"Stop quotidien dérivé : {daily_stop:+.0f}$")
    try:
        trade_objs = validate_trades(trade_objs, rules=dict(RULES, DAILY_STOP=daily_stop))
    except ValidationError as e:
        sys.exit(f"❌ {e}")

    total = sum(t["pl"] for t in trades)
    wins = sum(1 for t in trades if t["pl"] > 0)
    losses = sum(1 for t in trades if t["pl"] < 0)
    closed = wins + losses
    wr = round(100 * wins / closed) if closed else 0
    print(f"P/L total : {fmt_pl(total)} · {wins}W / {losses}L · WR {wr}%")

    documented = sum(1 for t in trade_objs if t.get("taggedBy") in ("declaration", "override"))
    doc_rate = round(100 * documented / len(trade_objs)) if trade_objs else 0
    print(f"Taux de documentation : {documented}/{len(trade_objs)} trades ({doc_rate}%)")

    # Render blocks
    equity_js = ",\n".join(
        f'    {{ date: "{e["date"]}", cum: {e["cum"]} }}' for e in equity)
    trades_js = ",\n".join(js_render(o) for o in trade_objs)
    intraday_js = ",\n".join(
        f'    {{ date: "{fr_date(p["date_iso"])}", t: "{p["time"]}", cum: {p["cum"]} }}'
        for p in intraday)

    html = inject(html, "EQUITY", equity_js)
    html = inject(html, "TRADES", trades_js)
    html = inject(html, "INTRADAY", intraday_js)

    # meta : fills + periodEnd + bestTrade
    html = re.sub(r"(fills:\s*)\d+", rf"\g<1>{len(fills)}", html, count=1)
    last_date = equity[-1]["date"] + " 2026"
    html = re.sub(r'(periodEnd:\s*")[^"]*"', rf'\g<1>{last_date}"', html, count=1)
    best_sub = f'{best["symbol"]} · {best["date"]} · réel {best["src"]}'
    html = re.sub(r'bestTrade:\s*\{[^}]*\}',
                  f'bestTrade: {{ value: "{fmt_pl(best["pl"])}", sub: "{best_sub}" }}',
                  html, count=1)

    with open(DASHBOARD, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Dashboard mis à jour : {DASHBOARD}")


if __name__ == "__main__":
    main()

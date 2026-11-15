#!/usr/bin/env python3
"""Write the Factory feed JSON that the companion site reads.

Every number comes from the advisor's own functions in ADVISOR_BIN; nothing here recomputes one.
Nothing here writes into the advisor's state: the run verdicts come from its cached violations.json.
"""

import argparse
import html
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

if "ADVISOR_BIN" not in os.environ:
    sys.exit("Set ADVISOR_BIN to the advisor's bin directory.")
ADVISOR_BIN = Path(os.environ["ADVISOR_BIN"])
PICKER_WINDOWS = ("1h", "3h", "6h", "12h", "24h", "7d", "30d")
PLAN_ENUM = ("claude", "codex", "grok", "opencode", "vercel")
WINDOW_ENUM = ("week", "month")
MODE_ENUM = ("percent", "credit", "none")
TONE_ENUM = ("plain", "warm", "hot")
CREDIT_LABELS = ("credit", "month full")
STATES = ("ok", "bad")
BIG_IDS = ("product_tickets", "per_runner_hour", "gbp_per_product", "runs_per_product", "violations", "linked_runs")
MORE_IDS = ("upkeep_tickets", "unattributed_runs", "runs_per_upkeep_ticket", "product_runs", "upkeep_runs", "prs_merged", "reviews")


def advisor():
    if not ADVISOR_BIN.is_dir():
        sys.exit(f"advisor bin not found: {ADVISOR_BIN}. Fix: set ADVISOR_BIN to the advisor's bin folder.")
    if str(ADVISOR_BIN) not in sys.path:
        sys.path.insert(0, str(ADVISOR_BIN))
    import run_verdict
    import score_view
    import usage_bar

    return usage_bar, score_view, run_verdict


def iso_utc(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def review_of(ub, plan, label):
    pill = ub.review_pill(plan, label)
    if not pill:
        return {"show": False, "known": False, "tip": ""}
    title = re.search(r'title="([^"]*)"', pill)
    return {"show": True, "known": " off" not in pill, "tip": html.unescape(title[1]) if title else ""}


def usage_part(ub, g, now):
    plans = ub.load()
    rows = ub.rows(plans) if plans else []
    opencode_credit = ub.credits(plans, now)
    vercel_credit = ub.token_pass_credit()
    groups = ub.runner_groups()
    cards = []
    for plan, label, primary, details in rows:
        credit = opencode_credit if plan == "opencode" else vercel_credit if plan == "vercel" else None
        mode = "credit" if credit else "percent" if primary else "none"
        cards.append({
            "plan": plan,
            "name": label,
            "primaryWindow": ub.PRIMARY.get(plan, "week"),
            "mode": mode,
            "usedPct": number(primary[0]) if primary else None,
            "resetsText": primary[1] if primary else None,
            "paceDelta": number(ub.pace_delta(plan)),
            "tone": "plain" if credit else (ub.tone(ub.pace_delta(plan)).strip() or "plain"),
            "creditUsd": number(credit[0]) if credit else None,
            "creditSubLabel": ("credit" if plan == "vercel" else "month full") if credit else None,
            "creditReadAt": iso_utc(credit[2]) if credit else None,
            "creditAsOf": (ub.as_of(credit, now) or None) if credit else None,
            "windows": [{"label": k, "usedPct": number(v)} for k, v in details],
            "runnersText": ub.runners_text(None if groups is None else groups.get(plan, {})),
            "runnersLive": groups is not None,
            "reviewer": review_of(ub, plan, label),
        })
    burn = {}
    plans_by_window = g.get("windows") if isinstance(g, dict) else None
    for window in PICKER_WINDOWS:
        entry = (plans_by_window or {}).get(window) or {}
        if not entry:
            continue
        raw = entry.get("plans") or {}
        burn[window] = {}
        for card in cards:
            v = raw.get(card["plan"]) or {}
            burn[window][card["plan"]] = {
                "pts": number(v.get("pts")),
                "gbp": number(v.get("gbp")),
                "pricedPts": number(v.get("priced_pts")),
                "todayUsd": number(opencode_credit[1]) if opencode_credit and card["plan"] == "opencode" else None,
            }
    return {"cards": cards, "burn": burn}


def cached_violations(rv):
    if rv.window("24h") is None:
        return None
    try:
        return json.loads((rv.GOAL / "violations.json").read_text())
    except (OSError, ValueError):
        return None


def big_items(sv, x, ref):
    return [{"id": BIG_IDS[i], "label": label, "display": shown, "sub": sub or None, "state": state or None,
             "target": target or None}
            for i, ((label, _tip), (shown, state, sub, target)) in enumerate(zip(sv.PRIMARY_ITEMS, sv.primary_values(x, ref)))]


def more_items(sv, x):
    review = x.get("review") or {}
    out = []
    for (label, _tip), value in list(zip(sv.BAR_ITEMS, sv.bar_values(x)))[1:]:
        if value is None:
            shown = "–"
        elif isinstance(value, float):
            shown = f"{value:g}"
        else:
            shown = sv.n(value)
        sub = None
        if label == "Reviews" and number(review.get("gbp")) is not None:
            sub = f"~£{review['gbp']:.2f}" + (f" · {review['unpriced']} unpriced" if review.get("unpriced") else "")
        out.append({"id": MORE_IDS[len(out)], "label": label, "display": shown, "sub": sub, "state": None, "target": None})
    return out


def kpis_part(sv, rv, g):
    cached = cached_violations(rv)
    verdicts = (cached or {}).get("windows") or {}
    windows = {}
    ref = (g.get("windows") or {}).get("7d")
    for window in PICKER_WINDOWS:
        x = (g.get("windows") or {}).get(window)
        if not isinstance(x, dict) or number(x.get("from")) is None or number(x.get("to")) is None:
            continue
        try:
            if window in verdicts:
                x["viol"] = verdicts[window]
            windows[window] = {
                "from": int(x["from"]),
                "to": int(x["to"]),
                "note": sv.full_note(x) or None,
                "big": big_items(sv, x, ref),
                "more": more_items(sv, x),
            }
        except (KeyError, TypeError, ValueError) as ex:
            print(f"kpis {window}: {type(ex).__name__}: {ex}; left out", file=sys.stderr)
    hourly = [{"t": int(h["t"]), "violations": int(h["v"]), "runs": int(h["r"])} for h in (cached or {}).get("hourly") or []]
    return {"windows": windows, "violations": {"top": max([h["violations"] for h in hourly] + [1]) if hourly else 0, "hourly": hourly}}


def build(ub, sv, rv, g, now):
    try:
        usage = usage_part(ub, g, now)
    except (OSError, KeyError, TypeError, ValueError) as ex:
        print(f"usage: {type(ex).__name__}: {ex}; writing the absent form", file=sys.stderr)
        usage = {"cards": [], "burn": {}}
    try:
        kpis = kpis_part(sv, rv, g)
    except (OSError, KeyError, TypeError, ValueError) as ex:
        print(f"kpis: {type(ex).__name__}: {ex}; writing the absent form", file=sys.stderr)
        kpis = {"windows": {}, "violations": {"top": 0, "hourly": []}}
    return {"generatedAt": iso_utc(now), "usage": usage, "kpis": kpis}


def validate(feed):
    bad = []

    def ok(cond, msg):
        if not cond:
            bad.append(msg)

    def is_num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    def is_iso(v):
        if not isinstance(v, str) or not v.endswith("Z"):
            return False
        try:
            datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return False
        return True

    def item(where, entry, ids):
        ok(set(entry) == {"id", "label", "display", "sub", "state", "target"}, f"{where}: needs id, label, display, sub, state, target")
        ok(entry.get("id") == ids, f"{where}: id must be {ids}, got {entry.get('id')}")
        ok(isinstance(entry.get("label"), str) and entry["label"], f"{where}.label: needs text")
        ok(isinstance(entry.get("display"), str) and entry["display"], f"{where}.display: needs pre-formatted text")
        ok(entry.get("sub") is None or isinstance(entry["sub"], str), f"{where}.sub: needs text or null")
        ok(entry.get("state") is None or entry.get("state") in STATES, f"{where}.state: needs ok, bad or null")
        ok(entry.get("target") is None or isinstance(entry["target"], str), f"{where}.target: needs text or null")

    ok(isinstance(feed, dict), "feed: not an object")
    if bad:
        return bad
    ok(set(feed) == {"generatedAt", "usage", "kpis"}, "feed: needs exactly generatedAt, usage, kpis")
    ok(is_iso(feed.get("generatedAt")), "generatedAt: needs an ISO 8601 UTC string")
    usage, kpis = feed.get("usage"), feed.get("kpis")
    ok(isinstance(usage, dict) and set(usage) == {"cards", "burn"}, "usage: needs exactly cards and burn")
    ok(isinstance(kpis, dict) and set(kpis) == {"windows", "violations"}, "kpis: needs exactly windows and violations")
    if bad:
        return bad
    cards = usage["cards"]
    ok(isinstance(cards, list), "usage.cards: needs an array")
    for i, card in enumerate(cards if isinstance(cards, list) else []):
        where = f"usage.cards[{i}]"
        ok(set(card) == {"plan", "name", "primaryWindow", "mode", "usedPct", "resetsText", "paceDelta", "tone", "creditUsd",
                         "creditSubLabel", "creditReadAt", "creditAsOf", "windows", "runnersText", "runnersLive", "reviewer"},
           f"{where}: field set does not match the contract")
        ok(card.get("plan") in PLAN_ENUM, f"{where}.plan: needs one of {PLAN_ENUM}")
        ok(isinstance(card.get("name"), str) and card["name"], f"{where}.name: needs text")
        ok(card.get("primaryWindow") in WINDOW_ENUM, f"{where}.primaryWindow: needs week or month")
        ok(card.get("mode") in MODE_ENUM, f"{where}.mode: needs percent, credit or none")
        ok(card.get("usedPct") is None or (is_num(card["usedPct"]) and 0 <= card["usedPct"] <= 100), f"{where}.usedPct: needs 0 to 100 or null")
        ok(card.get("resetsText") is None or isinstance(card["resetsText"], str), f"{where}.resetsText: needs text or null")
        ok(card.get("paceDelta") is None or is_num(card["paceDelta"]), f"{where}.paceDelta: needs a signed number or null")
        ok(card.get("tone") in TONE_ENUM, f"{where}.tone: needs plain, warm or hot")
        ok(card.get("creditUsd") is None or is_num(card["creditUsd"]), f"{where}.creditUsd: needs dollars or null")
        ok(card.get("creditSubLabel") is None or card["creditSubLabel"] in CREDIT_LABELS, f"{where}.creditSubLabel: needs credit or month full")
        ok(card.get("creditReadAt") is None or is_iso(card["creditReadAt"]), f"{where}.creditReadAt: needs an ISO 8601 UTC string or null")
        ok(card.get("creditAsOf") is None or (isinstance(card["creditAsOf"], str) and card["creditAsOf"].startswith(" · as of ")),
           f"{where}.creditAsOf: needs ' · as of HH:MM' or null")
        ok(isinstance(card.get("windows"), list), f"{where}.windows: needs an array")
        for j, w in enumerate(card.get("windows") or []):
            ok(set(w) == {"label", "usedPct"}, f"{where}.windows[{j}]: needs exactly label and usedPct")
            ok(isinstance(w.get("label"), str) and w["label"], f"{where}.windows[{j}].label: needs text")
            ok(w.get("usedPct") is None or (is_num(w["usedPct"]) and 0 <= w["usedPct"] <= 100), f"{where}.windows[{j}].usedPct: needs 0 to 100 or null")
        ok(isinstance(card.get("runnersText"), str) and card["runnersText"], f"{where}.runnersText: needs text")
        ok(isinstance(card.get("runnersLive"), bool), f"{where}.runnersLive: needs true or false")
        reviewer = card.get("reviewer")
        ok(isinstance(reviewer, dict) and set(reviewer) == {"show", "known", "tip"}, f"{where}.reviewer: needs exactly show, known, tip")
        if isinstance(reviewer, dict):
            ok(isinstance(reviewer.get("show"), bool), f"{where}.reviewer.show: needs true or false")
            ok(isinstance(reviewer.get("known"), bool), f"{where}.reviewer.known: needs true or false")
            ok(isinstance(reviewer.get("tip"), str), f"{where}.reviewer.tip: needs text")
        if card.get("mode") == "none":
            ok(card.get("usedPct") is None and card.get("resetsText") is None, f"{where}: no reading means null usedPct and resetsText")
        if card.get("mode") == "percent":
            ok(card.get("creditUsd") is None, f"{where}: percent mode has no creditUsd")
        if card.get("mode") == "credit":
            ok(is_num(card.get("creditUsd")) and is_iso(card.get("creditReadAt")), f"{where}: credit mode needs creditUsd and creditReadAt")
        if not (card.get("plan") == "opencode" and card.get("mode") == "credit"):
            ok(card.get("windows") == [], f"{where}.windows: empty outside credit-mode opencode")
    burn = usage["burn"]
    ok(isinstance(burn, dict), "usage.burn: needs an object")
    for window, per_plan in (burn if isinstance(burn, dict) else {}).items():
        ok(window in PICKER_WINDOWS, f"usage.burn.{window}: not a picker window")
        ok(isinstance(per_plan, dict), f"usage.burn.{window}: needs an object of plans")
        for plan, entry in (per_plan if isinstance(per_plan, dict) else {}).items():
            ok(plan in PLAN_ENUM, f"usage.burn.{window}.{plan}: not a plan")
            ok(isinstance(entry, dict) and set(entry) == {"pts", "gbp", "pricedPts", "todayUsd"},
               f"usage.burn.{window}.{plan}: needs exactly pts, gbp, pricedPts, todayUsd")
            for field in ("pts", "gbp", "pricedPts", "todayUsd"):
                ok(entry.get(field) is None or is_num(entry[field]), f"usage.burn.{window}.{plan}.{field}: needs a number or null")
    windows = kpis["windows"]
    ok(isinstance(windows, dict), "kpis.windows: needs an object")
    for window, entry in (windows if isinstance(windows, dict) else {}).items():
        where = f"kpis.windows.{window}"
        ok(window in PICKER_WINDOWS, f"{where}: not a picker window")
        ok(isinstance(entry, dict) and set(entry) == {"from", "to", "note", "big", "more"}, f"{where}: needs exactly from, to, note, big, more")
        ok(is_num(entry.get("from")) and is_num(entry.get("to")), f"{where}: from and to need unix seconds")
        ok(entry.get("note") is None or isinstance(entry["note"], str), f"{where}.note: needs text or null")
        big = entry.get("big")
        ok(isinstance(big, list) and len(big) == len(BIG_IDS), f"{where}.big: needs {len(BIG_IDS)} tiles")
        for j, tile in enumerate(big if isinstance(big, list) else []):
            if isinstance(tile, dict):
                item(f"{where}.big[{j}]", tile, BIG_IDS[j])
            else:
                bad.append(f"{where}.big[{j}]: not an object")
        more = entry.get("more")
        ok(isinstance(more, list) and len(more) == len(MORE_IDS), f"{where}.more: needs {len(MORE_IDS)} items")
        for j, row in enumerate(more if isinstance(more, list) else []):
            if isinstance(row, dict):
                item(f"{where}.more[{j}]", row, MORE_IDS[j])
            else:
                bad.append(f"{where}.more[{j}]: not an object")
    violations = kpis["violations"]
    ok(isinstance(violations, dict) and set(violations) == {"top", "hourly"}, "kpis.violations: needs exactly top and hourly")
    if isinstance(violations, dict):
        ok(is_num(violations.get("top")) and violations["top"] >= 0, "kpis.violations.top: needs a count of zero or more")
        hourly = violations.get("hourly")
        ok(isinstance(hourly, list), "kpis.violations.hourly: needs an array")
        ok(not (hourly and not is_num(violations.get("top"))) , "kpis.violations.top: needs a number")
        for j, hour in enumerate(hourly if isinstance(hourly, list) else []):
            ok(isinstance(hour, dict) and set(hour) == {"t", "violations", "runs"}, f"kpis.violations.hourly[{j}]: needs exactly t, violations, runs")
            for field in ("t", "violations", "runs"):
                ok(hour.get(field) is not None and is_num(hour[field]), f"kpis.violations.hourly[{j}].{field}: needs a number")
            ok(is_num(hour.get("t")) and hour["t"] % 3600 == 0, f"kpis.violations.hourly[{j}].t: needs a UTC hour start")
    return bad


def write_atomic(feed, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=str(out.parent), prefix=out.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            json.dump(feed, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, out)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write the Factory feed JSON the companion site reads.")
    parser.add_argument("--out", required=True, type=Path, help="path of the feed JSON to write")
    args = parser.parse_args(argv)
    ub, sv, rv = advisor()
    now = time.time()
    try:
        g = sv.load()
    except (OSError, ValueError) as ex:
        print(f"metric: {type(ex).__name__}: {ex}; writing the absent form", file=sys.stderr)
        g = None
    feed = build(ub, sv, rv, g if isinstance(g, dict) else {}, now)
    problems = validate(feed)
    if problems:
        for problem in problems:
            print(f"invalid feed: {problem}", file=sys.stderr)
        print(f"refused to write {args.out}: {len(problems)} contract problems", file=sys.stderr)
        return 1
    try:
        write_atomic(feed, args.out)
    except OSError as ex:
        print(f"cannot write {args.out}: {type(ex).__name__}: {ex}. Fix: point --out at a writable path.", file=sys.stderr)
        return 2
    usage, kpis = feed["usage"], feed["kpis"]
    print(f"wrote {args.out}: {len(usage['cards'])} usage cards, {len(usage['burn'])} burn windows, "
          f"{len(kpis['windows'])} kpi windows, {len(kpis['violations']['hourly'])} violation hours")
    return 0


if __name__ == "__main__":
    sys.exit(main())

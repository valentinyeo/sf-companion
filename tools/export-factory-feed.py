#!/usr/bin/env python3
"""Write the Factory feed JSON that the companion site reads.

Usage comes from token-ladder, OpenCode credit history, and Vercel's credits API.
Advisor helpers supply runner, reviewer, and burn readings without writing their state.
Factory KPIs use independent read-only source collectors.
"""

import factory_kpis

import argparse
import html
import json
import math
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

if "ADVISOR_BIN" not in os.environ:
    sys.exit("Set ADVISOR_BIN to the advisor's bin directory.")
ADVISOR_BIN = Path(os.environ["ADVISOR_BIN"])
if not os.environ.get("TOKEN_LADDER_STATUS"):
    sys.exit("Set TOKEN_LADDER_STATUS to token-ladder's status JSON file.")
TOKEN_LADDER_STATUS = Path(os.environ["TOKEN_LADDER_STATUS"])
PICKER_WINDOWS = ("1h", "3h", "6h", "12h", "24h", "7d", "30d")
PLAN_ENUM = ("claude", "codex", "grok", "opencode", "vercel", "deepseek", "openrouter")
PLAN_NAMES = ("Claude", "Codex", "Grok", "OpenCode", "Vercel", "DeepSeek", "OpenRouter")
WINDOW_ENUM = ("week", "month")
MODE_ENUM = ("percent", "credit", "none")
TONE_ENUM = ("plain", "warm", "hot")
CREDIT_LABELS = ("credit", "month full")
STATES = ("ok", "bad")


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
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def review_of(ub, plan, label):
    pill = ub.review_pill(plan, label)
    if not pill:
        return {"show": False, "known": False, "tip": ""}
    title = re.search(r'title="([^"]*)"', pill)
    return {"show": True, "known": " off" not in pill, "tip": html.unescape(title[1]) if title else ""}


def read_status():
    try:
        status = json.loads(TOKEN_LADDER_STATUS.read_text())
        return status if isinstance(status, dict) else {}
    except (OSError, ValueError):
        return {}


def opencode_reading():
    path = os.environ.get("OPENCODE_HISTORY")
    if not path:
        return None
    try:
        last = ""
        with Path(path).open() as history:
            for line in history:
                if line.strip():
                    last = line
        entry = json.loads(last)
        credit, at = number(entry.get("credits_usd")), number(entry.get("at"))
        if credit is not None and at is not None:
            return credit, number(entry.get("today_usd")), at, iso_utc(at)
    except (OSError, ValueError, AttributeError, OverflowError):
        pass
    return None


def vercel_reading(now):
    key = os.environ.get("AI_GATEWAY_API_KEY")
    if not key:
        return None
    request = urllib.request.Request(
        "https://ai-gateway.vercel.sh/v1/credits",
        headers={"Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            token_pass = json.load(response).get("token_pass")
        if not isinstance(token_pass, dict) or token_pass.get("remaining") is None:
            return None
        remaining = token_pass["remaining"]
        if isinstance(remaining, bool):
            return None
        credit = number(float(remaining))
        if credit is None:
            return None
        return credit, None, now, iso_utc(now)
    except (OSError, urllib.error.URLError, ValueError, TypeError, AttributeError):
        return None


def grok_reading(now):
    """Grok Bot plan usage (Grok, Cursor and X merged into one weekly plan), recorded by cursor-usage-read."""
    path = os.environ.get("GROK_STATE")
    if not path:
        return None
    try:
        state = json.loads(Path(path).read_text())
        used = number(state.get("pct"))
        resets = datetime.fromisoformat(state["resets_at"]).timestamp()
        updated = datetime.fromisoformat(state["updated_at"]).timestamp()
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None
    if used is None or not 0 <= used <= 100 or now - updated > 60 * 60:
        return None
    return used, resets


def fetch_json(url, key):
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def deepseek_reading(now):
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        return None
    try:
        infos = fetch_json("https://api.deepseek.com/user/balance", key).get("balance_infos") or []
        usd = next(i for i in infos if isinstance(i, dict) and i.get("currency") == "USD")
        credit = number(float(usd["total_balance"]))
    except (OSError, urllib.error.URLError, ValueError, TypeError, AttributeError, KeyError, StopIteration):
        return None
    return (credit, None, now, iso_utc(now)) if credit is not None else None


def openrouter_reading(now):
    """Credit left summed over every OpenRouter account whose management key is set."""
    keys = [os.environ.get(name) for name in ("OPENROUTER_MANAGEMENT_KEY", "OPENROUTER_MANAGEMENT_KEY_AGENTS")]
    keys = [key for key in keys if key]
    if not keys:
        return None
    left = 0.0
    try:
        for key in keys:
            data = fetch_json("https://openrouter.ai/api/v1/credits", key).get("data") or {}
            total, used = number(data.get("total_credits")), number(data.get("total_usage"))
            if total is None or used is None:
                return None
            left += max(0.0, total - used)
    except (OSError, urllib.error.URLError, ValueError, TypeError, AttributeError):
        return None
    return round(left, 2), None, now, iso_utc(now)


def usage_part(ub, g, now):
    status = read_status()
    sampled_at = number(status.get("ts"))
    fresh = sampled_at is not None and now - sampled_at <= 30 * 60
    opencode_credit = opencode_reading()
    vercel_credit = vercel_reading(now)
    grok = grok_reading(now)
    other_credit = {"deepseek": deepseek_reading(now), "openrouter": openrouter_reading(now)}
    groups = ub.runner_groups()
    cards = []
    for plan, label in zip(PLAN_ENUM, PLAN_NAMES):
        credit = opencode_credit if plan == "opencode" else vercel_credit if plan == "vercel" else other_credit.get(plan)
        reading = status.get(plan) if plan in ("claude", "codex") and fresh else None
        reading = reading if isinstance(reading, dict) and not reading.get("error") else {}
        week = reading.get("week")
        week = week if isinstance(week, dict) else {}
        used, time_gone = number(week.get("used")), number(week.get("time_gone"))
        used = used if used is not None and 0 <= used <= 100 else None
        delta = used - time_gone if used is not None and time_gone is not None else None
        resets = number(week.get("resets_at"))
        if plan == "grok" and grok is not None:
            used, resets = grok
            # Weekly plan: pace is usage minus the share of the week already gone.
            gone = 100 * (now - (resets - 7 * 24 * 3600)) / (7 * 24 * 3600)
            delta = used - gone if 0 <= gone <= 100 else None
        resets_text = None
        if used is not None and resets is not None:
            try:
                resets_text = ub.when(resets)
            except (OSError, ValueError, OverflowError):
                pass
        windows = []
        for key, window_label in (("week", "week"), ("five_hour", "5h")):
            window = reading.get(key)
            value = number(window.get("used")) if isinstance(window, dict) else None
            if value is not None and 0 <= value <= 100:
                windows.append({"label": window_label, "usedPct": value})
        age = max(0, int((now - credit[2]) / 60)) if credit else None
        age_text = f"{age // 60}h ago" if age is not None and age >= 60 else f"{age}m ago"
        cards.append({
            "plan": plan,
            "name": label,
            "primaryWindow": ub.PRIMARY.get(plan, "week"),
            "mode": "credit" if credit else "percent" if used is not None else "none",
            "usedPct": used,
            "resetsText": resets_text,
            "paceDelta": delta,
            "tone": ub.tone(delta).strip() or "plain",
            "creditUsd": credit[0] if credit else None,
            "creditSubLabel": "credit" if credit else None,
            "creditReadAt": credit[3] if credit else None,
            "creditAsOf": f" · as of {age_text}" if age is not None else None,
            "windows": windows,
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


def build(ub, sv, rv, g, now):
    usage = usage_part(ub, g, now)
    kpis = factory_kpis.collect(now)
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

    ok(isinstance(feed, dict), "feed: not an object")
    if bad:
        return bad
    ok(set(feed) == {"generatedAt", "usage", "kpis"}, "feed: needs exactly generatedAt, usage, kpis")
    ok(is_iso(feed.get("generatedAt")), "generatedAt: needs an ISO 8601 UTC string")
    usage, kpis = feed.get("usage"), feed.get("kpis")
    ok(isinstance(usage, dict) and set(usage) == {"cards", "burn"}, "usage: needs exactly cards and burn")
    ok(isinstance(kpis, dict) and set(kpis) == {"tiles", "notes"}, "kpis: needs exactly tiles and notes")
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
        if card.get("plan") not in ("claude", "codex") and not (card.get("plan") == "opencode" and card.get("mode") == "credit"):
            ok(card.get("windows") == [], f"{where}.windows: empty outside Claude, Codex or credit-mode opencode")
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
    tiles = kpis.get("tiles")
    ok(isinstance(tiles, list), "kpis.tiles: needs an array")
    ids = set()
    for tile in tiles if isinstance(tiles, list) else []:
        ok(isinstance(tile, dict), "kpis.tiles: needs objects")
        if not isinstance(tile, dict):
            continue
        ok(set(tile) == {"id", "label", "display", "source", "window", "details", "state"}, "kpis tile: unexpected fields")
        key = tile.get("id")
        ok(key in ("delivered", "verifier", "pace", "loops") and key not in ids, "kpis tile: unknown or duplicate id")
        ids.add(key)
        for field in ("label", "display", "source", "window"):
            ok(isinstance(tile.get(field), str) and bool(tile[field]), f"kpis tile {field}: needs text")
        ok(tile.get("state") is None or tile.get("state") in STATES, "kpis tile state: needs ok, bad or null")
        details = tile.get("details")
        ok(isinstance(details, list) and bool(details) and all(isinstance(d, str) and d for d in details), "kpis tile details: needs explanatory text")
    notes = kpis.get("notes")
    ok(isinstance(notes, list) and all(isinstance(n, str) and n for n in notes), "kpis.notes: needs text array")
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
          f"{len(kpis['tiles'])} KPI tiles, {len(kpis['notes'])} unavailable sources")
    return 0


if __name__ == "__main__":
    sys.exit(main())

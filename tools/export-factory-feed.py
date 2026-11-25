#!/usr/bin/env python3
import factory_kpis
import factory_shipping

import argparse
from collections import Counter
import html
import json
import math
import os
import re
import subprocess
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
TOKEN_LADDER_LIMITS = Path(os.environ.get("TOKEN_LADDER_LIMITS") or TOKEN_LADDER_STATUS.with_name("lane-limits.json"))
TOKEN_LADDER_CREDITS = Path(os.environ.get("TOKEN_LADDER_CREDITS") or TOKEN_LADDER_STATUS.with_name("lane-credits.json"))
TOKEN_LADDER_LAUNCHES = Path(os.environ.get("TOKEN_LADDER_LAUNCHES") or TOKEN_LADDER_STATUS.with_name("launches.jsonl"))
AGY_BIN = Path(os.environ["AGY_BIN"]) if os.environ.get("AGY_BIN") else Path.home() / ".local/bin/agy"
PROC_ROOT = Path("/proc")
OPENCODE_USAGE_API = "https://opencode.ai/zen/go/v1/usage"
OPENCODE_AUTH_FILES = (
    Path.home() / ".pi/agent/auth.json",
    Path.home() / ".local/share/opencode/auth.json",
)
OPENCODE_MONTHLY_SECONDS = 30 * 24 * 3600
OPENCODE_ANCHOR_MAX_AGE = 7 * 86400
AGY_TIMEOUT_SECONDS = 60
AGY_PRINT_TIMEOUT = "45s"
AGY_PERCENT = re.compile(r"^(\d{1,3})%$")
AGY_ROWS = {
    ("Gemini Models", "Weekly Limit Remaining"): ("gemini", "week"),
    ("Gemini Models", "Five Hour Limit Remaining"): ("gemini", "5h"),
    ("Claude and GPT models", "Weekly Limit Remaining"): ("claude-gpt", "week"),
    ("Claude and GPT models", "Five Hour Limit Remaining"): ("claude-gpt", "5h"),
}
AGY_WINDOWS = (
    (("gemini", "5h"), "gemini 5h"),
    (("claude-gpt", "week"), "claude/gpt week"),
    (("claude-gpt", "5h"), "claude/gpt 5h"),
)
PICKER_WINDOWS = ("1h",)
PLAN_ENUM = ("claude", "codex", "opencode", "vercel", "openrouter",
             "antigravity", "commandcode")
PLAN_NAMES = ("Claude", "Codex", "OpenCode", "Vercel", "OpenRouter",
              "Antigravity", "CommandCode")
ROSTER_BIN = Path(os.environ.get("ROSTER_BIN") or Path.home() / ".local/share/house-rules/fleet/roster-live")
ROSTER_TIMEOUT_SECONDS = 10
ROSTER_LINE = re.compile(r"^.+ \((?P<id>[^,]+), (?P<harness>claude|codex), .+\)$")
ROSTER_PLANS = {"claude": "claude", "codex": "codex"}
PLAN_LANES = {"antigravity": ("antigravity", "google"), "commandcode": ("commandcode", "credit:commandcode")}
LANE_TO_PLAN = {"google": "antigravity", "vercel-zai": "vercel"}
COMMANDCODE_MONTHLY_CREDITS = 70.0
WINDOW_ENUM = ("week", "month")
MODE_ENUM = ("percent", "credit", "none")
TONE_ENUM = ("plain", "warm", "hot")
CREDIT_LABELS = ("credit", "month full", "estimate")
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


def iso_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return number(stamp.timestamp())
    except (ValueError, TypeError, OverflowError):
        return None


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


def read_json(path):
    try:
        data = json.loads(Path(path).read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def skip_of(limits, plan, now):
    for key in PLAN_LANES.get(plan, (plan,)):
        raw = limits.get(key)
        reason = None
        if isinstance(raw, dict):
            until = number(raw.get("until"))
            if isinstance(raw.get("reason"), str) and raw["reason"].strip():
                reason = raw["reason"].strip()
        else:
            until = number(raw)
            recorded = limits.get(f"{key}:reason")
            if isinstance(recorded, str) and recorded.strip():
                reason = recorded.strip()
        if until is None or until <= now:
            continue
        if reason is None:
            reason = "manual skip (lane-limits)" if until - now > 24 * 3600 else "limited (lane-limits)"
        return {"reason": reason,
                "untilText": datetime.fromtimestamp(until, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    return None


def antigravity_note(pools):
    pool = pools.get("google") if isinstance(pools, dict) else None
    if not isinstance(pool, dict):
        return None
    if pool.get("used_up") and isinstance(pool.get("used_up_at"), str):
        return f"Quota used up at {pool['used_up_at']} · limit unknown"
    used_pct = number(pool.get("used_pct"))
    if used_pct is not None:
        return f"Quota {used_pct:.0f}% used"
    return f"Quota unknown: {pool.get('source') or 'no reading'}"


def parse_agy_usage(text):
    readings = {}
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) != 4:
            continue
        group, label, percent_text, stamp = (field.strip() for field in fields)
        match = AGY_PERCENT.match(percent_text)
        key = AGY_ROWS.get((group, label))
        reset = iso_timestamp(stamp)
        if match is None or key is None or reset is None:
            continue
        remaining = int(match.group(1))
        if 0 <= remaining <= 100:
            readings[key] = {"usedPct": float(100 - remaining), "resetsAt": reset}
    return readings


def agy_usage():
    if not AGY_BIN.is_file():
        return {}
    try:
        with tempfile.TemporaryDirectory() as cwd:
            done = subprocess.run(
                [str(AGY_BIN), "-p", "/usage", "--print-timeout", AGY_PRINT_TIMEOUT],
                cwd=cwd, capture_output=True, text=True, timeout=AGY_TIMEOUT_SECONDS, check=False,
            )
    except (OSError, subprocess.SubprocessError):
        return {}
    return parse_agy_usage(done.stdout) if done.returncode == 0 else {}


def agy_reading():
    rows = agy_usage()
    primary = rows.get(("gemini", "week"))
    if primary is None:
        return None
    return {"usedPct": primary["usedPct"], "resetsAt": primary["resetsAt"],
            "windows": [{"label": label, "usedPct": rows[key]["usedPct"]}
                        for key, label in AGY_WINDOWS if key in rows]}


def commandcode_reading(credits, now):
    entry = credits.get("commandcode") if isinstance(credits, dict) else None
    if not isinstance(entry, dict):
        return None
    remaining, start, end = number(entry.get("credits")), number(entry.get("period_start")), number(entry.get("period_end"))
    if remaining is None or start is None or end is None or now >= end or end <= start:
        return None
    used = max(0.0, COMMANDCODE_MONTHLY_CREDITS - remaining)
    used_pct = min(100.0, used / COMMANDCODE_MONTHLY_CREDITS * 100)
    gone_pct = max(0.0, min(100.0, (now - start) / (end - start) * 100))
    return {"usedPct": used_pct, "paceDelta": used_pct - gone_pct, "resetsAt": end,
            "note": f"{remaining:g}/{COMMANDCODE_MONTHLY_CREDITS:g} monthly credits left "
                    f"(~${remaining * 100 / COMMANDCODE_MONTHLY_CREDITS:.2f} Flash usage)"}


def fetch_json(url, key):
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {key}", "User-Agent": "sf-companion"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def opencode_api_key():
    env_key = os.environ.get("OPENCODE_API_KEY")
    if isinstance(env_key, str) and env_key.strip():
        return env_key.strip()
    configured = os.environ.get("OPENCODE_AUTH_FILE")
    candidates = (Path(configured),) if configured else OPENCODE_AUTH_FILES
    for path in candidates:
        entry = read_json(path).get("opencode-go")
        key = entry.get("key") if isinstance(entry, dict) else None
        if isinstance(key, str) and key.strip():
            return key.strip()
    return None


def opencode_usage_api(now):
    key = opencode_api_key()
    if not key:
        return None
    try:
        payload = fetch_json(OPENCODE_USAGE_API, key)
    except (OSError, ValueError):
        return None
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return None
    windows = []
    monthly_pct = None
    monthly_resets = None
    for api_field, label in (("monthly", "month"), ("weekly", "week"), ("rolling", "5h")):
        entry = usage.get(api_field)
        if not isinstance(entry, dict):
            continue
        pct = number(entry.get("percent"))
        if pct is None or not 0 <= pct <= 100:
            continue
        windows.append({"label": label, "usedPct": pct})
        if api_field == "monthly":
            monthly_pct = pct
            monthly_resets = iso_timestamp(entry.get("resetsAt"))
    if monthly_pct is None:
        return None
    delta = None
    if monthly_resets is not None:
        gone = 100 * (now - (monthly_resets - OPENCODE_MONTHLY_SECONDS)) / OPENCODE_MONTHLY_SECONDS
        if 0 <= gone <= 100:
            delta = monthly_pct - gone
    return {"usedPct": monthly_pct, "paceDelta": delta, "resetsAt": monthly_resets, "windows": windows}


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


def opencode_anchored_credit(credits, now):
    entry = credits.get("opencode") if isinstance(credits, dict) else None
    if not isinstance(entry, dict):
        return None
    usd = number(entry.get("usd"))
    at = number(entry.get("at"))
    if usd is None or usd < 0 or at is None or not 0 <= now - at <= OPENCODE_ANCHOR_MAX_AGE:
        return None
    return round(usd, 2), None, at, iso_utc(at)


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


def openrouter_reading(now):
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


def proc_state_alive(stat_path):
    try:
        text = stat_path.read_text(errors="replace")
        tail = text.rsplit(")", 1)[1].split()
        return bool(tail) and tail[0] not in ("Z", "X", "x")
    except (OSError, IndexError):
        return False


def proc_pid_alive(pid, proc_root=None):
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    root = PROC_ROOT if proc_root is None else Path(proc_root)
    if root.is_dir():
        return proc_state_alive(root / str(pid) / "stat")
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def is_plan_pick_run(argv):
    if not argv or "--run" not in argv:
        return False
    exe = os.path.basename(argv[0])
    if exe == "plan-pick":
        return True
    return exe.startswith("python") and len(argv) > 1 and os.path.basename(argv[1]) == "plan-pick"


def live_plan_pick_cwds(proc_root=None):
    root = PROC_ROOT if proc_root is None else Path(proc_root)
    if not root.is_dir():
        return None
    cwds = []
    try:
        entries = list(root.iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        argv = [part.decode("utf-8", errors="replace") for part in raw.split(b"\x00") if part]
        if not is_plan_pick_run(argv):
            continue
        if not proc_state_alive(entry / "stat"):
            continue
        try:
            cwd = os.path.realpath(os.readlink(entry / "cwd"))
        except OSError:
            continue
        cwds.append(cwd)
    return cwds


def worker_model_label(ub, model):
    return ub.model_name(model) if isinstance(model, str) and model.strip() else "?"


def plan_pick_runner_groups(ub, launches_path=None, proc_root=None):
    path = TOKEN_LADDER_LAUNCHES if launches_path is None else Path(launches_path)
    if not path.is_file():
        return None
    starts = {}
    finished = set()
    legacy_by_cwd = {}
    try:
        with path.open(errors="replace") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                lid = row.get("launch_id")
                if row.get("event") == "finish":
                    if lid:
                        finished.add(lid)
                elif lid:
                    starts[lid] = row
                elif isinstance(row.get("lane"), str) and row["lane"] != "server-hold":
                    cwd = row.get("cwd")
                    if isinstance(cwd, str) and cwd:
                        legacy_by_cwd[os.path.realpath(cwd)] = row
    except OSError:
        return None
    unfinished = [
        row for lid, row in starts.items()
        if lid not in finished and isinstance(row.get("lane"), str) and row["lane"] != "server-hold"
    ]
    unfinished.sort(key=lambda row: number(row.get("at")) or 0, reverse=True)
    live_cwds = live_plan_pick_cwds(proc_root)
    if live_cwds is None and any(not isinstance(row.get("pid"), int) for row in unfinished):
        return None
    cwd_slots = Counter(live_cwds or ())
    active = []
    for row in unfinished:
        pid = row.get("pid")
        if isinstance(pid, int) and not isinstance(pid, bool):
            if proc_pid_alive(pid, proc_root):
                active.append(row)
            continue
        cwd = row.get("cwd")
        if isinstance(cwd, str) and cwd:
            norm = os.path.realpath(cwd)
            if cwd_slots[norm] > 0:
                cwd_slots[norm] -= 1
                active.append(row)
    for norm, remaining in cwd_slots.items():
        if remaining > 0 and norm in legacy_by_cwd:
            active.extend([legacy_by_cwd[norm]] * remaining)
    out = {}
    for row in active:
        plan = LANE_TO_PLAN.get(row["lane"], row["lane"])
        if plan not in PLAN_ENUM:
            continue
        model_label = worker_model_label(ub, row.get("model"))
        raw_effort = row.get("effort")
        effort = raw_effort if isinstance(raw_effort, str) and raw_effort not in ("", "model-default") else ""
        key = (model_label, effort)
        out.setdefault(plan, {})[key] = out.get(plan, {}).get(key, 0) + 1
    return out


def merge_runner_groups(advisor_groups, plan_pick_groups):
    if advisor_groups is None and plan_pick_groups is None:
        return None
    merged = {}
    for source in (advisor_groups, plan_pick_groups):
        if not isinstance(source, dict):
            continue
        for plan, counts in source.items():
            if not isinstance(counts, dict):
                continue
            bucket = merged.setdefault(plan, {})
            for key, count in counts.items():
                bucket[key] = bucket.get(key, 0) + count
    return merged


def roster_chats():
    try:
        done = subprocess.run([str(ROSTER_BIN)], capture_output=True, text=True,
                              timeout=ROSTER_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    live = {}
    for line in done.stdout.splitlines():
        match = ROSTER_LINE.match(line.strip())
        if match is None or match.group("id") in live:
            continue
        live[match.group("id")] = ROSTER_PLANS[match.group("harness")]
    return Counter(live.values())


def load_text(chats, runners):
    parts = []
    if chats:
        parts.append(f"{chats} chat" + ("s" if chats > 1 else ""))
    if runners:
        parts.append(f"{runners} runner" + ("s" if runners > 1 else ""))
    if parts:
        return " · ".join(parts)
    return "idle" if chats is not None and runners is not None else "–"


def usage_part(ub, g, now):
    status = read_status()
    sampled_at = number(status.get("ts"))
    fresh = sampled_at is not None and now - sampled_at <= 30 * 60
    opencode_api = opencode_usage_api(now)
    opencode_credit = opencode_reading()
    antigravity = agy_reading()
    vercel_credit = vercel_reading(now)
    other_credit = {"openrouter": openrouter_reading(now)}
    groups = merge_runner_groups(ub.runner_groups(), plan_pick_runner_groups(ub))
    chats = roster_chats()
    limits = read_json(TOKEN_LADDER_LIMITS)
    credits = read_json(TOKEN_LADDER_CREDITS)
    opencode_estimate = opencode_anchored_credit(credits, now)
    pools = status.get("pools") if isinstance(status.get("pools"), dict) else {}
    cards = []
    for plan, label in zip(PLAN_ENUM, PLAN_NAMES):
        credit = vercel_credit if plan == "vercel" else other_credit.get(plan)
        credit_sub_label = "credit" if credit else None
        reading = status.get(plan) if plan in ("claude", "codex") and fresh else None
        reading = reading if isinstance(reading, dict) and not reading.get("error") else {}
        week = reading.get("week")
        week = week if isinstance(week, dict) else {}
        used, time_gone = number(week.get("used")), number(week.get("time_gone"))
        used = used if used is not None and 0 <= used <= 100 else None
        delta = used - time_gone if used is not None and time_gone is not None else None
        resets = number(week.get("resets_at"))
        resets_text = None
        note = antigravity_note(pools) if plan == "antigravity" else None
        windows = []
        if plan == "opencode":
            if opencode_api is not None:
                used = opencode_api["usedPct"]
                delta = opencode_api["paceDelta"]
                resets = opencode_api["resetsAt"]
                windows = opencode_api["windows"]
                if used >= 100 and opencode_estimate is not None:
                    note = f"Prepaid credit estimate: ${opencode_estimate[0]:.2f} left"
                elif used >= 100 and opencode_credit is not None:
                    note = f"Prepaid credit: ${opencode_credit[0]:.2f} left"
            elif opencode_credit is not None:
                credit = opencode_credit
                credit_sub_label = "credit"
            elif opencode_estimate is not None:
                credit = opencode_estimate
                credit_sub_label = "estimate"
                note = "Anchored credit estimate (lane-credits.json)"
        if plan == "antigravity" and antigravity is not None:
            used = antigravity["usedPct"]
            resets = antigravity["resetsAt"]
            windows = antigravity["windows"]
            note = None
        if plan == "commandcode":
            commandcode = commandcode_reading(credits, now)
            if commandcode is not None:
                used, delta = commandcode["usedPct"], commandcode["paceDelta"]
                resets = commandcode["resetsAt"]
                note = commandcode["note"]
        skip = skip_of(limits, plan, now)
        if used is not None and resets is not None:
            try:
                resets_text = ub.when(resets)
            except (OSError, ValueError, OverflowError):
                pass
        if plan in ("claude", "codex"):
            for key, window_label in (("week", "week"), ("five_hour", "5h")):
                window = reading.get(key)
                value = number(window.get("used")) if isinstance(window, dict) else None
                if value is not None and 0 <= value <= 100:
                    windows.append({"label": window_label, "usedPct": value})
        age = max(0, int((now - credit[2]) / 60)) if credit else None
        age_text = f"{age // 60}h ago" if age is not None and age >= 60 else f"{age}m ago"
        runners = sum(groups.get(plan, {}).values()) if groups is not None else None
        plan_chats = 0
        if plan in ROSTER_PLANS:
            plan_chats = chats.get(plan, 0) if chats is not None else None
        cards.append(((plan_chats or 0) + (runners or 0), {
            "plan": plan,
            "name": label,
            "primaryWindow": "month" if plan == "commandcode" else ub.PRIMARY.get(plan, "week"),
            "mode": "credit" if credit else "percent" if used is not None else "none",
            "usedPct": used,
            "resetsText": resets_text,
            "paceDelta": delta,
            "tone": ub.tone(delta).strip() or "plain",
            "creditUsd": credit[0] if credit else None,
            "creditSubLabel": credit_sub_label,
            "creditReadAt": credit[3] if credit else None,
            "creditAsOf": f" · as of {age_text}" if age is not None else None,
            "windows": windows,
            "runnersText": ub.runners_text(None if groups is None else groups.get(plan, {})),
            "runnersLive": groups is not None,
            "reviewer": review_of(ub, plan, label),
            "note": note,
            "skip": skip,
            "loadText": load_text(plan_chats, runners),
        }))
    cards = [card for _, card in sorted(cards, key=lambda entry: -entry[0])]
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
    try:
        import daily_burn
        burn_readings = daily_burn.readings()
    except (ImportError, OSError, ValueError, KeyError, TypeError):
        burn_readings = {}
    kpis = factory_kpis.collect(now, burn_readings=burn_readings, metric=g)
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
    ok(isinstance(kpis, dict) and set(kpis) == {"tiles", "notes", "shipping"}, "kpis: needs exactly tiles, notes and shipping")
    if bad:
        return bad
    cards = usage["cards"]
    ok(isinstance(cards, list), "usage.cards: needs an array")
    for i, card in enumerate(cards if isinstance(cards, list) else []):
        where = f"usage.cards[{i}]"
        ok(set(card) == {"plan", "name", "primaryWindow", "mode", "usedPct", "resetsText", "paceDelta", "tone", "creditUsd",
                         "creditSubLabel", "creditReadAt", "creditAsOf", "windows", "runnersText", "runnersLive", "reviewer",
                         "note", "skip", "loadText"},
           f"{where}: field set does not match the contract")
        ok(card.get("plan") in PLAN_ENUM, f"{where}.plan: needs one of {PLAN_ENUM}")
        ok(isinstance(card.get("loadText"), str) and card["loadText"], f"{where}.loadText: needs text")
        ok(isinstance(card.get("name"), str) and card["name"], f"{where}.name: needs text")
        ok(card.get("primaryWindow") in WINDOW_ENUM, f"{where}.primaryWindow: needs week or month")
        ok(card.get("mode") in MODE_ENUM, f"{where}.mode: needs percent, credit or none")
        ok(card.get("usedPct") is None or (is_num(card["usedPct"]) and 0 <= card["usedPct"] <= 100), f"{where}.usedPct: needs 0 to 100 or null")
        ok(card.get("resetsText") is None or isinstance(card["resetsText"], str), f"{where}.resetsText: needs text or null")
        ok(card.get("paceDelta") is None or is_num(card["paceDelta"]), f"{where}.paceDelta: needs a signed number or null")
        ok(card.get("tone") in TONE_ENUM, f"{where}.tone: needs plain, warm or hot")
        ok(card.get("creditUsd") is None or is_num(card["creditUsd"]), f"{where}.creditUsd: needs dollars or null")
        ok(card.get("creditSubLabel") is None or card["creditSubLabel"] in CREDIT_LABELS,
           f"{where}.creditSubLabel: needs credit, month full or estimate")
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
        ok(card.get("note") is None or (isinstance(card["note"], str) and card["note"]), f"{where}.note: needs text or null")
        skip = card.get("skip")
        ok(skip is None or (isinstance(skip, dict) and set(skip) == {"reason", "untilText"}),
           f"{where}.skip: needs null or exactly reason and untilText")
        if isinstance(skip, dict):
            ok(isinstance(skip.get("reason"), str) and skip["reason"], f"{where}.skip.reason: needs text")
            ok(isinstance(skip.get("untilText"), str) and skip["untilText"], f"{where}.skip.untilText: needs text")
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
        if card.get("plan") not in ("claude", "codex", "opencode", "antigravity"):
            ok(card.get("windows") == [], f"{where}.windows: empty outside Claude, Codex, OpenCode or Antigravity")
    burn = usage["burn"]
    ok(isinstance(burn, dict), "usage.burn: needs an object")
    for window, per_plan in (burn if isinstance(burn, dict) else {}).items():
        ok(window in PICKER_WINDOWS, f"usage.burn.{window}: not a supported burn window")
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
        ok(key in ("delivered", "verifier", "pace", "loops", "merges", "identity", "ci") and key not in ids, "kpis tile: unknown or duplicate id")
        ids.add(key)
        for field in ("label", "display", "source", "window"):
            ok(isinstance(tile.get(field), str) and bool(tile[field]), f"kpis tile {field}: needs text")
        ok(tile.get("state") is None or tile.get("state") in STATES, "kpis tile state: needs ok, bad or null")
        details = tile.get("details")
        ok(isinstance(details, list) and bool(details) and all(isinstance(d, str) and d for d in details), "kpis tile details: needs explanatory text")
    notes = kpis.get("notes")
    ok(isinstance(notes, list) and all(isinstance(n, str) and n for n in notes), "kpis.notes: needs text array")
    bad.extend(factory_shipping.validate(kpis["shipping"]))
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
    try:
        feed = build(ub, sv, rv, g if isinstance(g, dict) else {}, now)
    except factory_kpis.BudgetRefused:
        print(f"GitHub call budget refused the read. Kept the previous feed at {args.out} unchanged; the next run retries. "
              f"Fix: let the rolling hour clear, or cut calls with {factory_kpis.CACHE_ENV} kept on disk.", file=sys.stderr)
        return 3
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

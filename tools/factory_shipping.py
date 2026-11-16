import math
from datetime import datetime, timedelta, timezone


PLANS = ("claude", "codex", "grok", "opencode")
DAY = 86400
NO_READINGS = "no quota readings on any of the 30 UTC dates."
RETIRED_SAMPLER = "pacing sampler retired on 2026-11-15."
ABSENCE = {"grok": RETIRED_SAMPLER, "opencode": RETIRED_SAMPLER}


def minutes_utc(at):
    return datetime.fromtimestamp(at, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def plan_omissions(days):
    measured = {item["plan"] for day in days for item in day["burn"] if item["reading"]["kind"] == "measured"}
    return [{"plan": plan, "reason": ABSENCE.get(plan, NO_READINGS)} for plan in PLANS if plan not in measured]


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def cell(value, unit, source, window, reason):
    common = {"source": source, "window": window}
    if value is None:
        return dict(common, kind="missing", reason=reason)
    display = f"£{value:.2f}" if unit == "gbp" else f"{value:g}" + (" pts" if unit == "points" else " PRs")
    return dict(common, kind="measured", value=round(value, 4), display=display, barPct=0)


def shipping(now, prs, pr_source, readings, metric, max_gap=6 * 3600):
    today = datetime.fromtimestamp(now, timezone.utc).date()
    first = today - timedelta(days=29)
    counts = {}
    if prs is not None:
        seen = set()
        for pr in prs:
            key = (pr["repo"], pr["number"])
            if key in seen or not pr.get("mergedAt"):
                continue
            seen.add(key)
            at = datetime.fromisoformat(pr["mergedAt"].replace("Z", "+00:00")).timestamp()
            if at <= now:
                date = datetime.fromtimestamp(at, timezone.utc).date().isoformat()
                counts[date] = counts.get(date, 0) + 1
    first_at = datetime.combine(first, datetime.min.time(), timezone.utc).timestamp()
    bounded = {plan: sorted((at, used) for at, used in readings.get(plan, [])
                            if finite(at) and finite(used) and first_at - max_gap <= at <= now and used <= 100)
               for plan in PLANS}
    metric_days = metric.get("days")
    metric_days = metric_days if isinstance(metric_days, dict) else {}
    days = []
    for offset in range(30):
        date = first + timedelta(days=offset)
        start = datetime.combine(date, datetime.min.time(), timezone.utc).timestamp()
        end = min(start + DAY, now)
        key = date.isoformat()
        window = f"{key} 00:00 UTC to " + (datetime.fromtimestamp(end, timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
        merged = cell(counts.get(key, 0) if prs is not None else None, "prs", "GitHub search · fleet mergedAt", window,
                      "GitHub fleet PR collection failed; no complete merge count.")
        burn = []
        for plan in PLANS:
            rows = bounded[plan]
            pairs = [(a, b) for a, b in zip(rows, rows[1:])
                     if start <= b[0] < start + DAY and b[0] <= end and 0 < b[0] - a[0] <= max_gap]
            rises = sum(max(0, b[1] - a[1]) for a, b in pairs)
            source = f"Advisor · {plan} weekly quota rises"
            burn.append({"plan": plan, "reading": cell(rises if pairs else None, "points", source, window,
                         "No consecutive quota readings within 6h on this UTC date.")})
        at = metric.get("at")
        cost_day = metric_days.get(key)
        cost = cost_day.get("spent") if isinstance(cost_day, dict) else None
        cover = metric.get("cover")
        complete = finite(at) and start + DAY <= at <= now and finite(cover) and cover <= start and finite(cost)
        as_of = minutes_utc(at) if finite(at) and at <= now else "unknown"
        source = f"Advisor attributed £ · {as_of}"
        cost_cell = cell(cost if complete else None, "gbp", source, window,
                         "No closed-day attributed cost reading; missing or still incomplete in advisor metric.")
        denominator = merged.get("value")
        per_pr = cost / denominator if complete and denominator is not None and denominator > 0 else None
        ratio = cell(per_pr, "gbp", "Advisor attributed £ ÷ GitHub merges", window,
                     "No merged PRs on this date; division has no denominator." if denominator == 0 else
                     "Daily attributed cost or complete merge count unavailable.")
        days.append({"date": key, "merges": merged, "burn": burn, "cost": cost_cell, "perPr": ratio})
    series = [[d[key] for d in days] for key in ("merges", "cost", "perPr")] + [[d["burn"][i]["reading"] for d in days] for i in range(len(PLANS))]
    for cells in series:
        maximum = max((c["value"] for c in cells if c["kind"] == "measured"), default=0)
        for c in cells:
            if c["kind"] == "measured":
                c["barPct"] = round(100 * c["value"] / maximum, 2) if maximum else 0
    return {"days": days, "omissions": plan_omissions(days), "notes": [
        pr_source,
        "30 UTC dates, newest first; today to export time. Bars start at zero; each column has its own maximum. Usage window buttons do not change this chart.",
        "Quota points are observed rises, not tokens. Plans have different quotas; do not add their points. Resets add no burn. Gaps over 6h are excluded; measured values may undercount daily use.",
        "Vercel, DeepSeek and OpenRouter daily history is unavailable in these sources.",
        *(["OpenCode points cover its weekly subscription, not credit spend."] if any(d["burn"][3]["reading"]["kind"] == "measured" for d in days) else []),
        "£ and £/PR cover only the advisor's attributed priced subset, not the total bill. £/PR compares same-day fleet output, not the cost of an individual PR. Open days have no final cost.",
    ]}


def validate(chart):
    errors = []
    if not isinstance(chart, dict) or set(chart) != {"days", "notes", "omissions"}:
        return ["shipping: needs days, notes and omissions"]
    days = chart["days"]
    if not isinstance(days, list) or len(days) != 30:
        return ["shipping.days: needs 30 UTC dates"]
    previous = None
    for day in days:
        if not isinstance(day, dict) or set(day) != {"date", "merges", "burn", "cost", "perPr"}:
            errors.append("shipping day: unexpected fields")
            continue
        try:
            date = datetime.strptime(day["date"], "%Y-%m-%d").date()
            if date.isoformat() != day["date"] or (previous is not None and date != previous + timedelta(days=1)):
                errors.append("shipping dates: needs consecutive ordered UTC dates")
            previous = date
        except (ValueError, TypeError):
            errors.append("shipping date: needs YYYY-MM-DD")
        burn = day["burn"]
        if not isinstance(burn, list) or [b.get("plan") for b in burn if isinstance(b, dict)] != list(PLANS):
            errors.append("shipping burn: needs Claude, Codex, Grok and OpenCode in order")
            continue
        cells = [day["merges"], day["cost"], day["perPr"]] + [b.get("reading") for b in burn]
        for c in cells:
            if not isinstance(c, dict):
                errors.append("shipping cell: needs an object")
                continue
            if not all(isinstance(c.get(k), str) and c[k] for k in ("source", "window")):
                errors.append("shipping cell: needs source and window")
            if c.get("kind") == "measured":
                if set(c) != {"kind", "value", "display", "barPct", "source", "window"} or not finite(c.get("value")) or not finite(c.get("barPct")) or c["barPct"] > 100 or not isinstance(c.get("display"), str) or not c["display"]:
                    errors.append("shipping measured cell: needs finite nonnegative value, display and 0–100 barPct")
            elif c.get("kind") != "missing" or set(c) != {"kind", "reason", "source", "window"} or not isinstance(c.get("reason"), str) or not c["reason"]:
                errors.append("shipping missing cell: needs a reason, never a zero")
    if not isinstance(chart["notes"], list) or not chart["notes"] or not all(isinstance(n, str) and n for n in chart["notes"]):
        errors.append("shipping notes: needs source limitations")
    measured = set()
    for day in days:
        burn = day.get("burn") if isinstance(day, dict) else None
        if isinstance(burn, list):
            measured.update(item.get("plan") for item in burn if isinstance(item, dict) and isinstance(item.get("reading"), dict) and item["reading"].get("kind") == "measured")
    expected = [plan for plan in PLANS if plan not in measured]
    omissions = chart["omissions"]
    seen = []
    if not isinstance(omissions, list):
        errors.append("shipping omissions: needs one reason per plan with no readings")
    else:
        for item in omissions:
            if not isinstance(item, dict) or set(item) != {"plan", "reason"} or item.get("plan") not in PLANS or not isinstance(item.get("reason"), str) or not item["reason"]:
                errors.append("shipping omission: needs a plan and a reason")
            else:
                seen.append(item["plan"])
        if seen != expected:
            errors.append("shipping omissions: needs one reason per plan with no readings")
    return errors

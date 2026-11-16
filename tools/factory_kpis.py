import json
import math
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


BOARDS = (15, 2060, 11514)
DAY = 86400
LOOP_KINDS = {"chief", "lead", "solo-dev"}
REPOS = (
    "hypertask-ai/hypertask", "valentinyeo/house-rules", "valentinyeo/poteto-2-advisor",
    "valentinyeo/multiprompt", "valentinyeo/multiprompt-android", "valentinyeo/postbox",
    "valentinyeo/pecunia", "valentinyeo/triage", "valentinyeo/chromescribe",
    "valentinyeo/calorie-mcp-proto", "valentinyeo/valentinyeocom", "valentinyeo/yeoux-site",
    "valentinyeo/endless-testing", "valentinyeo/claude-cro", "valentinyeo/screencast2-go",
    "valentinyeo/token-ladder", "valentinyeo/upwork-auto-applier", "valentinyeo/sf-companion",
)
PR_QUERY = """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: 100, after: $after, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number createdAt updatedAt mergedAt
        comments(first: 100) {
          pageInfo { hasNextPage }
          nodes { body createdAt }
        }
      }
    }
  }
}
"""


class SourceUnavailable(ValueError):
    pass


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def command_json(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=90, check=True)
    return json.loads(result.stdout)


def read_tickets(now, run=command_json):
    rows = []
    for board in BOARDS:
        offset = 0
        while True:
            try:
                data = run(["hypertask", "--json", "task", "list", "--project", str(board),
                            "--filter", "updated_since=" + datetime.fromtimestamp(now - 7 * DAY, timezone.utc).isoformat(),
                            "--fields", "id,boardId,sectionIsDone,sectionChangedAt,assignees",
                            "--sort-by", "createdAt", "--sort-order", "asc",
                            "--limit", "100", "--offset", str(offset)])
            except (OSError, subprocess.SubprocessError) as error:
                raise SourceUnavailable(f"Hypertask board {board} could not be read for rolling 24h and 7d") from error
            if data.get("success") is not True or not isinstance(data.get("tasks"), list):
                raise ValueError("ticket read failed")
            page = data["tasks"]
            rows.extend(dict(t, boardId=board) for t in page)
            offset += len(page)
            if offset >= data["total"]:
                break
            if not page:
                raise ValueError("incomplete ticket pagination")
    return list({row["id"]: row for row in rows}.values())


def read_prs(now, run=command_json):
    rows = []
    for repo in [item.strip() for item in os.environ.get("FACTORY_REPOS", ",".join(REPOS)).split(",") if item.strip()]:
        owner, name = repo.strip().split("/")
        after = None
        while True:
            args = ["gh", "api", "graphql", "-f", "query=" + PR_QUERY,
                    "-f", "owner=" + owner, "-f", "name=" + name]
            if after:
                args += ["-f", "after=" + after]
            data = run(args)
            if data.get("errors"):
                raise ValueError("PR query failed")
            page = data["data"]["repository"]["pullRequests"]
            recent = [p for p in page["nodes"] if timestamp(p["updatedAt"]) >= now - 7 * DAY]
            for pr in recent:
                comments = pr["comments"]["nodes"]
                if pr["comments"]["pageInfo"]["hasNextPage"]:
                    pages = run(["gh", "api", "--paginate", "--slurp",
                                 f"repos/{repo}/issues/{pr['number']}/comments?per_page=100"])
                    comments = [{"body": c["body"], "createdAt": c["created_at"]} for p in pages for c in p]
                rows.append(dict(pr, comments=comments))
            if len(recent) < len(page["nodes"]) or not page["pageInfo"]["hasNextPage"]:
                break
            after = page["pageInfo"]["endCursor"]
    return rows


def tile(key, label, display, source, window, details, state=None):
    return {"id": key, "label": label, "display": display, "source": source,
            "window": window, "details": details, "state": state}


def delivered(tickets, now):
    done = [t for t in tickets if t.get("sectionIsDone") is True]
    missing = sum(timestamp(t.get("sectionChangedAt")) is None for t in done)
    if missing:
        raise SourceUnavailable(f"Done-move dates unavailable for {missing} Done tickets; update dates are not delivery dates")
    details = []
    totals = []
    for days in (1, 7):
        counts = {}
        total = 0
        for task in done:
            if not now - days * DAY <= timestamp(task["sectionChangedAt"]) <= now:
                continue
            total += 1
            board = task["boardId"]
            names = sorted({a["displayName"] for a in task.get("assignees", [])}) or ["Unassigned"]
            for name in names:
                key = f"Board {board} / {name}"
                counts[key] = counts.get(key, 0) + 1
        totals.append(total)
        details.append(f"Last {days}d: {total} ticket{'' if total == 1 else 's'}" + ("; no tickets entered Done" if total == 0 else ""))
        for board in BOARDS:
            count = sum(1 for t in done if t["boardId"] == board and now - days * DAY <= timestamp(t["sectionChangedAt"]) <= now)
            details.append(f"Board {board}, {days}d: {count}")
        details.extend(f"{key}, {days}d: {value}" for key, value in sorted(counts.items()))
    details.append("Each ticket counts once overall; shared assignees each receive credit. Assignees are current, not historical.")
    return tile("delivered", "Tickets delivered", f"{totals[0]} / day · {totals[1]} / week",
                "Hypertask boards 15, 2060, 11514 · sectionChangedAt", "Rolling 24h and 7d", details)


VERDICT = re.compile(r"^\s*(?:#{1,6}\s+|[-*]\s+)?(?:\*\*)?(?:(?:pstack[- ]verifier|verifier|verdict)\s*:\s*(?:\*\*)?)?(PASS\+NOTES|PASS|FAIL)(?=$|[\s*.:,])", re.I)


def verdict(body):
    fenced = False
    for line in body.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        if not fenced:
            match = VERDICT.match(line)
            if match:
                return match[1].upper()
    return None


def verifier(prs, now):
    outcomes = []
    merged = []
    for pr in prs:
        comments = sorted(pr["comments"], key=lambda c: c["createdAt"])
        first = next(((timestamp(c["createdAt"]), verdict(c["body"])) for c in comments
                      if verdict(c["body"]) and timestamp(c["createdAt"]) is not None and timestamp(c["createdAt"]) <= now), None)
        if first and now - 7 * DAY <= first[0]:
            outcomes.append(first[1])
        merged_at = timestamp(pr.get("mergedAt"))
        if merged_at is not None and now - 7 * DAY <= merged_at <= now:
            merged.append(any(verdict(c["body"]) and timestamp(c["createdAt"]) is not None
                              and timestamp(c["createdAt"]) <= merged_at for c in comments))
    passed = sum(v != "FAIL" for v in outcomes)
    absent = merged.count(False)
    display = f"{passed / len(outcomes):.0%}" if outcomes else "–"
    details = [f"{passed}/{len(outcomes)} PRs passed their first verdict" if outcomes else "No PRs received a first verdict in this window.",
               f"Merged without verdict: {absent / len(merged):.0%} ({absent}/{len(merged)})" if merged else "Merged without verdict: –; no merged PRs in this window.",
               "Repositories: " + ", ".join(os.environ.get("FACTORY_REPOS", ",".join(REPOS)).split(",")),
               "First PASS or PASS+NOTES counts as pass. Later verdicts never replace the first. Merge coverage uses comments present at merge time."]
    return tile("verifier", "Verifier first-pass rate", display, "GitHub fleet PR comments · PASS / PASS+NOTES / FAIL",
                "First verdicts and merges in rolling 7d", details)


def plan_pace(pools, now):
    details = []
    ratios = []
    for plan, pool in sorted(pools.items()):
        used = pool.get("used_pct")
        ratio = pool.get("pace_ratio")
        if not isinstance(used, (int, float)) or isinstance(used, bool) or not 0 <= used <= 100:
            details.append(f"{plan}: no usage reading")
            continue
        if not isinstance(ratio, (int, float)) or isinstance(ratio, bool) or not math.isfinite(ratio) or ratio < 0:
            details.append(f"{plan}: {used:g}% used; elapsed window percentage unavailable")
            continue
        ratios.append(ratio)
        reset = timestamp(pool.get("resets_at")) if isinstance(pool.get("resets_at"), str) else pool.get("resets_at")
        reset_text = datetime.fromtimestamp(reset, timezone.utc).strftime("%d %b %H:%M UTC") if isinstance(reset, (int, float)) and math.isfinite(reset) and 0 < reset < 253402300799 else "unknown reset"
        details.append(f"{plan}: {ratio:.2f}× maximum window pace · {used:g}% limiting-window usage · {'over pace' if ratio > 1 else 'within pace'} · resets {reset_text}")
    over = sum(r > 1 for r in ratios)
    if not ratios:
        raise SourceUnavailable("no plans expose both usage and elapsed window pace")
    details.append("For each plan, token-ladder supplies the maximum used% ÷ time-gone% across eligible windows. Its limiting-usage window may differ. Only plans with pace readings enter the denominator.")
    return tile("pace", "Plan usage pace", f"{over}/{len(ratios)} over pace", "token-ladder pools --json · pace_ratio",
                "Current plan windows at export time", details, "bad" if over else "ok")


def loop_health(roster, lines, now):
    names = {r["name"] for r in roster["rows"] if r.get("kind") in LOOP_KINDS}
    if not names:
        raise SourceUnavailable("no orchestrators in roster")
    latest = {}
    for line in lines.splitlines():
        match = re.match(r"(\S+) solo-wake: (.+) loop: (ok|would arm|arm|escalate|skip),\s*(.*)", line, re.I)
        if not match or match[2] not in names:
            continue
        at = timestamp(match[1])
        if at is None or not now - 45 * 60 <= at <= now:
            continue
        if match[2] not in latest or at >= latest[match[2]][0]:
            latest[match[2]] = (at, match[3].lower(), match[4])
    if not latest:
        raise SourceUnavailable("no loop observations in the last 45m; ordinary wakes are not loop fires")
    healthy = 0
    details = []
    for name in sorted(names):
        observation = latest.get(name)
        state = "no recent observation"
        if observation:
            at, state, why = observation
            if state == "ok":
                age = re.search(r"(?:last scheduled turn|scheduled turn|last fire|fired)\s+(\d+)\s*(?:min|m)\b", why)
                if age and now - at + (int(age[1]) + 1) * 60 <= 45 * 60:
                    healthy += 1
                else:
                    state = "scheduled turn age unavailable or older than 45m"
        details.append(f"{name}: {state}")
    return tile("loops", "Drain-loop health", f"{healthy / len(names):.0%}", "Fleet solo-wake loop observations · orchestrator roster",
                "Scheduled turns in last 45m at export time", [f"{healthy}/{len(names)} roster orchestrators with a recent loop fire", "Missing observations stay in the denominator. Rounded fire ages include one minute of uncertainty conservatively.", *details],
                "ok" if healthy == len(names) else "bad")


def collect(now, run=command_json):
    tiles = []
    notes = []
    home = Path.home()
    sources = (
        ("Tickets delivered", lambda: delivered(read_tickets(now, run), now)),
        ("Verifier first-pass rate", lambda: verifier(read_prs(now, run), now)),
        ("Plan usage pace", lambda: plan_pace(run(["token-ladder", "pools", "--json"]), now)),
        ("Drain-loop health", lambda: loop_health(
            json.loads(Path(os.environ.get("FACTORY_ROSTER", home / ".local/share/house-rules/fleet/roster.json")).read_text()),
            Path(os.environ.get("FACTORY_LOOP_LOG", home / ".local/state/fleet-switch/log.txt")).read_text(), now)),
    )
    for label, read in sources:
        try:
            tiles.append(read())
        except SourceUnavailable as error:
            notes.append(f"{label} unavailable. {error}. Not a measured zero.")
        except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
            notes.append(f"{label} unavailable. No complete source reading; not a measured zero.")
    return {"tiles": tiles, "notes": notes}

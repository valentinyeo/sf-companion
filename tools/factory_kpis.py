import json
import math
import os
import re
import subprocess
import statistics
from functools import cache
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
        mergeCommit { oid }
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


def read_pages(endpoint, run, key=None):
    rows = []
    page = 1
    while True:
        data = run(["gh", "api", endpoint + f"?per_page=100&page={page}"])
        batch = data[key] if key else data
        if not isinstance(batch, list):
            raise SourceUnavailable("GitHub pagination did not return a list")
        rows.extend(batch)
        if len(batch) < 100:
            return rows
        page += 1


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
                    comments = [{"body": c["body"], "createdAt": c["created_at"]}
                                for c in read_pages(f"repos/{repo}/issues/{pr['number']}/comments", run)]
                rows.append(dict(pr, repo=repo, comments=comments))
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


def merges(prs, now):
    merged = [p for p in prs if timestamp(p.get("mergedAt")) is not None
              and now - 7 * DAY <= timestamp(p["mergedAt"]) <= now]
    durations = []
    for pr in merged:
        opened = timestamp(pr.get("createdAt"))
        if opened is None or opened > timestamp(pr["mergedAt"]):
            raise SourceUnavailable("merged PR has no valid open-to-merge timestamps")
        durations.append((timestamp(pr["mergedAt"]) - opened) / 60)
    daily = sum(timestamp(p["mergedAt"]) >= now - DAY for p in merged)
    duration = f"{statistics.median(durations):.1f} min median" if durations else "– median"
    details = [f"Last 24h: {daily} merged PRs." + (" No PRs merged in the last 24h." if not daily else ""),
               f"{len(merged)} PRs merged in 7d; {len(merged) / 7:.2f} per day averaged over the full window.",
               "Open-to-merge includes draft and review time." if merged else "No merged PRs in this window; merge time has no samples.",
               "Repositories: " + ", ".join(os.environ.get("FACTORY_REPOS", ",".join(REPOS)).split(","))]
    return tile("merges", "PR throughput and merge time",
                f"{daily} merged in 24h · {len(merged) / 7:.1f} per day over 7d · {duration}",
                "GitHub fleet PRs · createdAt and mergedAt", "Rolling 24h count and 7d daily average; merge-time cohort is 7d", details)


def read_identities(run=command_json):
    script = """
import json, re, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import roster
sessions = Path.home() / '.config/hypertask-agents/credentials/sessions'
rows = []
for chat in roster.hosted_chats().values():
    name = chat.get('name')
    slug = re.sub(r'^-+|-+$', '', re.sub(r'[^a-z0-9]+', '-', name.lower())) if name else ''
    rows.append({'name': name, 'matched': bool(slug) and (sessions / (slug + '-agent-token')).is_file()})
print(json.dumps(rows))
"""
    return run(["python3", "-c", script, str(Path.home() / ".local/share/house-rules/fleet")])


def identity_sync(chats, now):
    if not isinstance(chats, list) or not chats:
        raise SourceUnavailable("no live Multibot chat inventory; identity sync has no denominator")
    if any(not isinstance(c.get("matched"), bool) for c in chats):
        raise SourceUnavailable("incomplete live chat identity checks")
    matched = sum(c["matched"] for c in chats)
    gaps = sorted(c.get("name") or "Unnamed chat" for c in chats if not c["matched"])
    return tile("identity", "Chat identity sync", f"{matched / len(chats):.0%}",
                "Fleet hosted_chats · solo-wake named agent-token existence rule", "Live Multibot chats at export time",
                [f"{matched}/{len(chats)} live chats have an agent-token file matching their Multibot name.",
                 "Includes reachable idle-stopped chats. This is solo-wake's identity-gap check, not proof of the active CLI login. Token contents are never read.",
                 "Gaps: " + ", ".join(gaps) if gaps else "No identity gaps in the live chat inventory."],
                "ok" if not gaps else "bad")


INFRA_FAILURE = re.compile(r"recent account payments have failed|billing (?:limit|error|problem)|failed to acquire.*runner|runner.*(?:lost communication|offline|shutdown signal)|hosted runner.*(?:unavailable|capacity)|no hosted runner|no space left on device|ENOSPC", re.I)
CODE_FAILURE = re.compile(r"error TS\d+|AssertionError|\bFAIL\s+\S+\.(?:test|spec)\.|(?:tests?|assertions?) failed|SyntaxError|IndentationError", re.I)
POLICY_FAILURE = re.compile(r"PR body must contain the line|required checks do not match|docs/ci-policy\.yml", re.I)
FAILED_RUN_LIMIT = 0.05
LIVE_MINUTES_LIMIT = 15


def read_actions(repo, start, end, run):
    window = "..".join(datetime.fromtimestamp(at, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") for at in (start, end))
    endpoint = f"repos/{repo}/actions/runs?per_page=100&created={window}"
    first = run(["gh", "api", endpoint])
    total = first["total_count"]
    if total > 1000:
        middle = (start + end) // 2
        if end <= start:
            raise SourceUnavailable("more than 1,000 Actions runs in one second; cannot read a complete cohort")
        return read_actions(repo, start, middle, run) + read_actions(repo, middle + 1, end, run)
    rows = first["workflow_runs"]
    for page in range(2, math.ceil(total / 100) + 1):
        rows += run(["gh", "api", endpoint + f"&page={page}"])["workflow_runs"]
    if len({r["id"] for r in rows}) < total:
        raise SourceUnavailable("GitHub Actions pagination is incomplete")
    return rows


def read_failure_kinds(repo, rows, run):
    failed = [r for r in rows if r["conclusion"] in ("failure", "timed_out", "startup_failure", "action_required", "stale")]
    kinds = {}
    for offset in range(0, len(failed), 20):
        batch = failed[offset:offset + 20]
        ids = [r["check_suite_node_id"] for r in batch]
        query = """query { nodes(ids: IDS) { id ... on CheckSuite {
          checkRuns(first:100, filterBy:{checkType:LATEST}) { pageInfo { hasNextPage } nodes {
            conclusion annotations(first:100) { pageInfo { hasNextPage }
              nodes { annotationLevel message title }
            }
          } }
        } } }""".replace("IDS", json.dumps(ids))
        data = run(["gh", "api", "graphql", "-f", "query=" + query])
        if data.get("errors"):
            raise SourceUnavailable("failed-job annotation query failed")
        suites = {s["id"]: s["checkRuns"] for s in data["data"]["nodes"] if s}
        for row in batch:
            checks = suites[row["check_suite_node_id"]]
            failed_checks = [c for c in checks["nodes"] if c["conclusion"] in ("FAILURE", "TIMED_OUT", "STARTUP_FAILURE", "ACTION_REQUIRED", "STALE")]
            if checks["pageInfo"]["hasNextPage"] or any(c["annotations"]["pageInfo"]["hasNextPage"] for c in failed_checks):
                annotations = []
                for job in read_pages(f"repos/{repo}/actions/runs/{row['id']}/jobs", run, "jobs"):
                    if job.get("conclusion") not in ("failure", "timed_out", "startup_failure", "action_required", "stale"):
                        continue
                    check = job["check_run_url"].rsplit("/", 1)[-1]
                    annotations.extend(a for a in read_pages(f"repos/{repo}/check-runs/{check}/annotations", run)
                                       if a.get("annotation_level") == "failure")
            else:
                annotations = [a for c in failed_checks for a in c["annotations"]["nodes"] if a["annotationLevel"] == "FAILURE"]
            text = "\n".join(a.get("message", "") + " " + (a.get("title") or "") for a in annotations)
            startup = row.get("conclusion") == "startup_failure" or any(
                str(c.get("conclusion") or "").lower() == "startup_failure" for c in failed_checks)
            if startup or INFRA_FAILURE.search(text):
                kinds[row["id"]] = "infra"
            elif POLICY_FAILURE.search(text) or CODE_FAILURE.search(text):
                kinds[row["id"]] = "code"
            else:
                kinds[row["id"]] = "unknown"
    return kinds


def read_ci(now, prs, run=command_json):
    runs = []
    live = []
    for repo in [r.strip() for r in os.environ.get("FACTORY_REPOS", ",".join(REPOS)).split(",") if r.strip()]:
        found = {r["id"]: r for r in read_actions(repo, int(now - DAY), int(now), run)}
        completed = []
        for row in found.values():
            created = timestamp(row.get("created_at"))
            updated = timestamp(row.get("updated_at"))
            if created is None or updated is None:
                raise SourceUnavailable("Actions run timestamps unavailable")
            if now - DAY <= created <= now and row["status"] == "completed" and updated <= now:
                completed.append(row)
        kinds = read_failure_kinds(repo, completed, run)
        runs.extend(dict(row, failure_kind=kinds.get(row["id"])) for row in completed)
        merged = [p for p in prs if p.get("repo") == repo and timestamp(p.get("mergedAt")) is not None
                  and now - DAY <= timestamp(p["mergedAt"]) <= now]
        if not merged:
            continue
        shas = {(p.get("mergeCommit") or {}).get("oid"): timestamp(p["mergedAt"]) for p in merged}
        page = 1
        receipts = {}
        while True:
            deployments = run(["gh", "api", f"repos/{repo}/deployments?per_page=100&page={page}"])
            for deployment in deployments:
                if deployment.get("environment", "").lower() != "production" or deployment.get("sha") not in shas:
                    continue
                statuses = read_pages(f"repos/{repo}/deployments/{deployment['id']}/statuses", run)
                for status in statuses:
                    at = timestamp(status.get("created_at"))
                    merged_at = shas[deployment["sha"]]
                    if status.get("state") == "success" and at is not None and merged_at <= at <= now:
                        receipts[deployment["sha"]] = min(at, receipts.get(deployment["sha"], at))
            if len(deployments) < 100 or timestamp(deployments[-1]["created_at"]) < now - DAY:
                break
            page += 1
        live.extend((at - shas[sha]) / 60 for sha, at in receipts.items())
    return {"runs": runs, "live_minutes": live}


def ci_health(data, prs, now):
    runs = data["runs"]
    live = data["live_minutes"]
    merged = sum(timestamp(p.get("mergedAt")) is not None and now - DAY <= timestamp(p["mergedAt"]) <= now for p in prs)
    counts = {kind: sum(r["failure_kind"] == kind for r in runs) for kind in ("infra", "code", "unknown")}
    failed = sum(counts.values())
    if live and merged:
        latency = f"{statistics.median(live):.1f} min median to live ({len(live)}/{merged} receipted)"
    elif merged:
        latency = f"– to live (0/{merged} receipted)"
    else:
        latency = "– to live"
    if runs:
        tenths = round(failed / len(runs) * 1000)
        share = f"{tenths // 10}%" if tenths % 10 == 0 else f"{tenths // 10}.{tenths % 10}%"
        failures = f"{share} runs failed · infra {counts['infra']} · code/policy {counts['code']} · unclassified {counts['unknown']}"
    else:
        failures = "– runs failed"
    details = [f"{len(live)}/{merged} merged PRs have an exact merge-SHA successful Production deployment receipt. Off target above {FAILED_RUN_LIMIT:.0%} failed runs or {LIVE_MINUTES_LIMIT:g} min receipted median.",
               "No matching successful Production deployment receipts; latency is unavailable, not zero." if not live else "Latency covers only receipted PRs, not the whole fleet. Earliest successful deployment per merge SHA counts.",
               f"{len(runs)} completed Actions runs created in 24h, latest attempt per run. Cancelled, skipped and neutral runs remain in the denominator.",
               f"Failures: infra {counts['infra']}, code/policy {counts['code']}, unclassified {counts['unknown']}.",
               "Classification uses the startup_failure conclusion and explicit failure annotations. Billing, runner, and startup_failure signatures are infra. Policy-check text is code/policy. Generic exit codes and other missing annotations stay unclassified.",
               "A zero code/policy count means no matching annotations, not zero product failures when unclassified runs remain.",
               "Repositories: " + ", ".join(os.environ.get("FACTORY_REPOS", ",".join(REPOS)).split(","))]
    if not runs:
        details.append("No completed Actions runs in this window; failure rates have no denominator.")
    off_target = (bool(runs) and failed / len(runs) > FAILED_RUN_LIMIT) or (bool(live) and statistics.median(live) > LIVE_MINUTES_LIMIT)
    return tile("ci", "CI health", f"{failures} · {latency}",
                "GitHub Actions run/job annotations and Production deployment statuses · fleet repos",
                "Runs created and PRs merged in rolling 24h", details,
                "bad" if off_target else None)


def collect(now, run=command_json):
    tiles = []
    notes = []
    home = Path.home()

    @cache
    def prs():
        return read_prs(now, run)

    sources = (
        ("Tickets delivered", lambda: delivered(read_tickets(now, run), now)),
        ("Verifier first-pass rate", lambda: verifier(prs(), now)),
        ("Plan usage pace", lambda: plan_pace(run(["token-ladder", "pools", "--json"]), now)),
        ("Drain-loop health", lambda: loop_health(
            json.loads(Path(os.environ.get("FACTORY_ROSTER", home / ".local/share/house-rules/fleet/roster.json")).read_text()),
            Path(os.environ.get("FACTORY_LOOP_LOG", home / ".local/state/fleet-switch/log.txt")).read_text(), now)),
        ("PR throughput and merge time", lambda: merges(prs(), now)),
        ("Chat identity sync", lambda: identity_sync(read_identities(run), now)),
        ("CI health", lambda: ci_health(read_ci(now, prs(), run), prs(), now)),
    )
    for label, read in sources:
        try:
            tiles.append(read())
        except SourceUnavailable as error:
            notes.append(f"{label} unavailable. {error}. Not a measured zero.")
        except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
            notes.append(f"{label} unavailable. No complete source reading; not a measured zero.")
    notes.extend([
        "Lead time unavailable. First exit from Todo and Done-move history are not exposed; waiting for HYCI-9390. Not a measured zero.",
        "Escapes unavailable. The exporter login cannot read all three boards for bug/incident links to merged PRs. A revert-only count would understate escapes. Not a measured zero.",
        "Rework unavailable. Runner logs exist, but a dated Done cohort and Done-to-Doing transition history do not; waiting for HYCI-9390. Not a measured zero.",
        "Cost per delivered ticket unavailable. Dated deliveries are blocked by HYCI-9390, so plan prices and token spend have no delivered-ticket denominator. Flat plans do not establish a zero total cost.",
        "Workers in flight vs slots unavailable. fleet/slots calculates a per-coordinator decision from running and ready counts but stores no tick receipts. Live chat counts cannot establish each coordinator's running count, cap or top shortfall reason. Not a measured zero.",
    ])
    return {"tiles": tiles, "notes": notes}

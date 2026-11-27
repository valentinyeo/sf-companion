import argparse
import csv
import io
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from bisect import bisect_left, bisect_right
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

HOUR = 3600
WEEK = 7 * 86400
VERSION = 5
PARALLEL_MINIMUM_FILES = 64
MAX_WORKERS = 8
RELEASE_EVERY = 16 * 1024 * 1024
TICKET = re.compile(r"\b[A-Z][A-Z0-9]{1,11}-[1-9][0-9]{0,8}\b")
MULTIBOT = re.compile(r"\bMULTIBOT_SESSION\s*[=:]\s*[\"']?([A-Za-z0-9_.:-]{1,80})")
PRIVATE = re.compile(r"[\w.+-]+@[\w.-]+|\b\d{1,3}(?:\.\d{1,3}){3}\b|(?:sk-|ghp_|gho_|eyJ)[A-Za-z0-9_./+=-]+|[A-Za-z0-9_+/=-]{32,}")
COUNTS = ("input", "output", "cacheRead", "cacheWrite", "requests")
PLANS = ("claude", "codex", "antigravity", "grok", "opencode", "vercel", "deepseek", "openrouter", "commandcode", "cursor")
OFFICIAL_PRICES = {
    "claude-fable-5-2": {"in": 8, "out": 40, "cached": 0.2, "cache_write": 10, "tiers": []},
}


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def stamp(value):
    if numeric(value):
        return value / 1000 if value > 100_000_000_000 else value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.timestamp() if parsed.tzinfo else None
        except ValueError:
            pass
    return None


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def digest(value):
    return hashlib.sha256(str(value).encode()).hexdigest()[:16]


def label(value, fallback="unknown"):
    if not isinstance(value, str):
        return fallback
    text = PRIVATE.sub("[redacted]", value)
    text = re.sub(r"[^\w .()\[\]:/-]", " ", text)
    return " ".join(text.split())[:80] or fallback


def release_cached_pages(handle, consumed=None):
    try:
        os.posix_fadvise(handle.fileno(), 0, 0 if consumed is None else consumed, os.POSIX_FADV_DONTNEED)
    except (AttributeError, OSError, ValueError):
        pass


def records(path, issues):
    released = 0
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            try:
                for line in handle:
                    consumed = handle.buffer.tell()
                    if consumed - released >= RELEASE_EVERY:
                        release_cached_pages(handle, consumed)
                        released = consumed
                    try:
                        row = json.loads(line)
                    except ValueError:
                        issues["invalid JSONL rows"] += 1
                        continue
                    if isinstance(row, dict):
                        yield row
            finally:
                release_cached_pages(handle)
    except OSError:
        issues["unreadable files"] += 1


def load(path):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def text_parts(content):
    if isinstance(content, str):
        yield content
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") in ("text", "output_text", "input_text") and isinstance(part.get("text"), str):
                yield part["text"]


def token_values(usage, provider):
    if not isinstance(usage, dict):
        return None
    if provider == "claude":
        fields = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    elif provider == "pi":
        fields = ("input", "output", "cacheRead", "cacheWrite")
    elif provider == "worker":
        fields = ("in", "out", "cached", "cache_write")
    else:
        fields = ("input_tokens", "output_tokens", "cached_input_tokens", "cache_write_input_tokens")
    incoming, outgoing, cached, written = (usage.get(k, 0) for k in fields)
    if not all(numeric(v) for v in (incoming, outgoing, cached, written)) or fields[0] not in usage or fields[1] not in usage:
        return None
    if provider == "codex":
        incoming -= cached
    if incoming < 0:
        return None
    return dict(zip(COUNTS[:4], (incoming, outgoing, cached, written)))


def list_prices(home):
    prices = {model: dict(price) for model, price in OFFICIAL_PRICES.items()}
    catalog = home / ".npm-global/lib/node_modules/@earendil-works/pi-coding-agent/node_modules/@earendil-works/pi-ai/dist/providers/data"
    for provider in ("anthropic", "openai", "openai-codex"):
        for models in load(catalog / (provider + ".json")).values():
            if not isinstance(models, dict):
                continue
            for model in models.values():
                if isinstance(model, dict) and isinstance(model.get("id"), str) and isinstance(model.get("cost"), dict):
                    cost = model["cost"]
                    prices[model["id"]] = {"in": cost.get("input"), "out": cost.get("output"),
                        "cached": cost.get("cacheRead"), "cache_write": cost.get("cacheWrite"),
                        "tiers": cost.get("tiers", [])}
    config = load(home / "projects/token-ladder/config.json")
    config.update(load(home / "projects/token-ladder/config.local.json"))
    prices.update(config.get("list_prices", {}))
    return prices


def cost_of(values, model, prices):
    price = prices.get(model, {})
    if values:
        context = values["input"] + values["cacheRead"] + values["cacheWrite"]
        for tier in sorted(price.get("tiers", []), key=lambda item: item.get("inputTokensAbove", math.inf)):
            if numeric(tier.get("inputTokensAbove")) and context > tier["inputTokensAbove"]:
                price = {**price, "in": tier.get("input"), "out": tier.get("output"),
                         "cached": tier.get("cacheRead"), "cache_write": tier.get("cacheWrite")}
    if not values or not all(numeric(price.get(k)) for k in ("in", "out", "cached")):
        return None
    write_price = price.get("cache_write")
    if values["cacheWrite"] and not numeric(write_price):
        return None
    return (values["input"] * price["in"] + values["output"] * price["out"] + values["cacheRead"] * price["cached"] + values["cacheWrite"] * (write_price or 0)) / 1_000_000


def observation(at, plan, session, chat, model, values, request_id, account=None):
    return {"hour": iso(int(at // HOUR) * HOUR), "plan": plan,
            "account": account or f"{plan} · account/key unrecorded", "chatId": digest(session),
            "chat": label(chat), "model": label(model), "ticket": "unassigned", "attribution": "unknown",
            **(values or dict.fromkeys(COUNTS[:4], 0)), "requests": 1,
            "tokensKnown": values is not None, "listCostUsd": None, "id": digest(request_id)}


def transcript(path, provider, prices, issues):
    session = path.stem
    chat = path.parent.name if provider == "claude" else "unknown project"
    model = "unknown"
    account = None
    requests = {}
    mentions = defaultdict(dict)
    previous = {}
    generation = 0
    for entry in records(path, issues):
        payload = entry.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        message = entry.get("message")
        message = message if isinstance(message, dict) else {}
        kind = entry.get("type")
        at = stamp(entry.get("timestamp"))
        if provider == "pi" and kind == "session":
            session = entry.get("id") or session
            chat = Path(entry.get("cwd") or "unknown project").name
        if kind == "session-owner" and entry.get("accountUuid"):
            account = "Claude account " + digest(entry["accountUuid"])
        if kind == "session_meta":
            session = payload.get("id", session)
            chat = Path(payload.get("cwd") or "unknown project").name
        if kind == "turn_context":
            model = payload.get("model") or model
        assistant = (provider == "pi" and message.get("role") == "assistant") or kind == "assistant" or (kind == "response_item" and payload.get("role") == "assistant") or (kind == "event_msg" and payload.get("type") == "agent_message") or (kind == "response_item" and payload.get("type") == "function_call")
        content = message.get("content") if provider in ("claude", "pi") else payload.get("content", payload.get("message", payload.get("arguments")))
        for text in text_parts(content):
            match = MULTIBOT.search(text)
            if match:
                chat = match[1].strip()
            if assistant and at is not None:
                identity = message.get("id") or entry.get("id") or entry.get("uuid") or payload.get("id") or digest(text)
                mentions[int(at // HOUR) * HOUR].setdefault(identity, set()).update(TICKET.findall(text))
        if assistant and at is not None and isinstance(content, list):
            identity = message.get("id") or entry.get("id") or entry.get("uuid")
            for part in content:
                if isinstance(part, dict) and part.get("type") in ("tool_use", "toolCall"):
                    keys = TICKET.findall(json.dumps(part.get("input", part.get("arguments", {}))))
                    mentions[int(at // HOUR) * HOUR].setdefault(identity, set()).update(keys)
        if at is None:
            continue
        plan = provider
        if provider == "pi":
            if not assistant or not message.get("usage"):
                continue
            plan = {"anthropic": "claude", "openai-codex": "codex", "opencode-go": "opencode",
                    "vercel-ai-gateway": "vercel", "openrouter-credit": "openrouter",
                    "openrouter": "openrouter"}.get(message.get("provider"), message.get("provider") or "unknown")
            model = message.get("model") or model
            values = token_values(message["usage"], "pi")
            request_id = message.get("responseId") or entry.get("id")
            if not request_id:
                issues["usage rows without request identity"] += 1
                continue
            request_id = str(message.get("provider")) + ":" + str(request_id)
            account = plan + " · Pi provider key/account"
        elif provider == "claude":
            if kind != "assistant" or not message.get("usage"):
                continue
            model = message.get("model") or model
            values = token_values(message["usage"], provider)
            request_id = message.get("id") or entry.get("requestId") or entry.get("uuid")
            if not request_id:
                issues["usage rows without request identity"] += 1
                continue
        elif kind == "event_msg" and payload.get("type") == "token_count":
            info = payload.get("info")
            if not isinstance(info, dict) or not isinstance(info.get("total_token_usage"), dict):
                continue
            total = info["total_token_usage"]
            if not all(numeric(total.get(k, 0)) for k in ("input_tokens", "output_tokens", "cached_input_tokens", "cache_write_input_tokens")):
                issues["invalid token counters"] += 1
                continue
            delta = {k: total.get(k, 0) - previous.get(k, 0) for k in total if numeric(total[k])}
            if any(v < 0 for v in delta.values()):
                issues["reset token counters"] += 1
                generation += 1
                delta = total
            previous = dict(total)
            if not any(delta.values()):
                continue
            values = token_values(delta, provider)
            request_id = f"{session}:{generation}:{json.dumps(total, sort_keys=True)}"
        else:
            continue
        row = observation(at, plan, entry.get("sessionId") or session, chat, model, values, request_id, account)
        row["listCostUsd"] = cost_of(values, model, prices)
        if provider == "pi":
            cost = message["usage"].get("cost", {})
            if isinstance(cost, dict) and cost.get("totalFromProvider") is False and numeric(cost.get("total")):
                row["listCostUsd"] = cost["total"]
        requests[row["id"]] = row
    for row in requests.values():
        row["chat"] = label(chat)
        row["project"] = label(path.parent.name if provider == "claude" else chat)
        hour = stamp(row["hour"])
        counts = Counter(ticket for tickets in mentions[hour].values() for ticket in tickets)
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if ranked:
            row["ticket"], row["attribution"] = ranked[0][0], "inferred"
    return list(requests.values()), digest(session)


def workers(path, prices, issues):
    starts, finishes = {}, {}
    for row in records(path, issues):
        identity = row.get("launch_id")
        if not identity and not row.get("event") and row.get("lane"):
            identity = "legacy:" + digest(json.dumps(row, sort_keys=True))
        if identity and row.get("event") in ("start", None):
            starts[identity] = row
        elif identity and row.get("event") == "finish":
            finishes[identity] = row
    result = []
    for identity, start in starts.items():
        end = finishes.get(identity, {})
        at = stamp(end.get("finished_at")) or stamp(start.get("at"))
        if at is None:
            continue
        lane = start.get("lane", "unknown")
        plan = {"google": "antigravity", "vercel-zai": "vercel"}.get(lane, lane)
        if plan not in PLANS:
            plan = "openrouter" if str(lane).startswith("openrouter") else "unknown"
        session = "worker:" + identity
        chat = Path(start.get("cwd") or "worker").name + " worker"
        model = start.get("model") or "unknown"
        values = token_values(end.get("tokens"), "worker")
        row = observation(at, plan, session, chat, model, values, "worker:" + identity)
        if start.get("account_label") or start.get("key_label"):
            row["account"] = label(start.get("account_label") or start.get("key_label"))
        row["parent"] = digest(start.get("session")) if start.get("session") else None
        row["start"] = stamp(start.get("at")) or at
        row["end"] = at
        ticket = start.get("ticket")
        if isinstance(ticket, str) and TICKET.fullmatch(ticket):
            row["ticket"], row["attribution"] = ticket, "recorded"
        receipt = end.get("cost_usd")
        row["listCostUsd"] = receipt if end.get("cost_basis") == "list-equivalent" and numeric(receipt) else cost_of(values, model, prices)
        result.append(row)
    return result


def antigravity(path, issues):
    result = []
    for index, entry in enumerate(records(path, issues)):
        at = stamp(entry.get("timestamp"))
        if at is None:
            continue
        usage = entry.get("usage")
        values = token_values(usage, "codex")
        if values is None and "display" not in entry:
            continue
        session = entry.get("conversationId") or Path(entry.get("workspace") or "antigravity").name
        result.append(observation(at, "antigravity", session, Path(entry.get("workspace") or "antigravity").name,
                                  entry.get("model") or "unknown", values, f"{path.name}:{index}"))
    return result


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, separators=(",", ":"), allow_nan=False)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def aggregate(rows):
    grouped = {}
    for row in rows:
        key = tuple(row[k] for k in ("hour", "plan", "account", "chatId", "chat", "model", "ticket", "attribution", "tokensKnown"))
        if key not in grouped:
            grouped[key] = {k: row[k] for k in (*COUNTS, "hour", "plan", "account", "chatId", "chat", "model", "ticket", "attribution", "tokensKnown", "listCostUsd")}
            continue
        item = grouped[key]
        for field in COUNTS:
            item[field] += row[field]
        item["listCostUsd"] = None if item["listCostUsd"] is None or row["listCostUsd"] is None else item["listCostUsd"] + row["listCostUsd"]
    return sorted(grouped.values(), key=lambda row: (row["hour"], row["plan"], row["chatId"], row["ticket"]))


def chat_names(home):
    names = {}
    roster = home / ".local/share/house-rules/fleet/roster-live"
    try:
        done = subprocess.run([str(roster)], capture_output=True, text=True, timeout=20)
        if done.returncode == 0:
            for line in done.stdout.splitlines():
                match = re.match(r"^(.+) \(([^,]+), [^,]+(?:, .*)?\)$", line)
                if match:
                    names[match[2]] = label(match[1])
    except (OSError, subprocess.TimeoutExpired):
        pass
    for path in (home / ".local/state/roster/announce").glob("*.json"):
        item = load(path)
        name = names.get(item.get("tmux")) or item.get("multibot") or item.get("name")
        if name:
            for identity in (item.get("sid"), item.get("tmux")):
                if identity:
                    names[digest(identity)] = label(name)
                    names[identity] = label(name)
    root = home / ".local/state/multiprompt"
    published = load(root / "chat-names.json")
    for path in (root / "agent-host").glob("*.config.json"):
        config = load(path)
        state = load(path.with_name(path.name.removesuffix(".config.json") + ".state.json"))
        tmux = config.get("tmux")
        named = published.get(tmux, {})
        named = named if isinstance(named, dict) else {}
        name = named.get("name")
        name = name or names.get(tmux)
        if not name:
            continue
        for identity in (tmux, state.get("sid"), state.get("native_session"), named.get("sid")):
            if isinstance(identity, str) and identity:
                names[identity] = names[digest(identity)] = label(name)
                names[digest(Path(identity).stem)] = label(name)
    for path in (home / ".claude/sessions").glob("*.json"):
        item = load(path)
        if item.get("sessionId") and item.get("name"):
            names.setdefault(digest(item["sessionId"]), label(item["name"]))
    return names


def usable_workers():
    try:
        available = len(os.sched_getaffinity(0))
    except AttributeError:
        available = os.cpu_count() or 1
    return max(1, min(available, MAX_WORKERS))


def file_signature(stat, price_version):
    return [VERSION, stat.st_size, stat.st_mtime_ns, price_version]


def file_report(path, provider, prices, price_version, cache_dir):
    try:
        stat = path.stat()
    except OSError:
        return [], None, {"unreadable files": 1}
    cache_path = cache_dir / (digest(str(path)) + ".json")
    cached = load(cache_path)
    signature = file_signature(stat, price_version)
    if cached.get("signature") == signature and isinstance(cached.get("rows"), list):
        return cached["rows"], cached.get("session"), cached.get("issues") or {}
    file_issues = Counter()
    if provider == "antigravity":
        rows, session = antigravity(path, file_issues), None
    else:
        rows, session = transcript(path, provider, prices, file_issues)
    try:
        atomic_json(cache_path, {"signature": signature, "rows": rows, "session": session, "issues": dict(file_issues)})
    except OSError:
        file_issues["cache writes failed"] += 1
    return rows, session, dict(file_issues)


WORKER_STATE = {}


def start_worker(prices, price_version, cache_dir):
    WORKER_STATE.update(prices=prices, price_version=price_version, cache_dir=Path(cache_dir))


def file_report_task(task):
    path, provider = task
    return file_report(Path(path), provider, WORKER_STATE["prices"], WORKER_STATE["price_version"], WORKER_STATE["cache_dir"])


def read_files(tasks, prices, price_version, cache_dir, workers):
    if workers <= 1 or len(tasks) < PARALLEL_MINIMUM_FILES:
        return [file_report(Path(path), provider, prices, price_version, cache_dir) for path, provider in tasks]
    try:
        with ProcessPoolExecutor(max_workers=workers, initializer=start_worker,
                                 initargs=(prices, price_version, str(cache_dir))) as pool:
            return list(pool.map(file_report_task, tasks, chunksize=8))
    except (OSError, RuntimeError):
        return [file_report(Path(path), provider, prices, price_version, cache_dir) for path, provider in tasks]


def local_report(home, now, cache_dir=None, processes=None):
    issues = Counter()
    prices = list_prices(home)
    price_version = digest(json.dumps(prices, sort_keys=True))
    cache_dir = cache_dir or home / ".local/state/sf-companion/burn-cache"
    pool_size = usable_workers() if processes is None else processes
    groups = (("claude", home / ".claude/projects", "**/*.jsonl"),
              ("codex", home / ".codex/sessions", "**/*.jsonl"),
              ("pi", home / ".pi/agent/sessions", "**/*.jsonl"),
              ("antigravity", home / ".gemini/antigravity-cli", "**/*.jsonl"))
    observations = {}
    names = chat_names(home)
    sources = []
    for provider, root, pattern in groups:
        paths = [path for path in sorted(root.glob(pattern)) if path.is_file()]
        found = len(paths)
        tasks = [(str(path), provider) for path in paths]
        for rows, _session, file_issues in read_files(tasks, prices, price_version, cache_dir, pool_size):
            issues.update(file_issues)
            for row in rows:
                raw_chat = row["chat"]
                row["chat"] = names.get(row["chatId"], names.get(raw_chat, row.get("project", raw_chat) if raw_chat.startswith("live-") else raw_chat))
                if row["chat"] == row.get("project") and row["chatId"] not in names:
                    row["chat"] += " [" + row["chatId"][:8] + "]"
                if stamp(row["hour"]) <= now:
                    observations[(provider, row["id"])] = row
        sources.append(f"{provider}: {found} transcript files" if found else f"{provider}: no local usage files")
    launch_path = home / ".local/state/token-ladder/launches.jsonl"
    receipts = workers(launch_path, prices, issues) if launch_path.exists() else []
    indexed = defaultdict(list)
    for row in observations.values():
        indexed[(row["plan"], row["model"])].append(row)
    for items in indexed.values():
        items.sort(key=lambda row: row["hour"])
    index_hours = {key: [stamp(row["hour"]) for row in items] for key, items in indexed.items()}
    for receipt in receipts:
        if receipt["end"] > now:
            continue
        if receipt.get("parent") in names:
            receipt["chat"] = names[receipt["parent"]] + " worker"
        receipt["chat"] += " [" + receipt["chatId"][:8] + "]"
        candidates = defaultdict(list)
        key = (receipt["plan"], receipt["model"])
        hours = index_hours.get(key, [])
        lower = bisect_left(hours, receipt["start"] - HOUR)
        upper = bisect_right(hours, receipt["end"])
        for row in indexed[key][lower:upper]:
            candidates[row["chatId"]].append(row)
        matching = [items for items in candidates.values() if receipt["tokensKnown"] and all(
            sum(row[k] for row in items) == receipt[k] for k in COUNTS[:4])]
        if len(matching) == 1:
            for row in matching[0]:
                if receipt["attribution"] == "recorded":
                    row["ticket"], row["attribution"] = receipt["ticket"], "recorded"
        else:
            observations[("worker", receipt["id"])] = receipt
    rows = aggregate(observations.values())
    status = load(home / ".local/state/token-ladder/status.json")
    pools = status.get("pools", {})
    plans = []
    for plan in sorted(set(PLANS) | {r["plan"] for r in rows}):
        pool = pools.get("google" if plan == "antigravity" else plan, {})
        reset = stamp(pool.get("resets_at")) if pool.get("window_minutes") == 10080 else None
        if reset is not None:
            reset += math.floor((now - reset) / WEEK + 1) * WEEK
        plans.append({"plan": plan, "weekStartsAt": iso(reset - WEEK) if reset else None, "weekResetsAt": iso(reset) if reset else None})
    missing_plans = sorted(set(PLANS) - {row["plan"] for row in rows})
    missing_note = ["No usage records for: " + ", ".join(missing_plans) + ". Not measured zero."] if missing_plans else []
    return {"generatedAt": iso(now), "rows": rows, "plans": plans,
            "notes": sources + missing_note + ["Antigravity history without token usage counts requests only.",
                "Account/key labels are unknown unless recorded; no key values are exported.",
                "Worker totals are assigned to the finish hour; unfinished launches are requests only.",
                "List-equivalent USD is not billed spend or subscription quota. Unpriced usage remains unknown.",
                "Receipt/transcript deduplication requires a unique match of model, time span and every token count; that source link is inferred."] +
                [f"{name}: {count}" for name, count in sorted(issues.items())]}


def http_json(url, key):
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + key, "User-Agent": "sf-companion"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def provider_key(home, provider):
    done = subprocess.run([str(home / ".npm-global/bin/pi"), "auth", "print-api-key", "--provider", provider],
                          capture_output=True, text=True, timeout=60)
    if done.returncode or not done.stdout.strip():
        raise ValueError("credential unavailable")
    return done.stdout.strip()


def key_usage_row(day, plan, account, model, requests, values, billed, prices, identity):
    start = stamp(day + "T00:00:00Z")
    if start is None or not numeric(requests) or (billed is not None and not numeric(billed)):
        raise ValueError("invalid provider totals")
    row = observation(start, plan, "api:" + identity, "Provider total, not a chat", model, values, identity, account)
    row.pop("id")
    row["requests"] = requests
    row["listCostUsd"] = cost_of(values, model, prices)
    return {"row": row, "periodEndsAt": iso(start + 86400), "billedCostUsd": billed}


def opencode_export(text, prices):
    reader = csv.DictReader(io.StringIO(text))
    required = {"day", "user_id", "model", "requests", "input_tokens", "output_tokens", "cache_read_tokens",
                "cache_write_5m_tokens", "cache_write_1h_tokens", "cost_usd"}
    if not required <= set(reader.fieldnames or []):
        raise ValueError("unknown OpenCode export format")
    result = []
    for entry in reader:
        values = {"input": float(entry["input_tokens"]), "output": float(entry["output_tokens"]),
                  "cacheRead": float(entry["cache_read_tokens"]),
                  "cacheWrite": float(entry["cache_write_5m_tokens"]) + float(entry["cache_write_1h_tokens"])}
        if not all(numeric(value) for value in values.values()) or not entry["user_id"] or not entry["model"]:
            raise ValueError("invalid OpenCode counters")
        account = "OpenCode usage key / account " + digest(entry["user_id"])
        item = key_usage_row(entry["day"], "opencode", account, entry["model"], float(entry["requests"]), values,
                             float(entry["cost_usd"]), prices, "opencode:" + entry["user_id"])
        if float(entry["cache_write_1h_tokens"]):
            item["row"]["listCostUsd"] = None
        result.append(item)
    return result


def read_paid_source(source, home, now, prices):
    if source == "opencode":
        done = subprocess.run([str(home / ".local/bin/yeo-key"), "--env", "OpenCode Check usage", "--",
            str(home / ".local/bin/plan-pick"), "--opencode-usage-export"],
            capture_output=True, text=True, timeout=90)
        if done.returncode:
            raise ValueError("OpenCode usage export unavailable")
        return opencode_export(done.stdout, prices), iso(int(now // 86400) * 86400 - 29 * 86400)
    provider = "openrouter-credit" if source == "openrouter" else "vercel-ai-gateway"
    key = provider_key(home, provider)
    result = []
    if source == "openrouter":
        data = http_json("https://openrouter.ai/api/v1/activity", key)
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise ValueError("unknown OpenRouter activity format")
        for entry in data["data"]:
            day = entry.get("date", "")[:10]
            item = key_usage_row(day, source, "OpenRouter openrouter-credit key", entry.get("model") or "unknown",
                entry.get("requests"), None, entry.get("usage"), prices, "openrouter-credit")
            for field, api_field in (("input", "prompt_tokens"), ("output", "completion_tokens")):
                if numeric(entry.get(api_field)):
                    item["row"][field] = entry[api_field]
            result.append(item)
        return result, iso(int(now // 86400) * 86400 - 29 * 86400)
    for at in (now - 86400, now):
        day = iso(at)[:10]
        query = urllib.parse.urlencode({"start_date": day, "end_date": day, "group_by": "model"})
        data = http_json("https://ai-gateway.vercel.sh/v1/report?" + query, key)
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise ValueError("unknown Vercel report format")
        for entry in data["results"]:
            result.append(key_usage_row(day, source, "Vercel AI Gateway Token Pass key", entry.get("model") or "unknown",
                entry.get("request_count"), None, entry.get("total_cost"), prices, "vercel-token-pass"))
    return result, iso(int(now // 86400) * 86400 - 86400)


def paid_usage(home, now):
    prices = list_prices(home)
    path = home / ".local/state/sf-companion/burn-key-usage.json"
    cached = load(path)
    saved, notes = {}, []
    for source in ("openrouter", "vercel", "opencode"):
        previous = cached.get(source, {})
        try:
            incoming, since = read_paid_source(source, home, now, prices)
            rows = [item for item in previous.get("rows", []) if item["row"]["hour"] < since] + incoming
            saved[source] = {"rows": rows, "at": iso(now)}
            notes.append(source + ": provider usage API read at " + iso(now) + ".")
        except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
            saved[source] = previous
            status = "HTTP " + str(exc.code) if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
            notes.append(source + ": usage API unavailable (" + status + "); last successful read: " + str(previous.get("at", "never")) + ".")
    try:
        atomic_json(path, saved)
    except OSError:
        notes.append("Provider usage history could not be cached; only this reading is available.")
    rows = [item for entry in saved.values() for item in entry.get("rows", [])]
    notes += ["Paid-key API totals are separate from transcript/worker totals, never added together. They can include other servers.",
              "Provider exports have UTC-day precision, not hourly precision. Intersecting dates include the entire day.",
              "OpenCode and OpenRouter expose a rolling history; older provider readings are retained after collection starts.",
              "Vercel collects today and yesterday; Token Pass-scoped keys may not have report access. Missing API counters remain unknown."]
    return rows, notes


def collect(now, home=None, remote=True):
    home = home or Path.home()
    report = local_report(home, now)
    if remote:
        try:
            source = Path(__file__).read_text()
            done = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "hetzner",
                                   "sudo -n -u inne -H bash -lc 'python3 - --local-only --now " + str(now) + "'"], input=source, text=True, capture_output=True, timeout=90)
            other = json.loads(done.stdout) if done.returncode == 0 else None
            if not isinstance(other, dict) or validate(other):
                raise ValueError("remote report unavailable")
            for row in other["rows"]:
                row["plan"] += " (Hetzner)"
                row["chatId"] = "hetzner-" + row["chatId"]
                row["chat"] += " (Hetzner)"
            report["plans"].extend({**plan, "plan": plan["plan"] + " (Hetzner)"} for plan in other["plans"])
            report["rows"] = aggregate([*report["rows"], *other["rows"]])
            report["notes"].append("Includes Hetzner through the existing read-only SSH export route.")
            report["notes"].extend("Hetzner: " + note for note in other["notes"])
        except (OSError, ValueError, subprocess.TimeoutExpired):
            report["notes"].append("This server only; Hetzner usage could not be reached through the existing SSH export route.")
    else:
        report["notes"].append("This server only.")
    if remote:
        report["keyUsage"], api_notes = paid_usage(home, now)
        report["notes"].extend(api_notes)
    return report


def validate(report):
    errors = []
    if not isinstance(report, dict) or set(report) not in ({"generatedAt", "rows", "plans", "notes"}, {"generatedAt", "rows", "plans", "notes", "keyUsage"}):
        return ["burn report: needs generatedAt, rows, plans and notes"]
    if stamp(report["generatedAt"]) is None or not isinstance(report["rows"], list) or not isinstance(report["plans"], list) or not isinstance(report["notes"], list):
        return ["burn report: invalid timestamp or collections"]
    for row in report["rows"]:
        fields = {*COUNTS, "hour", "plan", "account", "chatId", "chat", "model", "ticket", "attribution", "tokensKnown", "listCostUsd"}
        if not isinstance(row, dict) or set(row) != fields:
            errors.append("burn row: unexpected fields")
            continue
        if not all(numeric(row[k]) for k in COUNTS) or not isinstance(row["tokensKnown"], bool):
            errors.append("burn row: invalid token/request counts")
        if row["listCostUsd"] is not None and not numeric(row["listCostUsd"]):
            errors.append("burn row: invalid list-equivalent cost")
        if stamp(row["hour"]) is None or row["attribution"] not in ("recorded", "inferred", "unknown"):
            errors.append("burn row: invalid hour or attribution")
        if row["ticket"] != "unassigned" and (not isinstance(row["ticket"], str) or not TICKET.fullmatch(row["ticket"])):
            errors.append("burn row: invalid ticket key")
        if not all(isinstance(row[k], str) and row[k] for k in ("plan", "account", "chatId", "chat", "model")):
            errors.append("burn row: missing labels")
    for plan in report["plans"]:
        if not isinstance(plan, dict) or set(plan) != {"plan", "weekStartsAt", "weekResetsAt"} or not isinstance(plan.get("plan"), str):
            errors.append("burn plan: invalid reset anchor")
        elif any(plan[k] is not None and stamp(plan[k]) is None for k in ("weekStartsAt", "weekResetsAt")):
            errors.append("burn plan: invalid reset time")
    key_usage = report.get("keyUsage", [])
    if not isinstance(key_usage, list):
        errors.append("burn report: invalid paid-key usage")
    else:
        for item in key_usage:
            if not isinstance(item, dict) or set(item) != {"row", "periodEndsAt", "billedCostUsd"}:
                errors.append("burn report: invalid paid-key fields")
                continue
            end = stamp(item["periodEndsAt"])
            start = stamp(item["row"].get("hour")) if isinstance(item["row"], dict) else None
            if end is None or start is None or end != start + 86400:
                errors.append("burn report: invalid provider day")
            if item["billedCostUsd"] is not None and not numeric(item["billedCostUsd"]):
                errors.append("burn report: invalid billed cost")
            errors.extend(validate({"generatedAt": report["generatedAt"], "rows": [item["row"]], "plans": [], "notes": []}))
    if not all(isinstance(note, str) and note for note in report["notes"]):
        errors.append("burn report: invalid notes")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument("--now", type=float, default=None)
    args = parser.parse_args()
    result = collect(args.now or time.time(), remote=not args.local_only)
    problems = validate(result)
    if problems:
        print("Invalid burn report. Fix: inspect tools/factory_burn.py.", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, separators=(",", ":"), allow_nan=False))

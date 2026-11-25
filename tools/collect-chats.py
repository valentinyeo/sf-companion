#!/usr/bin/env python3

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
ROSTER_BIN = Path(os.environ.get("ROSTER_BIN") or HOME / ".local/share/house-rules/fleet/roster-live")
MP_SESSIONS_BIN = Path(os.environ.get("MP_SESSIONS_BIN") or HOME / ".multiprompt-runtime/mp-sessions")
CLAUDE_SESSIONS = HOME / ".claude/sessions"
CLAUDE_PROJECTS = HOME / ".claude/projects"
CODEX_SESSIONS = HOME / ".codex/sessions"
PI_SESSIONS = HOME / ".pi/agent/sessions"
ANNOUNCE_DIR = Path(os.environ.get("ROSTER_ANNOUNCE_DIR") or HOME / ".local/state/roster/announce")
PROC = Path("/proc")
INNE_HOST = os.environ.get("INNE_COMMS_HOST", "hetzner")
SERVER_CONTABO = "Contabo"
SERVER_INNE = "inne Hetzner"
SERVERS = (SERVER_CONTABO, SERVER_INNE)
HARNESSES = ("claude", "codex", "pi", "antigravity", "cursor")
UNKNOWN = "unknown"
ROSTER_TIMEOUT_SECONDS = 20
SSH_TIMEOUT_SECONDS = 90
RECENT_SECONDS = 3 * 86400
TAIL_BYTES = 200_000
FIELD_LIMIT = 60
ROSTER_LINE = re.compile(r"^(?P<name>.+) \((?P<tmux>[^,]+), (?P<harness>[a-z-]+)(?:, (?P<cwd>.*))?\)$")
MP_LINE = re.compile(r"^(?P<name>\S.*?)\{(?P<tmux>live-[0-9a-z-]+)\}\s")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
HOSTNAME = re.compile(r"\b[a-z][a-z0-9-]*(?:\.[a-z0-9-]+)*\.[a-z]{2,24}\b", re.IGNORECASE)
TOKEN = re.compile(r"[A-Za-z0-9_+/=-]{32,}")
SESSION_ID_NAME = re.compile(r"^(?:live-)?[0-9a-f]{16,}(?:-[0-9a-f]+)?$", re.IGNORECASE)
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
REDACTED = "[redacted]"
UNNAMED_CHAT = "unnamed chat"

REMOTE_COLLECTOR = r"""
import glob, json, os, sys
from pathlib import Path

home = Path.home()
registry = {}
for name in glob.glob(str(home / ".claude/sessions/*.json")):
    try:
        record = json.loads(Path(name).read_text())
    except (OSError, ValueError):
        continue
    try:
        os.kill(int(record.get("pid")), 0)
    except (OSError, TypeError, ValueError):
        continue
    if record.get("kind") == "interactive" and record.get("sessionId"):
        registry[record["sessionId"]] = record

transcripts = {}
for name in glob.glob(str(home / ".claude/projects/*/*.jsonl")):
    transcripts[Path(name).stem] = name


def tail(name):
    try:
        with open(name, "rb") as handle:
            handle.seek(0, 2)
            handle.seek(max(0, handle.tell() - 200000))
            return handle.read().decode("utf-8", "replace")
    except OSError:
        return ""


rows = []
for sid, record in registry.items():
    model = effort = None
    for line in tail(transcripts[sid]).splitlines()[1:] if sid in transcripts else []:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        message = entry.get("message")
        if entry.get("type") == "assistant" and isinstance(message, dict) and message.get("model"):
            model, effort = message["model"], entry.get("effort") or message.get("effort")
    rows.append({"name": record.get("name"), "cwd": record.get("cwd"), "harness": "claude",
                 "model": model, "effort": effort})
print(json.dumps(rows))
"""


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value):
    if not isinstance(value, str):
        return UNKNOWN
    text = CONTROL.sub(" ", value).strip().lstrip("*@").strip()
    if SESSION_ID_NAME.match(text):
        return UNNAMED_CHAT
    text = EMAIL.sub(REDACTED, text)
    text = IPV4.sub(REDACTED, text)
    text = HOSTNAME.sub(REDACTED, text)
    text = TOKEN.sub(REDACTED, text)
    text = " ".join(text.split())[:FIELD_LIMIT].strip()
    return text or UNKNOWN


def project_of(cwd):
    if not isinstance(cwd, str):
        return UNKNOWN
    path = cwd.replace("~", str(HOME), 1) if cwd.startswith("~") else cwd
    name = Path(path.rstrip("/")).name or UNKNOWN
    return "home" if Path(path) == HOME else clean(name)


def harness_of(raw):
    name = (raw or "").strip().lower()
    for harness in HARNESSES:
        if name == harness or name.startswith(harness):
            return harness
    if name in ("claude-code", "claudecode"):
        return "claude"
    return UNKNOWN


def chat(name, server, cwd, harness, model, effort):
    return {
        "name": clean(name),
        "server": server,
        "project": project_of(cwd),
        "harness": harness_of(harness),
        "model": clean(model),
        "effort": clean(effort),
    }


def fatal(message):
    print(f"collect-chats: {message}", file=sys.stderr)
    return 1


def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def tail_text(path):
    try:
        with open(path, "rb") as handle:
            handle.seek(0, 2)
            handle.seek(max(0, handle.tell() - TAIL_BYTES))
            body = handle.read().decode("utf-8", "replace")
    except OSError:
        return ""
    lines = body.splitlines()
    return "\n".join(lines[1:]) if lines else ""


def claude_sessions():
    sessions = {}
    for path in glob.glob(str(CLAUDE_SESSIONS / "*.json")):
        try:
            record = json.loads(Path(path).read_text())
        except (OSError, ValueError):
            continue
        if record.get("kind") == "interactive" and record.get("sessionId") and alive(record.get("pid")):
            sessions[record["sessionId"]] = record
    return sessions


def claude_transcripts():
    return {Path(path).stem: path for path in glob.glob(str(CLAUDE_PROJECTS / "*/*.jsonl"))}


def claude_reading(path):
    if path is None:
        return UNKNOWN, UNKNOWN
    model = effort = None
    for line in tail_text(path).splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        message = entry.get("message")
        if entry.get("type") == "assistant" and isinstance(message, dict) and message.get("model"):
            model = message["model"]
            effort = entry.get("effort") or message.get("effort")
    return model or UNKNOWN, effort or UNKNOWN


def announce_by_tmux():
    sessions = {}
    for path in glob.glob(str(ANNOUNCE_DIR / "*.json")):
        try:
            record = json.loads(Path(path).read_text())
        except (OSError, ValueError):
            continue
        tmux = record.get("tmux")
        sid = record.get("sid")
        if isinstance(tmux, str) and isinstance(sid, str):
            sessions[tmux] = sid
    return sessions


def held_session_files(markers, root):
    held = {}
    if not PROC.is_dir():
        return held
    for entry in glob.glob(str(PROC / "[0-9]*")):
        try:
            command = (Path(entry) / "cmdline").read_bytes().decode("utf-8", "replace")
        except OSError:
            continue
        if not any(marker in command for marker in markers):
            continue
        try:
            cwd = os.readlink(Path(entry) / "cwd")
        except OSError:
            continue
        for handle in glob.glob(f"{entry}/fd/*"):
            try:
                target = os.readlink(handle)
            except OSError:
                continue
            if target.startswith(str(root)) and target.endswith(".jsonl"):
                held[cwd] = target
    return held


def recent_files(pattern, seconds=RECENT_SECONDS):
    cutoff = time.time() - seconds
    found = []
    for path in glob.glob(pattern, recursive=True):
        try:
            if os.path.getmtime(path) >= cutoff:
                found.append((os.path.getmtime(path), path))
        except OSError:
            continue
    return [path for _, path in sorted(found, reverse=True)]


def first_json(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return json.loads(handle.readline())
    except (OSError, ValueError):
        return {}


def codex_reading(path):
    model = effort = None
    for line in tail_text(path).splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        payload = entry.get("payload") or {}
        if entry.get("type") == "turn_context" and payload.get("model"):
            model, effort = payload["model"], payload.get("effort")
    return model or UNKNOWN, effort or UNKNOWN


def pi_reading(path):
    model = effort = None
    for line in tail_text(path).splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") == "model_change" and entry.get("modelId"):
            model = entry["modelId"]
        if entry.get("type") == "thinking_level_change" and entry.get("thinkingLevel"):
            effort = entry["thinkingLevel"]
    return model or UNKNOWN, effort or UNKNOWN


def multibot_names():
    names = {}
    try:
        done = subprocess.run([str(MP_SESSIONS_BIN), "list"], capture_output=True, text=True,
                              timeout=ROSTER_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError):
        return names
    for line in done.stdout.splitlines():
        match = MP_LINE.match(line.strip())
        label = (match.group("name") if match else "").lstrip("*@").strip()
        if label and not SESSION_ID_NAME.match(label):
            names[match.group("tmux")] = label
    return names


def contabo_rows():
    try:
        done = subprocess.run([str(ROSTER_BIN)], capture_output=True, text=True,
                              timeout=ROSTER_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    sessions = claude_sessions()
    transcripts = claude_transcripts()
    announced = announce_by_tmux()
    names = multibot_names()
    codex_open = held_session_files(("codex",), CODEX_SESSIONS)
    pi_open = held_session_files(("pi", "/pi/"), PI_SESSIONS)
    rows = []
    for line in done.stdout.splitlines():
        match = ROSTER_LINE.match(line.strip())
        if match is None:
            continue
        harness = harness_of(match.group("harness"))
        cwd = (match.group("cwd") or "").replace("~", str(HOME), 1)
        session_id = announced.get(match.group("tmux"))
        if harness == "claude":
            path = transcripts.get(session_id) if session_id in sessions else None
            model, effort = claude_reading(path)
        elif harness == "codex":
            model, effort = codex_reading(codex_open[cwd]) if cwd in codex_open else (UNKNOWN, UNKNOWN)
        elif harness == "pi":
            model, effort = pi_reading(pi_open[cwd]) if cwd in pi_open else (UNKNOWN, UNKNOWN)
        else:
            model, effort = UNKNOWN, UNKNOWN
        name = names.get(match.group("tmux")) or match.group("name")
        rows.append(chat(name, SERVER_CONTABO, cwd, harness, model, effort))
    return rows


def inne_rows():
    try:
        done = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=10", INNE_HOST,
             "sudo -n -u inne -H bash -lc 'python3 -'"],
            input=REMOTE_COLLECTOR, capture_output=True, text=True, timeout=SSH_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    try:
        records = json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None
    return [chat(record.get("name"), SERVER_INNE, record.get("cwd"), record.get("harness"),
                 record.get("model"), record.get("effort")) for record in records]


def snapshot(rows_by_server, collected_at):
    servers = []
    chats = []
    for server in SERVERS:
        rows = rows_by_server.get(server)
        servers.append({
            "server": server,
            "state": "live" if rows is not None else "not-connected",
            "collectedAt": collected_at[server] if rows is not None else None,
        })
        chats.extend(rows or [])
    return {
        "generatedAt": now_iso(),
        "servers": servers,
        "chats": sorted(chats, key=lambda row: (SERVERS.index(row["server"]), row["name"].lower())),
    }


def main(argv):
    parser = argparse.ArgumentParser(description="Write the live chat roster for both servers.")
    parser.add_argument("--out", required=True, help="the JSON file to write")
    arguments = parser.parse_args(argv)
    collected_at = {}
    rows_by_server = {}
    for server, collect in ((SERVER_CONTABO, contabo_rows), (SERVER_INNE, inne_rows)):
        rows = collect()
        rows_by_server[server] = rows
        if rows is not None:
            collected_at[server] = now_iso()
        else:
            print(f"collect-chats: {server} is not readable, so it is reported as not connected", file=sys.stderr)
    body = snapshot(rows_by_server, collected_at)
    if not body["chats"]:
        return fatal("no server answered, so the snapshot would be empty. Fix: check the roster and the inne route.")
    out = Path(arguments.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    scratch = out.with_suffix(out.suffix + ".tmp")
    scratch.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    scratch.replace(out)
    print(f"chats: {len(body['chats'])} live chats, {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

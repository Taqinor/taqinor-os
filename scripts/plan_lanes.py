#!/usr/bin/env python3
"""Maximally-parallel lane planner for ``work on the plan`` runs.

The plan files (``docs/PLAN.md`` / ``docs/PLAN2.md`` / ``docs/ERROR_PLAN.md`` /
``docs/WEB_PLAN.md``) hold a long backlog. A run must NOT walk it top-down —
consecutive tasks live in the same category, touch the same app, and collapse
into one serial lane. The win is the opposite: pick a **maximally-parallel,
cross-category frontier** so up to ``--max-lanes`` truly-independent tasks build
at once, longest dependency chains first, slots refilled continuously.

This script reads a plan file and prints exactly that schedule. It is an
orchestration aid for the run, not a CI gate: nothing imports it and it lives
under ``scripts/`` (excluded from both CODEMAP fingerprints and the stage-name
scan), so it never affects a merge.

What it does
------------
For every unchecked ``[ ]`` BUILD-QUEUE task it derives:

* **lane key** -- the owned file-set, i.e. the backend app two tasks would
  collide on (``apps/crm``, ``apps/ventes`` ...). Tasks sharing a lane key run
  in sequence; different lane keys run in parallel. Derivation order (first
  hit wins, so precision is opt-in):

  1. an explicit ``@lane: <key>`` / ``@files: a/b.py, c/d.py`` tag on the task;
  2. an ``apps/<x>`` named in the nearest ``###``/``##`` header, or a
     ``<!-- lane: <key> -->`` comment placed under a header;
  3. file paths / ``app.Model`` dotted names cited in the task's backticks;
  4. a domain keyword in the section name or task text;
  5. else ``UNASSIGNED`` (``--check`` flags these so coverage can reach 100 %).

* **gate** -- ``ROUTINE``/``SCHEMA`` are buildable unattended; ``ARCH`` /
  ``DECISION`` / ``AUTH`` / ``COST`` / ``GALLERY`` and a non-pre-approved
  ``DEP:<lib>`` are stop-and-ask (skipped + flagged, never auto-built).

* **deps** -- explicit ``@after:<ID>`` and resolvable ``DEP:<...ID>`` edges, so
  a dependent task is held back to a later wave.

It then builds lanes, orders them longest-first (a list-scheduling / critical-
path heuristic -- start the long chains early so they don't tail the run), and
emits a wave plan where each wave holds one head per lane, up to ``--max-lanes``
distinct lanes. Tasks inside a lane stay sequential across waves.

Pure Python standard library; no third-party dependency.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLAN = ROOT / "docs" / "PLAN.md"

# ``- [ ] N14 — …`` / ``- [x] **A1 — …`` / ``- [BLOCKED: …] N26 — …``
_TASK_LIST_RE = re.compile(
    r"^\s*- \[(?P<status>[^\]]*)\]\s+\*{0,2}(?P<id>[A-Z]+\d+)\b\*{0,2}\s+—\s+(?P<label>.*)$"
)
# ``### T3 — Bulk actions on leads — [x]`` (header task with a trailing box)
_TASK_HEADER_RE = re.compile(
    r"^#{2,4}\s+(?P<id>[A-Z]+\d+)\s+—\s+(?P<label>.*?)\s+—\s+\[(?P<status>[^\]]*)\]"
)

# Sections whose tasks are never auto-built (kept out of the schedule entirely).
_NON_QUEUE_SECTION = re.compile(
    r"^#{1,3}\s+(GATED|MANUAL|DONE LOG|ALREADY LIVE)\b", re.IGNORECASE
)

# Stop-and-ask gate keywords (a task carrying any of these is skipped + flagged).
GATED_KEYWORDS = {"ARCH", "DECISION", "AUTH", "COST", "GALLERY"}

# Dependencies the founder pre-approved in the STANDING RULES -- a DEP on one of
# these is NOT a blocker.
PRE_APPROVED_DEPS = {
    "openpyxl", "leaflet", "celery", "celery-beat", "celerybeat", "beat",
    "brevo", "pyotp", "pywebpush", "vite-plugin-pwa", "pwa",
}

# An ``apps/<x>`` reference anywhere in a header or backtick.
_APP_PATH_RE = re.compile(r"\bapps/([a-z_][a-z0-9_]*)")
# A bare-app reference such as ``notifications/models.py`` or ``records.Attachment``.
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_FILE_REF_RE = re.compile(r"([a-z_][a-z0-9_]*)/[A-Za-z0-9_./]+\.(?:py|jsx?|html|css)")
_DOTTED_REF_RE = re.compile(r"\b([a-z_][a-z0-9_]*)\.[A-Z][A-Za-z0-9_]+")
_LANE_COMMENT_RE = re.compile(r"<!--\s*lanes?:\s*(?P<key>[^>]+?)\s*-->", re.IGNORECASE)
_AT_LANE_RE = re.compile(r"@(?:lane|files):\s*(?P<key>[^@()\n]+)", re.IGNORECASE)
_AFTER_RE = re.compile(r"@after:\s*(?P<ids>[A-Z0-9,\s-]+)", re.IGNORECASE)
_GATE_TOKEN_RE = re.compile(r"\b(ROUTINE|SCHEMA|ARCH|DECISION|AUTH|COST|GALLERY)\b")
_DEP_TOKEN_RE = re.compile(r"DEP:\s*([A-Za-z0-9_-]+)")
_TASK_ID_RE = re.compile(r"([A-Z]{1,6}\d{1,4})")

# Known backend app names (so a dotted ``records.Attachment`` resolves cleanly).
KNOWN_APPS = {
    "crm", "ventes", "stock", "installations", "sav", "reporting", "parametres",
    "authentication", "roles", "records", "core", "notifications", "automation",
    "audit", "dataimport", "publicapi", "contact", "customfields", "paie",
    "compta", "gestion_projet", "ged", "flotte", "qhse", "contrats", "kb",
    "litiges",
}

# Section-name -> lane fallback (for domain-named FG/N sections without apps/…).
SECTION_NAME_LANE = [
    ("crm", "apps/crm"),
    ("ventes", "apps/ventes"),
    ("facturation", "apps/ventes"),
    ("stock", "apps/stock"),
    ("procurement", "apps/stock"),
    ("installation", "apps/installations"),
    ("field execution", "apps/installations"),
    ("outillage", "apps/installations"),
    ("chantier", "apps/installations"),
    ("sav", "apps/sav"),
    ("parc", "apps/sav"),
    ("maintenance", "apps/sav"),
    ("monitoring", "apps/sav"),
    ("reporting", "apps/reporting"),
    ("analytics", "apps/reporting"),
    ("custom field", "apps/reporting"),
    ("paramètres", "apps/parametres"),
    ("rbac", "apps/parametres"),
    ("auth", "apps/parametres"),
    ("transversal", "apps/notifications"),
    ("notification", "apps/notifications"),
    ("automation", "apps/notifications"),
    ("scheduling", "apps/notifications"),
    ("integration", "apps/publicapi"),
    ("public api", "apps/publicapi"),
    ("webhook", "apps/publicapi"),
    ("ocr", "apps/publicapi"),
    ("comptab", "apps/compta"),
    ("finance", "apps/compta"),
    ("trésorerie", "apps/compta"),
    ("rh", "apps/rh"),
    ("hse", "apps/qhse"),
    ("croissance", "apps/crm"),
    ("marketing", "apps/crm"),
    ("portail", "apps/crm"),
    ("solaire", "apps/ventes"),
    ("opérations", "apps/installations"),
    ("supply-chain", "apps/stock"),
    ("logistique", "apps/stock"),
    ("flotte", "apps/flotte"),
    ("qualité", "apps/qhse"),
    ("plateforme", "apps/core"),
    ("mobile", "frontend"),
    ("bi", "apps/reporting"),
]

# Domain keywords in the task text itself (most specific first).
KEYWORD_LANE = [
    (r"\bpaie\b|bulletin|salaire|cnss|cimr|\bir\b", "apps/paie"),
    (r"comptab|écriture|grand livre|\bbalance\b|\bfec\b|\bcgnc\b", "apps/compta"),
    (r"\bcrm\b|\blead\b|prospect|pipeline|kanban", "apps/crm"),
    (r"devis|facture|avoir|paiement|encaiss|échéanc|acompte|\bdevise\b", "apps/ventes"),
    (r"stock|produit|inventaire|fournisseur|réception|approvision|réappro", "apps/stock"),
    (r"chantier|installation|intervention|\bpose\b|outillage|technici|terrain", "apps/installations"),
    (r"\bsav\b|ticket|maintenance|garantie|équipement|equipement|\bparc\b", "apps/sav"),
    (r"reporting|dashboard|tableau de bord|analytics|\bkpi\b|champ personnalis", "apps/reporting"),
    (r"rôle|permission|\brbac\b|sécurité|utilisateur|\b2fa\b|mot de passe", "apps/parametres"),
    (r"notification|automatis|digest|\bbeat\b|relance|scheduling", "apps/notifications"),
    (r"attachment|pièce jointe|@mention|\btag\b|chatter", "apps/records"),
]


def _norm_lane(raw: str) -> str:
    """Normalise a derived lane key to a single comparable token."""
    raw = raw.strip().strip(",").strip()
    if not raw:
        return ""
    # ``@files: apps/crm/models.py, …`` -> the owning app of the first path.
    first = raw.split(",")[0].strip()
    m = _APP_PATH_RE.search(first)
    if m:
        return f"apps/{m.group(1)}"
    if first in KNOWN_APPS:
        return f"apps/{first}"
    seg = first.split("/")[0]
    if seg in KNOWN_APPS:
        return f"apps/{seg}"
    return first


def _lane_from_refs(label: str) -> str:
    """Derive a lane from file paths / ``app.Model`` names in backticks."""
    votes: dict[str, int] = {}
    for span in _BACKTICK_RE.findall(label):
        m = _APP_PATH_RE.search(span)
        if m:
            votes[f"apps/{m.group(1)}"] = votes.get(f"apps/{m.group(1)}", 0) + 3
            continue
        fm = _FILE_REF_RE.search(span)
        if fm and fm.group(1) in KNOWN_APPS:
            key = f"apps/{fm.group(1)}"
            votes[key] = votes.get(key, 0) + 2
        dm = _DOTTED_REF_RE.search(span)
        if dm and dm.group(1) in KNOWN_APPS:
            key = f"apps/{dm.group(1)}"
            votes[key] = votes.get(key, 0) + 1
    if not votes:
        return ""
    return max(votes, key=lambda k: (votes[k], k))


def _lane_from_keywords(text: str) -> str:
    low = text.lower()
    for pattern, lane in KEYWORD_LANE:
        if re.search(pattern, low):
            return lane
    return ""


def _section_lane(headers: dict[str, str]) -> str:
    """Lane from the nearest section header / lane comment."""
    for level in ("###", "##"):
        head = headers.get(level, "")
        if not head:
            continue
        m = _APP_PATH_RE.search(head)
        if m:
            return f"apps/{m.group(1)}"
    comment = headers.get("comment", "")
    if comment:
        return _norm_lane(comment)
    for level in ("###", "##"):
        low = headers.get(level, "").lower()
        for needle, lane in SECTION_NAME_LANE:
            if needle in low:
                return lane
    return ""


def _classify_gate(label: str) -> tuple[str, list[str]]:
    """Return ('buildable'|'gated', [reasons])."""
    reasons: list[str] = []
    tokens = {t.upper() for t in _GATE_TOKEN_RE.findall(label)}
    hard = tokens & GATED_KEYWORDS
    if hard:
        reasons += sorted(hard)
    for dep in _DEP_TOKEN_RE.findall(label):
        # A DEP that names another task id is a dependency edge, not a gate.
        if _TASK_ID_RE.search(dep):
            continue
        if dep.lower() in PRE_APPROVED_DEPS:
            continue
        reasons.append(f"DEP:{dep}")
    return ("gated" if reasons else "buildable"), reasons


def _deps(label: str) -> set[str]:
    """Explicit dependency task-ids (@after:… and resolvable DEP:…ID)."""
    out: set[str] = set()
    for chunk in _AFTER_RE.findall(label):
        out.update(_TASK_ID_RE.findall(chunk.upper()))
    for dep in _DEP_TOKEN_RE.findall(label):
        out.update(_TASK_ID_RE.findall(dep))
    return out


def parse_tasks(path: Path) -> list[dict]:
    """Parse every unchecked BUILD-QUEUE task with its derived lane + gate."""
    headers = {"##": "", "###": "", "comment": ""}
    in_non_queue = False
    tasks: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("## ") or raw.startswith("# "):
            headers["##"] = raw
            headers["###"] = ""
            headers["comment"] = ""
            in_non_queue = bool(_NON_QUEUE_SECTION.match(raw))
            continue
        if raw.startswith("### "):
            headers["###"] = raw
            headers["comment"] = ""
            in_non_queue = bool(_NON_QUEUE_SECTION.match(raw))
            continue
        lane_comment = _LANE_COMMENT_RE.search(raw)
        if lane_comment:
            headers["comment"] = lane_comment.group("key")
            continue
        if in_non_queue:
            continue
        m = _TASK_LIST_RE.match(raw) or _TASK_HEADER_RE.match(raw)
        if not m:
            continue
        status = m.group("status").strip()
        if status.lower() != "":  # only the truly-open "[ ]" tasks
            continue
        label = m.group("label")
        # Lane derivation: explicit tag -> section -> refs -> keyword.
        at = _AT_LANE_RE.search(label)
        lane = _norm_lane(at.group("key")) if at else ""
        lane = lane or _section_lane(headers) or _lane_from_refs(label)
        lane = lane or _lane_from_keywords(headers.get("###", "")) or _lane_from_keywords(label)
        gate, reasons = _classify_gate(label)
        tasks.append({
            "id": m.group("id"),
            "lane": lane or "UNASSIGNED",
            "gate": gate,
            "gate_reasons": reasons,
            "deps": sorted(_deps(label)),
            "section": (headers["###"] or headers["##"]).lstrip("# ").strip(),
        })
    return tasks


def schedule(tasks: list[dict], max_lanes: int) -> dict:
    """Build lanes and a cross-category, longest-lane-first wave plan."""
    buildable = [t for t in tasks if t["gate"] == "buildable" and t["lane"] != "UNASSIGNED"]
    gated = [t for t in tasks if t["gate"] == "gated"]
    unassigned = [t for t in tasks if t["lane"] == "UNASSIGNED" and t["gate"] == "buildable"]

    # Group buildable tasks into lanes, preserving plan order within a lane.
    lanes: dict[str, list[dict]] = {}
    for t in buildable:
        lanes.setdefault(t["lane"], []).append(t)
    # Longest lane first => start the long chains early (critical-path heuristic).
    lane_order = sorted(lanes, key=lambda k: (-len(lanes[k]), k))

    buildable_ids = {t["id"] for t in buildable}
    scheduled: set[str] = set()
    cursor = {k: 0 for k in lanes}
    waves: list[list[dict]] = []
    while any(cursor[k] < len(lanes[k]) for k in lanes):
        wave: list[dict] = []
        for k in lane_order:
            if len(wave) >= max_lanes:
                break
            i = cursor[k]
            if i >= len(lanes[k]):
                continue
            head = lanes[k][i]
            # Hold a task back only on an *intra-batch* dependency not yet placed.
            pending = [d for d in head["deps"] if d in buildable_ids and d not in scheduled]
            if pending:
                continue
            wave.append(head)
        if not wave:  # remaining heads all blocked by each other -> emit as-is
            for k in lane_order:
                if cursor[k] < len(lanes[k]) and len(wave) < max_lanes:
                    wave.append(lanes[k][cursor[k]])
        for t in wave:
            cursor[t["lane"]] += 1
            scheduled.add(t["id"])
        waves.append(wave)

    return {
        "lanes": {k: [t["id"] for t in lanes[k]] for k in lane_order},
        "waves": [[t["id"] for t in w] for w in waves],
        "wave_detail": waves,
        "gated": gated,
        "unassigned": unassigned,
        "counts": {
            "buildable": len(buildable),
            "lanes": len(lanes),
            "waves": len(waves),
            "gated": len(gated),
            "unassigned": len(unassigned),
            "max_parallel": max((len(w) for w in waves), default=0),
        },
    }


def render(plan: dict, max_lanes: int, source: str) -> str:
    c = plan["counts"]
    out = [
        f"# Lane plan for {source}  (max-lanes={max_lanes})",
        "",
        f"{c['buildable']} buildable task(s) across {c['lanes']} independent lane(s) "
        f"-> {c['waves']} wave(s), up to {c['max_parallel']} in parallel.",
        f"{c['gated']} gated (skip + flag), {c['unassigned']} unassigned (need a "
        f"@lane:/@files: tag).",
        "",
        "## Waves (each row builds in parallel; one task per lane)",
    ]
    for n, wave in enumerate(plan["wave_detail"], 1):
        out.append(f"- **Wave {n}** ({len(wave)} parallel):")
        for t in wave:
            deps = f"  after {','.join(t['deps'])}" if t["deps"] else ""
            out.append(f"    - `{t['id']}`  [{t['lane']}]{deps}")
    out += ["", "## Lanes (tasks inside a lane run in sequence)"]
    for lane, ids in plan["lanes"].items():
        out.append(f"- **{lane}** ({len(ids)}): {', '.join(ids)}")
    if plan["gated"]:
        out += ["", "## Gated — skip and flag (never auto-built)"]
        for t in plan["gated"]:
            out.append(f"- `{t['id']}`  ({', '.join(t['gate_reasons'])})")
    if plan["unassigned"]:
        out += ["", "## Unassigned — add a `@lane:`/`@files:` tag for full coverage"]
        for t in plan["unassigned"]:
            out.append(f"- `{t['id']}`  ({t['section'][:60]})")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan maximally-parallel, cross-category lanes for a "
        "'work on the plan' run.",
    )
    parser.add_argument(
        "plan", nargs="?", default=str(DEFAULT_PLAN),
        help="plan file to schedule (default: docs/PLAN.md)",
    )
    parser.add_argument(
        "--max-lanes", type=int, default=8,
        help="worktree ceiling = max tasks to run in parallel per wave "
        "(default 8; raise it on a capable session)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--check", action="store_true",
        help="exit non-zero if any open buildable task is UNASSIGNED",
    )
    args = parser.parse_args(argv)

    path = Path(args.plan)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        print(f"plan file not found: {path}", file=sys.stderr)
        return 2

    tasks = parse_tasks(path)
    plan = schedule(tasks, max(1, args.max_lanes))
    source = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)

    if args.json:
        payload = {k: v for k, v in plan.items() if k != "wave_detail"}
        payload["source"] = source
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render(plan, max(1, args.max_lanes), source))

    if args.check and plan["unassigned"]:
        print(
            f"\n{len(plan['unassigned'])} buildable task(s) have no lane — "
            "add a `@lane:`/`@files:` tag.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

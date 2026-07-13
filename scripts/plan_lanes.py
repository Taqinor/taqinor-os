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

* **category label** -- the task's declared category (``ROUTINE`` / ``SCHEMA``
  / ``ARCH`` / ``DECISION`` / ``AUTH`` / ``COST`` / ``GALLERY`` / ``DEP:<lib>``).
  Per the **FOUNDER STANDING CONSENT (2026-06-21, Reda)** every category is
  buildable — the former auto-skip of ``ARCH``/``DECISION``/``AUTH``/``COST``/
  ``GALLERY``/``DEP`` is **LIFTED**. The planner still LABELS the category for
  visibility (and the DONE LOG must note new paid/external deps, auth changes,
  destructive migrations, or brand-new architecture), but it NEVER gates on it:
  nothing is auto-skipped. A task is only ever held back by a genuine external
  prerequisite the run cannot satisfy (a founder-provisioned credential/secret/
  account) or a conflict with a non-negotiable rule — those are marked
  ``[BLOCKED]`` in the plan, not auto-detected here. See CLAUDE.md.

* **deps** -- explicit ``@after:<ID>`` and resolvable ``DEP:<...ID>`` edges, so
  a dependent task is held back to a later wave.

It then builds lanes, orders them longest-first (a list-scheduling / critical-
path heuristic -- start the long chains early so they don't tail the run), and
emits a wave plan where each wave holds one head per lane, up to ``--max-lanes``
distinct lanes. Tasks inside a lane stay sequential across waves.

Pure Python standard library; no third-party dependency.

Lane assignment is a prose heuristic (regex/keyword matching over the task
text), not real static analysis of the codebase — a surprising grouping
should be sanity-checked by a human before the run trusts it.

SCA3 — build-order gating
--------------------------
If ``docs/BUILD_ORDER.yml`` (SCA1) is present, a task whose id-prefix names a
prerequisite group (an ``after:`` edge) that is under its completion
threshold (measured by ``scripts/plan_progress.py``, SCA2) is refused: it is
moved out of ``buildable`` into a new ``wave_blocked`` bucket with a French
reason listing exactly which prerequisite(s) are short, instead of being
silently scheduled out of order. ``--force-wave`` overrides this and lets the
task through (a founder-consigned escape hatch — every use is logged to
stderr). This is **strictly additive**: with no ``BUILD_ORDER.yml``, or for a
task whose prefix is absent from the file entirely or listed under
``unmapped_ok``, or one with no ``after:`` edge, gating is a pure no-op and
the schedule is byte-identical to before SCA3.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLAN = ROOT / "docs" / "PLAN.md"
DEFAULT_BUILD_ORDER = ROOT / "docs" / "BUILD_ORDER.yml"

# ``- [ ] N14 — …`` / ``- [x] **A1 — …`` / ``- [BLOCKED: …] N26 — …``
_TASK_LIST_RE = re.compile(
    r"^\s*- \[(?P<status>[^\]]*)\]\s+\*{0,2}(?P<id>[A-Z]+\d+)\b\*{0,2}\s+—\s+(?P<label>.*)$"
)
# ``### T3 — Bulk actions on leads — [x]`` (header task with a trailing box)
_TASK_HEADER_RE = re.compile(
    r"^#{2,4}\s+(?P<id>[A-Z]+\d+)\s+—\s+(?P<label>.*?)\s+—\s+\[(?P<status>[^\]]*)\]"
)
# Any raw checklist-style line, used only to detect lines that LOOK like a
# task marker but fail to match either regex above (malformed task) so
# ``parse_tasks``/``--check`` can flag it instead of silently dropping it.
_RAW_CHECKLIST_RE = re.compile(r"^\s*- \[")

# Sections whose tasks are never auto-built (kept out of the schedule entirely).
_NON_QUEUE_SECTION = re.compile(
    r"^#{1,3}\s+(GATED|MANUAL|DONE LOG|ALREADY LIVE)\b", re.IGNORECASE
)

# Category keywords kept ONLY as informational labels. Per the founder standing
# consent (2026-06-21) NONE of these gate any more — every category is buildable
# and nothing is auto-skipped. The set is empty so no keyword is ever treated as
# a stop-and-ask; the labels themselves are still surfaced for visibility.
GATED_KEYWORDS: set[str] = set()

# Category keywords the planner still recognises and LABELS (for the report and
# the DONE-LOG visibility note) -- labelling only, never gating.
LABEL_KEYWORDS = {"ARCH", "DECISION", "AUTH", "COST", "GALLERY"}

# --- Automatic model routing (founder rule: subagents NEVER inherit the
# session model; auto-pick the cheapest tier that fits — CLAUDE.md § model
# selection). An explicit ``@model:haiku|sonnet|opus`` tag on a task wins.
# ``fable`` is deliberately NOT routable here: it is a session-level scalpel
# (1-3 frontier passes when the founder asks to go deep), never a build lane.
_AT_MODEL_RE = re.compile(r"@model:\s*(?P<tier>haiku|sonnet|opus)\b", re.IGNORECASE)
_MODEL_RANK = {"haiku": 0, "sonnet": 1, "opus": 2}

# OPUS — high-risk/judgment lanes ONLY: the rule-#4 quote engine, `core` under
# import-linter contracts, auth/permissions/security surfaces, destructive
# migrations, brand-new cross-app architecture.
_OPUS_LABEL_RE = re.compile(
    r"quote_engine|generate_devis_premium|premium (?:PDF|engine)|R(?:È|E)GLE\s*#?4"
    r"|RULE\s*#?4|import-?linter|\.importlinter|destructive|irr(?:é|e)versible"
    r"|permission|RBAC|role_legacy|IsResponsable|IsAdmin|s(?:é|e)curit(?:é|e)"
    r"|security|\bSSO\b|\bSAML\b|\bJWT\b|\bMFA\b|\b2FA\b|chiffrement|encryption"
    r"|authentification|mot de passe|password|secret",
    re.IGNORECASE,
)
_OPUS_LANES = {"core", "authentication", "identity", "roles"}
_OPUS_ID_PREFIXES = ("YRBAC", "NTSEC", "QPERF")

# HAIKU — clearly mechanical only (scouting, docs, renames, verify-and-skip,
# DC single-source wiring). Conservative on purpose: when in doubt, sonnet.
_HAIKU_LABEL_RE = re.compile(
    r"docs?[ /-]only|README|typo|renomm(?:er|age)|\brename\b|one-?liner"
    r"|v(?:é|e)rifier (?:que|si|seulement)|verify(?:-and-skip| only)"
    r"|d(?:é|e)j(?:à|a) pr(?:é|e)sent|already present|libell(?:é|e)s? seulement"
    r"|wording|cha(?:î|i)ne de caract|comment(?:aire)? seulement",
    re.IGNORECASE,
)
_HAIKU_ID_PREFIXES = ("DC",)


def _model_tier(label: str, lane: str, task_id: str, gate_labels: list[str]) -> str:
    """Cheapest model tier that fits this task (haiku < sonnet < opus)."""
    explicit = _AT_MODEL_RE.search(label)
    if explicit:
        return explicit.group("tier").lower()
    if (
        _OPUS_LABEL_RE.search(label)
        or lane in _OPUS_LANES
        or task_id.upper().startswith(_OPUS_ID_PREFIXES)
        or {"AUTH", "DECISION", "ARCH"} & set(gate_labels)
    ):
        return "opus"
    if _HAIKU_LABEL_RE.search(label) or task_id.upper().startswith(_HAIKU_ID_PREFIXES):
        return "haiku"
    return "sonnet"


# Dependencies the founder long ago pre-approved. Kept for reference; with the
# standing consent a DEP no longer gates regardless of membership here.
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

# Task-id prefix extraction: a compound "FE-XFLT" (dash-joined) lane id, or a
# plain letter prefix ("ARC", "NTPLT", "SCA" ...). Mirrors
# scripts/plan_progress.py's own prefix derivation so a task's wave-gating
# lookup key matches exactly what plan_progress.py counts under.
_TASK_ID_PREFIX_RE = re.compile(r"^(?:([A-Z]+-[A-Z]+)|([A-Z]+))(\d+)")


def _task_prefix(task_id: str) -> str:
    m = _TASK_ID_PREFIX_RE.match(task_id)
    if not m:
        return ""
    return m.group(1) or m.group(2) or ""


def _task_number(task_id: str) -> int | None:
    m = _TASK_ID_PREFIX_RE.match(task_id)
    if not m:
        return None
    return int(m.group(3))


def gated_group_for_task(task_id: str, build_order: dict | None) -> str:
    """The group name to use as ``edge.group`` for THIS task.

    A plain prefix (``NTPLT``, ``FE-XFLT``) resolves to itself. A prefix that
    BUILD_ORDER.yml also splits into numbered-subset aliases (e.g. ``ARC1``
    is noyau, ``ARC3`` is sweep -- both share the bare prefix ``ARC``)
    resolves to whichever alias's ``members`` list contains this task's
    number; falls back to the bare prefix if no alias claims this number
    (e.g. an ARC task numbered outside 1-56's two named subsets).
    """
    prefix = _task_prefix(task_id)
    if not build_order or not prefix:
        return prefix
    number = _task_number(task_id)
    if number is None:
        return prefix
    aliases = build_order.get("aliases") or {}
    for alias_name, alias in aliases.items():
        if not isinstance(alias, dict):
            continue
        if alias.get("prefix") != prefix:
            continue
        members = alias.get("members") or []
        if number in members:
            return alias_name
    return prefix


# ---------------------------------------------------------------------------
# SCA3 — BUILD_ORDER.yml gating (additive; no-op when the file is absent).
# ---------------------------------------------------------------------------
# docs/BUILD_ORDER.yml (SCA1) is written in a deliberately minimal,
# hand-parseable YAML subset (2-space indents, ``key: value`` mappings,
# nested mappings, flow lists ``[a, b, c]``, ``#`` comments, no anchors/tags/
# multiline scalars — see that file's own header for the exact grammar). The
# stage-names CI job has no PyYAML install step, so this reads it with a tiny
# stdlib-only parser rather than a real YAML library.

class _MiniYamlParser:
    """Parses the specific minimal YAML subset BUILD_ORDER.yml is written in.

    NOT a general YAML parser -- deliberately narrow. Supports: ``#``
    comments/blank lines, 2-space-indented nested mappings, scalar values
    (str/int/float, quotes stripped), and flow-style lists
    (``[a, b, c]``/``[]``). Folded scalars (``>-``) are read as opaque prose
    and skipped by the gating logic below (only structural keys matter here).
    """

    def __init__(self, text: str):
        self._lines = self._strip_comments_and_blanks(text)

    @staticmethod
    def _strip_comments_and_blanks(text: str) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        in_fold = False
        fold_indent = -1
        for raw in text.splitlines():
            if not raw.strip():
                continue
            stripped = raw.lstrip(" ")
            indent = len(raw) - len(stripped)
            if in_fold:
                if indent > fold_indent:
                    continue  # folded-scalar continuation line -> skip
                in_fold = False
            if stripped.startswith("#"):
                continue
            # Strip a trailing ``# comment``. Only treat a '#' as starting a
            # comment if it is NOT preceded by an opening quote on this line
            # (BUILD_ORDER.yml never puts a literal '#' inside a quoted
            # value, but comments freely follow list items/scalars that
            # themselves contain quotes earlier in the line, e.g.
            # ``- FG   # legacy "feature gap" numbering...``).
            hash_idx = stripped.find("#")
            if hash_idx != -1:
                before = stripped[:hash_idx]
                if before.count('"') % 2 == 0 and before.count("'") % 2 == 0:
                    stripped = before.rstrip()
                    if not stripped:
                        continue
            if stripped.rstrip().endswith(">-") or stripped.rstrip().endswith("|-"):
                in_fold = True
                fold_indent = indent
            out.append((indent, stripped))
        return out

    @staticmethod
    def _parse_scalar(value: str):
        value = value.strip()
        if not value:
            return None
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            return value[1:-1]
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                return []
            return [_MiniYamlParser._parse_scalar(v) for v in inner.split(",")]
        try:
            if re.fullmatch(r"-?\d+", value):
                return int(value)
            if re.fullmatch(r"-?\d+\.\d+", value):
                return float(value)
        except ValueError:
            pass
        return value

    def parse(self) -> dict:
        pos = 0

        def parse_block(min_indent: int) -> dict:
            nonlocal pos
            node: dict = {}
            while pos < len(self._lines):
                indent, line = self._lines[pos]
                if indent < min_indent:
                    break
                if line.startswith("- "):
                    # a bare list item at this indent belongs to a parent
                    # list context this dict-only entry point doesn't model
                    # -- stop here (only reached for the top-level call;
                    # nested list-of-scalars is handled inside parse_list).
                    break
                if ":" not in line:
                    pos += 1
                    continue
                key, _, rest = line.partition(":")
                key = key.strip()
                rest = rest.strip()
                pos += 1
                if rest in (">-", "|-"):
                    # Folded/literal scalar: prose-only in BUILD_ORDER.yml
                    # (e.g. wave ``description``), its continuation lines
                    # were already dropped by the line preprocessor (only
                    # structural keys matter to the gating logic below) --
                    # store a marker string, never an empty dict, so a
                    # consumer can tell "prose omitted" from "missing key".
                    node[key] = "<folded-scalar-prose-omitted>"
                elif rest == "":
                    # nested mapping OR a list, written as following "- ..."
                    # lines at deeper indent.
                    if pos < len(self._lines) and self._lines[pos][0] > indent \
                            and self._lines[pos][1].startswith("- "):
                        node[key] = parse_list(indent)
                    else:
                        node[key] = parse_block(indent + 1)
                else:
                    node[key] = self._parse_scalar(rest)
            return node

        def parse_list(parent_indent: int) -> list:
            """Parse a sequence of ``- ...`` items at one indent level.

            Each item is either a bare scalar (``- ARC``) or the start of a
            mapping (``- group: ARC-sweep`` followed by sibling
            ``key: value`` lines indented to align with ``group`` -- i.e.
            ``item_indent + 2``, matching how a YAML block-sequence-of-
            -mappings is conventionally indented and how BUILD_ORDER.yml's
            ``edges:`` list is written).
            """
            nonlocal pos
            items: list = []
            while pos < len(self._lines):
                indent, line = self._lines[pos]
                if indent <= parent_indent or not line.startswith("- "):
                    break
                item_indent = indent
                after_dash = line[2:]
                if ":" in after_dash and not after_dash.startswith("["):
                    # mapping-style list item: "- key: value" starts a
                    # mapping whose remaining keys are sibling lines
                    # indented to item_indent + 2 (aligned under "key").
                    # Rewrite this one line as a synthetic "key: value" at
                    # the sibling indent and let parse_block consume it PLUS
                    # every following sibling line in one pass (avoids
                    # double-parsing the first key).
                    sibling_indent = item_indent + 2
                    self._lines[pos] = (sibling_indent, after_dash)
                    entry = parse_block(sibling_indent)
                    items.append(entry)
                else:
                    items.append(self._parse_scalar(after_dash))
                    pos += 1
            return items

        return parse_block(0)


def load_build_order(path: Path) -> dict | None:
    """Load+parse ``docs/BUILD_ORDER.yml``; ``None`` if the file is absent.

    A malformed file raises (loudly) rather than being silently ignored --
    the caller decides whether that should abort gating (it does not; see
    ``build_order_gate`` which treats a *load* failure as "skip gating" but
    prints a warning, matching the SCA3 backward-compatibility contract of
    never blocking a run over a broken/missing optional file).
    """
    if not path.is_file():
        return None
    return _MiniYamlParser(path.read_text(encoding="utf-8")).parse()


def _resolve_alias_prefixes(build_order: dict, name: str) -> set[str]:
    """A prerequisite name in an ``after:`` edge is either a real task-id
    prefix (``NTPLT``) or an alias (``ARC-noyau``) resolving to a subset of
    a real prefix's task numbers. Returns the set of real prefixes this name
    maps to for a plan_progress.py lookup (the numbered-subset distinction
    inside one prefix, e.g. ARC-noyau vs ARC-sweep, is NOT modelled by
    plan_progress.py's per-prefix percentage -- it is treated at the whole-
    prefix granularity, which is the conservative/safe direction: a subset
    alias is gated on the WHOLE prefix's progress, never less strict)."""
    aliases = build_order.get("aliases") or {}
    if name in aliases:
        alias = aliases[name]
        prefix = alias.get("prefix") if isinstance(alias, dict) else None
        return {prefix} if prefix else set()
    return {name}


def build_order_gate(
    task_id: str,
    build_order: dict | None,
    progress_lookup,
) -> list[str]:
    """Return a list of French unmet-prerequisite reasons for ``task_id``
    (empty list = not gated / allowed through).

    ``progress_lookup`` is a callable ``prefix -> pct float`` (normally
    ``scripts.plan_progress.group_pct``, injected so tests can fake it
    without touching real plan files).

    Two distinct group names come into play for one task: the bare id-prefix
    (``ARC``, used for the ``unmapped_ok`` check -- BUILD_ORDER.yml lists
    bare prefixes there) and the *gated group* (``ARC-noyau``/``ARC-sweep``
    when the numbered subset resolves to a member alias, else the same bare
    prefix) used to match an ``edges[].group`` entry -- this is what lets a
    numbered SUBSET of one letter-prefix (the ARC sweep tasks ARC3-5/7/12)
    be gated separately from the rest of that same prefix (the ARC kernel
    tasks) without needing a distinct task-id prefix.

    Backward compatibility (SCA3 contract): returns ``[]`` immediately when
    ``build_order`` is ``None`` (file absent), when ``task_id`` has no
    resolvable prefix, when the bare prefix appears in ``unmapped_ok``, or
    when no wave/edge in the file constrains this task's gated group at all
    -- i.e. the exact set of situations under which a plan file predates
    BUILD_ORDER.yml or simply isn't covered by it.
    """
    task_prefix = _task_prefix(task_id)
    if not build_order or not task_prefix:
        return []
    unmapped_ok = set(build_order.get("unmapped_ok") or [])
    if task_prefix in unmapped_ok:
        return []
    gated_group = gated_group_for_task(task_id, build_order)
    edges = build_order.get("edges") or []
    if not isinstance(edges, list):
        return []
    reasons: list[str] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        if edge.get("group") != gated_group:
            continue
        after = edge.get("after") or {}
        if not isinstance(after, dict):
            continue
        for prereq_name, threshold in after.items():
            try:
                threshold = float(threshold)
            except (TypeError, ValueError):
                continue
            real_prefixes = _resolve_alias_prefixes(build_order, prereq_name)
            # Conservative: the LOWEST progress among the resolved real
            # prefixes must clear the threshold (an alias naming several
            # prefixes is only "ready" once all of them are).
            worst_pct = min(
                (progress_lookup(p) for p in real_prefixes), default=0.0
            )
            if worst_pct < threshold:
                reasons.append(
                    f"{prereq_name} est à {worst_pct:.1f}% (seuil requis {threshold:.0f}%)"
                )
    return reasons


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


# An inline ``@blocked`` tag anywhere in a task body marks it blocked even while
# the checkbox stays ``[ ]`` (see _classify_gate).
_INLINE_BLOCKED_RE = re.compile(r"@blocked\b", re.IGNORECASE)


def _classify_gate(label: str) -> tuple[str, list[str]]:
    """Return ('buildable', [category labels]).

    Founder standing consent (2026-06-21): EVERY category is buildable, so this
    is always 'buildable' and nothing is auto-skipped. The returned list is the
    task's category labels (ARCH/DECISION/AUTH/COST/GALLERY and any DEP:<lib>),
    surfaced for visibility only — the run still notes a new paid/external dep,
    auth change, destructive migration, or brand-new architecture in the DONE
    LOG. ``GATED_KEYWORDS`` is empty, so it can never flip the status to gated.
    """
    labels: list[str] = []
    tokens = {t.upper() for t in _GATE_TOKEN_RE.findall(label)}
    labels += sorted(tokens & LABEL_KEYWORDS)
    for dep in _DEP_TOKEN_RE.findall(label):
        # A DEP that names another task id is a dependency edge, not a label.
        if _TASK_ID_RE.search(dep):
            continue
        labels.append(f"DEP:{dep}")
    # Inline ``@blocked:`` tag on an OPEN task (a founder/DB/rule gate) — exclude
    # it from buildable so it is never handed to a build agent. plan_lanes honours
    # a ``[BLOCKED:]`` CHECKBOX state, but a task can stay ``[ ]`` while carrying an
    # inline ``(@blocked: reason)`` tag in its body. Measured 2026-07-13: a whole
    # 9-task lane (ODX14/15/18/20/22, XACC12/XPOS19/YCASH5, XSAL5/14) was dispatched
    # to a worktree agent only to be returned all-blocked. Treat inline @blocked as
    # gated so it surfaces in the gated bucket with the rest.
    if _INLINE_BLOCKED_RE.search(label):
        return ("gated", labels + ["BLOCKED"])
    # GATED_KEYWORDS is intentionally empty -> never gated. Kept as a guard so a
    # future re-introduction of a gate keyword would still flow through here.
    gated = bool({t.upper() for t in _GATE_TOKEN_RE.findall(label)} & GATED_KEYWORDS)
    return ("gated" if gated else "buildable"), labels


def _deps(label: str) -> set[str]:
    """Explicit dependency task-ids (@after:… and resolvable DEP:…ID)."""
    out: set[str] = set()
    for chunk in _AFTER_RE.findall(label):
        out.update(_TASK_ID_RE.findall(chunk.upper()))
    for dep in _DEP_TOKEN_RE.findall(label):
        out.update(_TASK_ID_RE.findall(dep))
    return out


# --- Task effort/cost (for time-balanced worker packing) -------------------
# The plan tags each task's size inside its category paren, e.g.
# ``(ROUTINE — L, sonnet)`` / ``(SCHEMA — S/M, …)``. We turn that size into a
# relative cost so ``pack_workers`` can bin-pack lanes into N buckets that
# finish at ~the same wall-clock time (the founder rule: 8 parallel agents
# should all land together, not idle waiting on one heavy straggler). A task
# with no size tag defaults to ``M`` — the modal size, so an untagged task is
# never treated as free.
_COST_BY_SIZE = {"S": 1.0, "S/M": 1.5, "M": 2.0, "L": 4.0, "XL": 6.0}
_DEFAULT_COST = _COST_BY_SIZE["M"]
_SIZE_RE = re.compile(
    r"\((?:ROUTINE|SCHEMA|ARCH|AUTH|DECISION|COST|GALLERY|DEP)\b[^)]*?"
    r"[—-]\s*(XL|S/M|S|M|L)\b"
)


def _task_cost(label: str) -> float:
    """Relative effort weight parsed from the task's ``— <size>`` tag."""
    m = _SIZE_RE.search(label)
    return _COST_BY_SIZE.get(m.group(1), _DEFAULT_COST) if m else _DEFAULT_COST


# --- Declared files (for FORCED file-disjoint lanes) -----------------------
# A plan task line ends with ``Files: <path>, <path>, …``. Two tasks that share
# a SUBSTANTIVE file must never be co-scheduled in the same merge-batch (they'd
# collide at fold — the batch-4/shell+design pain). We parse those paths and
# union any lanes that share one, so every emitted lane (hence every packed
# worker) is file-disjoint by construction and folds clean the first time.
_FILE_PATH_RE = re.compile(
    r"[\w./-]+\.(?:py|jsx?|mjs|tsx?|css|html|txt|ya?ml|md)"
)
# Append-only / trivially keep-both shared surfaces: co-scheduling them is safe
# (their conflicts are additive), so they DON'T force a lane merge — otherwise
# index.css alone would collapse half the plan into one serial lane.
_APPEND_ONLY_SUFFIXES = (
    "index.css", "tokens.css", "print.css", "records-panels.css",
    "ui/index.js", "router/index.jsx", "main.jsx", "App.jsx",
    "docs/PLAN.md", "docs/PLAN2.md", "docs/CODEMAP.md",
)


def _is_append_only(path: str) -> bool:
    return any(path.endswith(sfx) for sfx in _APPEND_ONLY_SUFFIXES)


def _task_files(label: str) -> frozenset[str]:
    """Substantive file paths a task declares it will edit (its ``Files:``).

    Only the segment after the LAST ``Files:`` is scanned (paths elsewhere in
    the prose — ``webhooks.py:182`` refs — are ignored), and append-only shared
    surfaces are dropped (they never force a lane merge). Returns an empty set
    when the task declares no files, in which case it falls back to the lane
    heuristic exactly as before (fully backward-compatible).
    """
    idx = label.rfind("Files:")
    if idx < 0:
        idx = label.rfind("Files :")
    if idx < 0:
        return frozenset()
    tail = label[idx:]
    out = set()
    for raw in _FILE_PATH_RE.findall(tail):
        p = raw.strip("`'\" ")
        if p and not _is_append_only(p):
            out.add(p)
    return frozenset(out)


def pack_workers(
    lanes: dict[str, list[dict]], lane_order: list[str], n_workers: int,
) -> tuple[list[dict], dict[str, float]]:
    """Bin-pack whole lanes into ``n_workers`` time-balanced buckets (LPT).

    One bucket = one dispatched agent that drains ALL its lanes in sequence.
    Longest-processing-time-first (heaviest lane → currently-lightest bucket)
    is the classic 4/3-optimal greedy for makespan minimisation, so the 8
    agents finish at approximately the same time instead of one carrying a
    9-task lane while another carries a 1-task lane. A lane is never split
    across agents (it owns files that must build in sequence).
    """
    lane_cost = {k: sum(t["cost"] for t in lanes[k]) for k in lane_order}
    workers = [{"lanes": [], "tasks": [], "cost": 0.0} for _ in range(max(1, n_workers))]
    # Heaviest lane first; ties broken by name for deterministic output.
    for k in sorted(lane_order, key=lambda k: (-lane_cost[k], k)):
        w = min(workers, key=lambda w: (w["cost"], len(w["lanes"])))
        w["lanes"].append(k)
        w["tasks"].extend(t["id"] for t in lanes[k])
        w["cost"] = round(w["cost"] + lane_cost[k], 3)
    # Drop empty buckets (fewer lanes than workers) and order heaviest-first.
    workers = [w for w in workers if w["lanes"]]
    workers.sort(key=lambda w: (-w["cost"], w["lanes"][0]))
    return workers, lane_cost


def pack_pipelined_waves(
    lanes: dict[str, list[dict]],
    lane_order: list[str],
    n_workers: int,
    wave_size: int,
) -> list[list[dict]]:
    """Partition file-disjoint lanes into a SEQUENCE of pipelinable waves.

    Each wave is ``n_workers`` time-balanced agents draining ~``wave_size``
    tasks total (so a wave = one merge-batch). Because every lane is already
    file-disjoint (``_merge_lanes_by_shared_files``), *any* two lanes — and
    therefore any two waves — touch no common file: **wave K+1 can be BUILT
    while wave K runs its tests + CI**, and folds clean on top of it. Waves are
    filled heaviest-lane-first (long chains start early) and LPT-balanced inside
    each wave so its agents finish together. Returns ``[[worker, …], …]`` —
    one inner list per wave, each worker a ``{lanes, tasks, cost}`` bundle.

    The orchestrator work-steals across the soft wave boundary: when a wave-K
    agent finishes early it pulls the heaviest not-yet-started lane of wave K+1,
    so the pipeline never idles and successive waves stay length-balanced.
    """
    lane_cost = {k: sum(t["cost"] for t in lanes[k]) for k in lane_order}
    pending = sorted(lane_order, key=lambda k: (-len(lanes[k]), -lane_cost[k], k))
    waves: list[list[dict]] = []
    while pending:
        workers = [{"lanes": [], "tasks": [], "cost": 0.0}
                   for _ in range(max(1, n_workers))]
        wave_tasks = 0
        leftover: list[str] = []
        for k in pending:
            # Fill a wave until it holds ~wave_size tasks; defer the rest. A
            # single lane never spills across waves (it stays whole).
            if wave_tasks >= wave_size:
                leftover.append(k)
                continue
            w = min(workers, key=lambda w: (w["cost"], len(w["lanes"])))
            w["lanes"].append(k)
            w["tasks"].extend(t["id"] for t in lanes[k])
            w["cost"] = round(w["cost"] + lane_cost[k], 3)
            wave_tasks += len(lanes[k])
        workers = [w for w in workers if w["lanes"]]
        workers.sort(key=lambda w: (-w["cost"], w["lanes"][0]))
        waves.append(workers)
        pending = leftover
    return waves


def parse_tasks(path: Path) -> list[dict]:
    """Parse every unchecked BUILD-QUEUE task with its derived lane + gate.

    As a side effect, warns to stderr (once per line) about any ``- [`` line
    that fails to match BOTH ``_TASK_LIST_RE`` and ``_TASK_HEADER_RE`` — today
    such a malformed line simply vanishes from the schedule with no
    diagnostic, which lets a typo'd task silently never get built.
    """
    headers = {"##": "", "###": "", "comment": ""}
    in_non_queue = False
    tasks: list[dict] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
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
            if _RAW_CHECKLIST_RE.match(raw):
                print(
                    f"WARNING: malformed task line at {path}:{lineno} — "
                    f"looks like a checklist item but matches neither task "
                    f"regex: {raw.strip()!r}",
                    file=sys.stderr,
                )
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
            "prefix": _task_prefix(m.group("id")),
            "lane": lane or "UNASSIGNED",
            "gate": gate,
            "gate_reasons": reasons,
            "deps": sorted(_deps(label)),
            "section": (headers["###"] or headers["##"]).lstrip("# ").strip(),
            "model": _model_tier(label, lane or "UNASSIGNED", m.group("id"), reasons),
            "cost": _task_cost(label),
            "files": sorted(_task_files(label)),
        })
    return tasks


def apply_build_order_gate(
    tasks: list[dict],
    build_order: dict | None,
    progress_lookup,
    force_wave: bool = False,
) -> tuple[list[dict], list[dict]]:
    """SCA3 — split ``tasks`` into ``(allowed, wave_blocked)``.

    A task is *wave-blocked* when its id-prefix names a ``BUILD_ORDER.yml``
    edge whose prerequisite(s) are under threshold. ``force_wave=True`` lets
    every task through unchanged (the founder-consigned escape hatch) but
    each override is logged to stderr by the caller (``main``), not here, so
    this function stays silent/pure and unit-testable.

    Backward compatible by construction: ``build_order_gate`` (see above)
    already returns ``[]`` for every situation that predates SCA3 (no file,
    unmapped prefix, no edge) — this function is a thin wrapper that reuses
    exactly that no-op contract, so with no BUILD_ORDER.yml the return is
    always ``(tasks, [])``, i.e. the previous, ungated behaviour.
    """
    if force_wave or not build_order:
        return tasks, []
    allowed: list[dict] = []
    blocked: list[dict] = []
    for t in tasks:
        reasons = build_order_gate(t.get("id", ""), build_order, progress_lookup)
        if reasons:
            blocked.append({**t, "wave_block_reasons": reasons})
        else:
            allowed.append(t)
    return allowed, blocked


def count_malformed(path: Path) -> int:
    """Count ``- [`` lines that fail to match either task regex.

    Used by ``--check`` as a second, independent coverage signal alongside
    "unassigned lane": a line can match a task regex fine but still resolve
    to ``UNASSIGNED`` (caught elsewhere), or it can fail to match a task
    regex AT ALL and vanish from the schedule entirely (caught here). Reuses
    ``_RAW_CHECKLIST_RE`` / ``_TASK_LIST_RE`` / ``_TASK_HEADER_RE`` — no
    parsing state (headers/non-queue sections) needed since a malformed line
    is malformed regardless of the section it lives in.
    """
    malformed = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not _RAW_CHECKLIST_RE.match(raw):
            continue
        if _TASK_LIST_RE.match(raw) or _TASK_HEADER_RE.match(raw):
            continue
        malformed += 1
    return malformed


def _merge_lanes_by_shared_files(
    lanes: dict[str, list[dict]],
) -> tuple[dict[str, list[dict]], list[tuple[str, str, str]]]:
    """Union lanes that share a substantive declared file (union-find).

    Returns ``(merged_lanes, merges)`` where ``merges`` is a list of
    ``(file, lane_a, lane_b)`` triples for the report. The merged lane keeps the
    heaviest constituent lane's key and preserves each task's original plan
    order (tasks are re-sorted by their (section-stable) appearance). Idempotent
    and a no-op when no two lanes share a file.
    """
    parent = {k: k for k in lanes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # file -> the lanes that declare it (substantive files only; see _task_files)
    file_to_lanes: dict[str, list[str]] = {}
    for lk, ts in lanes.items():
        for t in ts:
            for f in t.get("files", ()):
                file_to_lanes.setdefault(f, []).append(lk)

    merges: list[tuple[str, str, str]] = []
    for f, lks in file_to_lanes.items():
        uniq = sorted(set(lks))
        for other in uniq[1:]:
            if find(uniq[0]) != find(other):
                merges.append((f, find(uniq[0]), find(other)))
            union(uniq[0], other)

    if not merges:
        return lanes, []

    # Rebuild lanes under their representative; keep a stable per-task order by
    # remembering the original index a task had inside its lane + lane order.
    order = {lk: i for i, lk in enumerate(lanes)}
    merged: dict[str, list[tuple[int, int, dict]]] = {}
    for lk, ts in lanes.items():
        root = find(lk)
        for i, t in enumerate(ts):
            merged.setdefault(root, []).append((order[lk], i, t))
    out: dict[str, list[dict]] = {}
    for root, triples in merged.items():
        triples.sort(key=lambda x: (x[0], x[1]))
        lane_tasks = []
        for _, _, t in triples:
            # Relabel to the merged root so the wave scheduler's cursor (keyed by
            # ``t["lane"]``) and lane_models resolve to the merged lane.
            t["lane"] = root
            lane_tasks.append(t)
        out[root] = lane_tasks
    return out, merges


def schedule(
    tasks: list[dict],
    max_lanes: int,
    wave_blocked: list[dict] | None = None,
    n_workers: int | None = None,
    wave_size: int = 80,
) -> dict:
    """Build lanes and a cross-category, longest-lane-first wave plan.

    ``wave_blocked`` (SCA3, optional -- defaults to none, so existing callers
    that never pass it get byte-identical behaviour to pre-SCA3) is a list of
    tasks already removed from ``tasks`` by ``apply_build_order_gate`` for
    carrying a French unmet-prerequisite reason on each entry
    (``wave_block_reasons``); it is surfaced in the returned plan/counts and
    rendered as its own section, but never re-added to ``buildable``.
    """
    wave_blocked = wave_blocked or []
    buildable = [t for t in tasks if t["gate"] == "buildable" and t["lane"] != "UNASSIGNED"]
    gated = [t for t in tasks if t["gate"] == "gated"]
    unassigned = [t for t in tasks if t["lane"] == "UNASSIGNED" and t["gate"] == "buildable"]

    # Group buildable tasks into lanes, preserving plan order within a lane.
    lanes: dict[str, list[dict]] = {}
    for t in buildable:
        lanes.setdefault(t["lane"], []).append(t)

    # FORCE FILE-DISJOINT LANES: union any two lanes whose tasks share a
    # substantive declared file, so no merge-batch ever co-schedules two lanes
    # that would collide at fold (the batch-4 / shell+design lesson). Append-only
    # shared surfaces (index.css, ui/index.js…) are already excluded from
    # ``files`` so they never collapse parallelism. Tasks with no ``Files:`` are
    # untouched → byte-identical to the pre-file behaviour for those.
    lanes, file_merges = _merge_lanes_by_shared_files(lanes)

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

    # One lane = ONE dispatched agent, so the lane's model is the highest tier
    # any of its tasks needs (a cheaper builder never lowers the risk bar).
    lane_models = {
        k: max((t["model"] for t in lanes[k]), key=_MODEL_RANK.__getitem__)
        for k in lane_order
    }
    model_counts = {tier: 0 for tier in _MODEL_RANK}
    for t in buildable:
        model_counts[t["model"]] += 1

    # Time-balanced worker buckets: pack whole lanes into <= n_workers agents
    # so all finish at ~the same wall-clock time (default: the same ceiling as
    # the per-wave parallelism, i.e. one agent per worker).
    workers, lane_costs = pack_workers(
        lanes, lane_order, n_workers if n_workers is not None else max_lanes,
    )

    def _emit_workers(ws):
        return [
            {
                "lanes": w["lanes"],
                "tasks": w["tasks"],
                "cost": round(w["cost"], 3),
                "model": max(
                    (lane_models[k] for k in w["lanes"]),
                    key=_MODEL_RANK.__getitem__,
                ),
            }
            for w in ws
        ]

    worker_out = _emit_workers(workers)

    # Pipelined merge-batches: a sequence of ~wave_size-task waves, each of
    # n_workers file-disjoint time-balanced agents. Wave K+1 is built while
    # wave K tests/CIs (lanes are globally file-disjoint → waves never collide).
    n_agents = n_workers if n_workers is not None else max_lanes
    pipe = pack_pipelined_waves(lanes, lane_order, n_agents, max(1, wave_size))
    pipelined = [
        {
            "wave": i + 1,
            "tasks_total": sum(len(w["tasks"]) for w in wave),
            "agents": _emit_workers(wave),
        }
        for i, wave in enumerate(pipe)
    ]

    return {
        "lanes": {k: [t["id"] for t in lanes[k]] for k in lane_order},
        "lane_models": lane_models,
        "lane_costs": {k: round(v, 3) for k, v in lane_costs.items()},
        "workers": worker_out,
        "pipelined_waves": pipelined,
        "waves": [[t["id"] for t in w] for w in waves],
        "wave_detail": waves,
        "gated": gated,
        "unassigned": unassigned,
        "wave_blocked": wave_blocked,
        "counts": {
            "buildable": len(buildable),
            "lanes": len(lanes),
            "waves": len(waves),
            "gated": len(gated),
            "unassigned": len(unassigned),
            "wave_blocked": len(wave_blocked),
            "max_parallel": max((len(w) for w in waves), default=0),
            "models": model_counts,
            "workers": len(worker_out),
            "makespan_cost": max((w["cost"] for w in worker_out), default=0.0),
            "total_cost": round(sum(lane_costs.values()), 3),
            "file_merges": len(file_merges),
            "pipelined_waves": len(pipelined),
            "wave_size": max(1, wave_size),
        },
        "file_merges": file_merges,
    }


def render(plan: dict, max_lanes: int, source: str) -> str:
    c = plan["counts"]
    out = [
        f"# Lane plan for {source}  (max-lanes={max_lanes})",
        "",
        f"{c['buildable']} buildable task(s) across {c['lanes']} independent lane(s) "
        f"-> {c['waves']} wave(s), up to {c['max_parallel']} in parallel.",
        f"{c['gated']} gated (auto-gating is OFF — every category builds; this "
        f"stays 0 by design), {c['unassigned']} unassigned (need a "
        f"@lane:/@files: tag).",
        f"Model mix (auto-routed; `@model:` tag overrides): "
        f"{c['models']['haiku']} haiku / {c['models']['sonnet']} sonnet / "
        f"{c['models']['opus']} opus — dispatch each lane's Agent with the "
        f"lane's `model=` below (founder rule: never inherit the session model).",
        "",
        f"## Workers ({c['workers']} time-balanced agents — dispatch ONE per row; "
        f"each drains its lanes in sequence)",
        f"Effort is bin-packed (LPT) so all agents finish together: "
        f"makespan ~{c['makespan_cost']:g} vs total {c['total_cost']:g} "
        f"(size cost S=1/M=2/L=4/XL=6; untagged=M).",
        f"File-disjoint: {c['file_merges']} lane-pair(s) merged on a shared "
        f"declared file, so every worker folds clean (append-only surfaces like "
        f"index.css exempt).",
    ]
    for n, w in enumerate(plan.get("workers", []), 1):
        lanes_desc = ", ".join(
            f"{lk}[{'/'.join(plan['lanes'][lk])}]" for lk in w["lanes"]
        )
        out.append(
            f"- **Agent {n}** (model={w['model']}, cost~{w['cost']:g}, "
            f"{len(w['tasks'])} task(s)): {lanes_desc}"
        )
    # Founder band: a lane should hold ~5-15 tasks. An oversized lane (often the
    # product of file-merges) serializes one agent far past its wave-mates and
    # defeats the time balance — surface it so the plan can split it via @lane:
    # tags (or accept the imbalance knowingly).
    oversized = {k: len(ids) for k, ids in plan["lanes"].items() if len(ids) > 15}
    if oversized:
        out += ["", "## Oversized lanes (>15 tasks — consider splitting via @lane: tags)"]
        for k, n in sorted(oversized.items(), key=lambda kv: -kv[1]):
            out.append(f"- **{k}**: {n} tasks — one agent will run ~{n / 10:.0f}x "
                       f"longer than a 10-task lane; split if the tasks allow it")
    pw = plan.get("pipelined_waves", [])
    if pw:
        out += [
            "",
            f"## Pipelined merge-batches ({c['pipelined_waves']} wave(s) of "
            f"~{c['wave_size']} tasks — build wave K+1 while wave K tests/CIs; "
            "waves are mutually file-disjoint so they never collide)",
            "Dispatch wave 1's agents now; when any agent finishes, work-steal "
            "the heaviest not-yet-started lane of the next wave (keeps the "
            "pipeline full and successive waves length-balanced).",
        ]
        for wave in pw:
            out.append(
                f"- **Wave {wave['wave']}** ({wave['tasks_total']} tasks, "
                f"{len(wave['agents'])} agents):"
            )
            for j, a in enumerate(wave["agents"], 1):
                out.append(
                    f"    - agent {j} (model={a['model']}, cost~{a['cost']:g}, "
                    f"{len(a['tasks'])} task(s)): {', '.join(a['lanes'])}"
                )
    out += [
        "",
        "## Waves (each row builds in parallel; one task per lane)",
    ]
    for n, wave in enumerate(plan["wave_detail"], 1):
        out.append(f"- **Wave {n}** ({len(wave)} parallel):")
        for t in wave:
            deps = f"  after {','.join(t['deps'])}" if t["deps"] else ""
            out.append(f"    - `{t['id']}`  [{t['lane']}] ({t['model']}){deps}")
    out += ["", "## Lanes (tasks inside a lane run in sequence; model = lane's max tier)"]
    for lane, ids in plan["lanes"].items():
        out.append(
            f"- **{lane}** ({len(ids)}, model={plan['lane_models'][lane]}): {', '.join(ids)}"
        )
    if plan["gated"]:
        out += ["", "## Gated — skip and flag (never auto-built)"]
        for t in plan["gated"]:
            out.append(f"- `{t['id']}`  ({', '.join(t['gate_reasons'])})")
    if plan["unassigned"]:
        out += ["", "## Unassigned — add a `@lane:`/`@files:` tag for full coverage"]
        for t in plan["unassigned"]:
            out.append(f"- `{t['id']}`  ({t['section'][:60]})")
    if plan.get("wave_blocked"):
        out += [
            "",
            "## Refusé — ordre de vague (BUILD_ORDER.yml, SCA3) — "
            "utiliser --force-wave pour outrepasser (fondateur, consigné)",
        ]
        for t in plan["wave_blocked"]:
            out.append(f"- `{t['id']}`  [{t['lane']}] — " + " ; ".join(t["wave_block_reasons"]))
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan maximally-parallel, cross-category lanes for a "
        "'work on the plan' run.",
    )
    parser.add_argument(
        "plan", nargs="*", default=[str(DEFAULT_PLAN)],
        help="plan file(s) to schedule (default: docs/PLAN.md). Pass SEVERAL "
        "to POOL them (e.g. docs/PLAN2.md docs/PLAN.md docs/new_tasks_plan.md) "
        "so lanes are chosen for FILE-DISJOINTNESS across plans first — the "
        "pipeline needs disjoint lanes more than it needs strict file order.",
    )
    parser.add_argument(
        "--max-lanes", type=int, default=8,
        help="worktree ceiling = max tasks to run in parallel per wave "
        "(default 8; raise it on a capable session)",
    )
    parser.add_argument(
        "--wave-size", type=int, default=80,
        help="target tasks per pipelined merge-batch (default 80). Lanes are "
        "packed into a SEQUENCE of ~this-size waves of --workers agents each; "
        "wave K+1 builds while wave K tests/CIs (waves are file-disjoint).",
    )
    parser.add_argument(
        "--workers", type=int, default=None,
        help="number of parallel AGENTS to time-balance lanes across "
        "(default: same as --max-lanes). Lanes are LPT bin-packed by task "
        "size so all agents finish at ~the same wall-clock time.",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--check", action="store_true",
        help="exit non-zero if any open buildable task is UNASSIGNED",
    )
    parser.add_argument(
        "--build-order", default=str(DEFAULT_BUILD_ORDER),
        help="BUILD_ORDER.yml path for SCA3 wave gating "
        "(default: docs/BUILD_ORDER.yml; missing file = gating is a no-op)",
    )
    parser.add_argument(
        "--force-wave", action="store_true",
        help="founder escape hatch (SCA3): bypass BUILD_ORDER.yml wave "
        "gating entirely for this run. Every use is logged to stderr.",
    )
    args = parser.parse_args(argv)

    plan_args = args.plan if isinstance(args.plan, list) else [args.plan]
    paths = []
    for p in plan_args:
        pth = Path(p)
        if not pth.is_absolute():
            pth = ROOT / pth
        if not pth.is_file():
            print(f"plan file not found: {pth}", file=sys.stderr)
            return 2
        paths.append(pth)
    path = paths[0]  # primary file (fingerprint/malformed checks, source label)

    # Pool tasks across every plan file so lanes can be chosen for
    # file-disjointness across plans first (the pipeline needs disjoint lanes
    # more than strict plan order). Single-file callers are unaffected.
    tasks = []
    for pth in paths:
        tasks.extend(parse_tasks(pth))

    build_order_path = Path(args.build_order)
    if not build_order_path.is_absolute():
        build_order_path = ROOT / build_order_path
    build_order = load_build_order(build_order_path)

    if args.force_wave and build_order is not None:
        print(
            "--force-wave: BUILD_ORDER.yml gating BYPASSED for this run "
            "(founder escape hatch, SCA3) — every prerequisite check below "
            "is skipped.",
            file=sys.stderr,
        )

    def _progress_lookup(prefix: str) -> float:
        import plan_progress  # lazy: keeps plan_lanes.py standalone-importable
        return plan_progress.group_pct(prefix)

    allowed_tasks, wave_blocked = apply_build_order_gate(
        tasks, build_order, _progress_lookup, force_wave=args.force_wave,
    )
    if wave_blocked and not args.force_wave:
        for t in wave_blocked:
            print(
                f"REFUSÉ (ordre de vague) : {t['id']} — "
                + " ; ".join(t["wave_block_reasons"]),
                file=sys.stderr,
            )

    plan = schedule(
        allowed_tasks, max(1, args.max_lanes), wave_blocked=wave_blocked,
        n_workers=args.workers, wave_size=args.wave_size,
    )
    source = ", ".join(
        p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else str(p)
        for p in paths
    )

    if args.json:
        payload = {k: v for k, v in plan.items() if k != "wave_detail"}
        payload["source"] = source
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render(plan, max(1, args.max_lanes), source))

    check_failed = False
    if args.check and plan["unassigned"]:
        print(
            f"\n{len(plan['unassigned'])} buildable task(s) have no lane — "
            "add a `@lane:`/`@files:` tag.",
            file=sys.stderr,
        )
        check_failed = True

    if args.check:
        malformed = count_malformed(path)
        if malformed:
            print(
                f"\n{malformed} line(s) look like a checklist task "
                "(`- [`) but match neither task regex — see the WARNING(s) "
                "above for file/line detail.",
                file=sys.stderr,
            )
            check_failed = True

    if check_failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

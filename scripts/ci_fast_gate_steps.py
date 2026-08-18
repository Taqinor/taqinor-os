#!/usr/bin/env python3
"""Extract the SHELL COMMANDS of a fast CI job straight from `.github/workflows/ci.yml`.

WHY THIS EXISTS (incident du 18/08/2026, PR #536). `scripts/preflight.ps1` promised
"run EVERY fast CI gate locally, in ONE pass" but carried a HAND-MAINTAINED copy of
the two job step lists. The copies drifted: preflight reported 16/16 green while the
very same push failed CI on `check_on_delete.py --financial` (backend-lint) and on
`check_choices_declares.py` (stage-names) — two checks preflight had simply never
heard of. At that point preflight was covering 3 of backend-lint's 23 checks and 12
of stage-names' 29. A green preflight that does not imply a green gate is worse than
no preflight: it buys a CI round-trip with false confidence.

The fix is structural, not another manual sync: preflight no longer OWNS a list. It
asks this script, which READS ci.yml — the same file GitHub reads — and prints the
job's steps. Add a check to ci.yml and preflight runs it on the next invocation, with
the same flags, forever. There is nothing left to keep in sync.

Usage
-----
    python scripts/ci_fast_gate_steps.py [--format sh|tsv] <job> [<job> ...]

    --format sh   (default) emits `step '<label>' '<command>'` lines, meant to be
                  redirected to a file and `.`-sourced by a POSIX shell that has
                  already defined a `step` function (that is what preflight does).
    --format tsv  emits `<label>\\t<working-directory>\\t<command>` — same data, for
                  a caller that drives the steps itself (preflight's -NoDocker path).

Exit codes: 0 on success, 2 on any problem (unknown job, unreadable workflow,
implausibly short step list, a skip rule that no longer matches anything). Every
failure is LOUD: a silent empty list would hand back the exact false green this
script exists to abolish.

Skipped steps
-------------
A handful of ci.yml steps only PREPARE the runner's environment — the prod Python
3.11 image preflight runs in already has them. They are listed in ``_SKIPS`` with a
reason, and each rule MUST still match at least one step: if ci.yml stops running
`sudo apt-get ...`, this script fails rather than silently keeping a dead rule. The
drift guard therefore points both ways.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - environment problem, reported loudly
    sys.stderr.write(
        "ci_fast_gate_steps: PyYAML est requis pour lire .github/workflows/ci.yml.\n"
        "  Dans l'image prod il est deja present (dependance de drf-spectacular).\n"
        "  Sur l'hote : pip install pyyaml\n"
    )
    raise SystemExit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# (regex on the `run:` text, human reason). Every rule must match >= 1 step.
_SKIPS = [
    (
        r"^\s*pip install flake8 import-linter",
        "preflight installe deja flake8 + import-linter (une fois, en mode -q)",
    ),
    (
        r"^\s*sudo apt-get",
        "librairies systeme WeasyPrint : deja dans l'image prod, et `sudo` n'y existe pas",
    ),
    (
        r"^\s*pip install -r requirements\.txt\s*$",
        "requirements.txt est deja installe dans l'image prod",
    ),
]

# A job that suddenly yields fewer steps than this almost certainly means the parse
# broke (or ci.yml was gutted) — either way, refuse rather than under-check.
_MIN_STEPS = 10


def _shq(text: str) -> str:
    """Quote `text` for POSIX sh (single quotes; newlines survive verbatim)."""
    return "'" + text.replace("'", "'\\''") + "'"


def label_for(command: str) -> str:
    """Short ASCII label for a step, derived from the command it runs.

    Deliberately NOT ci.yml's `name:` — those are long French sentences with accents
    and quotes, which render badly through docker -> Windows PowerShell. The script
    name plus its flags is both ASCII-safe and the thing you need in order to rerun
    the failure by hand.
    """
    flat = " ".join(command.split())
    m = re.match(r"python -m unittest ([\w.]+)", flat)
    if m:
        return "unittest " + m.group(1).rsplit(".", 1)[-1]
    m = re.match(r"python (?:-\S+\s+)*scripts/([\w_]+\.py)(.*)", flat)
    if m:
        flags = " ".join(a for a in m.group(2).split() if a.startswith("-"))
        return (m.group(1) + " " + flags).strip()
    m = re.match(r"python -m (\w+)", flat)
    if m:
        return m.group(1)
    return flat.split()[0] if flat.split() else "step"


def load_jobs(workflow: Path = WORKFLOW) -> dict:
    try:
        doc = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"ci_fast_gate_steps: impossible de lire {workflow} ({exc})")
    return (doc or {}).get("jobs") or {}


def validate_skip_rules(jobs: dict) -> None:
    """Every ``_SKIPS`` rule must still match something SOMEWHERE in ci.yml.

    Checked across the WHOLE workflow, not per job: a rule exists to describe a real
    ci.yml step, and a rule that matches nothing anymore means ci.yml moved and the
    skip list is stale — exactly the drift that made preflight lie in the first place.
    """
    unseen = []
    for pattern, reason in _SKIPS:
        hit = any(
            re.search(pattern, step.get("run") or "", re.MULTILINE)
            for job in jobs.values()
            for step in (job.get("steps") or [])
        )
        if not hit:
            unseen.append(f"{pattern!r} ({reason})")
    if unseen:
        raise SystemExit(
            "ci_fast_gate_steps: regle(s) de saut devenue(s) sans objet dans "
            "ci.yml : " + "; ".join(unseen) + ". Mettez _SKIPS a jour."
        )


def extract(job: str, jobs: dict):
    """Return [(label, working_directory, command)] for `job`, in ci.yml order."""
    if job not in jobs:
        raise SystemExit(
            f"ci_fast_gate_steps: job '{job}' absent de {WORKFLOW.name}. "
            f"Jobs connus : {', '.join(sorted(jobs))}"
        )

    steps = []
    for step in jobs[job].get("steps") or []:
        run = step.get("run")
        if not run:  # `uses:` steps (checkout / setup-python / cache) — not commands
            continue
        if any(re.search(p, run, re.MULTILINE) for p, _ in _SKIPS):
            continue
        workdir = str(step.get("working-directory") or ".")
        steps.append((label_for(run), workdir, run.strip()))

    if len(steps) < _MIN_STEPS:
        raise SystemExit(
            f"ci_fast_gate_steps: seulement {len(steps)} etapes extraites pour "
            f"'{job}' (seuil {_MIN_STEPS}) — la lecture de ci.yml est probablement "
            "cassee. On refuse plutot que de rendre un preflight faussement vert."
        )
    return steps


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jobs", nargs="+", help="nom(s) de job dans ci.yml")
    parser.add_argument("--format", choices=("sh", "tsv"), default="sh")
    args = parser.parse_args(argv)

    jobs = load_jobs()
    validate_skip_rules(jobs)
    out = []
    for job in args.jobs:
        for lbl, workdir, cmd in extract(job, jobs):
            full = cmd if workdir in (".", "") else f"cd {workdir} && {cmd}"
            if args.format == "sh":
                out.append(f"step {_shq(lbl)} {_shq(full)}")
            else:
                out.append(f"{lbl}\t{workdir}\t{cmd}")
    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

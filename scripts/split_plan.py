#!/usr/bin/env python3
"""Split docs/new_tasks_plan.md into per-domain plan files for PARALLEL
"work on the plan <domain>" sessions (founder request, 2026-07-10).

Moves whole ``## Groupe NTxxx`` SECTIONS (header + prose + tasks, verbatim)
into ``docs/plans/PLAN_<DOMAIN>.md`` per the DOMAIN_MAP below. Groups not in
the map (the platform tier + anything unrecognized) STAY in
new_tasks_plan.md — the safe default. new_tasks_plan.md is NOT in the
CODEMAP fingerprint surface, and neither are the new files, so this split
never touches the fingerprint.

Reconciliation is strict (WOW16 style): every line of the source file ends
up in exactly one place; task-line counts are asserted before/after.

The point of the split: each domain file carries an APP-OWNERSHIP CONTRACT
(the header written below). Two sessions draining two different domain files
can never collide on a Django app (migrations stay linear per app), never
tick the same plan file, and never race the plan fingerprint — so they all
merge to main independently, like the web/ERP split.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "new_tasks_plan.md"
OUTDIR = ROOT / "docs" / "plans"

# domain -> (NT group names, owned backend apps, owned frontend areas)
DOMAIN_MAP: dict[str, tuple[set[str], str, str]] = {
    "CRM_VENTES": (
        {"NTCRM", "NTCPQ", "NTMKT", "NTDMO"},
        "apps/crm, apps/ventes (HORS quote_engine — RULE #4 reste opus+review), "
        "apps/marketing, nouvelles apps cpq/territoires/contacts",
        "frontend/src/pages|features de crm, ventes, marketing",
    ),
    "FINANCE": (
        {"NTFIN", "NTTRE", "NTFPA", "NTCRD", "NTADM", "NTASS", "NTSUB", "NTMAR"},
        "apps/compta, apps/contrats, nouvelles apps fpa/credit/entites/adminops/"
        "assurances/fiscal/einvoice/tresorerie",
        "frontend/src/pages|features de compta, contrats, finance",
    ),
    "SUPPLY": (
        {"NTSCM", "NTWMS", "NTLOG", "NTDST", "NTRET", "NTMFG"},
        "apps/stock, apps/pos, nouvelles apps scm/wms/transport/douane/"
        "fidelite/promotions/negoce",
        "frontend/src/pages|features de stock, pos, achats",
    ),
    "SERVICE": (
        {"NTSRV", "NTFSM", "NTNRG", "NTSVC", "NTPRJ"},
        "apps/sav, apps/installations, apps/monitoring, nouvelles apps "
        "actifsnrg/ppa/services_pro/booking",
        "frontend/src/pages|features de sav, installations, terrain, monitoring",
    ),
    "RH_PAIE": (
        {"NTHCM", "NTPAY"},
        "apps/rh, apps/paie",
        "frontend/src/pages|features de rh, paie",
    ),
    "DOCS_JURIDIQUE": (
        {"NTDOC", "NTCOL", "NTJUR"},
        "apps/ged, apps/kb, apps/litiges, nouvelles apps datarooms/mailsync/juridique",
        "frontend/src/pages|features de ged, kb, litiges",
    ),
    "VERTICALS": (
        {"NTAGR", "NTHOT", "NTEDU", "NTSAN", "NTPRO", "NTCON", "NTESG"},
        "nouvelles apps agriculture/hospitality/education/sante/immobilier/"
        "btp_chantier/esg (aucune app existante)",
        "frontend/src/pages|features des verticaux correspondants",
    ),
}

_TASK_RE = re.compile(r"^- \[ \] ")
_GROUP_IN_HEADER = re.compile(r"\b(NT[A-Z]+)\d*\b")


def contract(domain: str, groups: set[str], apps: str, fe: str) -> str:
    return f"""# PLAN_{domain} — file de travail parallèle (split de new_tasks_plan.md, 2026-07-10)

> **CONTRAT DE PROPRIÉTÉ (non négociable — c'est lui qui garantit zéro conflit).**
> Une session `work on the plan {domain.lower()}` ne touche QUE :
> **backend :** {apps}.
> **frontend :** {fe}.
> Tout le reste est INTERDIT en écriture — une autre session peut le posséder.
> Lire une app étrangère = via son `selectors.py`/string-FK uniquement (jamais
> ses models/migrations). Une tâche qui EXIGE d'écrire hors périmètre →
> `[BLOCKED: hors périmètre {domain}]` + continuer (elle reviendra au run
> plateforme). Fichiers frontend PARTAGÉS (router/nav/api/ui) : ajouts
> APPEND-ONLY minimaux ; un conflit à l'update-branch se résout en prenant les
> DEUX ajouts. Base de test locale : `DB_NAME=erp_{domain.lower()}` (jamais la
> DB partagée). Chaque session merge sa propre branche `dev-{domain.lower()}`
> vers main indépendamment (update-branch → CI ~6 min → auto-merge) ; si
> `docs/CODEMAP.md` (fingerprint structure) conflicte à l'update, prendre
> l'arbre mergé et relancer `python scripts/codemap_fingerprint.py --write`.
> Ce fichier n'est PAS dans la surface du plan-fingerprint (comme WEB_PLAN.md) :
> tick + DONE LOG ici, jamais dans docs/CODEMAP.md §10.
> Groupes : {", ".join(sorted(groups))}. Règles WOW/CLAUDE.md inchangées
> (lane-draining, revue adversariale, retro, routage modèle via plan_lanes.py).

## DONE LOG (une ligne datée par tâche livrée)

"""


def main() -> int:
    lines = SOURCE.read_text(encoding="utf-8").splitlines(keepends=True)
    total_tasks_before = sum(1 for ln in lines if _TASK_RE.match(ln))

    group_of: dict[str, str] = {
        g: d for d, (gs, _, _) in DOMAIN_MAP.items() for g in gs
    }
    # Walk sections: groups live under '### Groupe NTxxx' headers; a new '###'
    # or any higher-level '## ' header ends the current group. '####' and
    # deeper sub-headers stay inside their group.
    out: dict[str, list[str]] = {d: [] for d in DOMAIN_MAP}
    kept: list[str] = []
    current: str | None = None  # domain the current section is routed to
    moved_groups: list[str] = []
    for line in lines:
        if line.startswith("### "):
            m = _GROUP_IN_HEADER.search(line)
            g = m.group(1) if m else None
            current = group_of.get(g or "")
            if current:
                moved_groups.append(g)
        elif line.startswith("## "):
            current = None
        (out[current] if current else kept).append(line)

    OUTDIR.mkdir(exist_ok=True)
    total_after = sum(1 for ln in kept if _TASK_RE.match(ln))
    for domain, chunk in out.items():
        gs, apps, fe = DOMAIN_MAP[domain]
        n = sum(1 for ln in chunk if _TASK_RE.match(ln))
        total_after += n
        path = OUTDIR / f"PLAN_{domain}.md"
        path.write_text(contract(domain, gs, apps, fe) + "".join(chunk),
                        encoding="utf-8", newline="")
        print(f"  PLAN_{domain}.md : {n} taches ({', '.join(sorted(set(gs) & set(moved_groups)))})")

    # STRICT reconciliation: no task line lost or duplicated.
    assert total_after == total_tasks_before, (
        f"RECONCILIATION FAILED: {total_tasks_before} tasks before, "
        f"{total_after} after — ABORT (nothing valid was written)"
    )
    pointer = (
        "\n> **SPLIT 2026-07-10 :** les groupes domaines sont partis dans "
        "`docs/plans/PLAN_*.md` (sessions parallèles `work on the plan "
        "<domaine>`) — ce fichier garde le TIER PLATEFORME (single-session).\n\n"
    )
    src_text = "".join(kept)
    first_nl = src_text.index("\n") + 1
    SOURCE.write_text(src_text[:first_nl] + pointer + src_text[first_nl:],
                      encoding="utf-8", newline="")
    n_kept = sum(1 for ln in kept if _TASK_RE.match(ln))
    print(f"  new_tasks_plan.md garde {n_kept} taches plateforme")
    print(f"  TOTAL {total_tasks_before} avant == {total_after} apres — OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""ARC8/ARC26 — pure platform-kernel guard logic (no Django, no DB, no I/O).

Lives inside ``apps/records`` so it is importable both by the CI entry point
``scripts/check_platform.py`` (which adds ``backend/django_core`` to ``sys.path``)
AND by the Django test runner (``apps/records/tests_check_platform.py``) — the
test container only mounts ``backend/django_core``, never ``scripts/``.

These functions are STRING/AST-free text scanners (regex over source text) so
they stay in the fast, DB-free ``stage-names`` CI lane.
"""
from __future__ import annotations

import re

# ── ARC8 — bespoke *Activity chatter classes ──────────────────────────────────

# Matches a model class whose name ends in "Activity" (the chatter shape), e.g.
# ``class LeadActivity(models.Model):``. Column-0 ``class`` only (module level).
ACTIVITY_CLASS_RE = re.compile(
    r"^class\s+([A-Za-z_][A-Za-z0-9_]*Activity)\s*\(([^)]*)\)\s*:",
    re.MULTILINE,
)

# The legacy chatter/activity classes present at ARC8 time (frozen — never
# migrated in this wave). A NEW *Activity model class NOT in this set must use
# the generic ``records.Activity`` instead. Format: "app.ClassName".
GRANDFATHERED_ACTIVITY_CLASSES = frozenset({
    "contrats.ContratActivity",
    "crm.LeadActivity",
    "crm.PlanActivite",
    "crm.EtapePlanActivite",
    "flotte.ActiviteFlotte",
    "ged.DocumentActivity",
    "gestion_projet.ProjetActivity",
    "installations.InterventionActivity",
    "installations.InstallationActivity",
    "installations.OrdreAssemblageActivity",
    "litiges.ReclamationActivity",
    "rh.DossierActivity",
    "rh.CandidatureActivity",
    "sav.TicketActivity",
    "sav.TicketActiviteAFaire",
    "ventes.DevisActivity",
    "ventes.FactureActivity",
})


def scan_activity_classes(app: str, text: str) -> list[str]:
    """Return NEW ``app.ClassName`` *Activity model classes found in ``text``.

    ``records`` is exempt (it OWNS the generic Activity). A match is reported
    only when its qualified name is NOT grand-fathered and the class subclasses
    a Django ``Model`` (bases mention ``Model``)."""
    if app == "records":
        return []
    found: list[str] = []
    for m in ACTIVITY_CLASS_RE.finditer(text):
        class_name, bases = m.group(1), m.group(2)
        if "Model" not in bases:
            continue  # e.g. a plain helper class, not a Django model
        qualified = f"{app}.{class_name}"
        if qualified not in GRANDFATHERED_ACTIVITY_CLASSES:
            found.append(qualified)
    return found


def activity_error_line(qualified: str) -> str:
    return (
        f"[ARC8] Nouvelle classe modèle « {qualified} » de type *Activity hors "
        f"de apps/records. Le chatter doit converger sur records.Activity "
        f"(records.services.log_activity + ChatterViewSetMixin) — n'ajoutez pas "
        f"un modèle chatter maison. Si c'est un cas légitime NON-chatter, "
        f"ajoutez-le à GRANDFATHERED_ACTIVITY_CLASSES."
    )


# ── ARC26 — « plus de FileField sauvage » ─────────────────────────────────────

# Toute NOUVELLE pièce jointe passe par ``records.Attachment`` (MinIO) ou
# ``ged.Document`` — jamais un nouveau ``models.FileField``/``ImageField``.
# Les 17 FileField existants (7 fichiers, inventaire gelé au 2026-07-10 par
# grep ``models.FileField(`` sur apps/*/models*.py) sont grand-fatherés À
# COMPTE CONSTANT : le garde-fou devient rouge si un fichier dépasse son
# compte gelé pour un nom de champ, ou si un couple (fichier, champ) inconnu
# apparaît. Chemins POSIX relatifs à ``backend/django_core``.
GRANDFATHERED_FILEFIELDS = {
    "apps/ao/models.py": {"fichier": 1},
    "apps/compta/models.py": {"justificatif": 1, "fichier": 2},
    "apps/flotte/models.py": {
        "devis_fichier": 1, "attestation": 1, "carte_grise_fichier": 1,
        "autorisation_fichier": 1, "constat_fichier": 1, "pv_fichier": 1,
        "photo": 1, "document": 1,
    },
    "apps/gestion_projet/models.py": {"fichier": 1},
    "apps/portail/models.py": {"fichier": 1},
    "apps/rh/models.py": {"justificatif": 1, "cv_fichier": 1},
    "apps/stock/models.py": {"pdf": 1},
}

FILEFIELD_RE = re.compile(
    r"^\s*([a-z_][a-z0-9_]*)\s*=\s*models\.(?:FileField|ImageField)\(",
    re.MULTILINE,
)


def scan_filefields(relpath: str, text: str) -> list[str]:
    """Return ``'chemin:champ'`` pour tout FileField/ImageField NON gelé.

    ``relpath`` : chemin POSIX relatif à ``backend/django_core`` (ex.
    ``'apps/flotte/models.py'``). Rouge si un champ inconnu apparaît OU si le
    compte d'un champ connu dépasse le compte gelé (deux ``fichier`` gelés
    dans compta : un 3ᵉ = violation)."""
    counts: dict[str, int] = {}
    for m in FILEFIELD_RE.finditer(text):
        name = m.group(1)
        counts[name] = counts.get(name, 0) + 1
    allowed = GRANDFATHERED_FILEFIELDS.get(relpath, {})
    violations: list[str] = []
    for name in sorted(counts):
        if counts[name] > allowed.get(name, 0):
            violations.append(f"{relpath}:{name}")
    return violations


def filefield_error_line(spec: str) -> str:
    return (
        f"[ARC26] Nouveau FileField/ImageField « {spec} » hors liste gelée. "
        f"Toute NOUVELLE pièce jointe passe par records.Attachment (MinIO) ou "
        f"ged.Document — jamais un FileField de plus. La liste gelée vit dans "
        f"apps/records/platform_guards.py (GRANDFATHERED_FILEFIELDS)."
    )

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


# ── ARC11 — imports WeasyPrint hors allowlist ─────────────────────────────────

# Tout rendu PDF passe désormais par ``core.pdf.render_pdf`` (le SEUL importeur
# de WeasyPrint autorisé à terme). L'allowlist gelée liste les fichiers SOURCE
# qui importent encore ``weasyprint`` directement : (1) exclusions permanentes
# règle #4 (le moteur de devis vendorisé) ; (2) le service lui-même
# ``core/pdf.py`` ; (3) les importeurs directs GELÉS (à migrer plus tard vers
# ``core.pdf``). Un NOUVEL import ``weasyprint`` hors de cette liste = rouge —
# il doit passer par ``core.pdf.render_pdf``. Les fichiers de TESTS
# (``tests.py``, ``test_*.py``, ``tests_*.py``, ``tests/``) sont hors périmètre :
# ils peuvent importer WeasyPrint pour valider un rendu réel. Chemins POSIX
# relatifs à ``backend/django_core`` — inventaire gelé au 2026-07-10 (grep
# ``import weasyprint`` / ``from weasyprint`` sur les fichiers source d'apps/ +
# core/pdf.py).
GRANDFATHERED_WEASYPRINT = frozenset({
    # Service partagé (importeur légitime unique à terme).
    "core/pdf.py",
    # Exclusions permanentes — règle #4 (moteur de devis vendorisé).
    "apps/ventes/quote_engine/generate_devis_premium.py",
    "apps/ventes/quote_engine/extra_docs.py",
    "apps/ventes/quote_engine/agricole/render.py",
    "apps/ventes/quote_engine/agricole/renderer.py",
    "apps/ventes/quote_engine/residential/render.py",
    "apps/ventes/quote_engine/residential/renderer.py",
    "apps/ventes/utils/pdf.py",
    "apps/ventes/connection_declaration.py",
    # Importeurs directs GELÉS (à migrer vers core.pdf plus tard).
    "apps/compta/pdf_badge_evenement.py",
    "apps/compta/pdf_certificat_enquete.py",
    "apps/compta/pdf_etats.py",
    "apps/compta/pdf_ras.py",
    "apps/contrats/pdf_location.py",
    "apps/contrats/services.py",
    "apps/documents/builders.py",
    "apps/ged/services.py",
    "apps/installations/rfq_pdf.py",
    "apps/kb/services.py",
    "apps/monitoring/report.py",
    "apps/paie/builders.py",
    "apps/pos/receipt.py",
    "apps/qhse/services.py",
    "apps/reporting/report_pdf.py",
    "apps/rh/pdf_sortie.py",
})

# ``import weasyprint`` OU ``from weasyprint import …`` (indentation quelconque —
# les importeurs paresseux sont FONCTION-LOCAUX). Un import commenté (``#``) ne
# matche pas (le ``^\s*`` interdit un ``#`` en tête).
WEASYPRINT_IMPORT_RE = re.compile(
    r"^\s*(?:import\s+weasyprint\b|from\s+weasyprint\b)",
    re.MULTILINE,
)


def is_test_path(relpath: str) -> bool:
    """True si ``relpath`` est un fichier de tests (hors périmètre des gardes
    de surface : les tests peuvent importer WeasyPrint pour un rendu réel).

    Couvre ``tests.py``, ``test_*.py``, ``tests_*.py`` et tout fichier sous un
    répertoire ``tests/``. ``relpath`` : chemin POSIX."""
    parts = relpath.split("/")
    if "tests" in parts[:-1]:  # un répertoire tests/ dans le chemin
        return True
    name = parts[-1]
    return name == "tests.py" or name.startswith("test_") or name.startswith("tests_")


def scan_weasyprint_import(relpath: str, text: str) -> bool:
    """True si ``text`` importe ``weasyprint`` ET ``relpath`` n'est ni gelé ni
    un fichier de tests. ``relpath`` : chemin POSIX relatif à
    ``backend/django_core``."""
    if relpath in GRANDFATHERED_WEASYPRINT or is_test_path(relpath):
        return False
    return bool(WEASYPRINT_IMPORT_RE.search(text))


def weasyprint_error_line(relpath: str) -> str:
    return (
        f"[ARC11] Import WeasyPrint direct hors allowlist dans « {relpath} ». "
        f"Tout rendu PDF passe par core.pdf.render_pdf (import paresseux de "
        f"WeasyPrint centralisé) — n'importez pas weasyprint directement. "
        f"L'allowlist gelée (moteur de devis règle #4 + importeurs à migrer) "
        f"vit dans apps/records/platform_guards.py (GRANDFATHERED_WEASYPRINT)."
    )


# ── ARC6 — numérotation count()+1 hors socle ──────────────────────────────────

# La numérotation de références anti-collision vit UNIQUEMENT dans
# ``core/numbering.py`` (plus-haut-utilisé+1, savepoint+retry) et son shim de
# ré-export ``apps/ventes/utils/references.py`` — cf. la règle « JAMAIS
# count()+1 » du repo (le motif est entré en collision en production : un
# document supprimé rétrécit le compte). Le garde-fou devient rouge sur tout
# NOUVEAU ``.count() + 1`` en CONTEXTE de référence/numéro (assignation ou
# f-string à un ``reference``/``numero``/``ref``) dans du code de PRODUCTION,
# hors des deux fichiers socle. Baseline gelée au 2026-07-10 : VIDE — aucun
# offender de production (les seuls ``.count()+1`` restants sont soit des tests,
# soit du calcul non-référence : un repli de slug société, une borne de boucle).
NUMBERING_HOME_FILES = frozenset({
    "core/numbering.py",
    "apps/ventes/utils/references.py",
    # Ce fichier DÉFINIT les motifs (regex + prose) : il contient le texte
    # ``.count() + 1`` en littéral, sans être du code de numérotation.
    "apps/records/platform_guards.py",
})

# Offenders GELÉS (fichier:motif). VIDE au 2026-07-10 — la baseline ne peut que
# décroître. Chemins POSIX relatifs à ``backend/django_core``.
GRANDFATHERED_NUMBERING = frozenset()  # type: frozenset[str]

# ``.count()`` suivi de ``+ 1`` dans une ligne qui mentionne aussi un jeton de
# CONTEXTE référence/numéro (``reference``, ``ref``, ``numero``, ``numéro``,
# ``num_``). On EXIGE la co-occurrence du jeton sur la même ligne pour éviter
# les faux positifs sur un ``count()+1`` légitime SANS rapport avec une
# référence (repli de slug ``company-{...}``, borne de boucle ``max_depth``).
# Le motif ``max(...)+1`` N'EST PAS visé : c'est le motif CORRECT endossé par le
# repo (versionnage par parent sous select_for_update dans contrats/kb/qhse).
NUMBERING_COUNT_RE = re.compile(
    r"(?i)(?:reference|\bref\b|numero|num[ée]ro|num_)"
    r".*\.count\(\)\s*\+\s*1"
    r"|\.count\(\)\s*\+\s*1.*(?:reference|\bref\b|numero|num[ée]ro|num_)",
)


def scan_numbering(relpath: str, text: str) -> list[str]:
    """Retourne ``['chemin:count+1', …]`` pour tout NOUVEAU ``.count() + 1`` en
    contexte de référence/numéro dans un fichier de PRODUCTION non gelé.

    ``relpath`` : chemin POSIX relatif à ``backend/django_core``. Les fichiers
    socle (``NUMBERING_HOME_FILES``) et les fichiers de tests sont exemptés
    (un test peut fabriquer une référence jetable via ``count()``)."""
    if relpath in NUMBERING_HOME_FILES or is_test_path(relpath):
        return []
    violations: list[str] = []
    for line in text.splitlines():
        if NUMBERING_COUNT_RE.search(line):
            spec = f"{relpath}:count+1"
            if spec not in GRANDFATHERED_NUMBERING and spec not in violations:
                violations.append(spec)
    return violations


def numbering_error_line(spec: str) -> str:
    return (
        f"[ARC6] Numérotation « {spec} » via .count()+1 hors socle. Les "
        f"références anti-collision passent par core.numbering.next_reference "
        f"(plus-haut-utilisé+1, race-safe) — JAMAIS count()+1 (un document "
        f"supprimé rétrécit le compte → collision en production). Cf. "
        f"apps/records/platform_guards.py (NUMBERING_HOME_FILES)."
    )

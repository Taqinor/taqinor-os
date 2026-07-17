"""ARC8/ARC26/SCA4/SCA37 — pure platform-kernel guard logic (no Django, no DB, no I/O).

Lives inside ``apps/records`` so it is importable both by the CI entry point
``scripts/check_platform.py`` (which adds ``backend/django_core`` to ``sys.path``)
AND by the Django test runner (``apps/records/tests_check_platform.py``) — the
test container only mounts ``backend/django_core``, never ``scripts/``.

These functions are STRING/AST-free text scanners (regex over source text) so
they stay in the fast, DB-free ``stage-names`` CI lane.
"""
from __future__ import annotations

import re
from pathlib import Path

# Répertoire des baselines gelées (SCA4), à CÔTÉ de ce module pour être lisible
# par les DEUX exécuteurs : le script CI (``scripts/check_platform.py``) ET le
# runner Django (qui ne monte que ``backend/django_core``, jamais ``scripts/``).
_BASELINE_DIR = Path(__file__).resolve().parent / "platform_baselines"


def _load_baseline(name: str) -> frozenset:
    """Charge une baseline gelée (un ``app.ClassName`` par ligne ; ``#`` = commentaire).

    Absente/illisible → frozenset vide (le garde échoue alors OUVERT : tout
    offender existant redevient rouge, jamais un faux vert)."""
    path = _BASELINE_DIR / name
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:  # pragma: no cover - baseline toujours committée
        return frozenset()
    return frozenset(
        s.strip() for s in lines if s.strip() and not s.lstrip().startswith("#"))


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
    # QX45/QX46 — renderers dédiés industriel/commercial (mêmes mirrors rule #4
    # que residential/agricole ci-dessus, CSS-tables, jamais flex).
    "apps/ventes/quote_engine/industriel/render.py",
    "apps/ventes/quote_engine/industriel/renderer.py",
    "apps/ventes/quote_engine/commercial/render.py",
    "apps/ventes/quote_engine/commercial/renderer.py",
    "apps/ventes/utils/pdf.py",
    "apps/ventes/connection_declaration.py",
    # Importeurs directs GELÉS (à migrer vers core.pdf plus tard).
    "apps/qhse/services.py",
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

    Couvre ``tests.py``, ``test_*.py``, ``tests_*.py``, tout fichier sous un
    répertoire ``tests/`` ou ``__tests__/``, et les tests FRONTEND
    ``*.test.js(x)`` / ``*.spec.js(x)`` (un test SCA24/SCA29 nomme légitimement
    la marque pour affirmer son ABSENCE dans le DOM). ``relpath`` : chemin
    POSIX."""
    parts = relpath.split("/")
    if "tests" in parts[:-1] or "__tests__" in parts[:-1]:
        return True
    name = parts[-1]
    if name == "tests.py" or name.startswith("test_") or name.startswith("tests_"):
        return True
    return bool(re.search(r"\.(test|spec)\.(js|jsx|ts|tsx|mjs)$", name))


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


# ── SCA4 — conformité noyau : modèles/viewsets hand-rollés hors socle ─────────
#
# Post-noyau (ARC1/ARC2), le socle multi-tenant EST posé : ``core.TenantModel``
# (FK ``company`` + timestamps) et ``core.viewsets.CompanyScopedModelViewSet``
# (scoping + forçage société côté serveur). SCA4 empêche une lane voyou de
# RE-hand-roller ce socle après coup — chaque copie manuelle redevenant une cible
# de sweep future (YDATA4/YRBAC12, nommés, non refaits ici).
#
# Deux gardes, chacun sur une BASELINE GELÉE qui ne peut que DÉCROÎTRE :
#   (M) tout NOUVEAU modèle (absent de la baseline) qui déclare
#       ``company = models.ForeignKey``/``OneToOneField`` À LA MAIN au lieu
#       d'hériter ``TenantModel`` = rouge ;
#   (V) tout NOUVEAU ViewSet ``ModelViewSet`` (absent de la baseline) qui n'hérite
#       PAS de ``CompanyScopedModelViewSet`` = rouge.
#
# EXEMPTIONS INLINE :
#   * ``core`` et ``authentication`` DÉFINISSENT le socle : leurs modèles portent
#     légitimement une FK ``company`` à la main (``TenantModel`` lui-même,
#     ``DeletionRecord``…). Ils sont hors périmètre du garde modèle.
#   * Les fichiers de tests sont hors périmètre (fixtures/fakes).
#   * La baseline liste les modèles/viewsets hand-rollés EXISTANTS (pré-SCA4,
#     inventaire du 2026-07-10) — chargée depuis un fichier de données committé
#     (``apps/records/platform_baselines/``). Elle ne peut que rétrécir : un modèle
#     converti à ``TenantModel`` / un viewset converti à
#     ``CompanyScopedModelViewSet`` DISPARAÎT de son fichier source, donc ne
#     matche plus — et son entrée de baseline devient inerte (le garde ignore une
#     entrée de baseline sans offender réel). YDATA4 fera le sweep de complétude.

# Apps qui DÉFINISSENT le socle (FK company à la main = légitime). Hors périmètre
# du garde modèle SCA4.
SOCLE_DEFINING_APPS = frozenset({"core", "authentication"})

# ``company = models.ForeignKey(`` OU ``company = models.OneToOneField(`` déclaré
# à la main dans le corps d'un modèle. Indentation quelconque (champ de classe).
HANDROLLED_COMPANY_FK_RE = re.compile(
    r"^\s*company\s*=\s*models\.(?:ForeignKey|OneToOneField)\b",
    re.MULTILINE,
)

# En-tête de classe : ``class Name(bases):``. Capture le nom + les bases brutes.
CLASS_HEADER_RE = re.compile(
    r"^class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*:",
    re.MULTILINE,
)


def _class_blocks(text: str):
    """Yield ``(class_name, bases_str, body_text)`` for each module-level class.

    Le corps va de la fin de l'en-tête jusqu'à la prochaine ``class`` de niveau
    module (colonne 0) ou la fin du fichier. Suffisant pour repérer un champ de
    classe (``company = …``) ou les bases — pas un parseur Python complet, mais
    déterministe et sans dépendance."""
    matches = list(CLASS_HEADER_RE.finditer(text))
    for i, m in enumerate(matches):
        name, bases = m.group(1), m.group(2)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        yield name, bases, text[start:end]


def scan_handrolled_models(app: str, text: str) -> list[str]:
    """Retourne ``['app.ClassName', …]`` des modèles déclarant une FK ``company``
    à la main dans ``text``. ``app`` : label d'app.

    Les apps qui DÉFINISSENT le socle (``core``/``authentication``) sont
    exemptées (leur FK ``company`` à la main est légitime).

    Un modèle qui HÉRITE de ``TenantModel`` et REdéclare ``company`` à
    l'identique n'est PAS un hand-roll : c'est le motif ARC1 documenté de
    préservation du ``related_name`` historique (cf. docstring de
    ``core.models.TenantModel`` et les pilotes ``notifications``)."""
    if app in SOCLE_DEFINING_APPS:
        return []
    found: list[str] = []
    for name, bases, body in _class_blocks(text):
        if "TenantModel" in bases:
            continue  # motif ARC1 : redéclaration légitime sur le socle
        if HANDROLLED_COMPANY_FK_RE.search(body):
            found.append(f"{app}.{name}")
    return found


# ``*ModelViewSet`` dans les bases, mais PAS ``CompanyScopedModelViewSet``. On
# repère un viewset concret non scopé au socle. ``ReadOnlyModelViewSet`` et les
# ``GenericViewSet`` ne portent pas d'écriture create → hors périmètre (le socle
# ARC2 vise ``ModelViewSet``).
MODELVIEWSET_BASE_RE = re.compile(r"\bModelViewSet\b")
SCOPED_BASE_RE = re.compile(r"\bCompanyScopedModelViewSet\b")
READONLY_BASE_RE = re.compile(r"\bReadOnlyModelViewSet\b")


def scan_unscoped_viewsets(app: str, text: str) -> list[str]:
    """Retourne ``['app.ClassName', …]`` des ViewSets ``ModelViewSet`` NON basés
    sur ``CompanyScopedModelViewSet`` dans ``text``.

    Un viewset dont les bases contiennent ``CompanyScopedModelViewSet`` est déjà
    au socle (vert). ``ReadOnlyModelViewSet`` seul (sans ``ModelViewSet``
    inscriptible) est hors périmètre."""
    found: list[str] = []
    for name, bases, _body in _class_blocks(text):
        if SCOPED_BASE_RE.search(bases):
            continue  # déjà au socle
        # ReadOnlyModelViewSet matche aussi \bModelViewSet\b — l'exclure sauf si
        # une VRAIE base ModelViewSet inscriptible est aussi présente.
        stripped = READONLY_BASE_RE.sub("", bases)
        if MODELVIEWSET_BASE_RE.search(stripped):
            found.append(f"{app}.{name}")
    return found


def handrolled_model_error_line(qualified: str) -> str:
    return (
        f"[SCA4] Nouveau modèle « {qualified} » déclare une FK « company » à la "
        f"main hors socle. Héritez de core.models.TenantModel (FK company + "
        f"timestamps) plutôt que de re-hand-roller la paire multi-société. Si "
        f"c'est un cas légitime (app qui définit le socle), ajoutez-le à la "
        f"baseline gelée apps/records/platform_baselines/handrolled_models.txt "
        f"(elle ne peut que décroître)."
    )


def unscoped_viewset_error_line(qualified: str) -> str:
    return (
        f"[SCA4] Nouveau ViewSet « {qualified} » (ModelViewSet) n'hérite pas de "
        f"core.viewsets.CompanyScopedModelViewSet — le scoping société + le "
        f"forçage de company côté serveur ne sont donc pas garantis. Basez-le sur "
        f"CompanyScopedModelViewSet. Si c'est un cas légitime, ajoutez-le à la "
        f"baseline gelée apps/records/platform_baselines/unscoped_viewsets.txt "
        f"(elle ne peut que décroître)."
    )


# Baselines gelées (chargées à l'import — une par fichier de données committé).
BASELINE_HANDROLLED_MODELS = _load_baseline("handrolled_models.txt")
BASELINE_UNSCOPED_VIEWSETS = _load_baseline("unscoped_viewsets.txt")


def new_handrolled_models(found: list[str]) -> list[str]:
    """Filtre ``found`` (offenders scannés) contre la baseline gelée : ne garde
    que les NOUVEAUX (absents de la baseline) = les violations réelles."""
    return [q for q in found if q not in BASELINE_HANDROLLED_MODELS]


def new_unscoped_viewsets(found: list[str]) -> list[str]:
    """Idem pour les viewsets non scopés au socle."""
    return [q for q in found if q not in BASELINE_UNSCOPED_VIEWSETS]


# ── SCA42 — clés de stockage préfixées company pour les NOUVEAUX uploads ──────
#
# Constat (motif ERR75 généralisé) : ``ventes/utils/pdf.py`` préfixe déjà ses
# clés par société (``devis/{company_id}/…``), mais les pièces jointes
# (``records/storage.py``) et les avatars (``authentication/avatars.py``)
# stockaient des clés PLATES (``attachments/{uuid}.ext`` / ``avatars/{uuid}.ext``).
# SCA42 préfixe les NOUVELLES clés par société ; ce garde empêche toute NOUVELLE
# clé de stockage plate (``attachments/{uuid…}`` / ``avatars/{uuid…}`` non
# préfixée) d'apparaître HORS des fichiers déjà connus (baseline gelée). Les
# objets existants ne bougent pas (lecture par clé stockée) — NTPLT8 (nommé)
# vérifiera l'isolation live de l'existant.

# Fichiers connus pour contenir une clé de stockage plate au 2026-07-10
# (inventaire) : la branche de repli rétro-compatible de records/avatars + la
# clé GED encore à migrer. Chemins POSIX relatifs à ``backend/django_core``.
GRANDFATHERED_FLAT_STORAGE_KEYS = frozenset({
    "authentication/avatars.py",   # branche de repli SCA42 (rétro-compat)
    "apps/records/storage.py",     # branche de repli SCA42 (rétro-compat)
    "apps/ged/services.py",        # clé attachments/{uuid} historique (à migrer)
})

# Clé de stockage f-string ``<prefix>/{X…`` où ``prefix`` ∈ {attachments,avatars}
# et le PREMIER segment interpolé ``{X`` n'est PAS un identifiant de société
# (``company``/``company_id``/``cid``/``c_id``…). Un préfixe company
# (``attachments/{cid}/…`` ou ``avatars/{company_id}/…``) a l'identifiant société
# juste après le slash → non matché. Une clé plate (``attachments/{uuid.uuid4()…``)
# matche. Le lookahead reconnaît tout jeton commençant par ``company``/``comp_id``
# ou exactement ``cid``/``c_id`` (bornés à droite pour ne pas confondre un autre
# identifiant).
FLAT_STORAGE_KEY_RE = re.compile(
    r"""f['"](?:attachments|avatars)/\{"""
    r"""(?!\s*(?:company[A-Za-z0-9_]*|comp_id|cid|c_id)\b)""",
)


def scan_flat_storage_key(relpath: str, text: str) -> bool:
    """True si ``text`` construit une clé de stockage PLATE (non préfixée
    company) ET ``relpath`` n'est ni gelé ni un fichier de tests.

    ``relpath`` : chemin POSIX relatif à ``backend/django_core``."""
    if relpath in GRANDFATHERED_FLAT_STORAGE_KEYS or is_test_path(relpath):
        return False
    return bool(FLAT_STORAGE_KEY_RE.search(text))


def flat_storage_key_error_line(relpath: str) -> str:
    return (
        f"[SCA42] Nouvelle clé de stockage PLATE (non préfixée company) dans "
        f"« {relpath} ». Préfixez les nouvelles clés par la société "
        f"(« {{app}}/{{company_id}}/{{uuid}}.ext », motif ERR75) pour l'isolation "
        f"multi-tenant du stockage objet. La liste gelée (branches de repli + clé "
        f"GED à migrer) vit dans apps/records/platform_guards.py "
        f"(GRANDFATHERED_FLAT_STORAGE_KEYS)."
    )


# ── SCA29 — anti-branding « taqinor » hardcodé dans les surfaces user-facing ──
#
# Constat : ~146 fichiers backend + 49 frontend mentionnent « taqinor » — la
# plupart LÉGITIMES (commentaires, seeds, chemins d'infra). Mais rien n'empêche
# la PROCHAINE chaîne client-facing hardcodée. SCA29 scanne les surfaces
# user-facing (littéraux de chaîne py des apps, ``frontend/src``, templates) à la
# recherche des motifs de MARQUE (``TAQINOR`` majuscule, domaine ``taqinor.ma``,
# email ``contact@taqinor``) contre une BASELINE DATÉE GELÉE : tout NOUVEAU hit =
# rouge. La baseline ne peut que DÉCROÎTRE (les fixes SCA24-27 la réduisent — un
# fichier nettoyé sort du scan et son entrée de baseline devient inerte).
#
# HEURISTIQUE (documentée) : on scanne LIGNE À LIGNE et on IGNORE les lignes de
# commentaire pur (``#…`` en py, ``//…`` / ``*…`` en JS/JSX) — un commentaire
# « taqinor » n'est pas une surface client. Le grain reste le FICHIER (un hit =
# le fichier entre au registre) : suffisant pour empêcher une régression sans
# suivre chaque occurrence. Les motifs de marque sont ÉTROITS (pas un simple
# « taqinor » qui matcherait un chemin d'infra ou une URL d'API interne) :
#   * ``TAQINOR`` — la marque en CAPITALES (libellé affiché) ;
#   * ``taqinor.ma`` — le domaine public (jamais hardcodé côté client : le
#     branding vient de ``TenantTheme``/``CompanyProfile``) ;
#   * ``contact@taqinor`` — l'email de contact hardcodé.

# Motifs de MARQUE user-facing (étroits — pas un « taqinor » générique).
BRANDING_RE = re.compile(r"TAQINOR|taqinor\.ma|contact@taqinor")

# Lignes de commentaire pur à ignorer (py ``#`` / JS ``//`` / bloc ``*``).
_COMMENT_LINE_RE = re.compile(r"^\s*(?:#|//|\*|/\*)")


def scan_branding(relpath: str, text: str) -> bool:
    """True si ``text`` contient un motif de MARQUE user-facing hors commentaire.

    ``relpath`` : chemin POSIX (backend relatif à ``backend/django_core`` ; ou
    ``frontend/src/...``). Les fichiers de tests sont hors périmètre (fixtures)."""
    if is_test_path(relpath):
        return False
    for line in text.splitlines():
        if _COMMENT_LINE_RE.match(line):
            continue
        if BRANDING_RE.search(line):
            return True
    return False


# Baseline gelée des fichiers user-facing contenant DÉJÀ un motif de marque
# (inventaire daté). Un fichier nettoyé (SCA24-27…) sort du scan → son entrée
# devient inerte ; la liste ne peut que décroître.
BASELINE_BRANDING = _load_baseline("branding_hits.txt")


def new_branding_hits(found: list[str]) -> list[str]:
    """Filtre les fichiers scannés contre la baseline gelée : NOUVEAUX hits."""
    return [p for p in found if p not in BASELINE_BRANDING]


def branding_error_line(relpath: str) -> str:
    return (
        f"[SCA29] Marque « taqinor » hardcodée dans une surface user-facing "
        f"« {relpath} » (motif TAQINOR / taqinor.ma / contact@taqinor). Le "
        f"branding client vient de TenantTheme/CompanyProfile (white-label), "
        f"jamais d'une chaîne en dur. Si c'est légitime (infra non client-facing), "
        f"ajoutez le fichier à la baseline gelée "
        f"apps/records/platform_baselines/branding_hits.txt (décroissante)."
    )


# ── SCA37 — garde CI kit pour le code NOUVEAU : plus de « document métier »
#    hand-rollé hors du kit ``core.documents.DocumentMetier`` (SCA30/31) ──────
#
# Constat (SCA37) : sans garde, le 18ᵉ document hand-rollé arrive au prochain
# flood. L'anatomie « document métier » (statut + lignes + totaux TTC figés)
# se répète sur le dépôt (cf. docstring ``core/documents.py``) ; le kit SCA30/31
# fournit désormais l'unité réutilisable. Ce garde empêche un NOUVEAU modèle de
# re-hand-roller cette anatomie au lieu d'hériter le kit.
#
# HEURISTIQUE (documentée) : un modèle CONCRET déclenche le garde quand LES
# TROIS conditions suivantes sont réunies dans le fichier scanné :
#   1. il déclare un champ ``statut`` (ou ``statut...``) à ``choices`` — la
#      machine d'états d'un document ;
#   2. une classe SŒUR nommée EXACTEMENT ``Ligne<MêmeNom>`` existe dans le même
#      fichier (même app) — le motif ligne/totaux d'un document ;
#   3. un champ ``montant_ttc`` (le nom EXACT posé par
#      ``core.documents.TotauxDocumentMixin``) est déclaré sur le modèle
#      LUI-MÊME OU sur sa ligne sœur — la chaîne de totaux figés.
# ET ses bases de classe ne mentionnent PAS ``DocumentMetier`` (un modèle qui
# hérite déjà le kit n'est jamais visé, même s'il porte par ailleurs les trois
# traits ci-dessus — c'est justement le but du kit).
#
# EXCLUSION PERMANENTE (règle #4, CLAUDE.md) — nommée et ABSOLUE, jamais un
# rétrofit exigé, jamais retirable par un nettoyage de baseline : Devis /
# Facture / BonCommande / Avoir restent sur leurs chaînes de statuts propres à
# jamais, séparées de ce kit et de la couche funnel ``STAGES.py`` (règle #2).
# ODX17 a sorti Facture/Avoir de ``ventes`` vers ``apps.facturation`` (même
# table physique, state-only) — l'exclusion suit le MODÈLE, pas son app
# d'origine. Un futur champ ``montant_ttc`` ajouté à l'un de ces quatre
# modèles ne doit JAMAIS faire rougir ce garde : l'exclusion est vérifiée
# AVANT la baseline, par nom qualifié, en dur dans ce module.
KIT_PERMANENT_EXCLUSIONS = frozenset({
    "ventes.Devis",
    "facturation.Facture",
    "ventes.BonCommande",
    "facturation.Avoir",
})

# ``statut`` (ou tout champ ``statut...``) déclaré avec des ``choices`` — motif
# large pour couvrir ``statut = models.CharField(max_length=.., choices=…)`` sur
# une ou plusieurs lignes (``DOTALL``).
KIT_STATUT_CHOICES_RE = re.compile(
    r"^\s*statut\w*\s*=\s*models\.\w*Field\([^)]*choices",
    re.MULTILINE | re.DOTALL,
)

# Champ ``montant_ttc`` déclaré (nom EXACT posé par ``TotauxDocumentMixin``).
KIT_MONTANT_TTC_RE = re.compile(r"^\s*montant_ttc\s*=\s*models\.", re.MULTILINE)


def scan_kit_bypass_documents(app: str, text: str) -> list[str]:
    """Retourne ``['app.ClassName', …]`` des documents hand-rollés NEUFS.

    ``app`` : label d'app ; ``text`` : le contenu d'UN fichier de modèles (les
    trois traits — statut/sœur/montant_ttc — doivent cohabiter dans le MÊME
    fichier, comme c'est le cas pour tout document existant du dépôt). Un
    modèle dans ``KIT_PERMANENT_EXCLUSIONS`` (règle #4) n'est JAMAIS retourné,
    quels que soient ses traits. Un modèle dont les bases mentionnent
    ``DocumentMetier`` (a déjà adopté le kit) n'est jamais retourné."""
    found: list[str] = []
    for name, bases, body in _class_blocks(text):
        qualified = f"{app}.{name}"
        if qualified in KIT_PERMANENT_EXCLUSIONS:
            continue
        if "DocumentMetier" in bases:
            continue  # a déjà adopté le kit — jamais un offender
        if not KIT_STATUT_CHOICES_RE.search(body):
            continue
        sibling_name = f"Ligne{name}"
        sibling_body = None
        for other_name, _other_bases, other_body in _class_blocks(text):
            if other_name == sibling_name:
                sibling_body = other_body
                break
        if sibling_body is None:
            continue  # pas de ligne sœur → pas l'anatomie visée
        if not (KIT_MONTANT_TTC_RE.search(body) or KIT_MONTANT_TTC_RE.search(sibling_body)):
            continue
        found.append(qualified)
    return found


def kit_bypass_error_line(qualified: str) -> str:
    return (
        f"[SCA37] Nouveau modèle « {qualified} » hand-roule l'anatomie "
        f"« document métier » (statut à choices + ligne sœur Ligne{qualified.split('.')[-1]} "
        f"+ champ montant_ttc) sans hériter core.documents.DocumentMetier "
        f"(+ LigneDocumentMetier/TotauxDocumentMixin, SCA30/31). Composez le "
        f"kit au lieu de re-copier statut/lignes/totaux à la main. Si c'est un "
        f"document PRÉ-EXISTANT au kit, ajoutez-le à la baseline gelée "
        f"apps/records/platform_baselines/kit_bypass_documents.txt (elle ne "
        f"peut que décroître) — sauf Devis/Facture/BonCommande/Avoir, qui "
        f"n'entrent JAMAIS dans cette baseline (exclusion permanente règle #4, "
        f"KIT_PERMANENT_EXCLUSIONS dans ce module)."
    )


# Baseline gelée (chargée à l'import) des documents hand-rollés PRÉ-kit.
BASELINE_KIT_BYPASS_DOCUMENTS = _load_baseline("kit_bypass_documents.txt")


def new_kit_bypass_documents(found: list[str]) -> list[str]:
    """Filtre ``found`` contre la baseline gelée : ne garde que les NOUVEAUX
    offenders (absents de la baseline ET absents de ``KIT_PERMANENT_EXCLUSIONS``
    — cette dernière est déjà appliquée en amont par ``scan_kit_bypass_documents``,
    revérifiée ici par défense en profondeur)."""
    return [
        q for q in found
        if q not in BASELINE_KIT_BYPASS_DOCUMENTS and q not in KIT_PERMANENT_EXCLUSIONS
    ]

"""Platform-kernel CI guards (Groupe ARC) — DB-free source scan.

Mirrors the spirit of ``scripts/check_stages.py`` / ``scripts/check_modules.py``:
it scans SOURCE files TEXTUALLY (no Django setup, no database) so it can run in
the fast, ungated ``stage-names`` CI job. (Wiring this into CI is ARC52 — this
file only PROVIDES the checks.)

The pure detection logic lives in ``apps/records/platform_guards.py`` so it is
importable BOTH here (CI entry point, run from repo root) AND by the Django test
runner — the test container only mounts ``backend/django_core``, never
``scripts/``. This module adds ``backend/django_core`` to ``sys.path`` to reuse
that single source of truth.

Checks
------
ARC8 — no NEW bespoke ``*Activity`` chatter model outside ``apps/records``: the
    13 near-identical ``*Activity`` classes are frozen legacy; any NEW chatter
    must converge on the generic ``records.Activity``.
ARC26 — no NEW ``FileField``/``ImageField`` outside the frozen list: every new
    attachment goes through ``records.Attachment`` / ``ged.Document``.
ARC11 — no NEW direct ``weasyprint`` import outside the frozen allowlist: every
    PDF render goes through ``core.pdf.render_pdf``.
ARC6 — no NEW ``.count() + 1`` reference/number generation outside the two
    numbering-home files: references go through ``core.numbering.next_reference``.
SCA4 — no NEW hand-rolled ``company`` FK model (must inherit ``TenantModel``)
    and no NEW ``ModelViewSet`` outside ``CompanyScopedModelViewSet``, both
    against a frozen baseline that can only shrink.
SCA42 — no NEW flat (non-company-prefixed) storage key outside the frozen
    baseline: new upload keys go ``{app}/{company_id}/{uuid}.ext`` (ERR75).
SCA29 — no NEW hardcoded ``taqinor`` brand string (TAQINOR / taqinor.ma /
    contact@taqinor) in user-facing surfaces outside the frozen baseline.
SCA37 — no NEW hand-rolled « document métier » (statut à choices + ligne sœur
    ``Ligne<Nom>`` + champ ``montant_ttc``) outside ``core.documents.DocumentMetier``
    (SCA30/31 kit), against a frozen baseline that can only shrink. Devis /
    Facture / BonCommande / Avoir are a PERMANENT, code-named exclusion
    (rule #4) — never baseline-listed, never retrofit-required.

Run
---
    python scripts/check_platform.py            # exits non-zero on a violation
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"

# Reuse the single source of truth for the pure guard logic.
if str(DJANGO_CORE) not in sys.path:
    sys.path.insert(0, str(DJANGO_CORE))
from apps.records.platform_guards import (  # noqa: E402
    activity_error_line,
    branding_error_line,
    filefield_error_line,
    flat_storage_key_error_line,
    handrolled_model_error_line,
    kit_bypass_error_line,
    new_branding_hits,
    new_handrolled_models,
    new_kit_bypass_documents,
    new_unscoped_viewsets,
    numbering_error_line,
    scan_activity_classes,
    scan_branding,
    scan_filefields,
    scan_flat_storage_key,
    scan_handrolled_models,
    scan_kit_bypass_documents,
    scan_numbering,
    scan_unscoped_viewsets,
    scan_weasyprint_import,
    unscoped_viewset_error_line,
    weasyprint_error_line,
)


CORE_DIR = DJANGO_CORE / "core"
AUTH_DIR = DJANGO_CORE / "authentication"


def _app_of(models_path: Path) -> str:
    """apps/<app>/models.py -> '<app>' (or the parent dir name for a package)."""
    rel = models_path.relative_to(APPS_DIR)
    return rel.parts[0]


def _iter_model_files():
    """Yield every model file under apps/.

    Couvre les trois dispositions du dépôt : ``models.py``, fichiers éclatés
    ``models_*.py`` (ex. ``installations/models_intervention.py``) et un
    paquet ``models/``."""
    yield from APPS_DIR.glob("*/models*.py")
    yield from APPS_DIR.glob("*/models/*.py")


def _iter_source_files():
    """Yield every ``.py`` source file that ARC11/ARC6 scan.

    Toutes les apps (``apps/**/*.py``) plus les deux fichiers socle scannés par
    ARC11/ARC6 (``core/pdf.py``, ``core/numbering.py``). Le filtrage des tests
    et des fichiers gelés se fait dans les scanners (source unique de vérité)."""
    yield from APPS_DIR.glob("**/*.py")
    yield CORE_DIR / "pdf.py"
    yield CORE_DIR / "numbering.py"


def find_new_activity_classes() -> list[str]:
    """Return ['app.ClassName', …] for NEW *Activity model classes on disk."""
    violations: list[str] = []
    for path in _iter_model_files():
        app = _app_of(path)
        text = path.read_text(encoding="utf-8")
        violations.extend(scan_activity_classes(app, text))
    return violations


def check_activity_convergence() -> list[str]:
    """ARC8 guard — returns a list of human-readable error lines (empty = OK)."""
    return [activity_error_line(q) for q in sorted(find_new_activity_classes())]


def find_new_filefields() -> list[str]:
    """ARC26 — retourne ['chemin:champ', …] pour tout FileField NON gelé."""
    violations: list[str] = []
    for path in _iter_model_files():
        relpath = path.relative_to(DJANGO_CORE).as_posix()
        text = path.read_text(encoding="utf-8")
        violations.extend(scan_filefields(relpath, text))
    return violations


def check_no_wild_filefields() -> list[str]:
    """ARC26 guard — plus de FileField sauvage (empty = OK)."""
    return [filefield_error_line(s) for s in sorted(find_new_filefields())]


def find_new_weasyprint_imports() -> list[str]:
    """ARC11 — retourne les chemins des importeurs WeasyPrint NON allowlistés."""
    violations: list[str] = []
    for path in _iter_source_files():
        if not path.exists():
            continue
        relpath = path.relative_to(DJANGO_CORE).as_posix()
        text = path.read_text(encoding="utf-8")
        if scan_weasyprint_import(relpath, text):
            violations.append(relpath)
    return violations


def check_weasyprint_allowlist() -> list[str]:
    """ARC11 guard — plus d'import WeasyPrint hors allowlist (empty = OK)."""
    return [weasyprint_error_line(p) for p in sorted(find_new_weasyprint_imports())]


def find_new_numbering() -> list[str]:
    """ARC6 — retourne ['chemin:count+1', …] pour tout count()+1 de référence."""
    violations: list[str] = []
    for path in _iter_source_files():
        if not path.exists():
            continue
        relpath = path.relative_to(DJANGO_CORE).as_posix()
        text = path.read_text(encoding="utf-8")
        violations.extend(scan_numbering(relpath, text))
    return violations


def check_numbering_home() -> list[str]:
    """ARC6 guard — plus de count()+1 de référence hors socle (empty = OK)."""
    return [numbering_error_line(s) for s in sorted(find_new_numbering())]


def _app_of_source(path: Path) -> str:
    """apps/<app>/**/*.py -> '<app>' (label d'app pour un fichier source quelconque)."""
    return path.relative_to(APPS_DIR).parts[0]


def find_new_handrolled_models() -> list[str]:
    """SCA4 — modèles NOUVEAUX (hors baseline) déclarant une FK company à la main."""
    found: list[str] = []
    for path in _iter_model_files():
        relpath = path.relative_to(DJANGO_CORE).as_posix()
        if relpath in (
            "apps/records/platform_guards.py",
        ):  # jamais un modèle
            continue
        app = _app_of(path)
        found.extend(scan_handrolled_models(app, path.read_text(encoding="utf-8")))
    return new_handrolled_models(sorted(set(found)))


def check_handrolled_models() -> list[str]:
    """SCA4 garde (M) — plus de modèle hand-rollé hors socle (empty = OK)."""
    return [handrolled_model_error_line(q) for q in sorted(find_new_handrolled_models())]


def find_new_unscoped_viewsets() -> list[str]:
    """SCA4 — ViewSets ModelViewSet NOUVEAUX (hors baseline) non basés socle."""
    found: list[str] = []
    for path in APPS_DIR.glob("**/*.py"):
        relpath = path.relative_to(DJANGO_CORE).as_posix()
        # Le module de gardes CITE les noms de bases en littéral (regex) — jamais
        # un vrai viewset ; l'exclure pour ne pas s'auto-signaler.
        if relpath == "apps/records/platform_guards.py":
            continue
        app = _app_of_source(path)
        found.extend(scan_unscoped_viewsets(app, path.read_text(encoding="utf-8")))
    return new_unscoped_viewsets(sorted(set(found)))


def check_unscoped_viewsets() -> list[str]:
    """SCA4 garde (V) — plus de ModelViewSet non scopé au socle (empty = OK)."""
    return [unscoped_viewset_error_line(q) for q in sorted(find_new_unscoped_viewsets())]


def find_new_flat_storage_keys() -> list[str]:
    """SCA42 — fichiers NOUVEAUX (hors baseline) construisant une clé de stockage
    plate (non préfixée company). Couvre apps/ + authentication/ (avatars)."""
    violations: list[str] = []
    for base in (APPS_DIR, AUTH_DIR):
        for path in base.glob("**/*.py"):
            relpath = path.relative_to(DJANGO_CORE).as_posix()
            # Le module de gardes CITE les préfixes en littéral (regex) — l'exclure.
            if relpath == "apps/records/platform_guards.py":
                continue
            if scan_flat_storage_key(relpath, path.read_text(encoding="utf-8")):
                violations.append(relpath)
    return violations


def check_flat_storage_keys() -> list[str]:
    """SCA42 guard — plus de clé de stockage plate hors baseline (empty = OK)."""
    return [flat_storage_key_error_line(p) for p in sorted(set(find_new_flat_storage_keys()))]


FRONTEND_SRC = ROOT / "frontend" / "src"


def find_new_branding_hits() -> list[str]:
    """SCA29 — fichiers user-facing NOUVEAUX (hors baseline) avec un motif marque.

    Surfaces : littéraux py des apps (backend) + ``frontend/src`` (JS/JSX/TS/TSX).
    Le module de gardes s'auto-exclut (il cite les motifs en littéral)."""
    found: list[str] = []
    for path in APPS_DIR.glob("**/*.py"):
        relpath = path.relative_to(DJANGO_CORE).as_posix()
        if relpath == "apps/records/platform_guards.py":
            continue
        if scan_branding(relpath, path.read_text(encoding="utf-8", errors="replace")):
            found.append(relpath)
    if FRONTEND_SRC.is_dir():  # absent quand seul backend/django_core est monté
        for pattern in ("**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx"):
            for path in FRONTEND_SRC.glob(pattern):
                relpath = path.relative_to(ROOT).as_posix()
                if scan_branding(relpath, path.read_text(encoding="utf-8", errors="replace")):
                    found.append(relpath)
    return new_branding_hits(sorted(set(found)))


def check_branding() -> list[str]:
    """SCA29 guard — plus de marque taqinor hardcodée hors baseline (empty = OK)."""
    return [branding_error_line(p) for p in sorted(set(find_new_branding_hits()))]


def find_new_kit_bypass_documents() -> list[str]:
    """SCA37 — documents NOUVEAUX (hors baseline) hand-roulant l'anatomie du kit
    (statut à choices + ligne sœur Ligne<Nom> + montant_ttc) sans hériter
    ``DocumentMetier``. Les trois traits doivent cohabiter dans le MÊME fichier
    de modèles (un seul passage par fichier, comme pour ARC8/ARC26)."""
    found: list[str] = []
    for path in _iter_model_files():
        app = _app_of(path)
        text = path.read_text(encoding="utf-8")
        found.extend(scan_kit_bypass_documents(app, text))
    return new_kit_bypass_documents(sorted(set(found)))


def check_kit_bypass_documents() -> list[str]:
    """SCA37 guard — plus de document métier hand-rollé hors kit (empty = OK)."""
    return [kit_bypass_error_line(q) for q in sorted(find_new_kit_bypass_documents())]


def run_checks() -> list[str]:
    """Run all platform guards; return the flat list of error lines."""
    errors: list[str] = []
    errors.extend(check_activity_convergence())
    errors.extend(check_no_wild_filefields())
    errors.extend(check_weasyprint_allowlist())
    errors.extend(check_numbering_home())
    errors.extend(check_handrolled_models())
    errors.extend(check_unscoped_viewsets())
    errors.extend(check_flat_storage_keys())
    errors.extend(check_branding())
    errors.extend(check_kit_bypass_documents())
    return errors


def main() -> int:
    # Les messages d'erreur sont en français (« » → …) : forcer UTF-8 sur la
    # console pour ne pas planter sur un terminal cp1252 (Windows). La CI tourne
    # déjà en UTF-8, ce reconfigure est un no-op inoffensif là-bas.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):  # pragma: no cover - flux non reconfigurable
        pass
    errors = run_checks()
    if errors:
        print("check_platform: VIOLATIONS")
        for line in errors:
            print("  - " + line)
        return 1
    print("check_platform: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""GARDE CI (backend-lint-fast) — ADEP20 : toute clé de réglage LUE est déclarée.

CLASSE C-ADEP-004 : `getattr(settings, 'WHATSAPP_CLOUD_VERIFY_TOKEN', None)` lit
un réglage que AUCUN `erp_agentique/settings/*.py` n'affecte : posée dans
l'environnement, la variable n'a AUCUN effet (le GET de vérification Meta
répondait 404 « Non configuré. » alors que le jeton était posé). Aucune garde
ne comparait les lectures aux réglages.

Stdlib pure (le job n'installe pas Django). Lecture AST de `backend/django_core`
(hors tests, migrations) : toute lecture `settings.X`, `getattr(settings, 'X',
…)`, `hasattr(settings, 'X')` dont X

  * n'est affecté dans AUCUN `erp_agentique/settings/*.py`,
  * n'est pas un réglage par défaut de Django (liste ci-dessous),
  * et ne retombe pas sur `os.environ` / `os.getenv` dans la MÊME fonction,

fait échouer la garde (« X lue par <fichier> n'est déclarée dans aucun
settings »). Dette du jour gelée dans `scripts/settings_non_declares_allow.txt`
(`fichier::CLÉ`) : elle ne peut que RÉTRÉCIR — une ligne morte (clé désormais
déclarée ou lecture retirée) fait échouer la garde.

Usage :
    python scripts/check_settings_declares.py [--write-baseline]
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _cliquet  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BACKEND = Path("backend") / "django_core"
SETTINGS_DIR = BACKEND / "erp_agentique" / "settings"
BASELINE = ROOT / "scripts" / "settings_non_declares_allow.txt"
ENTETE = (
    "# Base de reference de check_settings_declares.py (ADEP20).\n"
    "# Une ligne = `fichier::CLE` lue via django.conf.settings mais declaree dans\n"
    "# AUCUN erp_agentique/settings/*.py. DETTE : ne peut que RETRECIR (les\n"
    "# proprietaires retirent leurs lignes : ADEP32, ADEP35-ADEP40...).\n"
)
IGNORES = {"migrations", "node_modules", "__pycache__", "tests", "test"}

# Reglages par defaut de django.conf.global_settings couramment lus ; completes
# par l'import reel de Django quand il est disponible.
DEFAUTS_DJANGO = frozenset("""
ABSOLUTE_URL_OVERRIDES ADMINS ALLOWED_HOSTS APPEND_SLASH AUTHENTICATION_BACKENDS
AUTH_PASSWORD_VALIDATORS AUTH_USER_MODEL CACHES CACHE_MIDDLEWARE_ALIAS
CACHE_MIDDLEWARE_KEY_PREFIX CACHE_MIDDLEWARE_SECONDS CSRF_COOKIE_AGE
CSRF_COOKIE_DOMAIN CSRF_COOKIE_HTTPONLY CSRF_COOKIE_NAME CSRF_COOKIE_PATH
CSRF_COOKIE_SAMESITE CSRF_COOKIE_SECURE CSRF_FAILURE_VIEW CSRF_HEADER_NAME
CSRF_TRUSTED_ORIGINS CSRF_USE_SESSIONS DATABASES DATABASE_ROUTERS DATETIME_FORMAT
DATETIME_INPUT_FORMATS DATE_FORMAT DATE_INPUT_FORMATS DEBUG DEBUG_PROPAGATE_EXCEPTIONS
DEFAULT_AUTO_FIELD DEFAULT_CHARSET DEFAULT_EXCEPTION_REPORTER DEFAULT_FILE_STORAGE
DEFAULT_FROM_EMAIL DEFAULT_INDEX_TABLESPACE DEFAULT_TABLESPACE DISALLOWED_USER_AGENTS
EMAIL_BACKEND EMAIL_HOST EMAIL_HOST_PASSWORD EMAIL_HOST_USER EMAIL_PORT
EMAIL_SSL_CERTFILE EMAIL_SSL_KEYFILE EMAIL_SUBJECT_PREFIX EMAIL_TIMEOUT EMAIL_USE_LOCALTIME
EMAIL_USE_SSL EMAIL_USE_TLS FILE_UPLOAD_DIRECTORY_PERMISSIONS FILE_UPLOAD_HANDLERS
FILE_UPLOAD_MAX_MEMORY_SIZE FILE_UPLOAD_PERMISSIONS FILE_UPLOAD_TEMP_DIR FIXTURE_DIRS
FORCE_SCRIPT_NAME FORMAT_MODULE_PATH IGNORABLE_404_URLS INSTALLED_APPS INTERNAL_IPS
LANGUAGES LANGUAGES_BIDI LANGUAGE_CODE LANGUAGE_COOKIE_AGE LANGUAGE_COOKIE_NAME
LOCALE_PATHS LOGGING LOGGING_CONFIG LOGIN_REDIRECT_URL LOGIN_URL LOGOUT_REDIRECT_URL
MANAGERS MEDIA_ROOT MEDIA_URL MESSAGE_STORAGE MIDDLEWARE MIGRATION_MODULES
PASSWORD_HASHERS PASSWORD_RESET_TIMEOUT PREPEND_WWW ROOT_URLCONF SECRET_KEY
SECRET_KEY_FALLBACKS SECURE_CONTENT_TYPE_NOSNIFF SECURE_CROSS_ORIGIN_OPENER_POLICY
SECURE_HSTS_INCLUDE_SUBDOMAINS SECURE_HSTS_PRELOAD SECURE_HSTS_SECONDS
SECURE_PROXY_SSL_HEADER SECURE_REDIRECT_EXEMPT SECURE_REFERRER_POLICY SECURE_SSL_HOST
SECURE_SSL_REDIRECT SERVER_EMAIL SESSION_CACHE_ALIAS SESSION_COOKIE_AGE
SESSION_COOKIE_DOMAIN SESSION_COOKIE_HTTPONLY SESSION_COOKIE_NAME SESSION_COOKIE_PATH
SESSION_COOKIE_SAMESITE SESSION_COOKIE_SECURE SESSION_ENGINE SESSION_EXPIRE_AT_BROWSER_CLOSE
SESSION_FILE_PATH SESSION_SAVE_EVERY_REQUEST SESSION_SERIALIZER SETTINGS_MODULE SHORT_DATE_FORMAT
SHORT_DATETIME_FORMAT SIGNING_BACKEND SILENCED_SYSTEM_CHECKS SITE_ID STATICFILES_DIRS
STATICFILES_FINDERS STATIC_ROOT STATIC_URL STORAGES TEMPLATES TEST_RUNNER TIME_FORMAT
TIME_INPUT_FORMATS TIME_ZONE USE_I18N USE_L10N USE_THOUSAND_SEPARATOR USE_TZ
USE_X_FORWARDED_HOST USE_X_FORWARDED_PORT USE_X_FORWARDED_FOR WSGI_APPLICATION
X_FRAME_OPTIONS DATA_UPLOAD_MAX_MEMORY_SIZE DATA_UPLOAD_MAX_NUMBER_FIELDS
DATA_UPLOAD_MAX_NUMBER_FILES THOUSAND_SEPARATOR DECIMAL_SEPARATOR NUMBER_GROUPING
FIRST_DAY_OF_WEEK YEAR_MONTH_FORMAT MONTH_DAY_FORMAT TEMPLATE_DEBUG
""".split())


def defauts_django() -> frozenset:
    try:  # pragma: no cover - dépend de l'environnement
        from django.conf import global_settings
        return DEFAUTS_DJANGO | frozenset(
            n for n in dir(global_settings) if n.isupper())
    except Exception:
        return DEFAUTS_DJANGO


def cles_declarees(root: Path = ROOT) -> set:
    """Noms affectés au niveau module dans erp_agentique/settings/*.py."""
    noms = set()
    dossier = root / SETTINGS_DIR
    for p in sorted(dossier.glob("*.py")):
        try:
            arbre = ast.parse(p.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for n in ast.walk(arbre):
            cibles = []
            if isinstance(n, ast.Assign):
                cibles = n.targets
            elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
                cibles = [n.target]
            for c in cibles:
                for el in (c.elts if isinstance(c, (ast.Tuple, ast.List)) else [c]):
                    if isinstance(el, ast.Name) and el.id.isupper():
                        noms.add(el.id)
                    elif (isinstance(el, ast.Subscript) and isinstance(el.value, ast.Call)
                          and isinstance(el.slice, ast.Constant)):
                        noms.add(str(el.slice.value))  # globals()['X'] = ...
    return noms


def _alias_settings(arbre) -> set:
    alias = {"settings", "django_settings"}
    for n in ast.walk(arbre):
        if isinstance(n, ast.ImportFrom) and n.module == "django.conf":
            for a in n.names:
                if a.name == "settings":
                    alias.add(a.asname or a.name)
    return alias


def _utilise_environ(fonction) -> bool:
    for n in ast.walk(fonction):
        if isinstance(n, ast.Attribute) and n.attr in ("environ", "getenv"):
            return True
        if isinstance(n, ast.Name) and n.id in ("environ", "getenv"):
            return True
    return False


class _Lecteur(ast.NodeVisitor):
    def __init__(self, alias):
        self.alias = alias
        self.fonctions = []
        self.lectures = []  # (cle, environ_dans_la_fonction)

    def _fn(self, node):
        self.fonctions.append(node)
        self.generic_visit(node)
        self.fonctions.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = _fn

    def _enregistrer(self, cle):
        env = bool(self.fonctions) and _utilise_environ(self.fonctions[-1])
        self.lectures.append((cle, env))

    def visit_Attribute(self, node):
        if (isinstance(node.value, ast.Name) and node.value.id in self.alias
                and node.attr.isupper()):
            self._enregistrer(node.attr)
        self.generic_visit(node)

    def visit_Call(self, node):
        if (isinstance(node.func, ast.Name) and node.func.id in ("getattr", "hasattr")
                and len(node.args) >= 2 and isinstance(node.args[0], ast.Name)
                and node.args[0].id in self.alias
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
                and node.args[1].value.isupper()):
            self._enregistrer(node.args[1].value)
        self.generic_visit(node)


def _est_exclu(rel: Path) -> bool:
    return (any(p in IGNORES for p in rel.parts[:-1])
            or rel.name.startswith(("test_", "tests_")) or rel.name in ("tests.py", "conftest.py")
            or rel.parts[:3] == ("erp_agentique", "settings"))


def lectures_non_declarees(root: Path = ROOT) -> set:
    declarees = cles_declarees(root) | defauts_django()
    base = root / BACKEND
    trouvees = set()
    for p in sorted(base.rglob("*.py")):
        rel = p.relative_to(base)
        if _est_exclu(rel):
            continue
        try:
            source = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "settings" not in source:
            continue
        try:
            arbre = ast.parse(source)
        except SyntaxError:
            continue
        lecteur = _Lecteur(_alias_settings(arbre))
        lecteur.visit(arbre)
        for cle, env in lecteur.lectures:
            if cle in declarees or env:
                continue
            trouvees.add(f"{p.relative_to(root).as_posix()}::{cle}")
    return trouvees


def decrire(cle: str) -> str:
    fichier, nom = cle.split("::", 1)
    return f"{nom} lue par {fichier} n'est déclarée dans aucun settings (erp_agentique/settings/*.py)."


def verifier(trouvees: set, base: set) -> list:
    return _cliquet.comparer(trouvees, base, nom_fichier="settings_non_declares_allow.txt",
                             decrire=decrire)


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--autoriser-croissance", action="store_true")
    args = ap.parse_args(argv)
    trouvees = lectures_non_declarees()
    if args.write_baseline:
        try:
            _cliquet.ecrire(BASELINE, trouvees, ENTETE, "ADEP20 clé non déclarée",
                            autoriser_croissance=args.autoriser_croissance)
        except ValueError as exc:
            print("REFUS : " + str(exc))
            return 1
        print(f"Base réécrite ({len(trouvees)} entrée(s)).")
        return 0
    erreurs = verifier(trouvees, _cliquet.charger(BASELINE))
    if erreurs:
        print("check_settings_declares: ÉCHEC")
        for e in erreurs:
            print("  - " + e)
        return 1
    print(f"check_settings_declares: OK — {len(trouvees)} clé(s) non déclarée(s) "
          "gelée(s), aucune nouvelle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

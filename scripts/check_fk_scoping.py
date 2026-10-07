"""AUD601 — CI guard: a writable CROSS-APP FK on a ModelSerializer must be
validated same-company.

``TenantMixin.get_queryset`` scopes what a user READS. It says nothing about
what a user WRITES: the ``PrimaryKeyRelatedField`` that DRF auto-generates from
a ``ModelSerializer`` accepts ANY primary key of the target table — including a
neighbouring company's row. On the AO surfaces those values are rendered into a
document handed to the BUYER (bordereau des prix, onglet équipements), so the
leak is read by the end client, not by a log.

DB-free AST sweep (mirrors ``check_unique_scoping.py`` /
``check_tenant_isolation.py``):

  1. ``backend/django_core/apps/*/models*.py`` (+ ``models/``) + ``core/models.py``
     are parsed (SPL72: ``models.py`` AND every ``models_<x>.py`` split out of it) to
     map every ``ForeignKey('<app>.<Model>')`` and which models are
     tenant-scoped (they declare ``company`` or inherit a tenant base).
  2. Every ``*ModelSerializer`` subclass under ``apps/*/serializers*.py`` /
     ``apps/*/*_serializers.py`` (+ ``serializers/``) is
     matched to its ``Meta.model``; each ``Meta.fields`` entry that is a
     WRITABLE cross-app FK to a tenant-scoped model must be covered by either
     ``def validate_<field>`` or a declarative
     ``same_company_fields = (...)`` (``core.mixins.SameCompanyFKSerializerMixin``).

AANA47 / ASTK9 extensions: M2M fields, FK/M2M to the user (``CustomUser``) or
``roles.Role``, SAME-APP FKs to a tenant model, and ANY app module defining a
``ModelSerializer`` (``views/*.py`` included) are covered; a serializer that
inherits ``CompanyScopedRelationsMixin`` / ``CompanyScopedModelSerializer``
(``core.serializers``) is bounded for every relation.

Pre-existing, human-reviewed sites live in ``scripts/fk_scoping_allow.txt``
(``path::Serializer.field``); a NEW cross-app FK serializer field without
validation fails CI.

Usage:
    python scripts/check_fk_scoping.py            # check (CI)
    python scripts/check_fk_scoping.py --list     # list every cross-app FK site
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"
ALLOWLIST_PATH = ROOT / "scripts" / "fk_scoping_allow.txt"

FK_CALLS = ("ForeignKey", "OneToOneField")
#: AANA47 — les champs M2M écrivent eux aussi des clés d'une autre ligne.
M2M_CALLS = ("ManyToManyField",)
#: AANA47 — cibles TOUJOURS scopées société, même si leur modèle n'est pas dans
#: ``apps/*/models*.py`` (``CustomUser`` vit dans ``authentication/``) et malgré
#: ``FOUNDATION_APPS`` : une FK/M2M vers un utilisateur ou un rôle accepte sinon
#: la clé d'un compte d'une AUTRE société.
FORCED_TENANT_TARGETS = {("authentication", "CustomUser"), ("roles", "Role")}
#: ``settings.AUTH_USER_MODEL`` / ``get_user_model()`` ne sont pas des chaînes
#: littérales : on les lit comme ``authentication.CustomUser``.
USER_MODEL_ALIASES = {"authentication.CustomUser", "auth.User"}
#: ASTK9 — bases/mixins qui re-scopent TOUTES les relations d'un sérialiseur
#: (``core.serializers``) : un sérialiseur qui en hérite est borné.
SCOPING_BASES = {"CompanyScopedRelationsMixin", "CompanyScopedModelSerializer"}
#: Sous-dossiers jamais balayés pour les sérialiseurs.
SKIP_DIRS = {"migrations", "tests", "test", "management", "__pycache__",
             "node_modules"}
#: SPL72 — UNE seule découverte par garde : ``models.py`` ET ses scissions
#: ``models_<x>.py``, ``serializers.py`` ET ``serializers_<x>.py`` /
#: ``<x>_serializers.py`` (plus les dossiers ``models/`` / ``serializers/``).
#: Sans cela, scinder un gros fichier ferait SORTIR ses classes de la garde.
MODEL_GLOBS = ("models*.py",)
SERIALIZER_GLOBS = ("serializers*.py", "*_serializers.py")
#: Bases connues pour porter ``company`` sans le redéclarer.
TENANT_BASES = {"TenantModel", "CompanyScopedModel", "SoftDeleteTenantModel"}
#: Apps « socle » : une FK vers elles n'est pas une FK métier cross-app.
FOUNDATION_APPS = {"authentication", "auth", "contenttypes", "admin"}


# ── helpers AST ────────────────────────────────────────────────────────────

def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _call_name(node) -> str:
    """``models.ForeignKey(...)`` / ``ForeignKey(...)`` → ``ForeignKey``."""
    if not isinstance(node, ast.Call):
        return ""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _str_list(node):
    """Un littéral list/tuple de chaînes → liste Python (sinon ``None``)."""
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    out = []
    for elt in node.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            out.append(elt.value)
    return out


def _assigned_targets(stmt):
    if isinstance(stmt, ast.Assign):
        return [t.id for t in stmt.targets if isinstance(t, ast.Name)]
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        return [stmt.target.id]
    return []


def _is_user_model_ref(node) -> bool:
    """``settings.AUTH_USER_MODEL`` ou ``get_user_model()`` (AANA47)."""
    if isinstance(node, ast.Attribute):
        return node.attr == "AUTH_USER_MODEL"
    if isinstance(node, ast.Name):
        return node.id == "AUTH_USER_MODEL"
    return _call_name(node) == "get_user_model"


def _base_names(cls: ast.ClassDef):
    names = []
    for base in cls.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
    return names


# ── 1. carte des modèles ───────────────────────────────────────────────────

def _iter_app_files(app_dir: Path, globs, subdir: str):
    """Fichiers d'une app répondant à ``globs`` (à la racine) + ``subdir/*.py``,
    triés, sans doublon (``serializers.py`` répond à ``serializers*.py``)."""
    seen = set()
    for pattern in globs:
        for f in sorted(app_dir.glob(pattern)):
            if f.is_file() and f not in seen:
                seen.add(f)
                yield f
    sdir = app_dir / subdir
    if sdir.is_dir():
        for f in sorted(sdir.glob("*.py")):
            if f not in seen:
                seen.add(f)
                yield f


def _iter_model_files():
    core_models = DJANGO_CORE / "core" / "models.py"
    if core_models.is_file():
        yield "core", core_models
    if not APPS_DIR.is_dir():
        return
    for app_dir in sorted(APPS_DIR.iterdir()):
        if not app_dir.is_dir():
            continue
        for f in _iter_app_files(app_dir, MODEL_GLOBS, "models"):
            yield app_dir.name, f


def build_model_map():
    """→ (fks, tenant_models, name_to_keys, m2m_fields)

    ``fks``: ``{(app, Model): {field: (target_app, target_model)}}`` (FK, 1-1
    ET M2M — AANA47) ; ``m2m_fields``: ``{((app, Model), field)}`` des M2M.
    ``tenant_models``: ``{(app, Model)}`` portant une société.
    """
    fks = {}
    m2m_fields = set()
    declares_company = set()
    bases_of = {}
    name_to_keys = {}

    for app, path in _iter_model_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            key = (app, cls.name)
            bases_of[key] = _base_names(cls)
            name_to_keys.setdefault(cls.name, []).append(key)
            champs = fks.setdefault(key, {})
            for stmt in cls.body:
                noms = _assigned_targets(stmt)
                if not noms:
                    continue
                value = getattr(stmt, "value", None)
                if _call_name(value) not in FK_CALLS + M2M_CALLS:
                    continue
                est_m2m = _call_name(value) in M2M_CALLS
                cible = value.args[0] if value.args else None
                if _is_user_model_ref(cible):
                    brut = "authentication.CustomUser"
                elif (isinstance(cible, ast.Constant)
                        and isinstance(cible.value, str)):
                    brut = cible.value
                    if brut in USER_MODEL_ALIASES:
                        brut = "authentication.CustomUser"
                    elif "." not in brut and brut != "self":
                        brut = f"{app}.{brut}"      # ASTK9 : même app
                elif isinstance(cible, ast.Name) and cible.id != "self":
                    brut = f"{app}.{cible.id}"      # ASTK9 : classe locale
                else:
                    continue
                if "." not in brut:
                    continue
                t_app, t_model = brut.split(".", 1)
                for nom in noms:
                    if nom == "company":
                        declares_company.add(key)
                    champs[nom] = (t_app, t_model)
                    if est_m2m:
                        m2m_fields.add((key, nom))

    # Fixpoint : un modèle est tenant s'il déclare ``company`` ou hérite d'une
    # base tenant (nom de base connu, ou modèle tenant du dépôt).
    tenant = set(declares_company)
    change = True
    while change:
        change = False
        for key, bases in bases_of.items():
            if key in tenant:
                continue
            for b in bases:
                if b in TENANT_BASES:
                    tenant.add(key)
                    change = True
                    break
                for cand in name_to_keys.get(b, []):
                    if cand in tenant:
                        tenant.add(key)
                        change = True
                        break
                if key in tenant:
                    break
    return fks, tenant, name_to_keys, m2m_fields


# ── 2. balayage des sérialiseurs ───────────────────────────────────────────

def _iter_serializer_files():
    """AANA47 — TOUT module d'app qui définit un ``ModelSerializer`` (pas
    seulement ``serializers*.py`` : ``views/*.py``, ``api.py``…), hors
    migrations/tests/commandes. Un filtre texte évite de parser les modules
    sans sérialiseur."""
    if not APPS_DIR.is_dir():
        return
    for app_dir in sorted(APPS_DIR.iterdir()):
        if not app_dir.is_dir():
            continue
        for f in sorted(app_dir.rglob("*.py")):
            rel_parts = f.relative_to(app_dir).parts
            if any(part in SKIP_DIRS for part in rel_parts[:-1]):
                continue
            nom = f.name
            if nom.startswith(("test_", "tests_")) or nom in (
                    "tests.py", "conftest.py"):
                continue
            if nom.startswith("models") and f.parent == app_dir:
                continue
            try:
                if "ModelSerializer" not in f.read_text(encoding="utf-8"):
                    continue
            except (OSError, UnicodeDecodeError):
                continue
            yield app_dir.name, f


def _meta_of(cls: ast.ClassDef):
    for stmt in cls.body:
        if isinstance(stmt, ast.ClassDef) and stmt.name == "Meta":
            return stmt
    return None


def _serializer_facts(cls: ast.ClassDef):
    """Champs read-only déclarés, ``same_company_fields``, ``validate_*``."""
    read_only = set()
    same_company = set()
    validates = set()
    for stmt in cls.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if stmt.name.startswith("validate_"):
                validates.add(stmt.name[len("validate_"):])
            continue
        noms = _assigned_targets(stmt)
        if not noms:
            continue
        value = getattr(stmt, "value", None)
        if "same_company_fields" in noms:
            for f in (_str_list(value) or []):
                same_company.add(f)
            continue
        # ``x = serializers.XField(..., read_only=True)`` → non écrivable.
        if isinstance(value, ast.Call):
            for kw in value.keywords:
                if kw.arg in ("read_only",) and isinstance(kw.value, ast.Constant) \
                        and kw.value.value is True:
                    read_only.update(noms)
                if kw.arg == "source" and isinstance(kw.value, ast.Constant):
                    # champ dérivé/renommé : la FK brute n'est plus écrite ici
                    read_only.update(noms)
        if isinstance(value, ast.Call) and _call_name(value) in (
                "SerializerMethodField",):
            read_only.update(noms)
    return read_only, same_company, validates


def collect_sites():
    fks, tenant, name_to_keys, _m2m = build_model_map()
    sites = []   # (rel, cls, field, target, couvert)

    # SPL72 — l'héritage se résout sur TOUTES les classes sérialiseurs d'une MÊME
    # app (pas seulement le fichier courant) : un mixin de ``serializers.py`` couvre
    # une sous-classe déplacée dans ``serializers_<x>.py``.
    parsed = []                 # (app, rel, tree)
    classes_by_app = {}         # app -> {nom: ClassDef}
    for app, path in _iter_serializer_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        parsed.append((app, _rel(path), tree))
        table = classes_by_app.setdefault(app, {})
        for n in ast.walk(tree):
            if isinstance(n, ast.ClassDef):
                table.setdefault(n.name, n)

    for app, rel, tree in parsed:
        classes = classes_by_app[app]
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            bases = _base_names(cls)
            if not any(b.endswith("ModelSerializer") for b in bases):
                continue
            meta = _meta_of(cls)
            if meta is None:
                continue
            model_name = None
            declared_fields = None
            read_only_meta = set()
            for stmt in meta.body:
                noms = _assigned_targets(stmt)
                value = getattr(stmt, "value", None)
                if "model" in noms and isinstance(value, ast.Name):
                    model_name = value.id
                elif "model" in noms and isinstance(value, ast.Attribute):
                    model_name = value.attr
                if "fields" in noms:
                    if isinstance(value, ast.Constant) and value.value == "__all__":
                        declared_fields = "__all__"
                    else:
                        declared_fields = _str_list(value)
                if "read_only_fields" in noms:
                    read_only_meta.update(_str_list(value) or [])
            if model_name is None or declared_fields is None:
                continue
            key = (app, model_name)
            if key not in fks:
                cands = name_to_keys.get(model_name, [])
                if len(cands) != 1:
                    continue
                key = cands[0]
            champs_fk = fks.get(key, {})
            if not champs_fk:
                continue

            read_only, same_company, validates = _serializer_facts(cls)
            borne_par_base = bool(SCOPING_BASES & set(bases))
            # Héritage intra-APP : une base (même fichier ou autre fichier
            # sérialiseur de l'app) couvre ses sous-classes, transitivement.
            vus = {cls.name}
            pile = list(bases)
            while pile:
                b = pile.pop()
                base_cls = classes.get(b)
                if base_cls is None or b in vus:
                    continue
                vus.add(b)
                if b in SCOPING_BASES:
                    borne_par_base = True
                b_ro, b_sc, b_val = _serializer_facts(base_cls)
                read_only |= b_ro
                same_company |= b_sc
                validates |= b_val
                pile.extend(_base_names(base_cls))
                if SCOPING_BASES & set(_base_names(base_cls)):
                    borne_par_base = True

            noms_exposes = (list(champs_fk)
                            if declared_fields == "__all__" else declared_fields)
            for champ in noms_exposes:
                cible = champs_fk.get(champ)
                if cible is None:
                    continue
                t_app, t_model = cible
                force = (t_app, t_model) in FORCED_TENANT_TARGETS
                if not force and t_app in FOUNDATION_APPS:
                    continue
                if not force and (t_app, t_model) not in tenant:
                    continue          # cible non scopée société : rien à valider
                if champ in read_only or champ in read_only_meta:
                    continue
                couvert = (borne_par_base or champ in same_company
                           or champ in validates)
                sites.append((rel, cls.name, champ,
                              f"{t_app}.{t_model}", couvert))
    return sites


# ── allowlist + main ───────────────────────────────────────────────────────

def _load_allowlist():
    if not ALLOWLIST_PATH.is_file():
        return set()
    out = set()
    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(line)
    return out


def main(argv):
    list_mode = "--list" in argv
    allow = _load_allowlist()
    sites = collect_sites()

    if list_mode:
        for rel, cls, champ, cible, couvert in sorted(sites):
            etat = "OK " if couvert else "NON"
            print(f"{etat} {rel}::{cls}.{champ} -> {cible}")
        return 0

    offenders = []
    for rel, cls, champ, cible, couvert in sorted(sites):
        cle = f"{rel}::{cls}.{champ}"
        if couvert or cle in allow:
            continue
        offenders.append(f"{cle} -> {cible}")

    if offenders:
        print("check_fk_scoping: FK cross-app écrivable non validée "
              "même-société (absente de scripts/fk_scoping_allow.txt) :")
        for line in offenders:
            print(f"  - {line}")
        print(
            "\nAjoutez le mixin partagé "
            "(core.mixins.SameCompanyFKSerializerMixin) et déclarez "
            "same_company_fields = ('<champ>',), ou écrivez un "
            "validate_<champ> même-société. Si ce site est un cas relu et "
            "légitime, ajoutez 'chemin::Serializer.champ' à "
            "scripts/fk_scoping_allow.txt."
        )
        return 1

    print(f"check_fk_scoping: OK — {len(sites)} FK cross-app écrivables, "
          "toutes validées même-société ou allowlistées.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

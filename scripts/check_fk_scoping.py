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

  1. ``backend/django_core/apps/*/models.py`` + ``core/models.py`` are parsed to
     map every ``ForeignKey('<app>.<Model>')`` and which models are
     tenant-scoped (they declare ``company`` or inherit a tenant base).
  2. Every ``*ModelSerializer`` subclass under ``apps/*/serializers*.py`` is
     matched to its ``Meta.model``; each ``Meta.fields`` entry that is a
     WRITABLE cross-app FK to a tenant-scoped model must be covered by either
     ``def validate_<field>`` or a declarative
     ``same_company_fields = (...)`` (``core.mixins.SameCompanyFKSerializerMixin``).

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


def _base_names(cls: ast.ClassDef):
    names = []
    for base in cls.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
    return names


# ── 1. carte des modèles ───────────────────────────────────────────────────

def _iter_model_files():
    core_models = DJANGO_CORE / "core" / "models.py"
    if core_models.is_file():
        yield "core", core_models
    if not APPS_DIR.is_dir():
        return
    for app_dir in sorted(APPS_DIR.iterdir()):
        if not app_dir.is_dir():
            continue
        mp = app_dir / "models.py"
        if mp.is_file():
            yield app_dir.name, mp
        mdir = app_dir / "models"
        if mdir.is_dir():
            for f in sorted(mdir.glob("*.py")):
                yield app_dir.name, f


def build_model_map():
    """→ (fks, tenant_models)

    ``fks``: ``{(app, Model): {field: (target_app, target_model)}}``
    ``tenant_models``: ``{(app, Model)}`` portant une société.
    """
    fks = {}
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
                if _call_name(value) not in FK_CALLS:
                    continue
                cible = value.args[0] if value.args else None
                if not (isinstance(cible, ast.Constant)
                        and isinstance(cible.value, str)):
                    # FK vers une classe locale (même app) — hors périmètre.
                    continue
                brut = cible.value
                if "." not in brut:
                    continue
                t_app, t_model = brut.split(".", 1)
                for nom in noms:
                    if nom == "company":
                        declares_company.add(key)
                    champs[nom] = (t_app, t_model)

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
    return fks, tenant, name_to_keys


# ── 2. balayage des sérialiseurs ───────────────────────────────────────────

def _iter_serializer_files():
    if not APPS_DIR.is_dir():
        return
    for app_dir in sorted(APPS_DIR.iterdir()):
        if not app_dir.is_dir():
            continue
        sp = app_dir / "serializers.py"
        if sp.is_file():
            yield app_dir.name, sp
        sdir = app_dir / "serializers"
        if sdir.is_dir():
            for f in sorted(sdir.glob("*.py")):
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
    fks, tenant, name_to_keys = build_model_map()
    sites = []   # (rel, cls, field, target, couvert)

    for app, path in _iter_serializer_files():
        rel = _rel(path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        classes = {n.name: n for n in ast.walk(tree)
                   if isinstance(n, ast.ClassDef)}
        for cls in classes.values():
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
            # Héritage intra-fichier : une base couvre ses sous-classes.
            for b in bases:
                base_cls = classes.get(b)
                if base_cls is not None:
                    b_ro, b_sc, b_val = _serializer_facts(base_cls)
                    read_only |= b_ro
                    same_company |= b_sc
                    validates |= b_val

            noms_exposes = (list(champs_fk)
                            if declared_fields == "__all__" else declared_fields)
            for champ in noms_exposes:
                cible = champs_fk.get(champ)
                if cible is None:
                    continue
                t_app, t_model = cible
                if t_app == key[0] or t_app in FOUNDATION_APPS:
                    continue
                if (t_app, t_model) not in tenant:
                    continue          # cible non scopée société : rien à valider
                if champ in read_only or champ in read_only_meta:
                    continue
                couvert = champ in same_company or champ in validates
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

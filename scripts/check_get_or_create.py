"""YDATA15 — bloquant (ENF13): `get_or_create`/`update_or_create` lookup keys
should be backed by a `UniqueConstraint` (Django's documented race).

DB-free, AST-only (mirrors ``scripts/check_on_delete.py``). Scans every
``apps/*/*.py`` (migrations/tests excluded) for a
``.get_or_create(...)``/``.update_or_create(...)`` call and lists, per call
site, its LOOKUP keyword arguments (everything except ``defaults=``) — the
keys that SHOULD correspond to a company-scoped ``UniqueConstraint``/
``unique_together`` on the target model to make the call race-safe.

v1 = ADVISORY (per spec): it does not fix anything — it produces
``docs/get-or-create-audit.md`` (file:line, lookup keys) for human review.
The committed doc IS the baseline (same pattern as
``check_on_delete.py --financial``): a call site already recorded there
passes; a NEW site not yet recorded fails CI (forces the reviewer to look
at whether the target model needs a constraint before merging).

ENF18 (tranche get_or_create) — GARANTIE D'UNICITE RECONNUE (statique, AST,
stdlib). Un appel dont les kwargs de lookup contiennent TOUS les champs d'une
garantie d'unicite du modele cible est course-safe (la base refuse le doublon,
Django relit) : il n'est plus liste dans le registre et n'a pas besoin d'y
figurer. Garanties reconnues, lues dans ``models.py`` / ``models_*.py`` /
``models/*.py`` (apps/*, core, authentication) : champ ``unique=True`` /
``primary_key=True``, ``OneToOneField``, ``Meta.unique_together``,
``Meta.constraints`` ``UniqueConstraint(fields=[...])`` (heritees d'une classe
de base ; ``Base.Meta`` comprise). ``company_id`` equivaut a ``company`` (le
suffixe ``_id`` est ignore des deux cotes) ; ``pk=`` est toujours unique.
Prudence : une contrainte a ``condition=`` ne couvre l'appel que si chaque
terme de sa condition (``Q(a=1, b__isnull=True) & Q(...)``) est repris tel quel
dans le lookup (meme cle, meme valeur litterale) ; une condition en OR / NOT /
expression non lisible n'est jamais comptee ; un champ du lookup passe a la
valeur litterale ``None`` n'est pas compte (NULL != NULL en base). Limite assumee :
un champ ``null=True`` dont la valeur est une variable est compte. Recepteurs
resolus : ``Modele.objects`` (+ ``.select_for_update()``/``.all()``/``.using()``
...), un alias ``from .models import X as Y``, ``cls.objects`` / ``self.__class__``
/ ``type(self)`` dans une classe de modele. Tout le reste (variable, manager
lie ``obj.relation``, queryset filtre) reste liste : jamais un faux « couvert ».

Usage:
    python scripts/check_get_or_create.py          # lecture seule (CI)
    python scripts/check_get_or_create.py --write  # regenere le registre

ADEP29 : le controle est en LECTURE SEULE (deux lancements successifs sur un
appel nouveau rendent tous deux 1) ; le registre ne change que par ``--write``
et ses cles sont de CONTENU (``fichier::fonction::Modele``), pas de ligne.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import NamedTuple

TYPE_DE_CLE = "par_symbole"  # AMET81 — lu par audit_tache.py listes-figees : cle `fichier::fonction::Modele`
ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"
AUDIT_DOC = ROOT / "docs" / "get-or-create-audit.md"

CALL_NAMES = {"get_or_create", "update_or_create"}
# Appels de queryset qui ne FILTRENT pas : `Foo.objects.select_for_update().get_or_create`
# garde le meme lookup que `Foo.objects.get_or_create`.
QS_SANS_FILTRE = {"select_for_update", "all", "using", "select_related",
                  "prefetch_related", "only", "defer", "order_by"}


def _est_test(name: str) -> bool:
    return bool(re.match(r"^tests?(_.*)?\.py$", name) or name.endswith("_test.py"))


def _iter_source_files():
    if not APPS_DIR.is_dir():
        return
    for app_dir in sorted(APPS_DIR.iterdir()):
        if not app_dir.is_dir():
            continue
        for path in sorted(app_dir.rglob("*.py")):
            rel_parts = path.relative_to(app_dir).parts
            if "migrations" in rel_parts:
                continue
            name = path.name
            if re.match(r"^tests?(_.*)?\.py$", name) \
                    or name.endswith("_test.py") or "tests" in rel_parts:
                continue
            yield path


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _lookup_keys(node):
    """Keyword arg names of the call, excluding 'defaults'."""
    return sorted(kw.arg for kw in node.keywords
                  if kw.arg and kw.arg != "defaults")


def _lookup_valeurs(node):
    """{cle: noeud valeur} du lookup (hors `defaults`, hors `**dict` inconnu)."""
    return {kw.arg: kw.value for kw in node.keywords
            if kw.arg and kw.arg != "defaults"}


def _call_target_repr(node):
    """Best-effort textual form of the receiver, e.g. 'Devis.objects' or
    'self.queryset'."""
    try:
        return ast.unparse(node.func.value)
    except Exception:
        return "?"


def _modele(receiver: str) -> str:
    """Le modele vise : ``Devis.objects`` -> ``Devis`` ; ``self.queryset`` reste
    tel quel (la cle est de CONTENU, jamais un numero de ligne)."""
    return receiver.split(".objects", 1)[0] or receiver


# --------------------------------------------------------------------------
# ENF18 — index statique des garanties d'unicite des modeles
# --------------------------------------------------------------------------


def _nom_terminal(node) -> str:
    """``models.OneToOneField`` -> ``OneToOneField`` ; ``Foo`` -> ``Foo``."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _norm(champ: str) -> str:
    """``company_id`` == ``company`` (le suffixe ``_id`` est ignore des deux cotes)."""
    return champ[:-3] if champ.endswith("_id") and len(champ) > 3 else champ


def _vrai(node) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _chaines(node):
    """Liste des chaines litterales d'un tuple/liste ; None si autre chose."""
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    out = []
    for elt in node.elts:
        if not (isinstance(elt, ast.Constant) and isinstance(elt.value, str)):
            return None
        out.append(elt.value)
    return out


def _aplatir(node):
    """Elements d'une liste/tuple, ``a + b`` compris (``constraints = [..] + [..]``)."""
    if isinstance(node, (ast.List, ast.Tuple)):
        return list(node.elts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _aplatir(node.left) + _aplatir(node.right)
    return []


def _atomes_condition(node):
    """Condition d'une contrainte partielle -> conjonction ``[(cle, dump_valeur)]``
    (``Q(a=1, b__isnull=True) & Q(c=2)``) ; ``None`` si illisible (OR, NOT, expression)."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitAnd):
        gauche, droite = _atomes_condition(node.left), _atomes_condition(node.right)
        return None if gauche is None or droite is None else gauche + droite
    if isinstance(node, ast.Call) and _nom_terminal(node.func) == "Q":
        atomes = []
        for kw in node.keywords:
            if kw.arg is None or kw.arg.startswith("_"):
                return None
            atomes.append((kw.arg, ast.dump(kw.value)))
        for arg in node.args:
            sous = _atomes_condition(arg)
            if sous is None:
                return None
            atomes.extend(sous)
        return atomes
    return None


class _Modele:
    """Ce que l'AST d'une classe dit de son unicite."""

    def __init__(self, nom, app, bases, champs_uniques, nullables, meta, meta_bases):
        self.nom = nom
        self.app = app
        self.bases = bases                    # noms terminaux des classes meres
        self.champs_uniques = champs_uniques  # champs unique=True / pk / OneToOne
        self.nullables = nullables            # champs declares null=True (NULL != NULL en base)
        self.meta = meta                      # None = pas de `class Meta` ; sinon [(frozenset, atomes|None)]
        self.meta_bases = meta_bases          # `class Meta(Base.Meta)` -> ['Base']


def _champs_du_corps(classdef):
    """(champs uniques, champs ``null=True``) declares dans le corps de la classe."""
    out, nullables = [], set()
    for stmt in classdef.body:
        if isinstance(stmt, ast.Assign):
            cibles = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
            valeur = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            cibles, valeur = [stmt.target.id], stmt.value
        else:
            continue
        if not isinstance(valeur, ast.Call):
            continue
        unique = _nom_terminal(valeur.func) == "OneToOneField" or any(
            kw.arg in ("unique", "primary_key") and _vrai(kw.value) for kw in valeur.keywords)
        if unique:
            out.extend(cibles)
        if any(kw.arg == "null" and _vrai(kw.value) for kw in valeur.keywords):
            nullables.update(_norm(c) for c in cibles)
    return out, nullables


def _meta_uniques(meta):
    """``unique_together`` + ``UniqueConstraint(fields=[...])`` d'un ``class Meta``."""
    garanties = []
    for stmt in meta.body:
        if not isinstance(stmt, ast.Assign):
            continue
        cibles = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
        if "unique_together" in cibles:
            plat = _chaines(stmt.value)
            groupes = [plat] if plat else [_chaines(g) for g in _aplatir(stmt.value)]
            garanties.extend((frozenset(_norm(c) for c in g), []) for g in groupes if g)
        if "constraints" in cibles:
            for elt in _aplatir(stmt.value):
                if not (isinstance(elt, ast.Call) and _nom_terminal(elt.func) == "UniqueConstraint"):
                    continue
                kws = {kw.arg: kw.value for kw in elt.keywords if kw.arg}
                champs = _chaines(kws.get("fields"))
                if not champs:
                    continue  # UniqueConstraint(Lower(...)) : expression, jamais comptee
                atomes = [] if "condition" not in kws else _atomes_condition(kws["condition"])
                garanties.append((frozenset(_norm(c) for c in champs), atomes))
    return garanties


def _indexer_classes(tree, app):
    """Classes de modele d'un fichier : une ``_Modele`` par ClassDef de premier niveau."""
    out = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        meta, meta_bases = None, []
        for stmt in node.body:
            if isinstance(stmt, ast.ClassDef) and stmt.name == "Meta":
                meta = _meta_uniques(stmt)
                meta_bases = [b.value.id for b in stmt.bases
                              if isinstance(b, ast.Attribute) and isinstance(b.value, ast.Name)]
        uniques, nullables = _champs_du_corps(node)
        out.append(_Modele(node.name, app, [_nom_terminal(b) for b in node.bases],
                           uniques, nullables, meta, meta_bases))
    return out


def _fichiers_modeles():
    """Fichiers susceptibles de definir un modele : tout `*.py` (hors migrations/tests) de
    apps/*, core et authentication — un modele vit parfois hors `models.py`
    (`core/idempotency.py`) ; `_est_modele` ecarte ensuite les classes qui n'en sont pas."""
    racines = sorted(p for p in APPS_DIR.iterdir() if p.is_dir()) if APPS_DIR.is_dir() else []
    for extra in ("core", "authentication"):
        if (DJANGO_CORE / extra).is_dir():
            racines.append(DJANGO_CORE / extra)
    for racine in racines:
        for path in sorted(racine.rglob("*.py")):
            rel_parts = path.relative_to(racine).parts
            if "migrations" in rel_parts or "tests" in rel_parts or _est_test(path.name):
                continue
            yield path


_RE_BASE_MODELE = re.compile(r"^class\s+\w+\([^)]*(?:Model|Abstract)", re.M)


def _est_fichier_modeles(path: Path) -> bool:
    """models.py / models_*.py / models/*.py : toujours lus (les classes filles y vivent)."""
    return path.name == "models.py" or path.name.startswith("models_") or path.parent.name == "models"


def _app_de(path: Path) -> str:
    parts = path.relative_to(DJANGO_CORE).parts
    return parts[1] if parts[0] == "apps" else parts[0]


def _filtrer_modeles(classes):
    """Ne garde que les vrais modeles : une base `*Model` / `Abstract*`, ou une classe deja retenue
    (point fixe — `class Devis(TenantModel)`, `class Pdf(Devis)`)."""
    retenus = [c for c in classes if any(b.endswith("Model") or b.startswith("Abstract") for b in c.bases)]
    while True:
        noms = {c.nom for c in retenus}
        plus = [c for c in classes if c not in retenus and any(b in noms for b in c.bases)]
        if not plus:
            return retenus
        retenus += plus


def construire_index():
    """{nom de classe: [_Modele]} — un fichier illisible est ignore, jamais une exception."""
    classes = []
    for path in _fichiers_modeles():
        try:
            texte = path.read_text(encoding="utf-8")
            if not _est_fichier_modeles(path) and not _RE_BASE_MODELE.search(texte):
                continue  # evite de parser deux fois les milliers de fichiers qui ne definissent aucun modele
            tree = ast.parse(texte, filename=str(path))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        classes.extend(_indexer_classes(tree, _app_de(path)))
    index = {}
    for modele in _filtrer_modeles(classes):
        index.setdefault(modele.nom, []).append(modele)
    return index


def _candidats(nom, app, index, indices=()):
    """Classes portant ce nom. Ordre de preference : l'app d'ou le fichier importe le nom
    (``from apps.parametres.models_messages import X`` -> parametres), puis l'app appelante,
    puis toutes (un doublon de nom oblige alors TOUTES les classes a couvrir)."""
    toutes = index.get(nom, [])
    return ([m for m in toutes if m.app in indices] or [m for m in toutes if m.app == app] or toutes)


def _garanties_champs(modele, index, vus):
    """Garanties portees par les CHAMPS (propres + herites de toute classe mere)."""
    if id(modele) in vus:
        return []
    vus.add(id(modele))
    out = [(frozenset([_norm(c)]), []) for c in modele.champs_uniques]
    for base in modele.bases:
        for mere in _candidats(base, modele.app, index):
            out.extend(_garanties_champs(mere, index, vus))
    return out


def _garanties_meta(modele, index, vus):
    """Garanties du ``Meta`` : le sien (+ `class Meta(Base.Meta)`), sinon celui des meres."""
    if id(modele) in vus:
        return []
    vus.add(id(modele))
    if modele.meta is not None:
        out = list(modele.meta)
        sources = modele.meta_bases
    else:
        out, sources = [], modele.bases
    for base in sources:
        for mere in _candidats(base, modele.app, index):
            out.extend(_garanties_meta(mere, index, vus))
    return out


def _nullables(modele, index, vus):
    """Champs ``null=True`` du modele (propres + herites de toute classe mere)."""
    if id(modele) in vus:
        return set()
    vus.add(id(modele))
    out = set(modele.nullables)
    for base in modele.bases:
        for mere in _candidats(base, modele.app, index):
            out |= _nullables(mere, index, vus)
    return out


def garanties(modele, index):
    return _garanties_champs(modele, index, set()) + _garanties_meta(modele, index, set())


def _couvre(modele, index, valeurs):
    """Le lookup ``valeurs`` ({cle: noeud}) pointe-t-il au plus UNE ligne de ``modele`` ?"""
    if "id" in valeurs:
        return True
    # Un champ NULLABLE d'une contrainte n'epingle rien quand sa valeur peut etre NULL (NULL != NULL :
    # `owner_id=None` cree un doublon) : seule une constante non nulle compte. `company` fait exception
    # (FK tenant `null=True` historique, toujours posee a l'appel ; le litteral `None` reste exclu).
    nullables = _nullables(modele, index, set()) - {"company"}
    epingles = set()
    for cle, noeud in valeurs.items():
        if "__" in cle:
            continue
        constante = isinstance(noeud, ast.Constant)
        if constante and noeud.value is None:
            continue
        if _norm(cle) in nullables and not constante:
            continue
        epingles.add(_norm(cle))
    dumps = {cle: ast.dump(noeud) for cle, noeud in valeurs.items()}
    for champs, atomes in garanties(modele, index):
        if atomes is None or not champs <= epingles:
            continue
        if all(dumps.get(cle) == dump for cle, dump in atomes):
            return True
    return False


def _cible(recepteur, classe, imports):
    """(nom de la classe visee, apps d'import) ou (None, ()) si non resolu.

    ``Foo.objects`` / ``Foo.objects.select_for_update()`` / ``models.Foo.objects``
    -> ``Foo`` (alias ``import X as Y`` resolus) ; ``cls.objects``,
    ``self.__class__.objects``, ``type(self).objects`` -> la classe englobante."""
    while (isinstance(recepteur, ast.Call) and isinstance(recepteur.func, ast.Attribute)
           and recepteur.func.attr in QS_SANS_FILTRE):
        recepteur = recepteur.func.value
    if not isinstance(recepteur, ast.Attribute):
        return None, ()
    base = recepteur.value
    if isinstance(base, ast.Name):
        if base.id == "cls":
            return classe, ()
        if not base.id[:1].isupper():
            return None, ()
        origines = imports.get(base.id)
        if not origines:
            return base.id, ()
        if len({nom for nom, _ in origines}) != 1:
            return None, ()  # meme nom local importe de deux classes differentes : on ne devine pas
        return origines[0][0], tuple(sorted({app for _, app in origines if app}))
    if isinstance(base, ast.Attribute):
        if base.attr == "__class__" and isinstance(base.value, ast.Name) and base.value.id == "self":
            return classe, ()
        return (base.attr, ()) if base.attr[:1].isupper() else (None, ())
    if (isinstance(base, ast.Call) and isinstance(base.func, ast.Name) and base.func.id == "type"
            and len(base.args) == 1 and isinstance(base.args[0], ast.Name) and base.args[0].id == "self"):
        return classe, ()
    return None, ()


class Appel(NamedTuple):
    cle: str
    lineno: int
    call: str
    receiver: str
    keys: list
    app: str
    cible: object   # nom de la classe visee ou None
    valeurs: dict
    indices: tuple  # apps d'ou le fichier importe ce nom (preference de resolution)


def est_couvert(appel, index):
    """True si le lookup de l'appel est adosse a une garantie d'unicite connue."""
    if "pk" in appel.valeurs:
        return True
    if not appel.cible:
        return False
    candidats = _candidats(appel.cible, appel.app, index, appel.indices)
    return bool(candidats) and all(_couvre(m, index, appel.valeurs) for m in candidats)


class _Visiteur(ast.NodeVisitor):
    def __init__(self):
        self.pile = []
        self.classes = []
        self.appels = []  # (noeud, fonction qualifiee, classe englobante)

    def _porte(self, node):
        self.pile.append(node.name)
        self.generic_visit(node)
        self.pile.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = _porte

    def visit_ClassDef(self, node):
        self.classes.append(node.name)
        self._porte(node)
        self.classes.pop()

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and node.func.attr in CALL_NAMES:
            self.appels.append((node, ".".join(self.pile) or "<module>",
                                self.classes[-1] if self.classes else None))
        self.generic_visit(node)


def _imports(tree):
    """{nom local: [(nom d'origine, app d'origine ou None)]} des ``from X import Y [as Z]``
    (niveau fonction compris). L'app n'est lue que d'un import ABSOLU (``apps.parametres.models``
    -> parametres ; ``core.idempotency`` -> core) : un import relatif reste sans indice."""
    out = {}
    for n in ast.walk(tree):
        if not isinstance(n, ast.ImportFrom):
            continue
        parts = (n.module or "").split(".")
        app = None
        if n.level == 0 and parts[0] == "apps" and len(parts) > 1:
            app = parts[1]
        elif n.level == 0 and parts[0] in ("core", "authentication"):
            app = parts[0]
        for a in n.names:
            out.setdefault(a.asname or a.name, []).append((a.name, app))
    return out


def analyser(path: Path):
    """Appels get_or_create/update_or_create d'un fichier (liste d'``Appel``)."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    visiteur = _Visiteur()
    visiteur.visit(tree)
    imports = _imports(tree) if visiteur.appels else {}
    app = path.relative_to(APPS_DIR).parts[0]
    rows = []
    for node, fonction, classe in visiteur.appels:
        receiver = _call_target_repr(node)
        cle = f"{_rel(path)}::{fonction}::{_modele(receiver)}"
        cible, indices = _cible(node.func.value, classe, imports)
        rows.append(Appel(cle, node.lineno, node.func.attr, receiver, _lookup_keys(node), app,
                          cible, _lookup_valeurs(node), indices))
    return rows


def check_file(path: Path):
    """Compatibilite : (cle, ligne, appel, recepteur, cles) par appel du fichier."""
    return [(a.cle, a.lineno, a.call, a.receiver, a.keys) for a in analyser(path)]


def _load_baseline():
    if not AUDIT_DOC.exists():
        return set()
    out = set()
    for line in AUDIT_DOC.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("| `"):
            continue
        key = line.split("`", 2)[1]
        out.add(key)
    return out


def _write_audit_doc(rows):
    lines = [
        "# Audit get_or_create / update_or_create (YDATA15)",
        "",
        "Généré par `python scripts/check_get_or_create.py`. Chaque appel "
        "listé n'est adossé à AUCUNE garantie d'unicité connue du modèle cible "
        "(`unique=True`, `OneToOneField`, `unique_together`, `UniqueConstraint`, "
        "héritées comprises — lues en AST) : ses clés de lookup (hors `defaults`) "
        "devraient correspondre à une `UniqueConstraint`/`unique_together` "
        "company-scopée pour être course-safe. Les appels déjà adossés ne sont "
        "plus listés (ENF18). Advisory : ce sweep ne corrige rien (correctifs = "
        "ERROR_PLAN).",
        "",
        "Clé de CONTENU `fichier::fonction::Modèle` (jamais un numéro de ligne : "
        "une insertion en amont ne fait plus remonter les voisins comme "
        "nouveaux). Régénéré par `python scripts/check_get_or_create.py --write`.",
        "",
        "| Clé | Appel | Récepteur | Clés de lookup |",
        "|---|---|---|---|",
    ]
    for cle, lineno, call, receiver, keys in sorted(rows):
        lines.append(
            f"| `{cle}` | {call} | {receiver} | {', '.join(keys)} |")
    AUDIT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv):
    """Lecture SEULE par defaut (ADEP29) : comparaison au registre, jamais
    d'ecriture. ``--write`` regenere ``docs/get-or-create-audit.md``."""
    ecrire = "--write" in argv
    baseline = _load_baseline()
    index = construire_index()

    tous = []
    for path in _iter_source_files():
        tous.extend(analyser(path))
    ouverts = [a for a in tous if not est_couvert(a, index)]
    all_rows = [(a.cle, a.lineno, a.call, a.receiver, a.keys) for a in ouverts]

    print(f"check_get_or_create: {len(tous)} get_or_create/"
          f"update_or_create call(s) found, {len(tous) - len(ouverts)} backed by a "
          f"uniqueness guarantee, {len(ouverts)} to register.")
    for cle, lineno, call, receiver, keys in all_rows:
        print(f"  {cle}:{lineno}  {receiver}.{call}({', '.join(keys)})")

    findings = []
    for cle, lineno, call, receiver, keys in all_rows:
        if cle not in baseline:
            findings.append(
                f"{cle} (ligne {lineno}): NEW {call}({', '.join(keys)}) on "
                f"{receiver} — no known uniqueness guarantee covers this lookup; "
                "add a UniqueConstraint/unique_together on the target model "
                "(preferred) or review it and regenerate with "
                "`python scripts/check_get_or_create.py --write`, then commit "
                "docs/get-or-create-audit.md.")

    if ecrire:
        _write_audit_doc(all_rows)
        print(f"\ncheck_get_or_create: wrote {_rel(AUDIT_DOC)}")
        return 0

    if findings:
        print("\ncheck_get_or_create: violation(s) found:")
        for line in findings:
            print(f"  - {line}")
        return 1

    print("\ncheck_get_or_create: OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

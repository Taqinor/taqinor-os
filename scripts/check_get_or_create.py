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
dans le lookup (meme cle, meme valeur litterale) ; un terme ``~Q(f__isnull=True)`` /
``Q(f__isnull=False)`` / ``~Q(f='')`` est satisfait quand la valeur de ``f`` dans le
lookup est PROUVEE non nulle / non vide (voir ci-dessous) ; une condition en OR /
expression non lisible n'est jamais comptee ; un champ du lookup passe a la valeur
litterale ``None`` n'est pas compte (NULL != NULL en base).

VALEUR PROUVEE NON NULLE (ENF18) : un champ ``null=True`` dont la valeur est une VARIABLE
n'epingle rien (NULL != NULL) -- sauf si la fonction l'ecarte avant l'appel :
``if x is None: return|continue|raise`` / ``if not x or not y: ...`` (garde-fou d'entree,
sortie obligatoire), un appel DANS ``if x is not None:`` / ``if x:``, ou ``assert x``.
Le nom ne doit etre ni reaffecte entre le garde-fou et l'appel (boucles comprises).
``x is None`` ecarte prouve NON NUL ; ``not x`` ecarte prouve NON NUL ET NON VIDE.
Rien d'autre n'est devine (attribut, appel, lambda : jamais prouve). Recepteurs
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
    """Condition d'une contrainte partielle -> conjonction ``[(cle, dump_valeur, nie)]``
    (``Q(a=1, b__isnull=True) & ~Q(c='')`` ; ``nie`` = terme precede de ``~``) ; ``None`` si
    illisible (OR, expression, ``~`` d'un terme multiple)."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitAnd):
        gauche, droite = _atomes_condition(node.left), _atomes_condition(node.right)
        return None if gauche is None or droite is None else gauche + droite
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert):
        sous = _atomes_condition(node.operand)
        if sous is None or len(sous) != 1 or sous[0][2]:
            return None
        return [(sous[0][0], sous[0][1], True)]
    if isinstance(node, ast.Call) and _nom_terminal(node.func) == "Q":
        atomes = []
        for kw in node.keywords:
            if kw.arg is None or kw.arg.startswith("_"):
                return None
            atomes.append((kw.arg, ast.dump(kw.value), False))
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


_DUMP_VRAI = ast.dump(ast.Constant(value=True))
_DUMP_FAUX = ast.dump(ast.Constant(value=False))
_DUMP_VIDE = ast.dump(ast.Constant(value=""))


def _prouve(noeud, prouves, niveau):
    """La valeur ``noeud`` est-elle PROUVEE non nulle (``niveau='nonnul'``) ou non nulle ET non vide
    (``'vrai'``) ? Une constante se lit telle quelle ; une variable par ``prouves`` ({nom: niveau})."""
    if isinstance(noeud, ast.Constant):
        return noeud.value is not None and (niveau == "nonnul" or bool(noeud.value))
    if isinstance(noeud, ast.Name):
        return prouves.get(noeud.id) == "vrai" or (niveau == "nonnul" and noeud.id in prouves)
    return False


def _valeur_du_champ(valeurs, champ):
    """Noeud de la valeur passee pour ``champ`` (``champ`` ou ``champ_id``, jamais ``champ__lookup``)."""
    for cle, noeud in valeurs.items():
        if "__" not in cle and _norm(cle) == _norm(champ):
            return noeud
    return None


def _atome_ok(atome, valeurs, dumps, prouves):
    """Un terme ``(cle, dump, nie)`` de la condition d'une contrainte partielle est-il satisfait par le
    lookup ? Repris tel quel (meme cle, meme litteral) ; ou ``~Q(f__isnull=True)`` / ``Q(f__isnull=False)``
    avec ``f`` prouve non nul ; ou ``~Q(f='')`` avec ``f`` prouve non nul ET non vide."""
    cle, dump, nie = atome
    if not nie and dumps.get(cle) == dump:
        return True
    champ, _, suffixe = cle.partition("__")
    valeur = _valeur_du_champ(valeurs, champ)
    if valeur is None:
        return False
    if suffixe == "isnull" and dump in (_DUMP_VRAI, _DUMP_FAUX):
        return (dump == _DUMP_FAUX) != nie and _prouve(valeur, prouves, "nonnul")
    if nie and not suffixe and dump == _DUMP_VIDE:
        return _prouve(valeur, prouves, "vrai")
    return False


def _couvre(modele, index, valeurs, prouves=None):
    """Le lookup ``valeurs`` ({cle: noeud}) pointe-t-il au plus UNE ligne de ``modele`` ?
    ``prouves`` = {nom: niveau} des variables prouvees non nulles a cet appel (``_prouves_par_appel``)."""
    prouves = prouves or {}
    if "id" in valeurs:
        return True
    # Un champ NULLABLE d'une contrainte n'epingle rien quand sa valeur peut etre NULL (NULL != NULL :
    # `owner_id=None` cree un doublon) : seule une constante non nulle -- ou une variable PROUVEE non nulle
    # par un garde-fou de la fonction -- compte. `company` fait exception (FK tenant `null=True`
    # historique, toujours posee a l'appel ; le litteral `None` reste exclu).
    nullables = _nullables(modele, index, set()) - {"company"}
    epingles = set()
    for cle, noeud in valeurs.items():
        if "__" in cle:
            continue
        constante = isinstance(noeud, ast.Constant)
        if constante and noeud.value is None:
            continue
        if _norm(cle) in nullables and not constante and not _prouve(noeud, prouves, "nonnul"):
            continue
        epingles.add(_norm(cle))
    dumps = {cle: ast.dump(noeud) for cle, noeud in valeurs.items()}
    for champs, atomes in garanties(modele, index):
        if atomes is None or not champs <= epingles:
            continue
        if all(_atome_ok(atome, valeurs, dumps, prouves) for atome in atomes):
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
    prouves: dict = {}  # {nom: 'nonnul'|'vrai'} des variables prouvees non nulles a cet appel


def est_couvert(appel, index):
    """True si le lookup de l'appel est adosse a une garantie d'unicite connue."""
    if "pk" in appel.valeurs:
        return True
    if not appel.cible:
        return False
    candidats = _candidats(appel.cible, appel.app, index, appel.indices)
    return bool(candidats) and all(_couvre(m, index, appel.valeurs, appel.prouves) for m in candidats)


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


# --------------------------------------------------------------------------
# ENF18 — variables PROUVEES non nulles a un appel (garde-fous de la fonction)
# --------------------------------------------------------------------------


def _fusion(base, plus):
    """Fusionne deux {nom: niveau} ; ``'vrai'`` (non nul ET non vide) l'emporte sur ``'nonnul'``."""
    out = dict(base)
    for nom, niveau in plus.items():
        if out.get(nom) != "vrai":
            out[nom] = niveau
    return out


def _prouve_si(test, vrai=True):
    """{nom: niveau} PROUVE quand ``test`` vaut ``vrai`` (False : quand il est faux).

    ``x is not None`` vrai / ``x is None`` faux -> ``nonnul`` ; ``x`` vrai / ``not x`` faux -> ``vrai`` ;
    ``a and b`` vrai et ``a or b`` faux combinent leurs termes. Tout le reste ne prouve rien."""
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return _prouve_si(test.operand, not vrai)
    if isinstance(test, ast.Name):
        return {test.id: "vrai"} if vrai else {}
    if (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.left, ast.Name)
            and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value is None):
        if (isinstance(test.ops[0], ast.IsNot) and vrai) or (isinstance(test.ops[0], ast.Is) and not vrai):
            return {test.left.id: "nonnul"}
        return {}
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And) == vrai:
        out = {}
        for terme in test.values:
            out = _fusion(out, _prouve_si(terme, vrai))
        return out
    return {}


def _affectes(noeuds):
    """Noms (re)lies par ces noeuds : cibles d'affectation / ``for`` / ``with .. as`` / ``:=`` / ``del``,
    ``except .. as``, imports et ``def``/``class`` imbriques (sur-approximation : un nom en trop ne fait que
    retirer une preuve, jamais en inventer)."""
    out = set()
    for noeud in noeuds:
        for n in ast.walk(noeud):
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                out.add(n.id)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                out.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                out.update((a.asname or a.name).split(".")[0] for a in n.names)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.add(n.name)
    return out


def _sort_toujours(stmts):
    """Le bloc finit-il TOUJOURS par une sortie (``return`` / ``raise`` / ``continue`` / ``break``) ?"""
    return bool(stmts) and isinstance(stmts[-1], (ast.Return, ast.Raise, ast.Continue, ast.Break))


def _noter(noeud, connus, out):
    """Note, pour chaque appel get_or_create/update_or_create sous ``noeud``, les preuves en vigueur
    (``connus``). Un ``lambda`` s'execute plus tard : rien n'y est prouve."""
    if isinstance(noeud, ast.Lambda):
        connus = {}
    if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute) and noeud.func.attr in CALL_NAMES:
        out[id(noeud)] = dict(connus)
    for enfant in ast.iter_child_nodes(noeud):
        _noter(enfant, connus, out)


def _sans(connus, noms):
    return {nom: niveau for nom, niveau in connus.items() if nom not in noms}


def _parcourir(stmts, connus, out):
    """Parcourt un bloc d'instructions en propageant les preuves ``connus`` ({nom: niveau}) : un garde-fou
    ``if x is None: return`` prouve ``x`` pour la suite du bloc, un ``if x:`` pour son corps, un ``assert``
    pour la suite ; toute reaffectation du nom retire la preuve (boucles comprises)."""
    connus = dict(connus)
    for stmt in stmts:
        if isinstance(stmt, ast.If):
            _noter(stmt.test, connus, out)
            vrai, faux = _prouve_si(stmt.test, True), _prouve_si(stmt.test, False)
            _parcourir(stmt.body, _fusion(connus, vrai), out)
            _parcourir(stmt.orelse, _fusion(connus, faux), out)
            corps_sort, autre_sort = _sort_toujours(stmt.body), bool(stmt.orelse) and _sort_toujours(stmt.orelse)
            if corps_sort and not autre_sort:    # seule la branche sinon (ou le passage direct) continue
                perdus = _affectes(stmt.orelse)
                connus = _fusion(_sans(connus, perdus), _sans(faux, perdus))
            elif autre_sort and not corps_sort:  # seule la branche alors continue
                perdus = _affectes(stmt.body)
                connus = _fusion(_sans(connus, perdus), _sans(vrai, perdus))
            else:
                connus = _sans(connus, _affectes([stmt]))
        elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            base = _sans(connus, _affectes([stmt]))
            if isinstance(stmt, ast.While):
                _noter(stmt.test, base, out)
                _parcourir(stmt.body, _fusion(base, _prouve_si(stmt.test, True)), out)
            else:
                _noter(stmt.iter, connus, out)
                _parcourir(stmt.body, base, out)
            _parcourir(stmt.orelse, base, out)
            connus = base
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            for item in stmt.items:
                _noter(item.context_expr, connus, out)
            interieur = _sans(connus, _affectes([item.optional_vars for item in stmt.items if item.optional_vars]))
            _parcourir(stmt.body, interieur, out)
            connus = _sans(connus, _affectes([stmt]))
        elif isinstance(stmt, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            apres_corps = _sans(connus, _affectes(stmt.body))
            _parcourir(stmt.body, connus, out)
            for gestionnaire in stmt.handlers:
                _parcourir(gestionnaire.body, _sans(apres_corps, _affectes([gestionnaire])), out)
            _parcourir(stmt.orelse, apres_corps, out)
            _parcourir(stmt.finalbody, _sans(connus, _affectes([stmt])), out)
            connus = _sans(connus, _affectes([stmt]))
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for expr in stmt.decorator_list + stmt.args.defaults + [d for d in stmt.args.kw_defaults if d]:
                _noter(expr, connus, out)
            _parcourir(stmt.body, {}, out)
            connus = _sans(connus, {stmt.name})
        elif isinstance(stmt, ast.ClassDef):
            _parcourir(stmt.body, {}, out)
            connus = _sans(connus, {stmt.name})
        elif isinstance(stmt, ast.Assert):
            _noter(stmt, connus, out)
            connus = _fusion(connus, _prouve_si(stmt.test, True))
        else:  # instruction simple (ou compose non suivi -- match : jamais rien de prouve a l'interieur)
            _noter(stmt, {} if isinstance(stmt, getattr(ast, "Match", ())) else connus, out)
            connus = _sans(connus, _affectes([stmt]))
    return connus


def _prouves_par_appel(tree):
    """{id(noeud d'appel): {nom: niveau}} des variables prouvees non nulles a chaque appel du fichier."""
    out = {}
    _parcourir(tree.body, {}, out)
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
    prouves = _prouves_par_appel(tree) if visiteur.appels else {}
    app = path.relative_to(APPS_DIR).parts[0]
    rows = []
    for node, fonction, classe in visiteur.appels:
        receiver = _call_target_repr(node)
        cle = f"{_rel(path)}::{fonction}::{_modele(receiver)}"
        cible, indices = _cible(node.func.value, classe, imports)
        rows.append(Appel(cle, node.lineno, node.func.attr, receiver, _lookup_keys(node), app,
                          cible, _lookup_valeurs(node), indices, prouves.get(id(node), {})))
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

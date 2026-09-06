#!/usr/bin/env python3
"""AUD834 — un ViewSet a base TENANT doit servir un modele qui PORTE `company`.

POURQUOI CETTE GARDE EXISTE
---------------------------
`CompanyScopedModelViewSet`/`TenantMixin` filtrent le queryset par
`company=request.user.company` (`core/mixins.py`). Poser cette base sur un
modele qui n'a PAS de champ `company` (un enfant scope par son parent) donne
un `FieldError` a chaque list/retrieve/patch/delete — un 500 en production —
et une creation qui n'est plus scopee du tout. C'est exactement ce qui est
arrive a `TerritoireRegle`/`TerritoireMembre` (AUD814) : deux ecrans morts,
CI verte.

AUCUNE garde existante n'appariait la BASE d'un viewset au MODELE qu'il sert :
- `check_tenant_isolation.py` se satisfait de la base tenant (elle prouve
  l'intention de scoper, pas sa faisabilite) ;
- le balayage `core/tenant_isolation_scan.py` (YRBAC12) SAUTE structurellement
  les modeles concernes : `build_minimal_instance` leve `SkipModel` des qu'un
  champ obligatoire est une FK vers un autre modele — or un modele enfant sans
  `company` a par definition une FK obligatoire vers son parent. La forme meme
  du bug est la condition de son exclusion (85 % de skips tolerees par
  `core/tests/test_tenant_isolation_sweep.py`).

CE QU'ELLE FAIT (AST pur : ni base de donnees, ni Django, ni import)
--------------------------------------------------------------------
1. Indexe les modeles de `apps/*`, `core`, `authentication` et leur champ
   `company` (heritage des bases abstraites resolu de proche en proche).
2. Pour chaque classe de vue a base tenant, resout le modele servi
   (`queryset = Modele.objects...` ou `model = Modele`).
3. ECHOUE si ce modele n'a pas de `company` ET que la vue s'en remet quand
   meme au scoping de sa base — c'est-a-dire qu'elle ne definit pas
   `get_queryset`, ou que son `get_queryset` appelle `super()`.

LE CONTRE-EXEMPLE SAIN (patron de sortie, AUD814)
-------------------------------------------------
    class TerritoireRegleViewSet(CompanyScopedModelViewSet):
        def get_queryset(self):
            qs = viewsets.ModelViewSet.get_queryset(self)   # PAS super()
            return qs.filter(territoire__company=self.request.user.company)

Contourner la base explicitement (et scoper par le parent) rend la vue verte :
la garde ne demande pas de renoncer a la base tenant, elle demande que le
scoping REEL existe.

PRINCIPE ANTI-FAUX-POSITIF (assume)
-----------------------------------
Un doute ne rougit JAMAIS : modele introuvable, modele defini deux fois dont
une avec `company`, base de modele inconnue (donc `company` peut venir de
l'exterieur) → la vue est ignoree. Les cas SAINS deja revus vivent dans
`scripts/viewset_model_scope_allow.txt` (`chemin::Classe`), avec leur raison.

Usage :
    python scripts/check_viewset_model_scope.py          # garde CI
    python scripts/check_viewset_model_scope.py --list   # inventaire + verdict
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"
CORE_DIR = DJANGO_CORE / "core"
AUTH_DIR = DJANGO_CORE / "authentication"
ALLOWLIST_PATH = ROOT / "scripts" / "viewset_model_scope_allow.txt"

# Les trois dispositions REELLES du depot pour une surface de vues / de
# modeles (meme patron que check_tenant_isolation.py apres AUD828) : un fichier
# nu, un module prefixe/suffixe, ou un paquet.
_VIEW_FILE_PATTERNS = ("views.py", "views_*.py", "*_views.py")
_MODEL_FILE_PATTERNS = ("models.py", "models_*.py", "*_models.py")

# Bases qui APPORTENT le filtre `company=` (core/mixins.py, core/viewsets.py).
TENANT_BASE_RE = re.compile(r"(TenantMixin|CompanyScoped|Scoped\w*ViewSet)")
# Bases de modele du framework : elles ne peuvent apporter aucun champ.
FRAMEWORK_MODEL_BASES = {
    "Model", "models.Model", "AbstractUser", "AbstractBaseUser",
    "PermissionsMixin", "object",
}


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return path.name


def _dirs(root: Path):
    apps = root / "apps"
    dirs = sorted(apps.iterdir()) if apps.is_dir() else []
    return [d for d in dirs if d.is_dir()] + [root / "core", root / "authentication"]


def _iter_files(root: Path, patterns, package: str):
    seen = set()
    for app_dir in _dirs(root):
        if not app_dir.is_dir():
            continue
        for pattern in patterns:
            for f in sorted(app_dir.glob(pattern)):
                if f not in seen:
                    seen.add(f)
                    yield f
        pkg = app_dir / package
        if pkg.is_dir():
            for f in sorted(pkg.rglob("*.py")):
                if f.name != "__init__.py" and f not in seen:
                    seen.add(f)
                    yield f


def _base_names(classdef) -> list:
    names = []
    for b in classdef.bases:
        if isinstance(b, ast.Name):
            names.append(b.id)
        elif isinstance(b, ast.Attribute):
            names.append(b.attr)
    return names


def _porte_company(classdef) -> bool:
    """Champ `company` declare directement dans le corps de la classe."""
    for node in classdef.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "company":
                    return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.target.id == "company":
            return True
    return False


# ===========================================================================
# 1. Index des modeles
# ===========================================================================

def indexer_modeles(root: Path = DJANGO_CORE) -> dict:
    """{nom: [ {rel, company, bases} ]} — une liste, car deux apps peuvent
    definir le meme nom de classe."""
    index: dict = {}
    for path in _iter_files(root, _MODEL_FILE_PATTERNS, "models"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"),
                             filename=str(path))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            index.setdefault(node.name, []).append({
                "rel": _rel(path),
                "company": _porte_company(node),
                "bases": _base_names(node),
            })
    return index


def _company_par_heritage(entree: dict, index: dict, vus: set):
    """True / False / None (inconnu : une base n'est pas resolue)."""
    if entree["company"]:
        return True
    inconnu = False
    for base in entree["bases"]:
        if base in FRAMEWORK_MODEL_BASES:
            continue
        candidats = index.get(base)
        if not candidats:
            inconnu = True          # base venue d'ailleurs : on ne sait pas
            continue
        for candidat in candidats:
            cle = (candidat["rel"], base)
            if cle in vus:
                continue
            vus.add(cle)
            verdict = _company_par_heritage(candidat, index, vus)
            if verdict is True:
                return True
            if verdict is None:
                inconnu = True
    return None if inconnu else False


def modele_porte_company(nom: str, index: dict):
    """True / False / None (inconnu ou ambigu — le doute ne rougit jamais)."""
    entrees = index.get(nom)
    if not entrees:
        return None
    verdicts = [_company_par_heritage(e, index, set()) for e in entrees]
    if any(v is True for v in verdicts):
        return True                 # ambigu ou porteur : on ne rougit pas
    if any(v is None for v in verdicts):
        return None
    return False


# ===========================================================================
# 2. Vues a base tenant
# ===========================================================================

def _modele_servi(classdef):
    """Nom du modele servi, lu sur `queryset = X.objects...` ou `model = X`."""
    for node in classdef.body:
        if not isinstance(node, ast.Assign):
            continue
        cibles = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "queryset" in cibles:
            racine = node.value
            while isinstance(racine, (ast.Call, ast.Attribute)):
                racine = racine.func if isinstance(racine, ast.Call) else racine.value
            if isinstance(racine, ast.Name):
                return racine.id
        if "model" in cibles and isinstance(node.value, ast.Name):
            return node.value.id
    return None


def _get_queryset(classdef):
    for node in classdef.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == "get_queryset":
            return node
    return None


def _appelle_super(func) -> bool:
    for sub in ast.walk(func):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                and sub.func.id == "super":
            return True
        # super().get_queryset() sans parentheses intermediaires
        if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Call) \
                and isinstance(sub.value.func, ast.Name) \
                and sub.value.func.id == "super":
            return True
    return False


def indexer_vues(root: Path = DJANGO_CORE):
    """({nom: [ClassDef]}, [(rel, ClassDef)]) sur toute la surface de vues.

    L'index sert a resoudre un `get_queryset` herite d'un MIXIN local
    (`_PlaybookEnfantViewSetMixin` : le scoping reel vit dans le mixin, pas
    dans la classe finale — sans cette resolution la garde crie au loup).
    """
    par_nom: dict = {}
    classes = []
    for path in _iter_files(root, _VIEW_FILE_PATTERNS, "views"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"),
                             filename=str(path))
        except (OSError, SyntaxError):
            continue
        rel = _rel(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                par_nom.setdefault(node.name, []).append(node)
                classes.append((rel, node))
    return par_nom, classes


def resoudre_get_queryset(classdef, par_nom: dict, vus=None) -> str:
    """'propre' | 'delegue' | 'inconnu' — qui filtre REELLEMENT le queryset ?

    'propre'  : un get_queryset (ici ou dans un mixin local) qui n'appelle PAS
                super() — la vue fait son propre scoping, la base tenant est
                court-circuitee (patron de sortie d'AUD814).
    'delegue' : aucun get_queryset avant la base tenant, ou un get_queryset qui
                appelle super() — le `filter(company=...)` de la base
                s'applique.
    'inconnu' : une base n'est pas resolue — le doute ne rougit JAMAIS.
    """
    vus = set() if vus is None else vus
    gq = _get_queryset(classdef)
    if gq is not None:
        return "delegue" if _appelle_super(gq) else "propre"
    for base in _base_names(classdef):
        if TENANT_BASE_RE.search(base):
            return "delegue"
        candidats = par_nom.get(base)
        if not candidats:
            return "inconnu"
        verdicts = set()
        for candidat in candidats:
            if id(candidat) in vus:
                continue
            vus.add(id(candidat))
            verdicts.add(resoudre_get_queryset(candidat, par_nom, vus))
        if "propre" in verdicts:        # direction sure : on sous-detecte
            return "propre"
        if verdicts == {"delegue"}:
            return "delegue"
        return "inconnu"
    return "inconnu"


def analyser(root: Path = DJANGO_CORE):
    """Rend (constats, inventaire). constat = (cle, modele, raison)."""
    index = indexer_modeles(root)
    par_nom, classes = indexer_vues(root)
    constats, inventaire = [], []
    for rel, node in classes:
        if not any(TENANT_BASE_RE.search(b) for b in _base_names(node)):
            continue
        modele = _modele_servi(node)
        verdict = modele_porte_company(modele, index) if modele else None
        scoping = resoudre_get_queryset(node, par_nom)
        inventaire.append(
            f"{rel}::{node.name} modele={modele or '?'} "
            f"company={verdict} scoping={scoping}")
        if verdict is False and scoping == "delegue":
            raison = ("ne definit pas get_queryset (le filtre `company=` de la "
                      "base s'applique tel quel)"
                      if _get_queryset(node) is None else
                      "son get_queryset appelle super() (le filtre `company=` "
                      "de la base s'applique quand meme)")
            constats.append((f"{rel}::{node.name}", modele, raison))
    return constats, inventaire


# ===========================================================================
# 3. Allowlist + CLI
# ===========================================================================

ENTETE_ALLOWLIST = """\
# AUD834 — cas SAINS de `check_viewset_model_scope.py` : une vue a base tenant
# servant un modele sans `company`, dont le contournement est EXPLICITE et
# documente (bypass assume, scoping reel ailleurs).
#
# Format : `chemin/vers/views.py::NomDeClasse` (un par ligne), commentaires en
# `#`. Chaque ajout doit porter, juste au-dessus, la raison du bypass — une
# ligne sans justification est un defaut en attente.
"""


def charger_allowlist(path: Path | None = None) -> set:
    path = path or ALLOWLIST_PATH
    if not path.is_file():
        return set()
    return {
        ligne.strip()
        for ligne in path.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.strip().startswith("#")
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="AUD834 — base tenant vs modele sans `company`.")
    parser.add_argument("--list", action="store_true",
                        help="inventaire de toutes les vues a base tenant")
    args = parser.parse_args(argv)

    constats, inventaire = analyser()

    if args.list:
        for ligne in sorted(inventaire):
            print(ligne)
        print(f"\n{len(inventaire)} vue(s) a base tenant, "
              f"{len(constats)} sans modele porteur de `company`.")
        return 0

    allow = charger_allowlist()
    nouveaux = [c for c in constats if c[0] not in allow]

    if nouveaux:
        print(f"\nECHEC : {len(nouveaux)} vue(s) a base TENANT servent un modele "
              f"SANS champ `company` tout en s'en remettant au scoping de leur "
              f"base.\n")
        for cle, modele, raison in sorted(nouveaux):
            print(f"  {cle}")
            print(f"      modele servi : {modele} — aucun champ `company`")
            print(f"      {raison}")
        print("\nCE QUE CA DONNE EN PRODUCTION : `qs.filter(company=...)` sur un "
              "modele qui n'a pas ce champ leve un FieldError — 500 sur list, "
              "retrieve, patch et delete — et la creation n'est plus scopee du "
              "tout (defaut mesure sur TerritoireRegle/TerritoireMembre, "
              "AUD814).")
        print("\nCORRIGER — scoper par le PARENT sans passer par la base :")
        print("    def get_queryset(self):")
        print("        qs = viewsets.ModelViewSet.get_queryset(self)  # pas super()")
        print("        return qs.filter(parent__company=self.request.user.company)")
        print("... ou donner un vrai champ `company` au modele.")
        print(f"Un bypass EXPLICITE et documente s'inscrit dans "
              f"{_rel(ALLOWLIST_PATH)}, avec sa raison.")
        return 1

    print(f"check_viewset_model_scope : OK — {len(inventaire)} vue(s) a base "
          f"tenant, chacune sur un modele porteur de `company` ou scopee "
          f"autrement ({len(allow)} bypass documente(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Garde du VOCABULAIRE DE ROLES de composition — les QUATRE miroirs alignes.

LE DEFAUT QU'ELLE ATTRAPE (audit L3 du 16/09/2026, STKCAT2)
-----------------------------------------------------------
Le meme vocabulaire de roles (`panneau`, `onduleur_hybride`, `structure`...)
est recopie A LA MAIN dans QUATRE fichiers, deux cotes de la pile :

  1. backend/django_core/core/product_roles.py        ROLES_DEVIS
     (depuis STKCAT21, LA source du tuple ; `apps/ventes/models.py`
      l'ALIASE sous son nom historique ROLES_AUTO_COMPOSITION — le tuple qui
      AUTORISE un role dans ParametresGammes.marques / .ordre_lignes, un role
      absent est refuse en 400 — et `stock.Produit.role_devis` en tire ses
      `choices`. Cette garde lit la source ET verifie l'alias, sans quoi
      renommer l'un des deux la rendrait verte et vide)
  2. backend/django_core/apps/ventes/domain/catalogue.py   LIBELLES_ROLES
     (le libelle FR que le commercial lit dans « marque epinglee introuvable »)
  3. backend/django_core/apps/ventes/offres_tailles.py     _FAMILLES
     (le regroupement en familles de la page de comparaison de tailles)
  4. frontend/src/features/ventes/solar.js            PRODUCT_CATEGORIES
     (les lignes de l'ecran Parametres > Gammes & marques, et le libelle
      affiche par `roleLabel`)

Les quatre PROMETTENT en prose d'etre « le miroir EXACT » l'un de l'autre, et
rien ne le verifiait. Resultat mesure : `onduleur_offgrid` vivait depuis des
mois dans PRODUCT_CATEGORIES seul — l'ecran offrait d'epingler une marque sur
l'onduleur hors reseau, le serveur refusait le PATCH en 400 « role inconnu ».
Une prose ne se verifie pas ; cette garde si.

CE QU'ELLE COMPARE
------------------
  · l'ENSEMBLE des cles, identique dans les quatre listes (un role ajoute d'un
    seul cote est un ECHEC, quel que soit le cote) ;
  · les LIBELLES de LIBELLES_ROLES et de PRODUCT_CATEGORIES, egaux role par
    role — ce sont les deux seules listes qui portent un libelle, et elles
    s'annoncent toutes deux « miroir exact » ;
  · que chaque role de _FAMILLES porte bien une famille non vide.

Ce qu'elle NE compare PAS, volontairement : l'ORDRE. ROLES_AUTO_COMPOSITION,
LIBELLES_ROLES et PRODUCT_CATEGORIES partagent le meme ordre, mais _FAMILLES a
toujours eu le sien (panneau d'abord) et l'imposer casserait une liste lisible
sans rien prouver. Le classement des lignes de devis est gouverne par
`ParametresGammes.ordre_lignes`, pas par l'ordre de declaration.

Analyse STATIQUE pure (ast + texte), stdlib seule : ni Django, ni base, ni
node. ~1 s.

Usage :
    python scripts/check_roles_mirror.py
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_ROOT = ROOT / "backend" / "django_core"

PRODUCT_ROLES_PY = DJANGO_ROOT / "core" / "product_roles.py"
MODELS_PY = DJANGO_ROOT / "apps" / "ventes" / "models.py"
CATALOGUE_PY = DJANGO_ROOT / "apps" / "ventes" / "domain" / "catalogue.py"
OFFRES_PY = DJANGO_ROOT / "apps" / "ventes" / "offres_tailles.py"
SOLAR_JS = ROOT / "frontend" / "src" / "features" / "ventes" / "solar.js"


class Divergence(Exception):
    """Lecture impossible d'une des quatre sources (fichier/symbole absent)."""


# ===========================================================================
# Lecture des trois listes PYTHON (ast — aucun import, aucun Django)
# ===========================================================================

def _module(chemin: Path) -> ast.Module:
    if not chemin.exists():
        raise Divergence(f"fichier introuvable : {_relatif(chemin)}")
    return ast.parse(chemin.read_text(encoding="utf-8", errors="replace"),
                     filename=str(chemin))


def _relatif(chemin: Path) -> str:
    try:
        return chemin.relative_to(ROOT).as_posix()
    except ValueError:  # pragma: no cover — hors depot
        return chemin.as_posix()


def _affectation(module: ast.Module, nom: str, chemin: Path) -> ast.expr:
    """La valeur de l'affectation de MODULE `nom = ...` (la premiere)."""
    for noeud in module.body:
        if isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Name) and cible.id == nom:
                    return noeud.value
        elif isinstance(noeud, ast.AnnAssign):
            cible = noeud.target
            if (isinstance(cible, ast.Name) and cible.id == nom
                    and noeud.value is not None):
                return noeud.value
    raise Divergence(
        f"symbole `{nom}` introuvable au niveau module de {_relatif(chemin)}")


def _texte(noeud: ast.expr, quoi: str) -> str:
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return noeud.value
    raise Divergence(f"{quoi} n'est pas une chaine litterale")


def lire_roles_devis() -> list[str]:
    """Les cles de `core.product_roles.ROLES_DEVIS` — LA source du tuple."""
    chemin = PRODUCT_ROLES_PY
    valeur = _affectation(_module(chemin), "ROLES_DEVIS", chemin)
    if not isinstance(valeur, (ast.Tuple, ast.List)):
        raise Divergence(
            "ROLES_DEVIS n'est pas un tuple/liste litteral "
            f"dans {_relatif(chemin)}")
    return [_texte(element, "un element de ROLES_DEVIS")
            for element in valeur.elts]


def lire_roles_auto_composition() -> list[str]:
    """Les cles de `ROLES_AUTO_COMPOSITION` (apps/ventes/models.py).

    STKCAT21 — deux formes acceptees, et RIEN d'autre :

      * `ROLES_AUTO_COMPOSITION = ROLES_DEVIS` — l'ALIAS attendu aujourd'hui.
        La valeur lue est alors celle de `core/product_roles.py`, donc l'egalite
        est structurelle et non plus a tenir a la main ;
      * un tuple/liste LITTERAL — la forme d'avant STKCAT21, toujours comparee
        role par role (si quelqu'un re-copiait le tuple ici, la garde
        continuerait de le confronter aux trois autres miroirs au lieu de
        devenir aveugle).

    Toute autre forme (un import renomme, une concatenation, une comprehension)
    est refusee EXPLICITEMENT : une garde qui ne sait plus lire sa source doit
    ECHOUER, jamais passer en silence.
    """
    chemin = MODELS_PY
    valeur = _affectation(_module(chemin), "ROLES_AUTO_COMPOSITION", chemin)
    if isinstance(valeur, ast.Name):
        if valeur.id != "ROLES_DEVIS":
            raise Divergence(
                "ROLES_AUTO_COMPOSITION aliase `%s` dans %s — la seule source "
                "attendue est `ROLES_DEVIS` (core/product_roles.py)."
                % (valeur.id, _relatif(chemin)))
        return lire_roles_devis()
    if not isinstance(valeur, (ast.Tuple, ast.List)):
        raise Divergence(
            "ROLES_AUTO_COMPOSITION n'est ni l'alias `ROLES_DEVIS` ni un "
            f"tuple/liste litteral dans {_relatif(chemin)}")
    return [_texte(element, "un element de ROLES_AUTO_COMPOSITION")
            for element in valeur.elts]


def _dict_de_chaines(chemin: Path, nom: str) -> dict[str, str]:
    valeur = _affectation(_module(chemin), nom, chemin)
    if not isinstance(valeur, ast.Dict):
        raise Divergence(
            f"{nom} n'est pas un dictionnaire litteral dans "
            f"{_relatif(chemin)}")
    resultat: dict[str, str] = {}
    for cle, val in zip(valeur.keys, valeur.values):
        if cle is None:  # {**autre} — jamais dans ces listes
            raise Divergence(f"{nom} contient un depliage `**` non lisible "
                             "statiquement")
        resultat[_texte(cle, f"une cle de {nom}")] = _texte(
            val, f"une valeur de {nom}")
    return resultat


def lire_libelles_roles() -> dict[str, str]:
    return _dict_de_chaines(CATALOGUE_PY, "LIBELLES_ROLES")


def lire_familles() -> dict[str, str]:
    return _dict_de_chaines(OFFRES_PY, "_FAMILLES")


# ===========================================================================
# Lecture de la liste JAVASCRIPT (texte — pas de node dans la CI rapide)
# ===========================================================================

_DEBUT_JS = re.compile(r"^export\s+const\s+PRODUCT_CATEGORIES\s*=\s*\[",
                       re.MULTILINE)
#  ['onduleur_reseau', 'Onduleur Injection'],
_PAIRE_JS = re.compile(
    r"\[\s*'((?:[^'\\]|\\.)*)'\s*,\s*'((?:[^'\\]|\\.)*)'\s*\]")


def _desechappe(texte: str) -> str:
    return re.sub(r"\\(.)", r"\1", texte)


def lire_product_categories() -> list[tuple[str, str]]:
    """Les couples (cle, libelle) de `solar.js::PRODUCT_CATEGORIES`.

    Lecture TEXTUELLE bornee au bloc du tableau : le fichier est un module ES
    de plusieurs milliers de lignes, et la CI rapide n'a pas de node. Le bloc
    s'arrete au premier `]` en debut de ligne — la forme utilisee par le
    fichier depuis sa creation.
    """
    if not SOLAR_JS.exists():
        raise Divergence(f"fichier introuvable : {_relatif(SOLAR_JS)}")
    source = SOLAR_JS.read_text(encoding="utf-8", errors="replace")
    debut = _DEBUT_JS.search(source)
    if debut is None:
        raise Divergence(
            "`export const PRODUCT_CATEGORIES = [` introuvable dans "
            f"{_relatif(SOLAR_JS)}")
    fin = re.compile(r"^\]", re.MULTILINE).search(source, debut.end())
    if fin is None:
        raise Divergence(
            "fin du tableau PRODUCT_CATEGORIES (`]` en debut de ligne) "
            f"introuvable dans {_relatif(SOLAR_JS)}")
    bloc = source[debut.end():fin.start()]
    # Retire les commentaires de ligne : ils peuvent citer un role en exemple.
    bloc = re.sub(r"//[^\n]*", "", bloc)
    couples = [(_desechappe(cle), _desechappe(libelle))
               for cle, libelle in _PAIRE_JS.findall(bloc)]
    if not couples:
        raise Divergence(
            f"PRODUCT_CATEGORIES est vide dans {_relatif(SOLAR_JS)}")
    return couples


# ===========================================================================
# Comparaison
# ===========================================================================

def _doublons(cles: list[str]) -> list[str]:
    vus, doubles = set(), []
    for cle in cles:
        if cle in vus and cle not in doubles:
            doubles.append(cle)
        vus.add(cle)
    return doubles


def constats() -> list[str]:
    """La liste (vide = OK) des divergences, en francais."""
    problemes: list[str] = []

    # STKCAT21 — la SOURCE est `core.product_roles.ROLES_DEVIS` ; le tuple lu
    # cote ventes est son alias (ou, forme legacy, une copie litterale encore
    # comparee role par role).
    roles = lire_roles_devis()
    alias = lire_roles_auto_composition()
    libelles = lire_libelles_roles()
    familles = lire_familles()
    categories = lire_product_categories()
    cles_js = [cle for cle, _ in categories]

    sources = {
        "ROLES_AUTO_COMPOSITION (apps/ventes/models.py)": list(alias),
        "LIBELLES_ROLES (apps/ventes/domain/catalogue.py)": list(libelles),
        "_FAMILLES (apps/ventes/offres_tailles.py)": list(familles),
        "PRODUCT_CATEGORIES (frontend/src/features/ventes/solar.js)": cles_js,
    }

    for nom, cles in sorted(sources.items()):
        for double in _doublons(cles):
            problemes.append(f"{nom} : role `{double}` declare DEUX fois.")

    reference = set(roles)
    for nom, cles in sorted(sources.items()):
        manquants = sorted(reference - set(cles))
        surnumeraires = sorted(set(cles) - reference)
        if manquants:
            problemes.append(
                f"{nom} : role(s) MANQUANT(S) par rapport a "
                f"ROLES_AUTO_COMPOSITION : {', '.join(manquants)}.")
        if surnumeraires:
            problemes.append(
                f"{nom} : role(s) EN TROP, absent(s) de "
                f"ROLES_AUTO_COMPOSITION : {', '.join(surnumeraires)}.")

    # Les deux seules listes qui portent un LIBELLE se promettent mutuellement
    # « miroir exact » : le commercial doit lire le meme mot des deux cotes.
    libelles_js = dict(categories)
    for role in sorted(set(libelles) & set(libelles_js)):
        if libelles[role] != libelles_js[role]:
            problemes.append(
                f"role `{role}` : libelle DIFFERENT entre LIBELLES_ROLES "
                f"(\"{libelles[role]}\") et PRODUCT_CATEGORIES "
                f"(\"{libelles_js[role]}\").")

    for role in sorted(familles):
        if not (familles[role] or "").strip():
            problemes.append(
                f"role `{role}` : famille VIDE dans _FAMILLES "
                "(un role sans famille n'est cite nulle part sur la page de "
                "comparaison de tailles).")

    return problemes


def main(argv=None) -> int:
    del argv
    try:
        problemes = constats()
    except Divergence as exc:
        print(f"ECHEC : source de roles illisible : {exc}")
        print("Cette garde lit QUATRE listes nommees ; renommer ou deplacer "
              "l'une d'elles doit se refleter ici.")
        return 1

    if problemes:
        print(f"\nECHEC : {len(problemes)} divergence(s) entre les quatre "
              "miroirs du vocabulaire de roles.\n")
        for probleme in problemes:
            print(f"  - {probleme}")
        print("\nUn role doit exister dans LES QUATRE listes ou dans AUCUNE : "
              "un role present cote ecran seul fait refuser le PATCH en 400 "
              "(« role inconnu ») ; present cote serveur seul, il n'est "
              "jamais proposable. Les roles `structure_acier`/`structure_alu` "
              "restent des ALIAS conserves — ne les retirez pas.")
        return 1

    nombre = len(lire_roles_devis())
    print(f"OK : {nombre} roles de composition (source core/product_roles.py "
          "ROLES_DEVIS), identiques dans les quatre miroirs (backend models / "
          "libelles / familles / solar.js).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

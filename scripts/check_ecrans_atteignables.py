#!/usr/bin/env python3
"""Garde permanente : un ecran livre DOIT etre atteignable depuis le menu.

POURQUOI CETTE GARDE EXISTE — INCIDENT DU 03/08/2026
----------------------------------------------------
Le module « Appels d'offres » a ete livre et declare TERMINE : 194 taches
cochees, CI verte, deploye. Mesure faite le jour meme, en ouvrant l'app :

    68 ecrans existent sur le disque dans frontend/src/features/ao/
     7 seulement sont atteignables depuis le menu
    61 ne le sont pas.

Cinq onglets de la fiche affaire (Toitures, Calepinages, Bordereau, Dossier,
Questions terrain) rendent un ``<TabPlaceholder>`` « ecran dedie en
construction » alors que le vrai panneau est dans le dossier voisin. Quatre
routes du menu rendent un squelette « Ecran en construction » pour la meme
raison. Le fondateur l'a decouvert en essayant d'utiliser l'app.

CAUSE RACINE — LA MEME QUE LE DEFAUT FRONT<->BACK DEJA GARDE ICI
----------------------------------------------------------------
Les ecrans sont construits par des lanes PARALLELES, mais le SEUL fichier qui
les relie au menu — ``features/<app>/module.config.jsx`` — a un proprietaire
UNIQUE. Chaque lane livre son ecran ; personne ne revient le brancher. Le
travail existe, il est simplement inaccessible. Aucun test ne le voit : un
ecran orphelin compile, passe eslint, et ses propres tests unitaires sont
verts. C'est du code mort qui se croit vivant.

NE LA DESACTIVEZ PAS. Si elle rougit, c'est qu'un ecran vient d'etre livre
sans jamais pouvoir etre ouvert par un utilisateur — exactement 61 fois le
03/08/2026.

CE QU'ELLE FAIT (analyse statique pure, stdlib, sans build, sans node)
----------------------------------------------------------------------
1. Construit le graphe d'imports REEL du frontend a partir des points
   d'entree qu'un utilisateur emprunte vraiment :
     - ``frontend/src/main.jsx`` (donc le routeur, les providers, la mise en
       page, et tout ``src/pages/**`` monte par ``router/index.jsx``) ;
     - les composants REELLEMENT ROUTES par chaque
       ``features/*/module.config.jsx`` (que ``router/moduleRoutes.jsx``
       collecte par ``import.meta.glob`` — un glob dynamique qu'aucune analyse
       statique ne suit, d'ou la lecture explicite des ``routes:``).
   Puis suit les imports relatifs (statiques, ``export ... from``, et
   ``import()`` dynamique des ``lazy()``). Un sous-composant — une ligne de
   tableau, un badge, un tiroir — est donc credite PAR SON PARENT, comme un
   utilisateur l'atteint reellement.
2. CLASSE 1 « ecran inatteignable » : tout ``.jsx`` non-test sous
   ``frontend/src/features/<app>/`` que ce graphe n'atteint pas.
3. CLASSE 2 « placeholder devant un ecran reel » — le cas le plus grave, le
   travail est fait ET cache : une route ou un onglet qui rend un composant de
   remplissage (squelette defini dans le module.config, ``TabPlaceholder``,
   etat vide « en construction »...) alors qu'un vrai ecran du MEME SUJET
   existe dans le dossier de l'app.

PRINCIPE ANTI-FAUX-POSITIF (assume, delibere)
---------------------------------------------
Une garde qui crie au loup finit desactivee, et le defaut reviendra. Donc :
  - un ``module.config.jsx`` dont les ``routes:`` ne se lisent pas entierement
    (routes calculees, forme inattendue) est declare OPAQUE : TOUS ses imports
    relatifs sont credites comme atteignables et il ne produit AUCUNE alerte
    de classe 2. On sous-detecte, on n'invente pas ;
  - la classe 2 n'accuse QUE si un vrai ecran du meme sujet existe vraiment
    (dossier ou fichier de meme nom, jetons d'au moins 5 lettres, dossiers
    techniques comme ``components``/``hooks`` exclus). Un placeholder devant
    une fonctionnalite qui n'existe pas encore est LEGITIME et reste muet ;
  - les fichiers de test ne sont jamais des points d'entree : un ecran
    importe uniquement par son propre test reste inatteignable, et c'est la
    verite.

BASE DE REFERENCE — ELLE NE PEUT QUE RETRECIR
---------------------------------------------
La dette du 03/08/2026 est GELEE dans ``scripts/ecrans_atteignables_allow.txt``
— cette garde empeche la RECIDIVE, elle ne repare pas les 61 ecrans. Seule une
occurrence NOUVELLE echoue. ``--write-baseline`` REFUSE d'ajouter une ligne :
il ne sait qu'en retirer (celles qui sont branchees). Ajouter une dette exige
``--autoriser-croissance``, drapeau reserve au fondateur, visible en revue.

Usage :
    python scripts/check_ecrans_atteignables.py                 # garde CI
    python scripts/check_ecrans_atteignables.py --stats         # inventaire
    python scripts/check_ecrans_atteignables.py --write-baseline
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

from check_api_contract import scan_js

ROOT = Path(__file__).resolve().parent.parent
FRONT_SRC = ROOT / "frontend" / "src"
FEATURES = FRONT_SRC / "features"
ENTRY = FRONT_SRC / "main.jsx"
BASELINE_PATH = ROOT / "scripts" / "ecrans_atteignables_allow.txt"

# Extensions qu'un specificateur relatif peut designer sans etre ecrit.
EXTENSIONS = (".jsx", ".js", ".mjs")

# Un fichier de test n'est JAMAIS un chemin d'acces utilisateur.
TEST_MARKERS = (".test.", ".spec.")
TEST_DIRS = {"__tests__", "__mocks__"}

# Dossiers techniques : leur nom ne designe pas un « sujet metier », donc il ne
# peut pas servir a prouver qu'un vrai ecran se cache derriere un placeholder.
DOSSIERS_TECHNIQUES = {
    "component", "hook", "util", "lib", "store", "api", "style", "asset",
    "type", "constant", "helper", "shared", "common", "widget", "test",
    "page", "screen", "view", "ui", "data", "model", "service", "context",
    "provider", "config", "state", "form", "modal", "layout", "icon",
}

# Mots trop generiques pour designer un sujet (ils apparaissent dans presque
# tous les libelles d'onglet ou de nav).
MOTS_VIDES = {
    "ecran", "page", "vues", "liste", "fiche", "detail", "details", "tableau",
    "bord", "nouveau", "nouvelle", "gestion", "suivi", "general", "generale",
    "module", "onglet", "section", "apercu", "resume",
}

# Longueur minimale d'un jeton retenu comme « sujet ». En dessous, le risque
# d'appariement fortuit depasse la valeur du signal.
LONGUEUR_MIN_JETON = 5

# Noms de composants qui denoncent un remplissage. Employe avec DEUX autres
# conditions (un libelle litteral + un vrai ecran du meme sujet) : jamais seul.
NOM_PLACEHOLDER = re.compile(
    r"(?i)placeholder|squelette|skeleton|stub|construction|comingsoon|"
    r"abientot|avenir|todo|wip|bientot")

# Marqueurs textuels d'un ecran de remplissage (dans le corps du composant).
MARQUEURS_CONSTRUCTION = (
    "en construction", "a venir", "à venir", "bientot disponible",
    "bientôt disponible", "coming soon", "pas encore disponible",
)


# ===========================================================================
# 1. Lecture des sources frontend
# ===========================================================================

_CACHE: dict[Path, tuple] = {}


def lire(path: Path) -> tuple:
    """(code sans commentaires, code masque) — memoise.

    `scan_js` (partage avec check_api_contract.py) retire les commentaires en
    conservant les decalages, et rend une variante ou le CONTENU des chaines
    est efface : c'est elle qui rend le comptage d'accolades sur.
    """
    if path not in _CACHE:
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            src = ""
        code, _, masked = scan_js(src)
        _CACHE[path] = (code, masked)
    return _CACHE[path]


def est_test(path: Path) -> bool:
    if any(marker in path.name for marker in TEST_MARKERS):
        return True
    return any(part in TEST_DIRS for part in path.parts)


def resoudre(spec: str, importateur: Path) -> Path | None:
    """Specificateur relatif -> fichier reel, ou None (paquet npm, .css...)."""
    if not spec.startswith("."):
        return None
    spec = spec.split("?", 1)[0].split("#", 1)[0]
    base = importateur.parent / spec
    if base.is_file() and base.suffix in EXTENSIONS:
        return base.resolve()
    for extension in EXTENSIONS:
        candidat = Path(str(base) + extension)
        if candidat.is_file():
            return candidat.resolve()
    for extension in EXTENSIONS:
        candidat = base / f"index{extension}"
        if candidat.is_file():
            return candidat.resolve()
    return None


_SPEC_FROM = re.compile(r"""\bfrom\s*(['"])([^'"\n]+)\1""")
_SPEC_IMPORT_NU = re.compile(r"""\bimport\s*(['"])([^'"\n]+)\1""")
_SPEC_DYNAMIQUE = re.compile(r"""\bimport\s*\(\s*(['"])([^'"\n]+)\1""")
_SPEC_REQUIRE = re.compile(r"""\brequire\s*\(\s*(['"])([^'"\n]+)\1""")


def specificateurs(code: str):
    for motif in (_SPEC_FROM, _SPEC_IMPORT_NU, _SPEC_DYNAMIQUE, _SPEC_REQUIRE):
        for match in motif.finditer(code):
            yield match.group(2)


def imports_de(path: Path) -> set:
    code, _ = lire(path)
    cibles = set()
    for spec in specificateurs(code):
        cible = resoudre(spec, path)
        if cible is not None and not est_test(cible):
            cibles.add(cible)
    return cibles


# ===========================================================================
# 2. Lecture d'un module.config.jsx (ce qui est ROUTE, et ce qui est bouche)
# ===========================================================================

_LIAISON_LAZY = re.compile(
    r"""\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"""
    r"""(?:React\.)?lazy\s*\(""")
_IMPORT_DEFAUT = re.compile(
    r"""\bimport\s+([A-Za-z_$][\w$]*)\s*(?:,\s*\{[^}]*\}\s*)?from\s*"""
    r"""(['"])([^'"\n]+)\2""")
_DECLARATION = re.compile(
    r"""\b(?:function|class|const|let|var)\s+([A-Za-z_$][\w$]*)""")
_CLE_ROUTES = re.compile(r"\broutes\s*:\s*\[")
_CHAINE = re.compile(r"""(['"])([^'"\n]*)\1""")


def _bloc_equilibre(masked: str, debut: int) -> int | None:
    """Index de la fermeture equilibree du groupe ouvert en `debut`."""
    profondeur = 0
    for index in range(debut, len(masked)):
        caractere = masked[index]
        if caractere in "[{(":
            profondeur += 1
        elif caractere in "]})":
            profondeur -= 1
            if profondeur == 0:
                return index
    return None


def _objets_de_premier_niveau(masked: str, debut: int, fin: int):
    """(debut, fin) de chaque `{...}` de premier niveau entre deux bornes."""
    profondeur = 0
    ouverture = None
    for index in range(debut, fin):
        caractere = masked[index]
        if caractere == "{":
            if profondeur == 0:
                ouverture = index
            profondeur += 1
        elif caractere == "}":
            profondeur -= 1
            if profondeur == 0 and ouverture is not None:
                yield (ouverture, index)
                ouverture = None


def _valeur_de_cle(code: str, masked: str, debut: int, fin: int, cle: str):
    """Texte brut de `cle: <valeur>` dans l'objet [debut, fin], ou None."""
    motif = re.compile(r"\b%s\s*:\s*" % re.escape(cle))
    match = motif.search(masked, debut, fin)
    if not match:
        return None
    profondeur = 0
    for index in range(match.end(), fin):
        caractere = masked[index]
        if caractere in "[{(":
            profondeur += 1
        elif caractere in "]})":
            if profondeur == 0:
                return code[match.end():index].strip()
            profondeur -= 1
        elif caractere == "," and profondeur == 0:
            return code[match.end():index].strip()
    return code[match.end():fin].strip()


class ConfigModule:
    """Ce qu'un `module.config.jsx` route reellement.

    `opaque` = la lecture n'est pas certaine ; on credite alors TOUS ses
    imports relatifs et on n'accuse rien (principe anti-faux-positif).
    """

    def __init__(self, path: Path):
        self.path = path
        self.app = path.parent.name
        self.opaque = False
        self.ecrans_routes: set = set()      # fichiers reellement routes
        self.bouchons: list = []             # (chemin de route, sujets)
        self._lire()

    def _lire(self):
        code, masked = lire(self.path)
        liaisons = {}
        for match in _LIAISON_LAZY.finditer(code):
            fin = _bloc_equilibre(masked, match.end() - 1)
            corps = code[match.end():fin if fin else match.end() + 400]
            spec = _SPEC_DYNAMIQUE.search(corps)
            if spec:
                liaisons[match.group(1)] = resoudre(spec.group(2), self.path)
        for match in _IMPORT_DEFAUT.finditer(code):
            liaisons[match.group(1)] = resoudre(match.group(3), self.path)
        declares = {m.group(1) for m in _DECLARATION.finditer(code)}

        cle = _CLE_ROUTES.search(masked)
        if not cle:
            self.opaque = True
            return
        fin = _bloc_equilibre(masked, cle.end() - 1)
        if fin is None:
            self.opaque = True
            return
        vu = False
        for debut, borne in _objets_de_premier_niveau(masked, cle.end(), fin):
            vu = True
            composant = _valeur_de_cle(code, masked, debut, borne, "component")
            litteral = _CHAINE.match(
                _valeur_de_cle(code, masked, debut, borne, "path") or "")
            chemin = litteral.group(2) if litteral else ""
            if composant is None:
                self.opaque = True
                return
            identifiant = re.fullmatch(r"[A-Za-z_$][\w$]*", composant)
            if identifiant:
                cible = liaisons.get(composant, "absent")
                if isinstance(cible, Path):
                    self.ecrans_routes.add(cible)
                    continue
                if cible is None or composant in declares:
                    # Composant defini DANS le module.config (jamais un vrai
                    # ecran) : c'est un bouchon de route.
                    self.bouchons.append((chemin, self._sujets(chemin, composant)))
                    continue
                self.opaque = True     # identifiant inconnu : on ne devine pas
                return
            appel = re.match(r"([A-Za-z_$][\w$]*)\s*\((.*)\)\s*$", composant, re.S)
            if appel and appel.group(1) in declares:
                litteral = _CHAINE.search(appel.group(2) or "")
                titre = litteral.group(2) if litteral else ""
                self.bouchons.append((chemin, self._sujets(chemin, titre)))
                continue
            self.opaque = True
            return
        if not vu and masked[cle.end():fin].strip():
            # Des entrees existent mais aucune n'a la forme `{ ... }` attendue :
            # on ne sait pas ce qui est route -> opaque (jamais d'accusation).
            # `routes: []` (module route depuis router/index.jsx, ex. messaging)
            # est en revanche parfaitement LU : zero ecran route, pas d'opacite.
            self.opaque = True

    @staticmethod
    def _sujets(chemin: str, titre: str) -> set:
        jetons = set(mots_sujet(titre))
        for segment in (chemin or "").split("/"):
            if segment and not segment.startswith(":"):
                jetons.update(mots_sujet(segment))
        return jetons


# ===========================================================================
# 3. Sujets : normalisation et appariement avec les ecrans du dossier
# ===========================================================================

def normaliser(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte)
    sans_accent = "".join(c for c in decompose if not unicodedata.combining(c))
    return sans_accent.lower()


def singulier(jeton: str) -> str:
    return jeton[:-1] if len(jeton) > LONGUEUR_MIN_JETON and jeton.endswith("s") else jeton


def ardoise(texte: str) -> str:
    """Libelle -> identifiant lisible et STABLE pour la base de reference.

    « Toitures & relevés » -> `toitures-releves`. Aucune singularisation ici :
    la signature doit rester le libelle tel qu'il est ECRIT dans l'onglet, pour
    qu'un relecteur retrouve la ligne d'un coup d'oeil.
    """
    return re.sub(r"[^a-z0-9]+", "-", normaliser(texte)).strip("-") or "?"


def mots_sujet(texte: str) -> set:
    """Jetons normalises, au singulier, assez longs pour designer un sujet."""
    jetons = set()
    for brut in re.split(r"[^a-z0-9]+", normaliser(texte or "")):
        if len(brut) < LONGUEUR_MIN_JETON:
            continue
        # Singulier D'ABORD, mot vide ENSUITE : sinon « details » passe le
        # filtre que « detail » ne passe pas.
        jeton = singulier(brut)
        if jeton in MOTS_VIDES:
            continue
        jetons.add(jeton)
    return jetons


def index_sujets(app: str) -> dict:
    """sujet -> [ecrans reels de l'app portant ce sujet] (dossier ou fichier)."""
    dossier = FEATURES / app
    index: dict[str, list] = {}
    for path in sorted(dossier.rglob("*.jsx")):
        if est_test(path) or path.name == "module.config.jsx":
            continue
        relatif = path.relative_to(dossier)
        for partie in relatif.parts[:-1]:
            jeton = singulier(normaliser(partie))
            if jeton in DOSSIERS_TECHNIQUES or len(jeton) < LONGUEUR_MIN_JETON:
                continue
            index.setdefault(jeton, []).append(path)
        for jeton in mots_sujet(path.stem):
            index.setdefault(jeton, []).append(path)
    return index


# ===========================================================================
# 4. Placeholders montes DANS un ecran (onglets)
# ===========================================================================

_ELEMENT_JSX = re.compile(r"<([A-Z][\w$]*)\b([^<>]*?)/?>")
_LIBELLE = re.compile(
    r"""\b(?:title|titre|label|libelle)\s*=\s*\{?\s*(['"])([^'"\n]*)\1""")


def bouchons_dans(path: Path) -> list:
    """[(nom du composant, libelle, sujets)] des placeholders rendus ici."""
    code, _ = lire(path)
    trouves = []
    for match in _ELEMENT_JSX.finditer(code):
        nom, attributs = match.group(1), match.group(2)
        if not NOM_PLACEHOLDER.search(nom):
            continue
        libelle = _LIBELLE.search(attributs)
        if not libelle:
            continue
        trouves.append((nom, libelle.group(2), mots_sujet(libelle.group(2))))
    return trouves


# ===========================================================================
# 5. Analyse
# ===========================================================================

def atteignables() -> tuple:
    """(fichiers atteignables, configs lues)."""
    configs = [ConfigModule(p) for p in sorted(FEATURES.glob("*/module.config.jsx"))]
    racines = set()
    if ENTRY.is_file():
        racines.add(ENTRY.resolve())
    for config in configs:
        racines.add(config.path.resolve())
        if config.opaque:
            racines |= imports_de(config.path)
        else:
            racines |= {p for p in config.ecrans_routes if p is not None}
    vus = set()
    pile = [p for p in racines if p.is_file()]
    while pile:
        courant = pile.pop()
        if courant in vus:
            continue
        vus.add(courant)
        pile.extend(imports_de(courant) - vus)
    return vus, configs


def ecrans_de_features() -> list:
    ecrans = []
    for path in sorted(FEATURES.rglob("*.jsx")):
        if est_test(path) or path.name == "module.config.jsx":
            continue
        ecrans.append(path.resolve())
    return ecrans


def relatif(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def analyse():
    vus, configs = atteignables()
    ecrans = ecrans_de_features()
    orphelins = [p for p in ecrans if p not in vus]

    constats = []
    for path in orphelins:
        app = path.relative_to(FEATURES).parts[0]
        constats.append(("inatteignable", relatif(path), app, ""))

    index_par_app = {}
    for config in configs:
        if config.opaque:
            continue
        index = index_par_app.setdefault(config.app, index_sujets(config.app))
        for chemin, sujets in config.bouchons:
            cibles = _cibles(index, sujets)
            if cibles:
                constats.append((
                    "bouchon-route", f"{relatif(config.path)}::{chemin or '?'}",
                    config.app, ", ".join(sorted(relatif(c) for c in cibles)[:3])))

    for path in sorted(vus):
        try:
            app = path.relative_to(FEATURES).parts[0]
        except ValueError:
            continue
        if est_test(path) or path.name == "module.config.jsx":
            continue
        for _, libelle, sujets in bouchons_dans(path):
            index = index_par_app.setdefault(app, index_sujets(app))
            cibles = _cibles(index, sujets, sauf=path)
            if cibles:
                constats.append((
                    "bouchon-onglet", f"{relatif(path)}::{ardoise(libelle)}",
                    app, ", ".join(sorted(relatif(c) for c in cibles)[:3])))

    stats = {
        "ecrans": len(ecrans),
        "atteignables": len(ecrans) - len(orphelins),
        "orphelins": len(orphelins),
        "configs": len(configs),
        "opaques": sum(1 for c in configs if c.opaque),
        "noeuds": len(vus),
    }
    return constats, stats


def _cibles(index: dict, sujets: set, sauf: Path = None) -> list:
    cibles = []
    for sujet in sujets:
        for cible in index.get(sujet, []):
            if sauf is not None and cible.resolve() == sauf.resolve():
                continue
            cibles.append(cible)
    return sorted(set(cibles))


# ===========================================================================
# 6. Base de reference + CLI
# ===========================================================================

ENTETE_BASE = """\
# Base de reference de check_ecrans_atteignables.py — DETTE HISTORIQUE, RIEN D'AUTRE.
#
# Chaque ligne est un ecran livre puis jamais branche au menu (« inatteignable »),
# ou un placeholder rendu devant un vrai ecran du meme sujet (« bouchon-* »).
# Cette liste est l'inventaire VERIFIE de la dette du 03/08/2026 : 68 ecrans sur
# le disque dans features/ao, 7 atteignables, 61 non. La garde n'echoue que sur
# une occurrence ABSENTE de cette liste : elle empeche la RECIDIVE, elle ne
# repare pas le passif.
#
# REGLE ABSOLUE : CETTE LISTE NE PEUT QUE RETRECIR.
#   - brancher un ecran puis `python scripts/check_ecrans_atteignables.py
#     --write-baseline` retire sa ligne ;
#   - `--write-baseline` REFUSE d'ajouter une ligne. Ajouter une dette exige
#     `--autoriser-croissance`, drapeau reserve au fondateur, visible en revue.
#
# La signature est le CHEMIN (jamais `fichier:ligne`) : deplacer du code ne doit
# pas invalider la base.
"""


def signature(constat) -> str:
    classe, cible, _, _ = constat
    return f"{classe}|{cible}"


def charger_base(path: Path | None = None) -> set:
    # `path or BASELINE_PATH` resolu A L'APPEL, jamais en valeur par defaut :
    # une valeur par defaut est figee a la definition du module, si bien qu'un
    # test qui reassigne BASELINE_PATH ecrirait quand meme dans la VRAIE base
    # (piege rencontre en ecrivant les tests de ce fichier — il a effectivement
    # ecrase la base de reference du depot).
    path = path or BASELINE_PATH
    if not path.is_file():
        return set()
    return {
        ligne.strip()
        for ligne in path.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.strip().startswith("#")
    }


def ecrire_base(signatures: set, path: Path | None = None):
    path = path or BASELINE_PATH
    path.write_text(ENTETE_BASE + "\n".join(sorted(signatures)) + "\n",
                    encoding="utf-8", newline="\n")


def _par_app(constats) -> dict:
    compte: dict[str, int] = {}
    for classe, _, app, _ in constats:
        if classe == "inatteignable":
            compte[app] = compte.get(app, 0) + 1
    return compte


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description="Garde d'atteignabilite : un ecran livre doit etre ouvrable.")
    parser.add_argument("--stats", action="store_true",
                        help="inventaire chiffre, par app")
    parser.add_argument("--write-baseline", action="store_true",
                        help="retire de la base les ecrans desormais branches")
    parser.add_argument("--autoriser-croissance", action="store_true",
                        help="FONDATEUR UNIQUEMENT : autorise l'ajout de dettes")
    args = parser.parse_args(argv)

    constats, stats = analyse()

    if args.stats:
        print(f"Ecrans .jsx sous frontend/src/features : {stats['ecrans']} "
              f"({stats['atteignables']} atteignables, {stats['orphelins']} non).")
        print(f"module.config.jsx lus : {stats['configs']} "
              f"({stats['opaques']} opaque(s), credites en entier). "
              f"Graphe : {stats['noeuds']} module(s) atteints.")
        compte = _par_app(constats)
        if compte:
            totaux: dict[str, int] = {}
            for path in ecrans_de_features():
                app = path.relative_to(FEATURES).parts[0]
                totaux[app] = totaux.get(app, 0) + 1
            print("\nEcrans inatteignables par app :")
            for app, nombre in sorted(compte.items(), key=lambda kv: (-kv[1], kv[0])):
                print(f"  {app:<16} {nombre:>3} / {totaux.get(app, 0)}")

    signatures = {signature(c) for c in constats}
    base = charger_base()

    if args.write_baseline:
        ajouts = signatures - base
        amorce = not BASELINE_PATH.is_file()
        if ajouts and not (args.autoriser_croissance or amorce):
            print("REFUS : --write-baseline ne peut que RETRECIR la base.")
            print(f"{len(ajouts)} nouvelle(s) dette(s) voudraient y entrer :")
            for entree in sorted(ajouts)[:20]:
                print(f"  + {entree}")
            print("Branchez l'ecran, ou assumez la dette avec "
                  "--autoriser-croissance.")
            return 1
        ecrire_base(signatures)
        print(f"Base de reference reecrite : {BASELINE_PATH.relative_to(ROOT)} "
              f"({len(signatures)} entree(s), {len(base - signatures)} retiree(s)).")
        return 0

    nouveaux = [c for c in constats if signature(c) not in base]
    corriges = base - signatures

    if nouveaux:
        orphelins = [c for c in nouveaux if c[0] == "inatteignable"]
        bouchons = [c for c in nouveaux if c[0] != "inatteignable"]
        parties = []
        if orphelins:
            parties.append(f"{len(orphelins)} ecran(s) livre(s) mais "
                           f"INATTEIGNABLE(s) depuis le menu")
        if bouchons:
            parties.append(f"{len(bouchons)} placeholder(s) rendu(s) DEVANT un "
                           f"ecran reel")
        print(f"\nECHEC : {' et '.join(parties)} (hors base de reference).\n")
        for _, cible, app, _ in sorted(orphelins):
            print(f"  {cible}")
            print(f"      aucune chaine d'imports ne relie ce fichier a une route "
                  f"declaree dans features/{app}/module.config.jsx")
        for classe, cible, app, preuve in sorted(bouchons):
            fichier, _, sujet = cible.partition("::")
            quoi = "une route" if classe == "bouchon-route" else "un onglet"
            print(f"  {fichier}  ({quoi} : {sujet})")
            print(f"      rend un composant de remplissage alors que l'ecran reel "
                  f"existe deja : {preuve}")
        print("\nQUE FAIRE :")
        print("  - declarez une route dans `features/<app>/module.config.jsx` "
              "(`routes: [{ path, component: lazy(() => import('./<Ecran>')) }]`) "
              "et l'entree de nav correspondante ;")
        print("  - ou montez-le dans un onglet de l'ecran parent, a la place du "
              "placeholder ;")
        print("  - ou supprimez le fichier s'il est mort — mais ne le laissez "
              "pas livre-et-invisible.")
        print("\nCette garde existe a cause de l'incident du 03/08/2026 : 68 "
              "ecrans livres dans features/ao, 7 atteignables, 61 morts sur le "
              "disque (194 taches cochees, CI verte, module declare termine). "
              "Voir l'en-tete de scripts/check_ecrans_atteignables.py. "
              "NE LA DESACTIVEZ PAS.")
        return 1

    print(f"OK : {stats['ecrans']} ecran(s) sous features, aucun NOUVEL ecran "
          f"inatteignable ni placeholder devant un ecran reel "
          f"({len(base)} dette(s) historique(s) gelee(s), "
          f"dont {len(corriges)} desormais branchee(s)).")
    if corriges:
        print("Ces dettes corrigees peuvent quitter la base : "
              "python scripts/check_ecrans_atteignables.py --write-baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

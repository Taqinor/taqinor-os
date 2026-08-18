#!/usr/bin/env python3
"""Garde de VOCABULAIRE a source declaree — OPT-IN, zero faux positif par construction.

POURQUOI CETTE FORME ET PAS UNE AUTRE (PACT159 — mesure, pas opinion)
---------------------------------------------------------------------
La detection par RESSEMBLANCE est disqualifiee par la mesure : 18 listes de
choix frontend « candidates » trouvees automatiquement, 13 FAUX POSITIFS
(72 %). Et le cas fondateur — la liste de `ExigencesPage` — ne partageait
ZERO valeur avec le champ serveur qu'elle etait censee refleter : aucune
similarite ne pouvait le voir. Une garde qui crie au loup 3 fois sur 4 et rate
le seul vrai defaut n'est pas une garde ; elle finit desactivee.

LA SEULE FORME VIABLE EST DECLARATIVE. L'auteur de la liste DIT d'ou vient son
vocabulaire, avec un marqueur machine pose juste au-dessus :

    // source-choix: rh.DossierEmploye.motif_sortie
    const MOTIFS = [
      { value: 'demission', label: 'Démission' },
      ...
    ]

Pour un vocabulaire qui ne vit pas dans un `TextChoices` (fabrique, module de
constantes), le marqueur porte le chemin de la constante :

    // source-choix: ao.fabrique.approvisionnement.GRAVITES

REGLE ABSOLUE : SEULES LES LISTES MARQUEES SONT VERIFIEES. Une liste sans
marqueur n'est JAMAIS un rouge — c'est ce qui rend le taux de faux positifs nul
par construction, et c'est ce qui remplace les ~80 promesses en PROSE du depot
(« aligné sur X », « miroir de Y ») : une prose ne se verifie pas, un marqueur
si. Le commentaire d'`EmployeDetail.jsx` en est l'exemple : il PROMETTAIT
l'alignement sur `DossierEmploye.MotifSortie` et rien ne le verifiait.

LE PIEGE RESOLU : LE NOM QUALIFIE. `choices=Statut.choices` ecrit DANS
`class DossierEmploye` designe la classe IMBRIQUEE `DossierEmploye.Statut`, pas
un `Statut` de niveau module. Resoudre par nom simple donnait 6 faux candidats
mesures (plusieurs modeles declarent un `Statut` ou un `Type` different). La
resolution ci-dessous part donc TOUJOURS du modele porteur, puis remonte.

SENS DE LA COMPARAISON (delibere). Seul « la liste front declare une valeur que
le serveur ne connait pas » est un rouge : c'est le defaut qui casse un
enregistrement (400) ou un filtre (0 resultat). L'inverse — le serveur connait
une valeur que l'ecran n'offre pas — est un CHOIX d'ecran legitime (un
formulaire de sortie n'offre pas les statuts d'entree) et ne rougit jamais.

Usage :
    python scripts/check_choices_declares.py            # garde CI
    python scripts/check_choices_declares.py --stats    # + inventaire chiffre
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_ROOT = ROOT / "backend" / "django_core"
APPS_ROOT = DJANGO_ROOT / "apps"
FRONT_SRC = ROOT / "frontend" / "src"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_api_contract import scan_js  # noqa: E402

# `// source-choix: rh.DossierEmploye.motif_sortie`
# `// source-choix: installations.Installation.type_installation +__none__`
# Le `+` declare une SENTINELLE d'interface (« Tous », « Aucun ») qui n'est pas
# du vocabulaire serveur et n'est jamais envoyee telle quelle. Sans lui, trois
# listes MESUREES du depot devaient rester en prose a cause d'une seule valeur
# de filtre — et une sentinelle declaree se relit, contrairement a une prose.
MARQUEUR = re.compile(
    r"//\s*source-choix\s*:\s*(?P<cible>[A-Za-z_][\w.]*)"
    r"(?:\s*\+\s*(?P<sentinelles>[\w.]+(?:\s*,\s*[\w.]+)*))?")
# Un nom TOUT_EN_MAJUSCULES en dernier segment designe une CONSTANTE de module ;
# tout le reste est lu comme `app.Modele.champ`.
_CONSTANTE = re.compile(r"^_*[A-Z][A-Z0-9_]*$")

# `{ value: 'x', label: '…' }` — la forme du depot.
_VALEUR = re.compile(r"""\bvalue\s*:\s*(?P<q>['"])(?P<v>[^'"]*)(?P=q)""")
# `{ key: 'x', label: '…' }` — la seconde forme du depot (gestion_projet).
_CLE_TABLEAU = re.compile(r"""\bkey\s*:\s*(?P<q>['"])(?P<v>[^'"]*)(?P=q)""")
_CHAINE = re.compile(r"""(?P<q>['"])(?P<v>[^'"]*)(?P=q)""")
# Cle d'objet : `cle:` ou `'cle':` — le nom est le vocabulaire.
_CLE = re.compile(
    r"""(?:^|[{,])\s*(?:(?P<q>['"])(?P<qs>[^'"]*)(?P=q)"""
    r"""|(?P<id>[A-Za-z_$][\w$]*))\s*:""")


# ===========================================================================
# 1. Cote serveur : resoudre le vocabulaire declare
# ===========================================================================

def _module_tree(chemin: Path):
    try:
        return ast.parse(chemin.read_text(encoding="utf-8", errors="replace"),
                         filename=str(chemin))
    except (OSError, SyntaxError):
        return None


def _classes_de(noeud) -> dict:
    return {item.name: item for item in noeud.body if isinstance(item, ast.ClassDef)}


def _valeurs_de_textchoices(classe: ast.ClassDef) -> set:
    """{'demission', …} — la 1re composante de chaque membre du TextChoices."""
    valeurs = set()
    for item in classe.body:
        if not isinstance(item, ast.Assign) or len(item.targets) != 1:
            continue
        cible = item.targets[0]
        if not isinstance(cible, ast.Name) or cible.id.startswith("_"):
            continue
        valeur = item.value
        if isinstance(valeur, ast.Tuple) and valeur.elts:
            valeur = valeur.elts[0]
        if isinstance(valeur, ast.Constant) and isinstance(valeur.value, str):
            valeurs.add(valeur.value)
    return valeurs


def _valeurs_de_liste(noeud, constantes: dict = None) -> set | None:
    """[( 'x', 'Label'), …] ou ['x', …] -> {'x', …} ; None si illisible.

    `constantes` permet le cas MESURE du depot : `GRAVITES = (INFO,
    AVERTISSEMENT, BLOCAGE)` (apps/ao/fabrique/approvisionnement.py) — une
    liste de NOMS de constantes du meme module, pas de litteraux. Un seul
    niveau de deference, jamais recursif : au-dela, la source n'est plus
    certaine et l'on prefere refuser.
    """
    if not isinstance(noeud, (ast.List, ast.Tuple, ast.Set)):
        return None
    valeurs = set()
    for element in noeud.elts:
        if isinstance(element, (ast.Tuple, ast.List)) and element.elts:
            element = element.elts[0]
        if isinstance(element, ast.Name) and constantes:
            element = constantes.get(element.id)
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            valeurs.add(element.value)
        else:
            return None
    return valeurs or None


def _dotted(noeud) -> list | None:
    """`DossierEmploye.MotifSortie.choices` -> ['DossierEmploye','MotifSortie','choices']"""
    parties = []
    courant = noeud
    while isinstance(courant, ast.Attribute):
        parties.append(courant.attr)
        courant = courant.value
    if not isinstance(courant, ast.Name):
        return None
    parties.append(courant.id)
    parties.reverse()
    return parties


def _resoudre_reference(noeud, modele: ast.ClassDef, arbre, constantes: dict,
                        *, etendu: bool = False):
    """Valeurs designees par l'expression `choices=…`, ou None si incertain.

    LE PIEGE QUALIFIE : un nom SIMPLE ecrit dans le corps du modele designe
    d'abord la classe IMBRIQUEE de CE modele. Resoudre par nom simple au niveau
    module donnait 6 faux candidats mesures.

    `etendu` (2e passe PACT159) ajoute deux lectures : les attributs de CLASSE
    du modele porteur (`choices=KIND_CHOICES`) et la deference d'un nom de
    constante. Il est FAUX par defaut parce que `check_api_shapes.py` appelle
    cette fonction pour un tout autre usage — le contrat versionne d'API :
    elargir sa resolution deplacerait ce contrat, ce qui est une decision
    separee et non un effet de bord de la garde de vocabulaire.
    """
    extras = constantes if etendu else None
    parties = _dotted(noeud)
    if parties is None:
        return _valeurs_de_liste(noeud, extras)
    if parties[-1] == "choices":
        parties = parties[:-1]
    if not parties:
        return None
    imbriquees = _classes_de(modele)
    sommet = _classes_de(arbre)
    if len(parties) == 1:
        nom = parties[0]
        if nom in imbriquees:                 # `Statut` = DossierEmploye.Statut
            return _valeurs_de_textchoices(imbriquees[nom])
        # `choices=KIND_CHOICES` ou `KIND_CHOICES` est un attribut de CLASSE du
        # modele porteur (forme majoritaire de `core/models.py`) : il prime sur
        # un homonyme de module, exactement comme la classe imbriquee.
        propres = _constantes_de_module(modele) if etendu else {}
        if nom in propres:
            # `KIND_CHOICES = [(KIND_EXPORT, 'Sauvegarde'), …]` : les noms cites
            # sont des attributs de la MEME classe, pas du module.
            valeurs = _valeurs_de_liste(propres[nom], {**constantes, **propres})
            if valeurs is not None:
                return valeurs
        if nom in constantes:
            return _valeurs_de_liste(constantes[nom], extras)
        if nom in sommet:
            return _valeurs_de_textchoices(sommet[nom])
        return None
    porteur = sommet.get(parties[0])
    if porteur is None:
        return None
    for maillon in parties[1:]:
        suivant = _classes_de(porteur).get(maillon)
        if suivant is None:
            return None
        porteur = suivant
    return _valeurs_de_textchoices(porteur)


def _constantes_de_module(arbre) -> dict:
    out = {}
    for item in arbre.body:
        if isinstance(item, ast.Assign):
            for cible in item.targets:
                if isinstance(cible, ast.Name):
                    out[cible.id] = item.value
    return out


def valeurs_serveur(cible: str):
    """(valeurs, description lisible) ou (None, motif de l'echec).

    Une cible en TROIS segments finissant par un nom TOUT-EN-MAJUSCULES est
    ambigue : `flotte.Vehicule.CHECKLIST_MISE_EN_SERVICE` est un attribut de
    CLASSE, `ao.fabrique.GRAVITES` une constante de MODULE. On essaie donc le
    modele d'abord, le module ensuite, et l'on ne rend le motif d'echec que si
    les DEUX lectures echouent.
    """
    parties = cible.split(".")
    if len(parties) == 3 and _CONSTANTE.match(parties[-1]):
        valeurs, motif = _par_modele(cible, parties)
        if valeurs is not None:
            return valeurs, motif
    return _par_module_ou_modele(cible, parties)


def _par_module_ou_modele(cible: str, parties: list):
    if len(parties) < 2:
        return None, f"cible `{cible}` illisible (attendu `app.Modele.champ`)"

    if _CONSTANTE.match(parties[-1]):
        # `ao.fabrique.approvisionnement.GRAVITES`
        chemin = APPS_ROOT.joinpath(*parties[:-1]).with_suffix(".py")
        if not chemin.is_file():
            chemin = APPS_ROOT.joinpath(*parties[:-1]) / "__init__.py"
        if not chemin.is_file():
            return None, f"module introuvable pour `{cible}` ({chemin.name})"
        arbre = _module_tree(chemin)
        if arbre is None:
            return None, f"module illisible pour `{cible}`"
        constantes_module = _constantes_de_module(arbre)
        constante = constantes_module.get(parties[-1])
        if constante is None:
            return None, f"constante `{parties[-1]}` absente de {chemin.name}"
        valeurs = _valeurs_de_liste(constante, constantes_module)
        if valeurs is None:
            return None, (f"constante `{parties[-1]}` de {chemin.name} n'est pas "
                          "une liste de valeurs litterales")
        return valeurs, f"{cible} ({len(valeurs)} valeurs)"

    if len(parties) != 3:
        return None, (f"cible `{cible}` illisible (attendu `app.Modele.champ` "
                      "ou un chemin de constante `app.module.CONSTANTE`)")
    return _par_modele(cible, parties)


def modules_de_modeles(app: str) -> list:
    """Tous les fichiers ou un modele de `app` peut etre DECLARE.

    Mesure PACT159 : la moitie des applications du depot eclatent leurs
    modeles (`models_approvals.py`, `models_installation.py`, `models_tariff.py`)
    et ne gardent dans `models.py` qu'une ligne de re-export — invisible a
    l'AST. Ne lire que `models.py` refusait ces cibles pour une raison de
    RANGEMENT, pas de verite. `core` n'est pas sous `apps/` : les deux racines
    sont donc essayees.
    """
    chemins = []
    for base in (APPS_ROOT / app, DJANGO_ROOT / app):
        if not base.is_dir():
            continue
        principal = base / "models.py"
        if principal.is_file():
            chemins.append(principal)
        chemins.extend(sorted(base.glob("models_*.py")))
        paquet = base / "models"
        if paquet.is_dir():
            chemins.extend(sorted(paquet.glob("*.py")))
    return chemins


def _par_modele(cible: str, parties: list):
    app, modele_nom, champ = parties
    chemins = modules_de_modeles(app)
    if not chemins:
        return None, f"application `{app}` sans models.py (cible `{cible}`)"
    arbre = modele = None
    for chemin in chemins:
        arbre_candidat = _module_tree(chemin)
        if arbre_candidat is None:
            continue
        trouve = _classes_de(arbre_candidat).get(modele_nom)
        if trouve is not None:
            arbre, modele = arbre_candidat, trouve
            break
    if modele is None:
        return None, (f"modele `{modele_nom}` absent des modeles de `{app}` "
                      f"({len(chemins)} module(s) lus)")
    constantes = _constantes_de_module(arbre)
    for item in modele.body:
        if not isinstance(item, ast.Assign) or len(item.targets) != 1:
            continue
        cible_nom = item.targets[0]
        if not isinstance(cible_nom, ast.Name) or cible_nom.id != champ:
            continue
        if not isinstance(item.value, ast.Call):
            # Vocabulaire porte par un ATTRIBUT DE CLASSE et non par un champ :
            # `Vehicule.CHECKLIST_MISE_EN_SERVICE = ('immatriculation_faite', …)`
            # (mesure PACT159 : le miroir front existait, exact, et restait en
            # prose faute d'une cible declarable).
            valeurs = _valeurs_de_liste(
                item.value, {**constantes, **_constantes_de_module(modele)})
            if valeurs is not None:
                return valeurs, f"{cible} ({len(valeurs)} valeurs)"
            return None, (f"`{champ}` de `{modele_nom}` n'est ni un champ "
                          "Django ni une liste de valeurs litterales")
        for kw in item.value.keywords:
            if kw.arg != "choices":
                continue
            valeurs = _resoudre_reference(kw.value, modele, arbre, constantes,
                                          etendu=True)
            if valeurs is None:
                return None, (f"`{cible}` : les `choices` ne sont pas resolubles "
                              "statiquement (source non figee)")
            return valeurs, f"{cible} ({len(valeurs)} valeurs)"
        return None, f"champ `{champ}` de `{modele_nom}` ne declare aucun `choices`"
    return None, f"champ `{champ}` absent du modele `{modele_nom}` (apps/{app}/models.py)"


# ===========================================================================
# 2. Cote frontend : lire la liste marquee
# ===========================================================================

# Le marqueur porte sur la liste qui le SUIT IMMEDIATEMENT. Sans cette borne,
# un marqueur pose devant un objet (et non un tableau) irait chercher la
# premiere liste du fichier, 300 lignes plus bas : un rouge sur du code sain.
PORTEE_MARQUEUR = 400


def _bloc_de_liste(masque: str, depart: int):
    """(debut, fin) du premier `[ … ]` ou `{ … }` equilibre apres `depart`.

    PACT159 (2e passe) : le depot ecrit son vocabulaire sous DEUX formes, pas
    une. Mesure sur les 68 promesses en prose : 8 d'entre elles portent sur un
    OBJET `{ cle: 'Libelle' }` (ChatterTimeline, paieLogic, procurement,
    equipement, statuses…). N'accepter que le tableau condamnait ces
    promesses a rester en prose pour une raison purement syntaxique.
    """
    candidats = [position for position in (masque.find("[", depart),
                                           masque.find("{", depart))
                 if position >= 0]
    if not candidats:
        return None
    debut = min(candidats)
    if debut - depart > PORTEE_MARQUEUR:
        return None
    profondeur = 0
    for index in range(debut, len(masque)):
        caractere = masque[index]
        if caractere in "[{(":
            profondeur += 1
        elif caractere in "])}":
            profondeur -= 1
            if profondeur == 0:
                return (debut, index + 1)
    return None


def _profondeurs(masque_bloc: str) -> list:
    """Profondeur d'imbrication AVANT chaque caractere du bloc."""
    niveaux, profondeur = [], 0
    for caractere in masque_bloc:
        niveaux.append(profondeur)
        if caractere in "[{(":
            profondeur += 1
        elif caractere in "])}":
            profondeur -= 1
    return niveaux


def _cles_de_premier_niveau(code_bloc: str, masque_bloc: str) -> set:
    """Cles d'un objet `{ cle: …, 'autre': … }` — SEULEMENT au 1er niveau.

    Une cle imbriquee (`{ a: { couleur: 'x' } }`) n'est pas du vocabulaire :
    la profondeur est calculee sur le masque, donc les accolades ecrites dans
    une chaine ne faussent rien. Une cle calculee `[expr]:` reste a une
    profondeur > 1 et est donc ignoree — dans le sens SUR (moins de valeurs
    lues ne peut jamais fabriquer un rouge).
    """
    niveaux = _profondeurs(masque_bloc)
    cles = set()
    for trouve in _CLE.finditer(masque_bloc):
        debut = trouve.start("qs") if trouve.group("qs") is not None \
            else trouve.start("id")
        if niveaux[debut] != 1:
            continue
        cles.add(code_bloc[trouve.start("qs"):trouve.end("qs")]
                 if trouve.group("qs") is not None else trouve.group("id"))
    return cles


def _paires_de_premier_niveau(code_bloc: str, masque_bloc: str):
    """`[['csv','CSV'], ['parquet','Parquet']]` -> {'csv','parquet'} ou None.

    C'est la forme meme des `choices` Python, recopiee telle quelle cote
    ecran (parametres). Sans ce cas, le repli « toutes les chaines du bloc »
    lisait AUSSI les libelles et criait au loup sur du code sain.
    """
    niveaux = _profondeurs(masque_bloc)
    valeurs, index, taille = set(), 0, len(masque_bloc)
    while index < taille:
        if masque_bloc[index] == "[" and niveaux[index] == 1:
            trouve = _CHAINE.search(masque_bloc, index + 1)
            fin_paire = masque_bloc.find("]", index + 1)
            if trouve is None or (0 <= fin_paire < trouve.start()):
                return None
            valeurs.add(code_bloc[trouve.start("v"):trouve.end("v")])
            index = fin_paire + 1 if fin_paire > index else index + 1
            continue
        index += 1
    return valeurs or None


def valeurs_frontend(code: str, masque: str, depart: int):
    """({valeurs}, None) ou (None, motif) — la liste marquee, lue du source."""
    bornes = _bloc_de_liste(masque, depart)
    if bornes is None:
        return None, ("le marqueur `source-choix` ne precede aucune liste "
                      "`[ … ]` ni aucun objet `{ … }` lisible")
    bloc = code[bornes[0]:bornes[1]]
    masque_bloc = masque[bornes[0]:bornes[1]]

    if bloc.lstrip().startswith("{"):
        valeurs = _cles_de_premier_niveau(bloc, masque_bloc)
        if valeurs:
            return valeurs, None
        return None, ("objet marque sans cle de premier niveau lisible")

    for motif in (_VALEUR, _CLE_TABLEAU):
        valeurs = {trouve.group("v") for trouve in motif.finditer(bloc)}
        if valeurs:
            return valeurs, None
    if "{" in bloc:
        return None, ("liste d'objets sans cle `value:` ni `key:` — un "
                      "marqueur `source-choix` exige une liste lisible par "
                      "machine")
    valeurs = _paires_de_premier_niveau(bloc, masque_bloc)
    if valeurs:
        return valeurs, None
    valeurs = {trouve.group("v") for trouve in _CHAINE.finditer(bloc)}
    if valeurs:
        return valeurs, None
    return None, "liste marquee vide ou illisible"


def fichiers_frontend(racine: Path = None):
    racine = FRONT_SRC if racine is None else racine
    if not racine.is_dir():
        return []
    vus = []
    for motif in ("*.js", "*.jsx", "*.mjs"):
        for chemin in sorted(racine.rglob(motif)):
            if "node_modules" in chemin.parts:
                continue
            vus.append(chemin)
    return vus


# ===========================================================================
# 3. Rapprochement
# ===========================================================================

def analyser(racine: Path = None):
    """([(fichier, ligne, cible, motif)], nombre de listes marquees verifiees)."""
    constats, verifiees = [], 0
    for chemin in fichiers_frontend(racine):
        try:
            source = chemin.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "source-choix" not in source:
            continue
        code, _, masque = scan_js(source)
        relatif = (chemin.relative_to(ROOT).as_posix()
                   if chemin.is_relative_to(ROOT) else chemin.as_posix())
        for trouve in MARQUEUR.finditer(source):
            ligne = source.count("\n", 0, trouve.start()) + 1
            cible = trouve.group("cible")
            attendues, description = valeurs_serveur(cible)
            if attendues is None:
                constats.append((relatif, ligne, cible, description))
                continue
            trouvees, motif = valeurs_frontend(code, masque, trouve.end())
            if trouvees is None:
                constats.append((relatif, ligne, cible, motif))
                continue
            verifiees += 1
            sentinelles = {mot.strip() for mot
                           in (trouve.group("sentinelles") or "").split(",")
                           if mot.strip()}
            inventees = sorted(trouvees - attendues - sentinelles)
            if inventees:
                constats.append((
                    relatif, ligne, cible,
                    f"valeur(s) INVENTEE(S) {', '.join(repr(v) for v in inventees)} : "
                    f"le champ `{cible}` ne les connait pas "
                    f"(il accepte : {', '.join(sorted(attendues))})"))
    return constats, verifiees


# ===========================================================================
# 4. Les promesses en PROSE : converties, ou REFUSEES une par une
# ===========================================================================
#
# PACT159 exige que les ~80 promesses en prose du depot soient « converties ou
# refusees une par une ». Une promesse qui n'est ni l'un ni l'autre serait
# exactement ce que la tache reproche : une phrase que rien ne verifie et que
# personne n'a tranchee. L'inventaire ci-dessous est donc EXHAUSTIF, et
# `--promesses` signale toute promesse nouvelle ou reformulee (a trancher).

PROMESSE = re.compile(
    r"(?i)//.*?(align[ée]s? sur|miroir de|m[êe]mes valeurs que|copie de"
    r"|repris? (?:de|du)|conforme [àa]|selon .*TextChoices)")

# Distance (en lignes) sous laquelle une promesse est consideree CONVERTIE par
# un marqueur voisin.
PORTEE_PROSE = 8

MOTIFS_REFUS = {
    "COMPORTEMENT": "porte sur un comportement ou une fonction, jamais sur "
                    "une liste de valeurs",
    "MIROIR_JS": "la source citee est un autre fichier frontend, pas le "
                 "serveur : rien a declarer",
    "SCALAIRE": "precede une constante scalaire, pas une liste",
    "NOMBRES": "table de nombres (tarifs, irradiance, paliers), pas un "
               "vocabulaire de valeurs",
    "SANS_SOURCE": "la source serveur n'est ni un champ `choices=` ni une "
                   "liste litterale (champ calcule, registre, noms de champs)",
    "FORME": "la liste n'expose pas son vocabulaire au 1er niveau (derivee au "
             "runtime, ou valeurs imbriquees)",
    "TEST": "fichier de test : decrit une parite, ne rend aucun choix a "
            "l'ecran",
    "HORS_MODELE": "vocabulaire STAGES.py — le tunnel n'est adosse a AUCUN "
                   "modele (regle #2 CLAUDE.md) : aucune cible declarable",
}

REFUS = {
    "frontend/src/api/iaApi.js": [("contrat (a) d'`axios.js`", "MIROIR_JS")],
    "frontend/src/api/ventesApi.js": [("sélecteur ZFAC12", "COMPORTEMENT")],
    "frontend/src/features/adsengine/adsengine.js": [
        ("Grille neuve", "COMPORTEMENT")],
    "frontend/src/features/adsengine/adsengineApi.js": [
        ("Chemins alignés", "COMPORTEMENT")],
    "frontend/src/features/adsengine/ApprovalsScreen.jsx": [
        ("editCopyDiff", "MIROIR_JS")],
    "frontend/src/features/adsengine/CommentsInboxScreen.jsx": [
        ("PRIVATE_REPLY_WINDOW_DAYS", "SCALAIRE")],
    "frontend/src/features/agriculture/darAlert.js": [
        ("check_dar_guard", "COMPORTEMENT")],
    "frontend/src/features/ao/provenance.test.jsx": [
        ("Sanity check", "TEST")],
    "frontend/src/features/crm/CallLogPopover.jsx": [
        ("LeadActivity.OUTCOMES", "FORME")],
    "frontend/src/features/crm/crm-porte.test.jsx": [
        ("SECTION_LABELS", "TEST")],
    "frontend/src/features/crm/stages.js": [
        ("CONVERSION_STAGE", "HORS_MODELE")],
    "frontend/src/features/crm/workspace/draftCore.js": [
        ("LeadForm.jsx", "MIROIR_JS")],
    "frontend/src/features/crm/workspace/useLeadDraft.js": [
        ("LeadForm.jsx", "MIROIR_JS")],
    "frontend/src/features/gestion_projet/constants.jsx": [
        ("machine à états", "FORME")],
    "frontend/src/features/installations/statuses.js": [
        ("recul côté UI", "COMPORTEMENT")],
    "frontend/src/features/paie/paieLogic.js": [
        ("ORDRE_STATUTS", "FORME")],
    "frontend/src/features/sav/equipement.js": [
        ("garantie_etat", "SANS_SOURCE")],
    "frontend/src/features/stock/labels.js": [
        ("Préfixes connus", "SANS_SOURCE")],
    "frontend/src/features/ventes/agronomy.js": [
        ("Aligné sur solar.js", "MIROIR_JS")],
    "frontend/src/features/ventes/ConceptionElectrique.jsx": [
        # PV43 — DC_M_MINIMUM/DC_M_PAR_CHAINE : constantes scalaires de
        # préremplissage (la valeur AFFICHÉE vient du serveur), pas une liste.
        ("electrical_service.py", "SCALAIRE")],
    "frontend/src/features/ventes/module.config.jsx": [
        ("/sav/action-requise", "COMPORTEMENT")],
    "frontend/src/features/ventes/solar.js": [
        # PVOND (2026-08-18) — le commentaire decrit l'avertissement « vivier
        # batterie vide », un comportement, pas une liste de valeurs.
        ("livrer un kit silencieusement sans stockage", "COMPORTEMENT"),
        ("MIROIR de la source Python", "NOMBRES"),
        ("computeROI", "NOMBRES"),
        ("plafonds cumulatifs", "NOMBRES"),
        ("constants_82_21.py", "NOMBRES"),
        ("injection_annuelle", "COMPORTEMENT")],
    "frontend/src/features/ventes/solar.injection.test.mjs": [
        ("Valeurs", "TEST")],
    "frontend/src/components/layout/ChatBell.jsx": [
        ("Icône de chat", "MIROIR_JS")],
    "frontend/src/components/layout/Sidebar.odx6.test.jsx": [
        ("coquille redevient NEUTRE", "TEST")],
    "frontend/src/lib/monitoring.test.mjs": [("Sentry frontend", "TEST")],
    "frontend/src/router/moduleRoutes.jsx": [
        ("AUCUNE copie de cette règle", "COMPORTEMENT")],
    "frontend/src/pages/crm/leads/views/KanbanView.jsx": [
        ("STAGES.py", "HORS_MODELE")],
    "frontend/src/pages/crm/leads/views/ListView.jsx": [
        ("features/crm/stages", "HORS_MODELE")],
    "frontend/src/pages/installations/InstallationsPage.jsx": [
        ("vue CRM", "COMPORTEMENT")],
    "frontend/src/pages/installations/views/InstallationsSkeleton.jsx": [
        ("entonnoir chantier", "SCALAIRE")],
    "frontend/src/pages/interventions/MaJourneePage.jsx": [
        ("STATUT_ORDER", "COMPORTEMENT")],
    "frontend/src/pages/parametres/AvanceSection.jsx": [
        ("customfieldables", "SANS_SOURCE")],
    "frontend/src/pages/parametres/EtapesChantierSection.jsx": [
        ("exige_*", "SANS_SOURCE")],
    "frontend/src/pages/parametres/peConstants.js": [
        ("Défauts métier", "NOMBRES")],
    "frontend/src/pages/parametres/TarificationSection.jsx": [
        ("DEFAULT_RESIDENTIAL_TIERS", "NOMBRES")],
    "frontend/src/pages/Rapports.jsx": [("hors effet", "COMPORTEMENT")],
    "frontend/src/pages/sav/EquipementsPage.jsx": [
        ("equipement.js", "SANS_SOURCE")],
    "frontend/src/pages/sav/TicketKeyboard.apx31.test.mjs": [
        ("memes gardes", "TEST")],
    "frontend/src/pages/stock/StockList.jsx": [("garde backend QG4",
                                                "COMPORTEMENT")],
    "frontend/src/pages/ventes/DevisActionBoardPage.jsx": [
        ("Relances du jour", "COMPORTEMENT"),
        ("wa.me", "MIROIR_JS")],
    "frontend/src/pages/ventes/factureKanban.js": [
        ("solde partiel", "MIROIR_JS"),
        ("isOverdue", "MIROIR_JS")],
}


def promesses(racine: Path = None):
    """(converties, refusees, nouvelles) — inventaire des promesses en prose."""
    converties, refusees, nouvelles = [], [], []
    for chemin in fichiers_frontend(racine):
        try:
            lignes = chemin.read_text(encoding="utf-8",
                                      errors="replace").splitlines()
        except OSError:
            continue
        relatif = (chemin.relative_to(ROOT).as_posix()
                   if chemin.is_relative_to(ROOT) else chemin.as_posix())
        for index, ligne in enumerate(lignes):
            if not PROMESSE.search(ligne):
                continue
            voisinage = "\n".join(lignes[max(0, index - 3):
                                         index + PORTEE_PROSE])
            if "source-choix" in voisinage:
                converties.append((relatif, index + 1))
                continue
            motif = next((categorie
                          for fragment, categorie in REFUS.get(relatif, [])
                          if fragment in ligne), None)
            if motif is None:
                nouvelles.append((relatif, index + 1, ligne.strip()))
            else:
                refusees.append((relatif, index + 1, motif))
    return converties, refusees, nouvelles


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Garde de vocabulaire a source declaree (opt-in, PACT159).")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--promesses", action="store_true",
                        help="inventaire des promesses en prose : converties, "
                             "refusees (avec motif), a trancher")
    args = parser.parse_args(argv)

    if args.promesses:
        converties, refusees, nouvelles = promesses()
        print(f"Promesses en prose CONVERTIES (marqueur pose) : "
              f"{len(converties)}.")
        print(f"Promesses REFUSEES (tranchees une par une)    : "
              f"{len(refusees)}.")
        for categorie, phrase in sorted(MOTIFS_REFUS.items()):
            compte = sum(1 for _, _, motif in refusees if motif == categorie)
            if compte:
                print(f"    {compte:>3}  {categorie:<12} {phrase}")
        if nouvelles:
            print(f"\nA TRANCHER : {len(nouvelles)} promesse(s) en prose ni "
                  "converties ni refusees.\n")
            for relatif, ligne, texte in nouvelles:
                print(f"  {relatif}:{ligne}\n      {texte[:100]}")
            print("\nPoser un marqueur `// source-choix: app.Modele.champ` "
                  "au-dessus de la liste, OU inscrire la promesse dans "
                  "`REFUS` avec son motif.")
            return 1
        print("\nAucune promesse en prose en suspens.")
        return 0

    constats, verifiees = analyser()
    if args.stats:
        print(f"Listes de choix frontend a source DECLAREE : {verifiees}.")
        print(f"Divergences : {len(constats)}.")

    if constats:
        print(f"\nECHEC : {len(constats)} liste(s) de choix frontend divergent de "
              f"la source qu'elles DECLARENT.\n")
        for relatif, ligne, cible, motif in sorted(constats):
            print(f"  {relatif}:{ligne}  (// source-choix: {cible})")
            print(f"      {motif}")
        print("\nUne liste marquee `// source-choix:` PROMET que son vocabulaire "
              "vient du serveur. Corriger la liste, corriger le modele, ou "
              "retirer le marqueur (une liste NON marquee n'est jamais "
              "controlee — cette garde est volontairement opt-in).")
        return 1

    print(f"OK : {verifiees} liste(s) de choix frontend a source declaree, "
          "toutes alignees sur le vocabulaire du serveur.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

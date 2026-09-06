"""AUD515 -- garde CI transverse : un modele a MACHINE D'ETATS ne laisse jamais
son ``statut`` writable au serialiseur.

LE PATRON QU'IL FERME. « signe sans signature », « cloture sans CAPA »,
« livre sans stock » : le meme defaut a ete confirme INDEPENDAMMENT sur quatre
apps (contrats, qhse, sav, ventes -- AUD501/AUD505/AUD506/AUD512/AUD514). Ce
n'est donc plus un accident local mais une CLASSE SYSTEMIQUE. Le repo se dote
d'un point de transition DEDIE (``machine_etats.py``, ``changer_statut*``) qui
porte toutes les gardes metier -- puis laisse un PATCH brut du corps poser le
meme champ sans en traverser aucune.

CE QUE LE SCRIPT FAIT. Il DECOUVRE les modeles gouvernes (aucune liste
statique a maintenir a la main), puis exige, pour chacun, que TOUT serialiseur
de modele qui l'expose ferme la porte d'ecriture.

DECOUVERTE (deux sources, semantiques) :

  1. un modele importe depuis ``.models`` a l'interieur d'un module
     ``apps/<app>/machine_etats.py`` ;
  2. un modele dont l'app declare une fonction de transition dediee
     ``changer_statut*`` au niveau module : le PREMIER parametre nomme
     l'objet gouverne (``changer_statut(contrat, ...)`` ->  ``Contrat``,
     ``changer_statut_vehicule(vehicule, ...)`` -> ``Vehicule``), et le nom
     resolu doit correspondre a une classe de modele REELLE de cette app.

PORTE FERMEE = l'une de ces quatre formes, au choix :

  * ``statut`` figure dans ``Meta.read_only_fields`` ;
  * la classe definit ``validate_statut`` (refus des valeurs reservees) ;
  * ``Meta.fields`` est une liste EXPLICITE qui n'expose pas ``statut`` ;
  * ``Meta.exclude`` retire ``statut``.

CE QUE LE SCRIPT NE FAIT PAS. Il ne devine pas les modeles gouvernes par un
mecanisme non declare : c'est un CLIQUET, pas un recensement. Un modele non
decouvert n'est jamais un faux rouge -- il est simplement pas encore couvert,
et le jour ou son app se dote d'un point de transition dedie, il entre dans le
perimetre tout seul.

Usage :
    python scripts/check_machine_etats_statut_readonly.py          # CI
    python scripts/check_machine_etats_statut_readonly.py --list   # inventaire
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"
ALLOWLIST_PATH = ROOT / "scripts" / "machine_etats_statut_allow.txt"

CHAMP = "statut"
PREFIXE_TRANSITION = "changer_statut"
SEPARATEUR = "|"


def base_de_reprise(path: Path = ALLOWLIST_PATH) -> dict:
    """Rend ``{cle: raison}`` -- l'existant FIGE le jour ou le garde est ne.

    Le garde est ne ROUGE (cinq serialiseurs). Corriger les cinq d'un coup
    depasse le perimetre de la tache qui cree le garde : chacun a la sienne.
    La base fige donc l'existant pour que le garde protege contre une
    REGRESSION et contre tout NOUVEAU modele des aujourd'hui, et elle ne peut
    que DECROITRE (une entree se retire quand sa tache atterrit).
    """
    entrees = {}
    if not path.exists():
        return entrees
    for ligne in path.read_text(encoding="utf-8").splitlines():
        nue = ligne.strip()
        if not nue or nue.startswith("#"):
            continue
        cle, _, raison = nue.partition(SEPARATEUR)
        cle = cle.strip()
        if cle:
            entrees[cle] = raison.strip()
    return entrees


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _parse(path: Path):
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):  # pragma: no cover - fichier illisible
        return None


def _fichiers(app_dir: Path, base: str) -> list[Path]:
    """``models.py`` + ``models_*.py`` + le paquet ``models/`` (idem
    ``serializers``). Le depot utilise les trois formes."""
    trouves = [p for p in app_dir.glob(f"{base}*.py") if p.is_file()]
    paquet = app_dir / base
    if paquet.is_dir():
        trouves.extend(sorted(paquet.glob("*.py")))
    return trouves


def _camel(nom_snake: str) -> str:
    return "".join(mot.capitalize() for mot in nom_snake.split("_") if mot)


def modeles_de_l_app(app_dir: Path) -> set[str]:
    """Noms des classes de modeles declarees par l'app."""
    noms = set()
    for path in _fichiers(app_dir, "models"):
        tree = _parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                noms.add(node.name)
    return noms


def modeles_gouvernes(app_dir: Path) -> set[str]:
    """Les modeles de CETTE app dotes d'un point de transition dedie."""
    connus = modeles_de_l_app(app_dir)
    gouvernes: set[str] = set()

    machine = app_dir / "machine_etats.py"
    tree = _parse(machine) if machine.exists() else None
    if tree is not None:
        for node in ast.walk(tree):
            if (isinstance(node, ast.ImportFrom)
                    and (node.module or "") == "models"):
                for alias in node.names:
                    if alias.name in connus:
                        gouvernes.add(alias.name)

    for path in _fichiers(app_dir, "services"):
        tree = _parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith(PREFIXE_TRANSITION):
                continue
            if not node.args.args:
                continue
            candidat = _camel(node.args.args[0].arg)
            if candidat in connus:
                gouvernes.add(candidat)
    return gouvernes


def _noms_de_liste(node) -> set[str] | None:
    """Les chaines litterales d'une liste/tuple, ou ``None`` si non litteral."""
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    noms = set()
    for element in node.elts:
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            noms.add(element.value)
        else:
            return None
    return noms


def _meta_de(classe: ast.ClassDef):
    for node in classe.body:
        if isinstance(node, ast.ClassDef) and node.name == "Meta":
            return node
    return None


def _assignation(meta: ast.ClassDef, cible: str):
    for node in meta.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == cible:
                    return node.value
    return None


def porte_fermee(classe: ast.ClassDef) -> bool:
    """Vrai si ce serialiseur ne laisse pas ``statut`` writable."""
    for node in classe.body:
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == f"validate_{CHAMP}"):
            return True
    meta = _meta_de(classe)
    if meta is None:
        return False
    lecture_seule = _noms_de_liste(_assignation(meta, "read_only_fields"))
    if lecture_seule and CHAMP in lecture_seule:
        return True
    exclus = _noms_de_liste(_assignation(meta, "exclude"))
    if exclus and CHAMP in exclus:
        return True
    champs = _noms_de_liste(_assignation(meta, "fields"))
    if champs is not None and CHAMP not in champs:
        return True
    return False


def _modele_de(meta: ast.ClassDef) -> str | None:
    valeur = _assignation(meta, "model")
    if isinstance(valeur, ast.Name):
        return valeur.id
    if isinstance(valeur, ast.Attribute):
        return valeur.attr
    return None


def divergences(inclure_reprise: bool = False) -> list[str]:
    """Les serialiseurs qui laissent ``statut`` writable sur un modele gouverne.

    ``inclure_reprise`` -- rendre AUSSI les entrees figees dans la base de
    reprise (utile pour prouver que le detecteur VOIT ; le mode CI les tait).
    """
    gelees = set() if inclure_reprise else set(base_de_reprise())
    trouvees: list[str] = []
    for app_dir in sorted(p for p in APPS_DIR.iterdir() if p.is_dir()):
        gouvernes = modeles_gouvernes(app_dir)
        if not gouvernes:
            continue
        for path in _fichiers(app_dir, "serializers"):
            tree = _parse(path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                meta = _meta_de(node)
                if meta is None:
                    continue
                modele = _modele_de(meta)
                if modele not in gouvernes:
                    continue
                if porte_fermee(node):
                    continue
                cle = f"{app_dir.name}.{modele}.{node.name}"
                if cle in gelees:
                    continue
                trouvees.append(
                    f"{_rel(path)}:{node.lineno}  {cle} "
                    f"-- « {CHAMP} » writable")
    return trouvees


def inventaire() -> list[str]:
    lignes = []
    for app_dir in sorted(p for p in APPS_DIR.iterdir() if p.is_dir()):
        for modele in sorted(modeles_gouvernes(app_dir)):
            lignes.append(f"{app_dir.name}.{modele}")
    return lignes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Garde AUD515 — statut read_only sur un modele a "
                    "machine d'etats.")
    parser.add_argument("--list", action="store_true", dest="list_mode",
                        help="imprime les modeles gouvernes decouverts")
    parser.add_argument("--tout", action="store_true",
                        help="ignore la base de reprise (preuve que le "
                             "detecteur voit)")
    args = parser.parse_args(argv)

    if args.list_mode:
        for ligne in inventaire():
            print(ligne)
        return 0

    gouvernes = inventaire()
    fautifs = divergences(inclure_reprise=args.tout)
    reprise = base_de_reprise()
    print(f"check_machine_etats_statut_readonly: {len(gouvernes)} modele(s) a "
          f"point de transition dedie decouvert(s), {len(reprise)} entree(s) "
          f"de reprise figee(s).")
    if not fautifs:
        print("check_machine_etats_statut_readonly: OK — aucun « statut » "
              "writable sur un modele gouverne.")
        return 0

    print("\ncheck_machine_etats_statut_readonly: « statut » WRITABLE sur un "
          "modele a machine d'etats :")
    for ligne in fautifs:
        print(f"  - {ligne}")
    print(
        "\nUn point de transition dedie ne vaut que si la porte d'ecriture "
        "generique est fermee : un PATCH brut du corps pose le meme champ sans "
        "traverser AUCUNE garde metier (« signe » sans signature, « cloture » "
        "sans CAPA, « livre » sans stock). Fermez la porte au choix : "
        f"« {CHAMP} » dans Meta.read_only_fields, un validate_{CHAMP} qui "
        "refuse les valeurs reservees, ou un Meta.fields explicite qui ne "
        f"l'expose pas.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

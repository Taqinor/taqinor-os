#!/usr/bin/env python
"""ACAL345 (C-ACAL-146) — Detecteur de duplicata LITTERAL >= 6 lignes.

POURQUOI
--------
L'audit calepinage a trouve le meme code recopie entre ``frontend/src/pages``,
``frontend/src/features``, ``apps/web/src`` et le moteur de devis
``apps/ventes/quote_engine`` (jumeaux C-ACAL-142/143/144…) : chaque copie
derive seule, et un correctif applique a l'une laisse l'autre fausse. Aucun
detecteur n'existait (pas de jscpd dans le depot). Cette garde MESURE la
duplication litterale et empeche qu'elle CROISSE : la base de dette
``scripts/duplicats_litteraux_allow.txt`` gele l'etat reel du jour
d'amorcage et ne peut que RETRECIR.

CE QU'ELLE MESURE, EXACTEMENT
-----------------------------
1. Chaque fichier de code (.py .js .jsx .ts .tsx .mjs .astro .css) des
   quatre racines est NORMALISE : espaces compactes, lignes vides retirees,
   commentaires de ligne (``//``, ``#``, ``/*``, ``*``, ``{/*``, ``<!--``),
   lignes de pure ponctuation (``}`` ``)`` ``);`` ``]`` …) et lignes
   ``import`` / ``from … import`` / ``export … from`` retirees.
2. Toute fenetre de ``SEUIL`` (6) lignes SIGNIFICATIVES consecutives presente
   dans au moins DEUX fichiers DIFFERENTS est un duplicata. Une repetition
   interne a un seul fichier n'en est pas un.
3. Les fenetres chevauchantes d'un fichier sont fusionnees en BLOCS
   maximaux. La cle d'un bloc = empreinte (sha1, 12 car.) de son texte
   normalise + la liste triee des fichiers qui portent ce meme bloc :
   ``<empreinte>|<fichier1>,<fichier2>``. Jamais un numero de ligne : un bloc
   qui descend de vingt lignes ne doit pas invalider la base.

Ce n'est PAS une detection structurelle (renommer une variable masque la
copie) et la garde ne SUPPRIME rien : les doublons trouves sont l'objet
d'autres taches.

USAGE
-----
    python scripts/check_duplicats_litteraux.py              # garde CI
    python scripts/check_duplicats_litteraux.py --stats      # chiffres
    python scripts/check_duplicats_litteraux.py --stats --perimetre calepinage
    python scripts/check_duplicats_litteraux.py --liste      # tous les blocs
    python scripts/check_duplicats_litteraux.py --write-baseline   # retrecit
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "scripts" / "duplicats_litteraux_allow.txt"

RACINES = (
    "frontend/src/pages",
    "frontend/src/features",
    "apps/web/src",
    "backend/django_core/apps/ventes/quote_engine",
)
EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".astro", ".css"}
DOSSIERS_IGNORES = {"node_modules", "__pycache__", "dist", ".astro"}

SEUIL = 6

PERIMETRES = {
    # Blocs touchant le calepinage : features/calepinage, ToitureDesign,
    # roofPro11 et la lib toiture.
    "calepinage": re.compile(
        r"(?i)features/calepinage/|ToitureDesign|roofpro11|lib/[^ ]*toiture"
        r"|toiture[^ /]*/lib/"),
}

_ESPACES = re.compile(r"\s+")
_COMMENTAIRE = re.compile(r"^(?://|/\*|\*|\{/\*|<!--|-->)")
_PONCTUATION = re.compile(r"^[\s{}()\[\];,.:>]*$")
# Lineaire (aucun `.*` suivi d'une autre condition : une ligne minifiee de
# plusieurs centaines de Ko commencant par `export` rendait la regex
# quadratique).
_IMPORT = re.compile(r"^(?:import\b|from\s+\S+\s+import\b)")
_EXPORT_FROM = re.compile(r"^export\s[^'\"]*\sfrom\s*['\"]")


def normaliser_ligne(ligne: str, python: bool) -> str:
    """'' si la ligne n'est pas significative, sinon sa forme compactee."""
    texte = _ESPACES.sub(" ", ligne).strip()
    if not texte:
        return ""
    if _COMMENTAIRE.match(texte) or (python and texte.startswith("#")):
        return ""
    if _PONCTUATION.match(texte):
        return ""
    if _IMPORT.match(texte) or _EXPORT_FROM.match(texte):
        return ""
    return texte


def lignes_significatives(texte: str, python: bool) -> list:
    """[(numero de ligne d'origine, ligne normalisee)]."""
    sortie = []
    for numero, ligne in enumerate(texte.splitlines(), 1):
        norme = normaliser_ligne(ligne, python)
        if norme:
            sortie.append((numero, norme))
    return sortie


def fichiers_scannes(racine: Path | None = None) -> list:
    racine = racine or ROOT
    trouves = []
    for rel in RACINES:
        base = racine / rel
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in EXTENSIONS or not path.is_file():
                continue
            if DOSSIERS_IGNORES.intersection(path.relative_to(racine).parts):
                continue
            trouves.append(path)
    return trouves


class Bloc:
    """Un bloc duplique maximal dans UN fichier."""

    def __init__(self, fichier: str, debut: int, fin: int, texte: str,
                 nb_lignes: int, partenaires: set):
        self.fichier = fichier
        self.partenaires = partenaires   # fichiers portant ses fenetres
        self.debut = debut
        self.fin = fin
        self.texte = texte
        self.nb_lignes = nb_lignes
        self.empreinte = hashlib.sha1(texte.encode("utf-8")).hexdigest()[:12]


class Duplicat:
    """Un meme bloc (meme texte normalise) porte par plusieurs fichiers."""

    def __init__(self, empreinte: str, blocs: list):
        self.empreinte = empreinte
        self.blocs = sorted(blocs, key=lambda b: (b.fichier, b.debut))

    @property
    def fichiers(self) -> list:
        """Le bloc et tous les fichiers qui en partagent une fenetre."""
        tous = set()
        for bloc in self.blocs:
            tous.add(bloc.fichier)
            tous.update(bloc.partenaires)
        return sorted(tous)

    @property
    def cle(self) -> str:
        return f"{self.empreinte}|{','.join(self.fichiers)}"

    @property
    def nb_lignes(self) -> int:
        return self.blocs[0].nb_lignes


def analyse(racine: Path | None = None, seuil: int = SEUIL):
    """Rend (duplicats, stats). `racine` resolue A L'APPEL (tests)."""
    racine = racine or ROOT
    contenus = {}
    for path in fichiers_scannes(racine):
        try:
            texte = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(racine).as_posix()
        contenus[rel] = lignes_significatives(texte, path.suffix == ".py")

    # Fenetre -> ensemble des fichiers qui la portent.
    porteurs: dict[int, set] = {}
    fenetres_par_fichier: dict[str, list] = {}
    for rel, lignes in contenus.items():
        cles = []
        for i in range(len(lignes) - seuil + 1):
            cle = hash(tuple(norme for _, norme in lignes[i:i + seuil]))
            cles.append(cle)
            porteurs.setdefault(cle, set()).add(rel)
        fenetres_par_fichier[rel] = cles

    blocs = []
    lignes_dupliquees = 0
    for rel, cles in fenetres_par_fichier.items():
        lignes = contenus[rel]
        couvertes = set()
        i = 0
        while i < len(cles):
            if len(porteurs[cles[i]]) < 2:
                i += 1
                continue
            j = i
            while j + 1 < len(cles) and len(porteurs[cles[j + 1]]) >= 2:
                j += 1
            segment = lignes[i:j + seuil]
            couvertes.update(range(i, j + seuil))
            partenaires = set()
            for k in range(i, j + 1):
                partenaires.update(porteurs[cles[k]])
            blocs.append(Bloc(rel, segment[0][0], segment[-1][0],
                              "\n".join(n for _, n in segment), len(segment),
                              partenaires))
            i = j + 1
        lignes_dupliquees += len(couvertes)

    groupes: dict[str, list] = {}
    for bloc in blocs:
        groupes.setdefault(bloc.empreinte, []).append(bloc)
    duplicats = sorted((Duplicat(e, b) for e, b in groupes.items()),
                       key=lambda d: (-d.nb_lignes, d.cle))

    total = sum(len(lignes) for lignes in contenus.values())
    stats = {
        "fichiers": len(contenus),
        "lignes": total,
        "blocs": len(duplicats),
        "lignes_dupliquees": lignes_dupliquees,
        "pourcent": (100.0 * lignes_dupliquees / total) if total else 0.0,
    }
    return duplicats, stats


# ---------------------------------------------------------------------------
# Base de dette
# ---------------------------------------------------------------------------

ENTETE_BASE = """\
# Base de dette de scripts/check_duplicats_litteraux.py (ACAL345, C-ACAL-146).
#
# Chaque ligne est `<empreinte>|<fichier1>,<fichier2>,...` : un bloc d'au moins
# 6 lignes significatives copie A L'IDENTIQUE (apres normalisation) entre
# frontend/src/pages, frontend/src/features, apps/web/src et
# backend/django_core/apps/ventes/quote_engine, mesure le jour de l'amorcage.
#
# La garde n'echoue que sur un bloc ABSENT de cette liste : elle empeche la
# RECIDIVE, elle ne supprime rien.
#
# REGLE ABSOLUE : CETTE LISTE NE PEUT QUE RETRECIR.
#   - supprimer une copie puis
#     `python scripts/check_duplicats_litteraux.py --write-baseline` retire sa
#     ligne ;
#   - `--write-baseline` REFUSE d'ajouter une ligne. Ajouter une dette exige
#     `--autoriser-croissance`, drapeau reserve au fondateur, visible en revue.
"""


def charger_base(path: Path | None = None) -> set:
    # Chemin resolu A L'APPEL : une valeur par defaut figee a la definition
    # du module ferait ecrire un test dans la VRAIE base.
    path = path or BASELINE_PATH
    if not path.is_file():
        return set()
    return {
        ligne.strip()
        for ligne in path.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.strip().startswith("#")
    }


def ecrire_base(cles: set, path: Path | None = None):
    path = path or BASELINE_PATH
    path.write_text(ENTETE_BASE + "".join(f"{c}\n" for c in sorted(cles)),
                    encoding="utf-8", newline="\n")


def _imprime(duplicat: Duplicat):
    print(f"  [{duplicat.empreinte}] {duplicat.nb_lignes} lignes "
          f"significatives :")
    for bloc in duplicat.blocs:
        print(f"      {bloc.fichier}:{bloc.debut}-{bloc.fin}")
    autres = [f for f in duplicat.fichiers
              if f not in {b.fichier for b in duplicat.blocs}]
    if autres:
        print(f"      (copie partielle dans : {', '.join(autres)})")


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description="Duplicata litteral >= 6 lignes entre pages/, features/, "
                    "apps/web et quote_engine.")
    parser.add_argument("--stats", action="store_true",
                        help="nombre de blocs, lignes dupliquees, %% du code")
    parser.add_argument("--perimetre", choices=sorted(PERIMETRES),
                        help="ne garde que les blocs touchant ce perimetre")
    parser.add_argument("--liste", action="store_true",
                        help="imprime chaque bloc (fichier:lignes)")
    parser.add_argument("--write-baseline", action="store_true",
                        help="retire de la base les blocs disparus")
    parser.add_argument("--autoriser-croissance", action="store_true",
                        help="FONDATEUR UNIQUEMENT : autorise l'ajout de dettes")
    args = parser.parse_args(argv)

    debut = time.monotonic()
    duplicats, stats = analyse()
    duree = time.monotonic() - debut

    vus = duplicats
    if args.perimetre:
        motif = PERIMETRES[args.perimetre]
        vus = [d for d in duplicats if any(motif.search(f) for f in d.fichiers)]

    if args.stats:
        print(f"Fichiers analyses           : {stats['fichiers']}")
        print(f"Lignes significatives       : {stats['lignes']}")
        print(f"Blocs dupliques (>= {SEUIL} l.)  : {stats['blocs']}")
        print(f"Lignes dupliquees           : {stats['lignes_dupliquees']} "
              f"({stats['pourcent']:.2f} % du code)")
        if args.perimetre:
            print(f"Blocs touchant « {args.perimetre} » : {len(vus)}")
        print(f"Duree                       : {duree:.1f} s")

    if args.liste or (args.perimetre and args.stats):
        for duplicat in vus:
            _imprime(duplicat)

    cles = {d.cle for d in duplicats}
    base = charger_base()

    if args.write_baseline:
        ajouts = cles - base
        amorce = not BASELINE_PATH.is_file()
        if ajouts and not (args.autoriser_croissance or amorce):
            print("REFUS : --write-baseline ne peut que RETRECIR la base.")
            print(f"{len(ajouts)} nouveau(x) bloc(s) voudrai(en)t y entrer.")
            return 1
        ecrire_base(cles)
        print(f"Base reecrite : {len(cles)} entree(s), "
              f"{len(base - cles)} retiree(s).")
        return 0

    nouveaux = [d for d in duplicats if d.cle not in base]
    if nouveaux:
        print(f"\nECHEC : {len(nouveaux)} bloc(s) de code COPIE (>= {SEUIL} "
              f"lignes identiques dans deux fichiers) hors base de dette :\n")
        for duplicat in nouveaux:
            _imprime(duplicat)
        print("\nA FAIRE : importez le code partage au lieu de le recopier "
              "(ou extrayez-le dans un module commun). La base "
              "scripts/duplicats_litteraux_allow.txt ne peut que retrecir.")
        return 1

    disparus = base - cles
    print(f"OK : {len(duplicats)} bloc(s) duplique(s), tous dans la base de "
          f"dette ({len(base)} entree(s), dont {len(disparus)} disparue(s)) "
          f"— {duree:.1f} s.")
    if disparus:
        print("Ces dettes resorbees peuvent quitter la base : "
              "python scripts/check_duplicats_litteraux.py --write-baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

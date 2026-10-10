"""Socle des regles C20 : diff entre deux commits, lignes LOGIQUES, taches cochees.

Ligne logique (Python) = un jeton `tokenize.NEWLINE` : une instruction sur
plusieurs lignes compte 1, un commentaire ou une ligne vide 0. JS/TS : ligne non
vide hors commentaire. Aucune baseline n'est lue : tout vient de `git`.
"""
from __future__ import annotations

import ast
import bisect
import copy
import io
import re
import subprocess
import sys
import tokenize
from collections import namedtuple
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import audit_tache  # noqa: E402  (empreinte AST du corps : empreinte_corps)

DJANGO = "backend/django_core/"
SUFFIXES_CODE = (".py", ".js", ".jsx", ".mjs", ".ts", ".tsx")
SUFFIXES_LUS = SUFFIXES_CODE + (".md", ".txt", ".yml", ".yaml", ".example")
COCHE = re.compile(r"^- \[[xX]\] (\S+)(.*)$", re.M)
BUDGET = re.compile(r"lignes nettes attendues\s*≤\s*([-−]?)\s*(\d[\d  ]*)")
BACKTICKS = re.compile(r"`([^`\n]+)`")


class Echec(Exception):
    """La garde ne peut pas juger : elle echoue (jamais un vert muet)."""


@dataclass(frozen=True)
class Constat:
    regle: str
    fichier: str
    symbole: str
    message: str

    def cible(self) -> str:
        return f"{self.fichier}::{self.symbole}" if self.symbole else self.fichier


@dataclass(frozen=True)
class Changement:
    statut: str
    avant: str | None
    apres: str | None


Defn = namedtuple("Defn", "qualname kind debut fin noeud")
BLOCS = ("body", "orelse", "finalbody", "handlers", "cases")


def definitions(arbre) -> list:
    """`qualname` d'`audit_tache.definitions` ; blocs d'instructions seulement, empreinte a la demande."""
    trouvees, pile = [], [(arbre, "")]
    while pile:
        noeud, prefixe = pile.pop()
        for champ in BLOCS:
            for enfant in getattr(noeud, champ, None) or ():
                if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    kind = "classe" if isinstance(enfant, ast.ClassDef) else "fonction"
                    trouvees.append(Defn(prefixe + enfant.name, kind, enfant.lineno, enfant.end_lineno, enfant))
                    pile.append((enfant, prefixe + enfant.name + "."))
                else:
                    pile.append((enfant, prefixe))
    return trouvees


class Fichier:
    """Texte + lignes logiques + (Python) definitions AST d'un cote du diff."""

    def __init__(self, chemin: str, texte: str):
        self.chemin, self.texte, self.brutes = chemin, texte, len(texte.splitlines())
        self.arbre, self.defs = None, []
        if chemin.endswith(".py"):
            try:
                self.arbre = ast.parse(texte)
                self.defs = definitions(self.arbre)
            except (SyntaxError, ValueError):
                pass

    @cached_property
    def lignes(self) -> list:
        return lignes_logiques(self.texte, self.chemin)

    def compter(self, debut: int, fin: int) -> int:
        return bisect.bisect_right(self.lignes, fin) - bisect.bisect_left(self.lignes, debut)

    def empreinte(self, d) -> str:
        """`audit_tache.empreinte_corps` SANS les imports : un deplacement re-cible ses imports locaux."""
        copie = copy.deepcopy(d.noeud)
        for n in ast.walk(copie):
            for champ in BLOCS:
                bloc = getattr(n, champ, None)
                if isinstance(bloc, list) and any(isinstance(s, (ast.Import, ast.ImportFrom)) for s in bloc):
                    setattr(n, champ, [s for s in bloc if not isinstance(s, (ast.Import, ast.ImportFrom))]
                            or [ast.Pass()])
        return audit_tache.empreinte_corps(copie)


def lignes_logiques(texte: str, chemin: str) -> list:
    """Numeros (tries) des lignes ou finit une ligne logique."""
    if chemin.endswith(".py"):
        try:
            jetons = tokenize.generate_tokens(io.StringIO(texte).readline)
            return [j.start[0] for j in jetons if j.type == tokenize.NEWLINE]
        except (tokenize.TokenError, SyntaxError):
            pass
    return [i for i, ligne in enumerate(texte.splitlines(), 1)
            if ligne.strip() and not ligne.strip().startswith(("#", "//", "/*", "*"))]


def est_code(chemin: str | None) -> bool:
    """Code maintenu : hors migrations generees, node_modules et `docs/` (sondes = pieces de dossier)."""
    return bool(chemin) and chemin.endswith(SUFFIXES_CODE) and "/migrations/" not in chemin \
        and "node_modules/" not in chemin and not chemin.startswith("docs/")


def git(racine, *args, entree: bytes | None = None) -> bytes:
    proc = subprocess.run(["git", *args], cwd=str(racine), input=entree, capture_output=True)
    if proc.returncode != 0:
        raise Echec(f"git {' '.join(args[:3])} : {proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout


def lire_blobs(racine, specs: list) -> dict:
    """{`sha:chemin`: texte ou None} en UN processus `git cat-file --batch`."""
    if not specs:
        return {}
    sortie = git(racine, "cat-file", "--batch", entree="".join(s + "\n" for s in specs).encode("utf-8"))
    resultat, pos = {}, 0
    for spec in specs:
        fin = sortie.index(b"\n", pos)
        entete, pos = sortie[pos:fin].split(), fin + 1
        if len(entete) != 3 or not entete[2].isdigit():
            resultat[spec] = None
            continue
        taille = int(entete[2])
        blob = sortie[pos:pos + taille]
        resultat[spec] = blob.decode("utf-8", "replace") if entete[1] == b"blob" else None
        pos += taille + 1
    return resultat


def changements(racine, base: str, tete: str) -> list:
    brut = git(racine, "diff", "--name-status", "-z", "-M", base, tete).decode("utf-8", "replace")
    jetons, sortie, i = brut.split("\0"), [], 0
    while i < len(jetons) - 1:
        statut = jetons[i]
        if statut[:1] in "RC":
            sortie.append(Changement(statut, jetons[i + 1] if statut[0] == "R" else None, jetons[i + 2]))
            i += 3
            continue
        chemin = jetons[i + 1]
        sortie.append(Changement(statut, None if statut == "A" else chemin, None if statut == "D" else chemin))
        i += 2
    return sortie


def alias(chemin: str) -> set:
    """Un chemin s'ecrit en entier ou relatif a django_core (`apps/...`) — jamais nu."""
    return {chemin, chemin[len(DJANGO):]} if chemin.startswith(DJANGO) else {chemin}


def cite(texte: str, chemin: str) -> bool:
    """La ligne cite-t-elle `chemin` EXACT entre backticks (`fichier` ou `fichier::symbole`) ?"""
    noms = alias(chemin)
    return any(jeton.split("::")[0].strip() in noms for jeton in BACKTICKS.findall(texte))


def budget(texte: str) -> int | None:
    """Premier `lignes nettes attendues ≤ N` de la ligne (signe − compris)."""
    m = BUDGET.search(texte)
    if not m:
        return None
    valeur = int(re.sub(r"\D", "", m.group(2)))
    return -valeur if m.group(1) else valeur


class Contexte:
    """Le diff `base..tete` d'un depot, lu en une passe ; memo des analyses."""

    def __init__(self, racine, base: str, tete: str):
        self.racine, self.base, self.tete = Path(racine), base, tete
        self.changements = changements(racine, base, tete)
        specs = [f"{sha}:{ch}" for c in self.changements for sha, ch in ((base, c.avant), (tete, c.apres))
                 if ch and ch.endswith(SUFFIXES_LUS)]
        self._blobs = lire_blobs(racine, specs)
        self._fichiers, self.memo = {}, {}
        self.taches = taches_cochees(self)
        self.deplaces = None

    def texte(self, cote: str, chemin: str | None, lire: bool = False) -> str | None:
        if not chemin:
            return None
        spec = f"{self.base if cote == 'base' else self.tete}:{chemin}"
        if spec not in self._blobs and lire:
            self._blobs.update(lire_blobs(self.racine, [spec]))
        return self._blobs.get(spec)

    def fichier(self, cote: str, chemin: str | None) -> Fichier | None:
        cle = (cote, chemin)
        if cle not in self._fichiers:
            texte = self.texte(cote, chemin)
            self._fichiers[cle] = None if texte is None else Fichier(chemin, texte)
        return self._fichiers[cle]

    def paires_py(self):
        """(changement, base, tete) des fichiers Python de code modifies ou ajoutes."""
        for c in self.changements:
            if c.apres and c.apres.endswith(".py") and est_code(c.apres):
                tete = self.fichier("tete", c.apres)
                if tete is not None and tete.arbre is not None:
                    yield c, self.fichier("base", c.avant), tete

    def arbre_tete(self) -> set:
        if "arbre" not in self.memo:
            noms = git(self.racine, "ls-tree", "-r", "--name-only", self.tete).decode("utf-8", "replace")
            self.memo["arbre"] = set(noms.splitlines())
        return self.memo["arbre"]


def taches_cochees(ctx: Contexte) -> list:
    """[(id, ligne)] des taches que la PR coche (`[ ]`→`[x]`) ou ajoute deja cochees, sous docs/."""
    avant, apres = set(), {}
    for c in ctx.changements:
        for cote, chemin in (("base", c.avant), ("tete", c.apres)):
            if not (chemin and chemin.startswith("docs/") and chemin.endswith(".md")):
                continue
            for m in COCHE.finditer(ctx.texte(cote, chemin) or ""):
                if cote == "base":
                    avant.add(m.group(1))
                else:
                    apres.setdefault(m.group(1), m.group(0))
    return [(ident, ligne) for ident, ligne in apres.items() if ident not in avant]

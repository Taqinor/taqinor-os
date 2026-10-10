"""Regle SPL — un deplacement n'est pas une croissance (preuve par le CONTENU).

Empreinte AST du corps (`audit_tache.empreinte_corps`) qui QUITTE un `fichier::symbole` et APPARAIT
ailleurs = deplacement : FONCTION_NEUVE ne la juge pas, FICHIER_MUR retire ses lignes de la
destination, FACADE admet son re-export dans le fichier quitte. Corps < 5 lignes logiques : pas une preuve.
"""
from __future__ import annotations

from dataclasses import dataclass, field

MIN_LIGNES = 5


@dataclass
class Deplacements:
    entres: set = field(default_factory=set)
    sortis: set = field(default_factory=set)
    lignes_entrees: dict = field(default_factory=dict)


def _empreintes(ctx, cote: str) -> dict:
    """{empreinte: {(fichier, qualname): lignes}} ; la base est rangee sous le NOUVEAU nom (renommage)."""
    sortie = {}
    for c in ctx.changements:
        chemin = c.avant if cote == "base" else c.apres
        if not (chemin and chemin.endswith(".py")):
            continue
        fichier = ctx.fichier(cote, chemin)
        for d in (fichier.defs if fichier else []):
            n = fichier.compter(d.debut, d.fin)
            if n >= MIN_LIGNES:
                sortie.setdefault(d.empreinte, {})[(c.apres or c.avant, d.qualname)] = n
    return sortie


def verifier(ctx) -> Deplacements:
    base, tete = _empreintes(ctx, "base"), _empreintes(ctx, "tete")
    resultat = Deplacements()
    arrivees = {}
    for empreinte, places in tete.items():
        partis = set(base.get(empreinte, {})) - set(places)
        venus = {cle: n for cle, n in places.items() if cle not in base.get(empreinte, {})}
        if partis and venus:
            resultat.sortis |= partis
            arrivees.update(venus)
    resultat.entres = set(arrivees)
    for (fichier, qual), n in arrivees.items():
        parents = {".".join(qual.split(".")[:i]) for i in range(1, qual.count(".") + 1)}
        if not any((fichier, p) in resultat.entres for p in parents):
            resultat.lignes_entrees[fichier] = resultat.lignes_entrees.get(fichier, 0) + n
    return resultat

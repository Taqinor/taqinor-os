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


def _symboles(ctx, cote: str) -> dict:
    """{(fichier, qualname): (Fichier, Defn)} ; la base est rangee sous le NOUVEAU nom (renommage)."""
    sortie = {}
    for c in ctx.changements:
        chemin = c.avant if cote == "base" else c.apres
        fichier = ctx.fichier(cote, chemin) if chemin and chemin.endswith(".py") else None
        for d in (fichier.defs if fichier else []):
            sortie[(c.apres or c.avant, d.qualname)] = (fichier, d)
    return sortie


def _empreintes(symboles: dict, cles: set) -> dict:
    """{empreinte: {cle: lignes logiques}} des seuls symboles partis ou arrives (hachage a la demande)."""
    sortie = {}
    for cle in cles:
        fichier, d = symboles[cle]
        n = fichier.compter(d.debut, d.fin)
        if n >= MIN_LIGNES:
            sortie.setdefault(fichier.empreinte(d), {})[cle] = n
    return sortie


def verifier(ctx) -> Deplacements:
    base, tete = _symboles(ctx, "base"), _symboles(ctx, "tete")
    partis = _empreintes(base, set(base) - set(tete))
    venus = _empreintes(tete, set(tete) - set(base))
    resultat, arrivees = Deplacements(), {}
    for empreinte, places in venus.items():
        if empreinte in partis:
            resultat.sortis |= set(partis[empreinte])
            arrivees.update(places)
    resultat.entres = set(arrivees)
    for (fichier, qual), n in arrivees.items():
        parents = {".".join(qual.split(".")[:i]) for i in range(1, qual.count(".") + 1)}
        if not any((fichier, p) in resultat.entres for p in parents):
            resultat.lignes_entrees[fichier] = resultat.lignes_entrees.get(fichier, 0) + n
    return resultat

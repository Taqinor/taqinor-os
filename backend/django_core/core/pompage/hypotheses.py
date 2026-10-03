"""AGR110 — LA table unique des hypothèses de pompage, chacune avec sa source.

Avant : le rendement groupe valait 0,5 « EST. » à l'écran (``solar.js``) mais
0,55/0,50 sur le site (``estimatorAgricole.ts``) ; le bassin 2× au serveur mais
1× sur le site — un même projet pouvait afficher deux puissances de pompe et
deux bassins (C2-18). Ici, UNE table : chaque entrée porte sa valeur, son
statut et sa source, et c'est la SEULE origine des constantes du moteur
``core.pompage``, de la réponse d'aperçu (``hypotheses`` du contrat
``etude_pompage_preview.json``) et de l'estimateur du site (AGW409, via
l'échantillon ``apps/ventes/contract_samples/hypotheses_pompage.json``, tenu
ÉGAL à :func:`export` par ``core/tests/test_agr110_hypotheses_pompage.py``).

Statuts : ``physique`` (constante physique) | ``source`` (source primaire
citée) | ``source_secondaire`` (citée de seconde main) | ``EST.`` (estimation
explicite, plage citée).
Usages : ``calcul`` | ``controle_conception`` | ``alerte`` | ``indication`` —
une entrée ``indication`` n'est JAMAIS la valeur par défaut d'un réglage.

NE PAS FAIRE (Groupe AGR) : AUCUN multiplicateur de bassin, AUCUN derate empilé
sur PVGIS (ses 14 % de pertes sont déjà compris), AUCUN seuil non sourcé.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union

#: Version de l'export (champ ``version`` de ``hypotheses_pompage.json``).
VERSION_HYPOTHESES = 1

STATUTS = frozenset({"physique", "source", "source_secondaire", "EST."})
USAGES = frozenset({"calcul", "controle_conception", "alerte", "indication"})


@dataclass(frozen=True)
class Plage:
    """Une plage {min, max} (bornes incluses)."""

    min: float
    max: float

    def en_dict(self):
        return {"min": self.min, "max": self.max}


@dataclass(frozen=True)
class Hypothese:
    cle: str
    valeur: Union[float, int, Plage]
    statut: str
    source: str
    usage: str

    def en_dict(self):
        valeur = (self.valeur.en_dict() if isinstance(self.valeur, Plage)
                  else self.valeur)
        return {"cle": self.cle, "valeur": valeur, "statut": self.statut,
                "source": self.source, "usage": self.usage}


TABLE = (
    Hypothese(
        cle="energie_hydraulique_wh_par_m3_m",
        valeur=2.725,
        statut="physique",
        source="ρ·g/3600 (ρ = 1000 kg/m³, g = 9,81 m/s²)",
        usage="calcul",
    ),
    Hypothese(
        cle="cv_vers_kw",
        valeur=0.7355,
        statut="physique",
        source="1 CV (cheval-vapeur métrique) = 735,5 W",
        usage="calcul",
    ),
    Hypothese(
        cle="rendement_groupe",
        valeur=0.35,
        statut="EST.",
        source="borne basse de la plage AMEE 0,35-0,55, Guide PSIA, PDF du 14/01/2019 (décision fondateur 03/10/2026 : seule valeur qui tient AMEE et SPIS à ± 20 %)",
        usage="calcul",
    ),
    Hypothese(
        cle="ratio_champ_pompe_bande_alerte",
        valeur=Plage(1.2, 1.5),
        statut="source",
        source=("docs/superpowers/specs/"
                "2026-06-24-agricole-quote-redesign-design.md:58"),
        usage="alerte",
    ),
    Hypothese(
        cle="hazen_williams_c_pvc_pehd",
        valeur=150,
        statut="source",
        source="bulletin IPEX mis en ligne 08/2022 ; AWWA M23",
        usage="calcul",
    ),
    Hypothese(
        cle="pertes_pvgis_comprises_pct",
        valeur=14,
        statut="source",
        source=("backend/django_core/apps/parametres/pvgis_profils.py:128 "
                "(PVGIS_LOSS_PCT) — déjà comprises : AUCUN derate "
                "supplémentaire (les 0,82-0,90 de Water Mission sont "
                "refusés : double comptage)"),
        usage="calcul",
    ),
    Hypothese(
        cle="tolerance_conception_pct",
        valeur=Plage(-5, 20),
        statut="source_secondaire",
        source=("Water Mission 2019 citant IEC 62253:2011 (texte de la norme "
                "non lu) — contrôle de conception et affichage seulement, "
                "JAMAIS un seuil de recette (AGR606 : réglage société sans "
                "défaut)"),
        usage="controle_conception",
    ),
    Hypothese(
        cle="part_debit_essai_pct",
        valeur=Plage(80, 90),
        statut="source",
        source=("Water Mission 2021 — indication à côté du réglage société "
                "AGR107, jamais un défaut"),
        usage="indication",
    ),
    Hypothese(
        cle="pression_goutte_a_goutte_bar",
        valeur=Plage(1.5, 3),
        statut="source",
        source="AMEE — indication à côté de la saisie, jamais un défaut",
        usage="indication",
    ),
)


def hypothese(cle):
    """L'entrée ``cle`` de la table (``KeyError`` si elle n'existe pas)."""
    for entree in TABLE:
        if entree.cle == cle:
            return entree
    raise KeyError(cle)


def valeur(cle):
    """La valeur brute d'une hypothèse (une :class:`Plage` pour une plage)."""
    return hypothese(cle).valeur


def table():
    """La table entière, en dicts NEUFS (l'appelant peut les muter)."""
    return [entree.en_dict() for entree in TABLE]


def utilisees(cles):
    """Les entrées effectivement utilisées par un calcul, dans l'ordre de la
    table, recopiées telles quelles (``hypotheses`` de la réponse d'aperçu)."""
    voulues = set(cles)
    return [entree.en_dict() for entree in TABLE if entree.cle in voulues]


def export():
    """L'export complet — ÉGAL à ``exemple`` de ``hypotheses_pompage.json``."""
    return {"version": VERSION_HYPOTHESES, "hypotheses": table()}

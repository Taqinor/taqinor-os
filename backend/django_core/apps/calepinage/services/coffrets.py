# -*- coding: utf-8 -*-
"""CALX230 — dimensionner un coffret DC par son nombre d'ENTRÉES réelles.

LE CONSTAT
----------
``core/electrique/nomenclature.py`` posait un ou deux coffrets DC par une
règle de comptage écrite en dur (``1 if nb_chaines <= 2 else 2``, sans
source), et aucune entité « coffret » n'existait ailleurs : ni nombre
d'entrées, ni nombre de sorties, ni rattachement à un emplacement.

CE QUE CE MODULE FAIT
----------------------
``coffrets_dc`` — un coffret DC par équipement ``type: "coffret_dc"`` posé
dans ``electrical.equipements[]`` (contrat CALX201), chacun avec une
capacité d'entrées SAISIE (sur l'équipement lui-même, clé
``capaciteEntrees`` — le schéma est ``additionalProperties: true`` — ou
résolue par la fiche produit ``produitId`` via le paramètre
``capacites``) ; les chaînes lui sont réparties dans l'ordre du plan, une
répartition qui dépasse la capacité totale est REFUSÉE en nommant le
nombre de chaînes en trop ; les fusibles de chaîne suivent la règle
EXISTANTE (``core.electrique.protections`` — IEC 62548 §7.3.3, exigés dès
trois chaînes en parallèle), aucun seuil neuf.

AUCUN CHIFFRE INVENTÉ, AUCUN SEUIL NEUF (D-CALX 7, règles du lot 4)
---------------------------------------------------------------------
Ce module ne pose ni calibre, ni capacité, ni ratio : une capacité
manquante REFUSE la répartition en nommant le coffret. Le seul seuil
utilisé (``SEUIL_CHAINES_PARALLELES_FUSIBLE``) est IMPORTÉ du noyau,
jamais recopié.

CROCHET ATTENDU (phase 2, hors fichiers de cette lane)
--------------------------------------------------------
``coffrets_dc`` n'a pas encore d'appelant en production : c'est
``apps/calepinage/services/electrique.py`` (CALX246/228, lane E2) qui doit
résoudre ``electrical.equipements[]`` depuis le document, résoudre les
capacités par ``produitId`` (fiche ``stock.Produit``), l'appeler et
transmettre son résultat à ``core.electrique.nomenclature.nomenclature``
(paramètre ``resultat_coffrets_dc``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from core.electrique.protections import SEUIL_CHAINES_PARALLELES_FUSIBLE

__all__ = [
    "TYPE_COFFRET_DC", "CoffretDc", "ResultatCoffretsDc", "coffrets_dc",
]

#: L'énumération FERMÉE du contrat CALX201 ne connaît que ce type pour un
#: coffret DC — le seul filtré ici.
TYPE_COFFRET_DC = "coffret_dc"


@dataclass(frozen=True)
class CoffretDc:
    """Un coffret DC RÉELLEMENT posé — ses entrées, ses fusibles."""

    id: str
    label: str
    capacite_entrees: Optional[int]
    #: Repères des chaînes qui lui sont effectivement raccordées.
    chaines: Tuple[str, ...] = ()
    fusibles_requis: bool = False
    nb_fusibles: int = 0


@dataclass(frozen=True)
class ResultatCoffretsDc:
    coffrets: Tuple[CoffretDc, ...] = ()
    #: Répartitions refusées (capacité dépassée ou non publiée) — le
    #: coffret ou la chaîne fautive est NOMMÉ, jamais un refus muet.
    refus: Tuple[str, ...] = ()
    #: Omissions qui ne sont pas des refus (aucun coffret posé du tout).
    omissions: Tuple[str, ...] = ()


def _entrees_coffret_dc(equipements):
    """Les équipements ``type: "coffret_dc"`` du plan, dans leur ORDRE."""
    return [eq for eq in (equipements or ())
            if isinstance(eq, dict) and eq.get("type") == TYPE_COFFRET_DC]


def _capacite_entiere(eq, capacites):
    """La capacité d'entrées d'un coffret — ``None`` si non publiée.

    Priorité à ``capacites`` (résolue par l'appelant sur la fiche produit
    ``produitId``, CALX60) ; à défaut, la clé ``capaciteEntrees`` SAISIE
    directement sur l'équipement (le schéma CALX201 est
    ``additionalProperties: true``, cette clé lui est donc admise).
    """
    brute = None
    if capacites:
        brute = capacites.get(eq.get("id"))
    if brute is None:
        brute = eq.get("capaciteEntrees")
    if brute is None:
        return None
    try:
        return int(brute)
    except (TypeError, ValueError):
        return None


def _repere_chaine(chaine):
    if isinstance(chaine, dict):
        return chaine.get("repere")
    return getattr(chaine, "repere", None)


def coffrets_dc(chaines, equipements, *, capacites=None):
    """CALX230 — un coffret DC par organe RÉELLEMENT posé.

    Args:
        chaines: les chaînes calculées (``core.electrique.types.Chaine`` ou
            équivalent — accès ``.repere``, ou un dict à la même clé) qu'il
            faut raccorder.
        equipements: ``electrical.equipements[]`` du document (contrat
            CALX201) — seuls les ``type: "coffret_dc"`` sont retenus, dans
            l'ordre où ils apparaissent.
        capacites: ``{id équipement: capacité d'entrées}`` — résolue par
            l'appelant sur la fiche ``produitId`` (CALX60). À défaut, la
            clé ``capaciteEntrees`` saisie sur l'équipement fait foi.

    Returns:
        ``ResultatCoffretsDc``. Aucun coffret posé et des chaînes à
        raccorder ⇒ ``coffrets`` vide, le motif dans ``omissions`` — la
        LIGNE de nomenclature est alors omise, jamais devinée.
    """
    chaines = tuple(chaines or ())
    postes = _entrees_coffret_dc(equipements)
    if not postes:
        if chaines:
            return ResultatCoffretsDc(omissions=(
                "coffret(s) de chaînes DC omis du bordereau : aucun coffret "
                "DC n'est posé dans le plan (electrical.equipements[] type "
                "« coffret_dc ») — le nombre de coffrets n'est plus deviné "
                "à partir du nombre de chaînes",))
        return ResultatCoffretsDc()

    refus = []
    restantes = list(chaines)
    coffrets = []
    for eq in postes:
        identifiant = eq.get("id")
        label = eq.get("label") or identifiant
        capacite = _capacite_entiere(eq, capacites)
        if capacite is None:
            refus.append(
                "coffret DC « %s » : capacité d'entrées non publiée — "
                "renseignez sa fiche produit (produitId) ou sa capacité "
                "d'entrées ; aucune chaîne ne lui est affectée" % label)
            capacite_effective = 0
        else:
            capacite_effective = max(capacite, 0)
        assignees = []
        while restantes and len(assignees) < capacite_effective:
            assignees.append(restantes.pop(0))
        chaines_reperes = tuple(_repere_chaine(c) or "?" for c in assignees)
        fusibles_requis = len(assignees) >= SEUIL_CHAINES_PARALLELES_FUSIBLE
        coffrets.append(CoffretDc(
            id=identifiant, label=label, capacite_entrees=capacite,
            chaines=chaines_reperes, fusibles_requis=fusibles_requis,
            nb_fusibles=(2 * len(assignees)) if fusibles_requis else 0,
        ))

    if restantes:
        capacite_totale = sum((c.capacite_entrees or 0) for c in coffrets)
        refus.append(
            "%d chaîne(s) sans coffret DC : la capacité cumulée des "
            "coffrets posés (%d entrée(s)) est dépassée — posez un coffret "
            "supplémentaire ou augmentez sa capacité"
            % (len(restantes), capacite_totale))

    return ResultatCoffretsDc(coffrets=tuple(coffrets), refus=tuple(refus))

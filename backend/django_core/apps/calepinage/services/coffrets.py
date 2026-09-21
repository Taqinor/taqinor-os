# -*- coding: utf-8 -*-
"""CALX230/231/232 — dimensionner les coffrets DC par leurs ENTRÉES réelles,
deux niveaux de regroupement quand plusieurs coffrets remontent, et le
coffret AC par ses DÉPARTS réels.

LE CONSTAT
----------
``core/electrique/nomenclature.py`` posait un ou deux coffrets DC par une
règle de comptage écrite en dur (``1 if nb_chaines <= 2 else 2``, sans
source), et aucune entité « coffret » n'existait ailleurs : ni nombre
d'entrées, ni nombre de sorties, ni rattachement à un emplacement. La
chaîne canonique du schéma unifilaire ne connaît par ailleurs qu'UN coffret
DC (``core/electrique/schema.py:8-13``) : une architecture à deux niveaux
(coffrets de toiture → coffret de regroupement) n'était pas représentable.

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
trois chaînes en parallèle), aucun seuil neuf. CALX231 — chaque
``coffret_dc`` peut désigner un ``coffret_dc`` parent (clé ``parentId``,
même discipline ``additionalProperties``) : le courant d'entrée du parent
CUMULE celui de ses enfants, deux niveaux de regroupement sont admis, et
une boucle de parenté ou une profondeur supérieure à deux est REFUSÉE en
nommant le coffret fautif. CALX232 — ``coffret_ac`` publie ``{departs,
organes, calibre_tete_a, regle_source}`` : un départ par branche AC de
micro-onduleurs (CALX210) ou un départ unique en régime chaîne ; ``organes``
compte les organes de protection AC réellement retenus
(``core.electrique.types.COTE_AC``) ; la règle d'enveloppe citée
(NF C 15-100 §512.2) est celle qu'``core/electrique/protections.py`` cite
déjà pour ARM1 — jamais une nouvelle.

AUCUN CHIFFRE INVENTÉ, AUCUN SEUIL NEUF (D-CALX 7, règles du lot 4)
---------------------------------------------------------------------
Ce module ne pose ni calibre, ni capacité, ni ratio : une capacité
manquante REFUSE la répartition en nommant le coffret, un calibre non lu
est OMIS en le disant. Le seul seuil utilisé
(``SEUIL_CHAINES_PARALLELES_FUSIBLE``) est IMPORTÉ du noyau, jamais
recopié.

CROCHET ATTENDU (phase 2, hors fichiers de cette lane)
--------------------------------------------------------
Ni ``coffrets_dc`` ni ``coffret_ac`` n'ont encore d'appelant en production :
c'est ``apps/calepinage/services/electrique.py`` (CALX246/228, lane E2) qui
doit résoudre ``electrical.equipements[]`` depuis le document, résoudre les
capacités par ``produitId`` (fiche ``stock.Produit``), appeler ces deux
fonctions et transmettre leurs résultats à
``core.electrique.nomenclature.nomenclature`` (paramètres
``resultat_coffrets_dc`` / ``resultat_coffret_ac``) ; le tronçon qui relie
un coffret enfant à son parent est dimensionné par CALX225
(``services/troncons.py``, lane T, hors fichiers de cette lane) à partir de
l'Isc cumulé publié ici.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from core.electrique.protections import SEUIL_CHAINES_PARALLELES_FUSIBLE
from core.electrique.types import COTE_AC

__all__ = [
    "TYPE_COFFRET_DC", "REGLE_ENVELOPPE_AC",
    "CoffretDc", "ResultatCoffretsDc", "CoffretAc",
    "coffrets_dc", "coffret_ac",
]

#: L'énumération FERMÉE du contrat CALX201 ne connaît que ce type pour un
#: coffret DC — le seul filtré ici.
TYPE_COFFRET_DC = "coffret_dc"

#: CALX232 — la règle d'enveloppe AC. LA MÊME que celle qu'
#: ``core/electrique/protections.py`` cite déjà pour l'organe ARM1
#: (NF C 15-100 §512.2, dimensionnement par le nombre d'organes hébergés) —
#: le coffret AC la republie, sans en écrire une nouvelle.
REGLE_ENVELOPPE_AC = (
    "NF C 15-100 §512.2 — l'enveloppe d'un coffret de protection se "
    "dimensionne par le nombre d'organes qu'elle héberge")


@dataclass(frozen=True)
class CoffretDc:
    """Un coffret DC RÉELLEMENT posé — ses entrées, sa parenté, ses fusibles."""

    id: str
    label: str
    capacite_entrees: Optional[int]
    #: Repères des chaînes qui lui sont effectivement raccordées.
    chaines: Tuple[str, ...] = ()
    #: CALX231 — le ``coffret_dc`` parent désigné (``parentId``), ou
    #: ``None`` pour un coffret racine.
    parent_id: Optional[str] = None
    #: 0 = coffret racine ; 1 = un niveau de regroupement ; 2 = deux
    #: niveaux (le maximum admis).
    profondeur: int = 0
    #: Isc de SES propres chaînes seulement (A).
    isc_propre_a: float = 0.0
    #: Isc cumulé — le sien + celui de tous ses descendants (A). Égal à
    #: ``isc_propre_a`` pour un coffret sans enfant.
    isc_cumule_a: float = 0.0
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


@dataclass(frozen=True)
class CoffretAc:
    """CALX232 — le coffret AC, dimensionné par ses départs réels."""

    departs: int = 0
    organes: int = 0
    calibre_tete_a: Optional[float] = None
    regle_source: str = REGLE_ENVELOPPE_AC
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


def _isc_chaine(chaine, isc_par_chaine):
    """L'Isc d'UNE chaîne — la correspondance saisie prime, sinon son champ."""
    repere = _repere_chaine(chaine)
    if isc_par_chaine and repere in isc_par_chaine:
        try:
            return float(isc_par_chaine[repere])
        except (TypeError, ValueError):
            return 0.0
    valeur = (chaine.get("isc_a") if isinstance(chaine, dict)
              else getattr(chaine, "isc_a", None))
    try:
        return float(valeur) if valeur is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _topologie(postes):
    """CALX231 — ``(profondeurs, exclus, refus)`` : parenté validée.

    ``profondeurs`` — ``{id: profondeur}`` pour les coffrets dont la
    parenté est SAINE (0, 1 ou 2 niveaux). ``exclus`` — les ``id`` refusés
    (boucle, parent inconnu, profondeur > 2) : ils ne reçoivent AUCUNE
    chaîne, la répartition les ignore.
    """
    ids_connus = {eq.get("id") for eq in postes}
    parent_de = {eq.get("id"): eq.get("parentId") for eq in postes
                 if eq.get("parentId")}
    profondeurs = {}
    exclus = set()
    refus = []
    for identifiant in sorted(ids_connus):
        chemin = []
        courant = identifiant
        en_boucle = False
        parent_invalide = None
        while courant is not None:
            if courant in chemin:
                en_boucle = True
                break
            chemin.append(courant)
            parent = parent_de.get(courant)
            if parent is not None and parent not in ids_connus:
                parent_invalide = parent
                break
            courant = parent
        if en_boucle:
            exclus.add(identifiant)
            refus.append(
                "coffret DC « %s » : boucle de parenté détectée (%s) — un "
                "coffret ne peut pas remonter, directement ou indirectement, "
                "vers lui-même" % (identifiant, " -> ".join(chemin + [courant])))
            continue
        if parent_invalide is not None:
            exclus.add(identifiant)
            refus.append(
                "coffret DC « %s » : le coffret parent « %s » qu'il désigne "
                "n'est posé nulle part dans le plan"
                % (identifiant, parent_invalide))
            continue
        profondeur = len(chemin) - 1
        if profondeur > 2:
            exclus.add(identifiant)
            refus.append(
                "coffret DC « %s » : profondeur de regroupement de %d "
                "niveaux (de la chaîne jusqu'à son ancêtre le plus haut), "
                "au-delà du maximum de deux niveaux admis"
                % (identifiant, profondeur))
            continue
        profondeurs[identifiant] = profondeur
    return profondeurs, exclus, refus


def coffrets_dc(chaines, equipements, *, capacites=None, isc_par_chaine=None):
    """CALX230/231 — un coffret DC par organe RÉELLEMENT posé.

    Args:
        chaines: les chaînes calculées (``core.electrique.types.Chaine`` ou
            équivalent — accès ``.repere``/``.isc_a``, ou un dict aux mêmes
            clés) qu'il faut raccorder.
        equipements: ``electrical.equipements[]`` du document (contrat
            CALX201) — seuls les ``type: "coffret_dc"`` sont retenus, dans
            l'ordre où ils apparaissent. Chacun peut désigner un
            ``parentId`` (CALX231, deux niveaux de regroupement admis).
        capacites: ``{id équipement: capacité d'entrées}`` — résolue par
            l'appelant sur la fiche ``produitId`` (CALX60). À défaut, la
            clé ``capaciteEntrees`` saisie sur l'équipement fait foi.
        isc_par_chaine: ``{repère chaîne: Isc en A}`` — à défaut, l'Isc
            porté par la chaîne elle-même (champ ``isc_a``).

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

    profondeurs, exclus, refus = _topologie(postes)
    postes_valides = [eq for eq in postes if eq.get("id") not in exclus]

    restantes = list(chaines)
    coffrets = []
    for eq in postes_valides:
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
        isc_propre = sum(_isc_chaine(c, isc_par_chaine) for c in assignees)
        fusibles_requis = len(assignees) >= SEUIL_CHAINES_PARALLELES_FUSIBLE
        coffrets.append(CoffretDc(
            id=identifiant, label=label, capacite_entrees=capacite,
            chaines=chaines_reperes, parent_id=eq.get("parentId"),
            profondeur=profondeurs.get(identifiant, 0),
            isc_propre_a=isc_propre, isc_cumule_a=isc_propre,
            fusibles_requis=fusibles_requis,
            nb_fusibles=(2 * len(assignees)) if fusibles_requis else 0,
        ))

    if restantes:
        capacite_totale = sum((c.capacite_entrees or 0) for c in coffrets)
        refus.append(
            "%d chaîne(s) sans coffret DC : la capacité cumulée des "
            "coffrets posés (%d entrée(s)) est dépassée — posez un coffret "
            "supplémentaire ou augmentez sa capacité"
            % (len(restantes), capacite_totale))

    # ── Isc cumulé du parent = somme de ses enfants (CALX231) ───────────────
    par_id = {c.id: c for c in coffrets}
    enfants_de: Dict[str, list] = {}
    for c in coffrets:
        if c.parent_id and c.parent_id in par_id:
            enfants_de.setdefault(c.parent_id, []).append(c.id)

    def _isc_cumule(identifiant):
        c = par_id[identifiant]
        total = c.isc_propre_a
        for enfant_id in enfants_de.get(identifiant, ()):
            total += _isc_cumule(enfant_id)
        return total

    coffrets_finaux = tuple(
        dataclasses.replace(c, isc_cumule_a=_isc_cumule(c.id))
        for c in coffrets)

    return ResultatCoffretsDc(coffrets=coffrets_finaux, refus=tuple(refus))


def _protections_ac(conception):
    """Les organes AC RETENUS de la conception — ``()`` si aucun.

    ``conception`` est duck-typée : ``conception.resultat.protections``
    (forme de ``core.electrique.types.ResultatElectrique``, chaque organe
    portant son ``.cote``) — c'est la même conception que consomment déjà
    ``core.electrique.concevoir`` et ``services/protections.py``.
    """
    resultat = getattr(conception, "resultat", None)
    protections = getattr(resultat, "protections", None) or ()
    return tuple(p for p in protections if getattr(p, "cote", None) == COTE_AC)


def _calibre_numerique(texte):
    """Le premier nombre d'un calibre publié (« 32 A / 230 V » → ``32.0``).

    Une LECTURE, jamais un seuil : le calibre est déjà celui que
    ``core.electrique.protections`` a retenu et cité ; ce n'est qu'un
    formatage à défaire pour republier le nombre à côté.
    """
    if not texte:
        return None
    lus = []
    trouve = False
    for caractere in texte:
        if caractere.isdigit():
            lus.append(caractere)
            trouve = True
        elif caractere == "," and trouve:
            lus.append(".")
        elif trouve:
            break
    if not lus:
        return None
    try:
        return float("".join(lus))
    except ValueError:
        return None


def coffret_ac(conception, branches):
    """CALX232 — le coffret AC, dimensionné par ses DÉPARTS réels.

    Args:
        conception: porte ``.resultat.protections`` (organes AC déjà
            retenus par ``core.electrique.protections.concevoir_protections``
            ou la check-list ``services/protections.py``).
        branches: les branches AC de micro-onduleurs publiées par CALX209 —
            vide ou absent = régime chaîne (UN départ, l'onduleur).

    Returns:
        ``CoffretAc``. En régime micro, il n'y a PAS de calibre de tête
        commun : chaque départ porte déjà son propre organe (CALX210), la
        chose est dite plutôt que devinée.
    """
    branches = tuple(branches or ())
    organes_ac = _protections_ac(conception)

    if branches:
        departs = len(branches)
        calibre_tete = None
        omissions: Tuple[str, ...] = () if not organes_ac else (
            "calibre de tête OMIS : en régime micro-onduleurs chaque départ "
            "porte son propre organe (CALX210), il n'y a pas de protection "
            "de tête commune à calibrer",)
        return CoffretAc(departs=departs, organes=len(organes_ac),
                         calibre_tete_a=calibre_tete,
                         regle_source=REGLE_ENVELOPPE_AC,
                         omissions=omissions)

    if not organes_ac:
        return CoffretAc(departs=0, organes=0, calibre_tete_a=None,
                         regle_source=REGLE_ENVELOPPE_AC,
                         omissions=("aucun organe AC retenu : coffret AC "
                                    "omis du bordereau",))

    tete = next((p for p in organes_ac if p.repere == "QAC1"), None)
    calibre_tete = _calibre_numerique(tete.calibre) if tete is not None else None
    omissions = () if calibre_tete is not None else (
        "calibre de tête OMIS : le calibre du disjoncteur AC de tête "
        "(QAC1) n'a pas pu être lu sur les organes retenus",)
    return CoffretAc(departs=1, organes=len(organes_ac),
                     calibre_tete_a=calibre_tete,
                     regle_source=REGLE_ENVELOPPE_AC, omissions=omissions)

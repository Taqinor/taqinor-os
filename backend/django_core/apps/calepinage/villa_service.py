"""Le moteur VILLA / SURFACE LIBRE du calepinage — rapatrié du service AO.

SOLMVP15b — ``apps.ventes`` (villa, devis résidentiel) lisait ce moteur par
le sélecteur ``calepinage_villa`` du module AO, qui déléguait à
``apps/ao/services.py``. AO sort du produit : la moitié PURE de ce service —
celle qui ne lit ni n'écrit AUCUNE ligne (AOF163) — vit désormais ici, à la
ligne près. Même format d'entrée canonique, mêmes signatures, même dict de
sortie, mêmes refus français : les appelants n'ont changé que d'adresse
d'import.

CE QUI RESTE CHEZ AO : tout ce qui PERSISTE (``AppelOffre``, ``ToitureAO``,
``VarianteCalepinage``…). Une villa n'a pas de projet AO et n'en crée pas.

CE QUI EST DÉJÀ AILLEURS DANS CE MODULE : ``moteur_service.py`` porte le
calcul STATELESS *par DOCUMENT du contrat* (``calepinage_json``,
``cout_calepinage`` — entrée = un dict sérialisé). Les fonctions ci-dessous
sont l'autre porte du MÊME moteur ``core.calepinage`` : entrée = des OBJETS
(``SurfacePolygone`` / ``AreaRecord``), sortie = ``ResultatCalepinage`` +
preuve AOF163. Aucune des deux ne réimplémente l'autre ; elles ne partagent
aucun helper (l'``EntreeCalepinage`` de ``moteur_service._entree`` est
DÉSÉRIALISÉE d'un document, celle d'ici est ASSEMBLÉE d'objets, et la preuve
d'AOF163 n'a ni le vocabulaire ni les clés de ``moteur_io.preuve_vers_json``).

LECTURE PURE : aucune ligne n'est lue ni écrite, hors la résolution du produit
panneau (PV12), qui passe par ``apps.stock.selectors``.
"""
from __future__ import annotations


def _entree_calepinage_canonique(*, repere, surface, kits, parametres,
                                 obstacles=(), zones=()):
    """Assemble l'``EntreeCalepinage`` canonique (format AO) — sans ORM.

    ``appliquer_regles`` DÉRIVE le dégagement de chaque obstacle depuis son
    type et sa provenance : le moteur ne devine jamais un dégagement en
    silence, et la villa hérite donc exactement de la même règle que l'AO.
    """
    from core.calepinage.obstacles import appliquer_regles
    from core.calepinage.serialisation import EntreeCalepinage

    return EntreeCalepinage(
        repere=repere, surfaces=(surface,), kits=tuple(kits),
        parametres=parametres,
        obstacles=tuple(appliquer_regles(tuple(obstacles))),
        zones=tuple(zones))


def _preuve_publiable(resultat, politique):
    """``ResultatOptimum`` -> preuve sérialisable (aucun coût, aucun prix)."""
    return {
        'methode': resultat.preuve.methode.value,
        'pas_recherche_m': resultat.preuve.pas_recherche_m,
        'compte_retenu': resultat.preuve.compte_retenu,
        'compte_optimal': resultat.preuve.compte_optimal,
        'borne_superieure': resultat.preuve.borne_superieure,
        'nb_plans_optimaux': resultat.preuve.nb_plans_optimaux,
        'ecart_a_l_optimum': resultat.ecart_a_l_optimum,
        'politique_pas': getattr(politique, 'code', ''),
    }


def calepiner_surface(*, surface, kits, parametres, obstacles=(), zones=(),
                      politique=None, repere='SURFACE'):
    """Calepine UNE enveloppe et ses obstacles — SANS aucun projet AO.

    C'est le point d'entrée PARTAGÉ : la villa (``apps.ventes``, qui lit via
    ``apps.calepinage.selectors``) et l'AO passent par le MÊME moteur, sur
    le MÊME format d'entrée. Aucune ligne n'est créée, aucune n'est lue :
    la fonction ne touche pas l'ORM (elle est appelable hors transaction,
    hors société).

    Rend un dict ``{'entree', 'resultat', 'preuve', 'rangees', 'tables'}`` où
    ``resultat`` est un ``ResultatCalepinage`` — le MÊME objet que le chemin
    AO, porteur du couple ``(hash_entree, version_moteur)``.
    """
    from core.calepinage.perf import optimiser_economique
    from core.calepinage.poseur import poser_plan
    from core.calepinage.serialisation import ResultatCalepinage

    entree = _entree_calepinage_canonique(
        repere=repere, surface=surface, kits=kits, parametres=parametres,
        obstacles=obstacles, zones=zones)
    calcul = optimiser_economique(entree.surfaces[0], entree.parametres,
                                  entree.obstacles, entree.zones, politique)
    rangees = tuple((y0, entree.parametres.kit(code))
                    for y0, code in calcul.rangees)
    tables = poser_plan(entree.surfaces[0], rangees, entree.obstacles,
                        entree.zones)
    return {
        'entree': entree,
        'resultat': ResultatCalepinage.depuis_resultat(entree, calcul),
        'preuve': _preuve_publiable(calcul, politique),
        'rangees': calcul.rangees,
        'tables': tuple(tables),
    }


def kit_panneau_du_produit(produit_panneau, *, company=None):
    """PV12 — le ``Kit`` de calepinage d'un PRODUIT panneau du catalogue.

    ``produit_panneau`` est un identifiant OU une instance de ``stock.Produit``.
    Un identifiant est TOUJOURS résolu DANS la société (``company`` devient
    alors obligatoire) : sans ce scoping, le panneau d'une autre société
    entrerait dans un calcul, et une villa se retrouverait chiffrée sur un
    module qui n'appartient pas à son vendeur.

    La géométrie vient de ``apps.stock.selectors.kit_from_produit`` — jamais
    d'un import de ``apps.stock.models`` (frontière cross-app du dépôt). Elle
    rend ``None`` dès qu'une des trois grandeurs requises manque (longueur,
    largeur, puissance) : l'appelant retombe alors sur son kit par défaut,
    parce que **le moteur ne devine jamais une géométrie**.
    """
    from apps.stock import selectors as stock_selectors

    if produit_panneau is None:
        return None
    produit = produit_panneau
    if isinstance(produit_panneau, (int, str)):
        if company is None:
            raise ValueError(
                'Résoudre un produit panneau par identifiant exige une '
                "société : sans elle, le panneau d'une autre société "
                'entrerait dans le calcul.')
        produit = stock_selectors.get_produit_scoped(company, produit_panneau)
        if produit is None:
            raise ValueError(
                'Produit panneau « %s » introuvable dans cette société.'
                % (produit_panneau,))
    elif company is not None:
        attendue = getattr(company, 'pk', company)
        if getattr(produit, 'company_id', attendue) != attendue:
            raise ValueError(
                'Le produit panneau « %s » appartient à une autre société.'
                % (getattr(produit, 'nom', produit),))
    return stock_selectors.kit_from_produit(produit)


def calepiner_villa(area, *, ordre='lnglat', kit=None, produit_panneau=None,
                    company=None, retrait_m=None, pas_recherche_m=0.01,
                    famille=None):
    """Calepine une toiture VILLA (``AreaRecord`` du lecteur de cartes).

    ``ordre`` est EXPLICITE et jamais deviné : le lecteur de cartes sérialise
    en ``[lng, lat]`` (GeoJSON) tandis que le lead CRM stocke ``[lat, lng]`` —
    une confusion produit une toiture retournée, plausible et fausse.

    ``produit_panneau`` (PV12) fait poser le panneau RÉELLEMENT vendu : le kit
    est dérivé de la fiche technique du produit, dans la société. Il ne prime
    jamais sur un ``kit`` fourni explicitement (celui-là est déjà un choix), et
    une fiche incomplète retombe sur ``KIT_VILLA_720`` — inchangé.

    ``famille`` (PV66) choisit la FORME DE TABLE — ``SUD`` (module unique plein
    sud) ou ``EST_OUEST`` (chevron dos-à-dos) — et se compose avec ce qui
    précède : le panneau retenu, quelle que soit son origine, est celui que la
    famille met en table. Sans famille demandée, le kit part intact et le
    calcul est bit-à-bit celui d'avant PV66.

    Aucune ligne AO n'est créée ni lue : une villa n'a pas de projet AO.
    Rend le même dict que ``calepiner_surface`` + ``projection``,
    ``politique`` et ``panneaux`` (structure compatible avec l'écran existant,
    pour ne rien casser côté front).
    """
    from core.calepinage.adaptateurs.villa import (
        RETRAIT_VILLA_M, vers_entree, vers_panneaux,
    )
    from core.calepinage.types import KIT_VILLA_720

    kit = (kit
           or kit_panneau_du_produit(produit_panneau, company=company)
           or KIT_VILLA_720)
    entree, projection, politique = vers_entree(
        area, ordre=ordre, kit=kit,
        retrait_m=RETRAIT_VILLA_M if retrait_m is None else retrait_m,
        pas_recherche_m=pas_recherche_m, famille=famille)
    kit = entree.kits[0]
    sortie = calepiner_surface(
        surface=entree.surfaces[0], kits=entree.kits,
        parametres=entree.parametres, obstacles=entree.obstacles,
        zones=entree.zones, politique=politique, repere=entree.repere)
    sortie['projection'] = projection
    sortie['politique'] = politique
    sortie['kit'] = kit
    sortie['panneaux'] = vers_panneaux(sortie['tables'], projection, kit,
                                       entree.parametres.axe_rangee)
    return sortie

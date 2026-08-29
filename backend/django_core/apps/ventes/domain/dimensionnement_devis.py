"""QJR77 — LA COUCHE LIÉE AU DEVIS du dimensionnement (déplacement PUR).

CE QUE CE MODULE EST. ``apps.ventes.dimensionnement`` était DEUX modules dans
un fichier : un balayage PUR — sans base de données, sans instance, testable
avec des nombres (``bornes_candidates``, ``balayer_tailles``,
``choisir_recommandation*``, ``recommander_taille``…) — et la couche qui LIT
un ``Devis`` (ses lignes, son ``roof_layout``, sa remise) et qui MUTE
l'instance qu'on lui passe (:data:`_MEMO_PLAFOND_PHYSIQUE`). La seconde vit
ici depuis le 29/08/2026.

CE DÉPLACEMENT NE CHANGE RIEN. Les corps sont repris À L'OCTET PRÈS ;
``apps.ventes.dimensionnement`` RÉ-EXPORTE chacun de ces noms, si bien
qu'aucun appelant n'a été touché et que ``from apps.ventes.dimensionnement
import plafond_toit_du_devis`` continue de fonctionner. Le pin de surface
``apps/ventes/tests/test_qjr_dimensionnement_surface.py`` garde ce contrat :
un ré-export oublié y est rouge en quelques secondes, là où flake8 ne
signale JAMAIS la disparition d'un nom importé par un AUTRE module.

RÈGLE #4 : ce module n'écrit RIEN (aucun statut, aucune ligne, aucun total,
aucun PDF) — il LIT un devis et rend des nombres de VENTE, jamais un prix
d'achat ni une marge.

POURQUOI L'IMPORT DES OUTILS PURS EST EN BAS DE CE FICHIER. Les deux moitiés
se citent : celle-ci a besoin des outils du balayage (``_num``,
``_lire_composition``, ``_payback``…), et ``dimensionnement.py`` a besoin des
noms d'ici pour les ré-exporter. Placer LES DEUX imports en fin de fichier —
après toutes les définitions — rend le cycle inoffensif DANS LES DEUX SENS
d'import : quel que soit le module chargé le premier, l'autre trouve déjà
définis les noms qu'il vient chercher. Les fonctions, elles, ne résolvent
leurs globales qu'à l'APPEL, jamais à l'import.
"""
from __future__ import annotations

import logging
import math
from decimal import Decimal

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# L'ÉCHELLE DE PALIERS BATTERIE (ordre fondateur, 25/08/2026)
# ════════════════════════════════════════════════════════════════════════════
#
# VERBATIM : « more than just 2 batteries in the web page battery option ; extra
# batteries might add extra panels with extra cost, that is still fine ».
#
# CE QUI CHANGE PAR RAPPORT À DIM2. Le mini-balayage de ``balayer_tailles``
# répond à « à CHAMP DONNÉ, que change une batterie de plus ? » — et la règle
# « batteries toujours pleines » y REJETTE tout palier qu'un champ trop petit
# ne saurait charger. La question du fondateur est l'INVERSE : « et si je veux
# CETTE banque de batteries, que faut-il ? ». La même règle ne rejette donc
# plus le palier : elle TIRE LES PANNEAUX NÉCESSAIRES. Des batteries en plus
# amènent des panneaux en plus, qui coûtent plus — « that is still fine ».

#: Nombre de paliers montrés AU-DELÀ du palier retenu. Ce n'est pas une règle
#: métier : c'est la LONGUEUR RAISONNABLE d'un choix à l'écran. La liste
#: s'arrête de toute façon d'elle-même au plafond du toit ou dès qu'un palier
#: ne se remplit plus, souvent bien avant.
#: BATHOMO (fondateur 26/08/2026) — « we can go up to 30 or 40 kWh using
#: 5 kWh batteries, no problem » : 8 → 16, marge explicite pour que l'échelle
#: n'écrête plus une installation qui peut légitimement monter à 6-8 packs
#: de 5 kWh au-delà du palier retenu (l'ancienne valeur suffisait déjà
#: mathématiquement combinée à ``MAX_PALIERS_STOCKAGE``, mais la coupait
#: PILE là où un grand champ commençait à devenir intéressant).
MAX_PALIERS_ECHELLE = 16

#: GARDE-FOU DE CALCUL : nombre maximal de tailles de champ réellement sondées.
#: Chaque sonde coûte une composition catalogue par palier PLUS douze
#: simulations journalières ; la recherche du champ minimal est DICHOTOMIQUE
#: (≈ log₂ du plafond, mutualisée entre paliers puisqu'ils montent ensemble),
#: si bien que ce plafond n'est jamais atteint sur un profil réel — il est là
#: pour qu'un catalogue pathologique ne puisse pas faire boucler un aperçu.
MAX_SONDES_ECHELLE = 24


def plafond_toit_du_devis(devis):
    """Le nombre de panneaux que le calepinage 3D DESSINE — la cible du devis.

    CE N'EST PAS LA CONTENANCE DU TOIT, et cette docstring a menti jusqu'au
    26/08/2026 : elle annonçait « panneaux PHYSIQUEMENT POSABLES » alors
    qu'elle délègue à ``services._cible_panneaux_du_layout``, qui lit
    ``layout.result.panels`` — LE NOMBRE DE PANNEAUX QUE LE COMMERCIAL A
    DESSINÉS. Il dessine ce dont le client a besoin, puis s'arrête : le toit en
    tient presque toujours davantage. Le mensonge a coûté une vraie régression
    (devis live test15) : la taille « Max » d'``offres_tailles`` s'ancrait ici,
    Recommandé est resynchronisé sur ce MÊME dessin, donc Max valait Recommandé
    sur TOUT devis calepiné et la troisième carte s'effondrait toujours.

    CE NOMBRE-CI RESTE LE BON POUR LA RESYNCHRONISATION ET POUR L'ÉCHELLE DE
    PALIERS : ce qui a été dessiné EST la cible de resynchronisation, et il est
    lu par la MÊME fonction qu'elle (``_cible_panneaux_du_layout`` sur
    ``Devis.roof_layout``) — deux lectures du toit finiraient par diverger.

    LA CONTENANCE, elle, se MESURE sur la géométrie réelle :
    :func:`apps.ventes.calepinage_options.capacite_toit_du_devis` (panneaux
    conservés + extension maximale prouvée à l'intérieur du polygone). C'est
    elle, et elle seule, qui a le droit de dire « ce toit accepte N panneaux ».

    ``None`` quand le devis ne porte aucun calepinage — l'échelle n'est alors
    bornée que par ses garde-fous de calcul, jamais par une surface inventée.
    """
    layout = getattr(devis, 'roof_layout', None)
    if not isinstance(layout, dict):
        return None
    from apps.ventes.services import (
        _cible_panneaux_du_layout, extract_roof_config)
    try:
        toiture = extract_roof_config(layout) or {}
    except Exception:  # noqa: BLE001 — un layout illisible n'est pas un plafond
        toiture = {}
    try:
        cible = int(_cible_panneaux_du_layout(layout, toiture) or 0)
    except Exception:  # noqa: BLE001
        return None
    return cible if cible > 0 else None


def contour_du_devis_lnglat(devis):
    """Les anneaux ``[[lng, lat], …]`` du TRACÉ CLIENT de ce devis, ou ``[]``.

    DEUX SOURCES, DANS CET ORDRE, ET AUCUNE N'INVENTE UNE GÉOMÉTRIE :

    1. les zones du calepinage porté par le devis (``roof_layout['zones']``,
       ``vertices`` en ``[[lng, lat], …]`` — la convention de
       ``services.zone_toit_depuis_contour``, qui y recopie précisément le
       contour dessiné par le client) ;
    2. à défaut, ``Lead.roof_outline`` via ``services.contour_client_lnglat``
       (qui porte déjà les deux formes réellement stockées et le seuil de trois
       sommets).

    Un anneau de moins de trois sommets est écarté, jamais réparé.
    """
    anneaux = []
    layout = getattr(devis, 'roof_layout', None)
    if isinstance(layout, dict):
        for zone in (layout.get('zones') or []):
            if not isinstance(zone, dict):
                continue
            anneau = []
            for point in (zone.get('vertices') or []):
                if not isinstance(point, (list, tuple)) or len(point) < 2:
                    continue
                try:
                    anneau.append([float(point[0]), float(point[1])])
                except (TypeError, ValueError):
                    continue
            if len(anneau) >= 3:
                anneaux.append(anneau)
    if anneaux:
        return anneaux
    from apps.ventes.services import contour_client_lnglat
    contour = contour_client_lnglat(getattr(devis, 'lead', None))
    return [contour] if contour else []


#: Mémo posé sur l'INSTANCE de devis — même patron que
#: ``calepinage_options._MEMO_CAPACITE``. La borne physique lit le catalogue
#: (le produit panneau et sa fiche technique) : sans mémo, un endpoint public
#: non caché la relirait une fois par carte et par variante.
_MEMO_PLAFOND_PHYSIQUE = '_taqinor_plafond_physique'


def plafond_physique_du_devis(devis):
    """La BORNE PHYSIQUE DURE du tracé client — ``None`` si indéterminable.

    ``aire du contour ÷ aire d'un panneau``, prononcée par la fonction qui la
    porte déjà (:func:`apps.ventes.services.plafond_physique_du_contour`) : on
    ne réécrit pas ici une seconde formule de surface. Plusieurs zones se
    SOMMENT — chacune est un morceau de toit réel.

    CE QUE CETTE BORNE EST, ET CE QU'ELLE N'EST PAS. Elle ne dépend d'aucun
    paramètre que le client ne nous a pas donné (ni pente, ni azimut, ni retrait
    de rive) : elle n'invente rien, et elle est LARGE par construction — un
    calepinage réel tient toujours nettement moins. Ce n'est donc PAS une
    contenance ; c'est le mur au-delà duquel une taille serait physiquement
    impossible. Elle ne sert qu'à PLAFONNER, jamais à proposer un nombre.

    Ne lève JAMAIS : un catalogue ou une géométrie illisibles ne valent pas un
    plafond, ils valent ``None``.
    """
    memo = getattr(devis, _MEMO_PLAFOND_PHYSIQUE, None)
    if isinstance(memo, tuple) and len(memo) == 1:
        return memo[0]
    plafond = None
    try:
        from apps.ventes.services import (
            _panneau_pour_calepinage, plafond_physique_du_contour)
        anneaux = contour_du_devis_lnglat(devis)
        if anneaux:
            produit, _societe = _panneau_pour_calepinage(
                getattr(devis, 'roof_layout', None) or {},
                company=getattr(devis, 'company', None), devis=devis)
            total = 0
            for anneau in anneaux:
                part = plafond_physique_du_contour(anneau, produit)
                if part:
                    total += int(part)
            plafond = total or None
    except Exception:  # noqa: BLE001 — une géométrie illisible n'est pas un
        # plafond : on n'en publie aucun.
        logger.warning('plafond physique du toit indisponible', exc_info=True)
        plafond = None
    try:
        setattr(devis, _MEMO_PLAFOND_PHYSIQUE, (plafond,))
    except Exception:  # noqa: BLE001 — un objet non mutable ne coûte que le
        # mémo, jamais le résultat.
        pass
    return plafond


def plus_grande_contenance(capacite, plafond, borne_physique=None):
    """LA RÈGLE « ce toit accepte N panneaux », en UN SEUL endroit.

    LA CONTENANCE MESURÉE COMMANDE. Quand elle existe, le compte DESSINÉ n'est
    qu'un plancher : le ``max()`` n'est pas une hésitation, la contenance vaut
    par construction au moins le posé (elle part de lui et ne fait qu'ajouter),
    si bien que le second terme ne l'emporte que sur un layout dont le
    ``result.panels`` déclaré dépasse les panneaux réellement sérialisés. Dans
    ce cas-là, refuser de compter la différence RÉTRÉCIRAIT une borne qui
    existait déjà — on ne durcit jamais un plafond de toit sur une incohérence
    de données.

    SANS CONTENANCE MESURÉE, LE COMPTE DESSINÉ NE PINCE PLUS RIEN (correction
    ordonnée le 28/08/2026). Un devis AUTOMATIQUE naît avec un layout
    CONTOUR-SEUL (``services.zone_toit_depuis_contour``) : aucun panneau n'y est
    sérialisé, donc rien n'est mesurable, et ``result.panels`` n'y porte que la
    CIBLE VENDUE. Le prendre pour un plafond de toit revenait à dire « ce toit
    accepte exactement ce que je viens de vendre » — Max valait Recommandé, la
    troisième carte s'effondrait sur tout devis automatique, et la présence du
    layout court-circuitait en plus le repli « dernière taille éligible du
    balayage ». Le dessin reste ce qu'il est — la cible de RESYNCHRONISATION —
    et la seule borne honnête qui subsiste est la borne PHYSIQUE du tracé
    (:func:`plafond_physique_du_devis`).

    ``None`` quand rien n'aboutit : pas de plafond de toit du tout (jamais une
    surface inventée).
    """
    if capacite:
        valeurs = [int(v) for v in (capacite, plafond) if v]
        return max(valeurs)
    return int(borne_physique) if borne_physique else None


def contenance_toit_du_devis(devis):
    """Le plus grand nombre de panneaux que le TOIT de ce devis accepte.

    LA FONCTION QUE TOUT CE QUI PROPOSE UNE TAILLE DOIT LIRE — l'échelle de
    paliers batterie comme les trois tailles Éco/Recommandé/Max. Elle mesure
    (:func:`~apps.ventes.calepinage_options.capacite_toit_du_devis` : panneaux
    conservés + extension maximale PROUVÉE dans le polygone réel) ; à défaut de
    géométrie mesurable, elle retombe sur la BORNE PHYSIQUE du tracé client
    (:func:`plafond_physique_du_devis`) — et sur rien d'autre : le compte
    DESSINÉ ne borne plus le toit (voir :func:`plus_grande_contenance`). Sans
    tracé ni calepinage : ``None`` et AUCUNE borne de toit, exactement comme
    avant.

    UN SEUL BALAYAGE PAR REQUÊTE : la mesure est mémoïsée sur l'instance de
    devis, si bien que l'échelle, les cartes et la clé publique la partagent.
    Le mur physique, lui, n'est LU QUE si la mesure a échoué — il interroge le
    catalogue, et le calculer d'office coûterait une requête par dérivation
    pour un nombre que :func:`plus_grande_contenance` jetterait.
    """
    from apps.ventes.calepinage_options import capacite_toit_du_devis
    capacite = capacite_toit_du_devis(devis)
    physique = None if capacite else plafond_physique_du_devis(devis)
    return plus_grande_contenance(capacite, plafond_toit_du_devis(devis),
                                  physique)


def _compter_modules_batterie(lignes_vue):
    """``(nb de modules 5 kWh, nb de modules 10 kWh)`` LUS sur la composition.

    Le kWh est celui du NOM du produit — c'est-à-dire le NOMINAL imprimé sur
    l'étiquette, la grandeur avec laquelle le fondateur et le client comptent
    (« deux batteries de 10 »), là où ``capacite_kwh`` porte la capacité UTILE
    fichée. Les deux coexistent volontairement : l'une se compte, l'autre se
    calcule.

    Un module d'une AUTRE taille (le jour où le catalogue en référence un) ne
    tombe dans aucun des deux compteurs — jamais reclassé de force dans le
    voisin le plus proche : ``capacite_kwh`` continue, lui, à dire la vérité.
    """
    from apps.ventes.services import _parse_kwh
    cinq = dix = 0
    for ligne in (lignes_vue or []):
        if ligne.get('role') != 'batterie':
            continue
        nominal = _num(_parse_kwh(ligne.get('designation') or ''))
        quantite = int(_num(ligne.get('quantite')))
        if quantite <= 0:
            continue
        if abs(nominal - 5.0) < 1.0:
            cinq += quantite
        elif abs(nominal - 10.0) < 1.0:
            dix += quantite
    return cinq, dix


def _compter_modules_batterie_generique(lignes_vue):
    """``(nb_modules, module_kwh)`` — GÉNÉRALISATION de
    :func:`_compter_modules_batterie` à N'IMPORTE QUEL calibre (A1, revue
    adversariale Fable 26/08/2026) : ``nb_batteries_5``/``nb_batteries_10``
    rendent ``(0, 0)`` pour un devis dont le module vendu n'est NI 5 NI
    10 kWh (le Deye BOS-B-Pack16, 16 kWh, un produit RÉEL des gammes) — une
    composition pourtant bien réelle (prix, capacité) semblerait alors « sans
    batterie ».

    Une composition est TOUJOURS HOMOGÈNE (BATHOMO — jamais un mélange de
    calibres) : au plus UN nominal apparaît réellement sur les lignes
    batterie d'UNE composition. Ce compteur additionne leurs quantités et
    rend ce nominal-là, quel qu'il soit — jamais restreint à 5/10.
    ``(0, None)`` si aucune ligne batterie lisible n'est présente — jamais
    un calibre inventé."""
    from apps.ventes.services import _parse_kwh
    total = 0
    module_kwh = None
    for ligne in (lignes_vue or []):
        if ligne.get('role') != 'batterie':
            continue
        quantite = int(_num(ligne.get('quantite')))
        if quantite <= 0:
            continue
        nominal = _parse_kwh(ligne.get('designation') or '')
        if nominal is None or nominal <= 0:
            continue
        total += quantite
        if module_kwh is None:
            module_kwh = nominal
    return (total, module_kwh) if total > 0 else (0, None)


def _lignes_produit_du_devis(devis):
    """Les LIGNES PRODUIT réellement facturées par ce devis, ou ``[]``.

    Les intertitres de section et les notes (``XSAL14``) ne portent ni prix ni
    quantité : ils ne comptent dans aucun total, donc dans aucune lecture de
    ce module. Ne lève jamais (un devis non sauvegardé n'a pas de lignes)."""
    try:
        lignes = list(devis.lignes.all())
    except Exception:  # noqa: BLE001 — devis détaché / sans lignes
        return []
    return [ligne for ligne in lignes
            if getattr(ligne, 'est_ligne_produit', True)
            and ligne.quantite is not None
            and ligne.prix_unitaire is not None]


def facteur_remise_du_devis(devis) -> float:
    """Le facteur multiplicatif de remise RÉELLEMENT appliqué par ce devis.

    POURQUOI CE FACTEUR EXISTE. Les paliers de l'échelle sont chiffrés sur une
    composition CATALOGUE (prix publics bruts), alors que la carte de la page
    publique affiche le TTC du DEVIS — remise comprise. Sans ce facteur, la
    pilule « retenue » et la carte annonçaient deux prix différents pour le
    MÊME kit, et l'écart entre deux pilules d'un devis remisé était faux.

    LA MÊME SOURCE QUE LE MOTEUR DE RENDU. ``quote_engine.builder`` chiffre une
    ligne à ``prix_unitaire × (1 − remise_ligne/100)`` puis applique
    ``Devis.remise_globale`` au sous-total HT : ce facteur est exactement le
    rapport ``HT net / HT brut`` de cette chaîne, lu sur les lignes RÉELLES.

    PORTÉE : les lignes que l'option AVEC BATTERIE facture — les lignes
    communes (``variante = ''``) et les lignes ``'avec'``, jamais les lignes
    réservées à l'option SANS batterie (L-2OPT). Sur un devis mono-option,
    toutes les lignes sont communes : la portée est le devis entier.

    APPROXIMATION ASSUMÉE ET UNIQUE : quand les lignes portent des remises
    UNITAIRES DIFFÉRENTES, un seul facteur ne peut pas les représenter toutes —
    c'est alors la remise MOYENNE (pondérée par le montant) qui est appliquée à
    chaque palier. Le cas courant (aucune remise de ligne, une remise globale)
    est rendu au centime près. Vaut ``1.0`` (aucune remise) dès que rien n'est
    lisible : jamais un rabais inventé sur un devis qui n'en porte pas.
    """
    try:
        lignes = [ligne for ligne in _lignes_produit_du_devis(devis)
                  if (getattr(ligne, 'variante', '') or '') != 'sans']
        brut = sum(_num(ligne.quantite) * _num(ligne.prix_unitaire)
                   for ligne in lignes)
        if brut <= 0:
            return 1.0
        apres_lignes = sum(
            _num(ligne.quantite) * _num(ligne.prix_unitaire)
            * (1.0 - _num(getattr(ligne, 'remise', 0)) / 100.0)
            for ligne in lignes)
        globale = _num(getattr(devis, 'remise_globale', 0))
        facteur = (apres_lignes / brut) * (1.0 - globale / 100.0)
    except Exception:  # noqa: BLE001 — un aperçu ne casse jamais un écran
        logger.warning('facteur de remise illisible sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return 1.0
    # Un facteur nul, négatif ou non fini (NaN compris — toute comparaison
    # avec NaN est fausse) ne décrit aucune remise réelle : on rend le prix
    # catalogue plutôt qu'un prix fabriqué.
    if not 0 < facteur < math.inf:
        return 1.0
    return facteur


def capacite_batterie_des_lignes(devis):
    """La capacité batterie des LIGNES RÉELLES de ce devis, ou ``None``.

    C'EST LA CAPACITÉ QUE LE CLIENT ACHÈTE, pas celle que le moteur aurait
    conseillée. Le générateur pose les lignes sur un champ arrondi
    (``autoFillLines`` cible ``round(kwc/5)×5``), si bien que l'optimum du
    moteur et les lignes vendues peuvent désigner deux capacités différentes :
    marquer « Retenu pour ce devis » d'après le moteur affichait alors le prix
    d'une AUTRE capacité que celle du devis.

    Mesurée avec la MÊME grandeur que les paliers de l'échelle
    (:func:`capacite_utile_batterie` — fiche technique d'abord, nom ensuite),
    sans quoi la comparaison opposerait des utiles à des nominaux.

    ``None`` quand le devis ne porte AUCUNE ligne batterie : aucun palier n'est
    alors marqué ``retenu`` — jamais un marquage au hasard."""
    try:
        from apps.ventes.services import _is_battery

        total = 0.0
        for ligne in _lignes_produit_du_devis(devis):
            designation = getattr(ligne, 'designation', '') or ''
            if not _is_battery(designation):
                continue
            quantite = _num(ligne.quantite)
            if quantite <= 0:
                continue
            total += _num(capacite_utile_batterie(
                getattr(ligne, 'produit', None), designation)) * quantite
    except Exception:  # noqa: BLE001 — un aperçu ne casse jamais un écran
        logger.warning('capacité batterie des lignes illisible sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None
    return round(total, 2) if total > 0 else None


def module_batterie_du_devis(devis):
    """BATHOMO (fondateur 26/08/2026) — le CALIBRE (en kWh, un flottant
    POSITIF quelconque — voir F6 ci-dessous) DÉJÀ engagé par les LIGNES
    RÉELLES de ce devis, ou ``None`` si aucune ligne batterie n'existe
    encore.

    « the battery-related features in the quote web page should ALWAYS use
    the quote items — if the quote has 5 kWh batteries the web page should
    only show 5 kWh batteries ; and we can go up to 30 or 40 kWh using 5 kWh
    batteries, no problem. » :func:`echelle_paliers_batterie` passe cette
    valeur en ``batterie_module_kwh`` à CHAQUE composition qu'elle sonde
    (:func:`apps.ventes.services.composition_residentielle`) : l'échelle
    grandit alors en N modules de CE SEUL calibre — jamais un re-choix
    catalogue qui basculerait vers l'autre calibre au passage d'un multiple
    de 10.

    F6 (revue adversariale 26/08/2026) — GÉNÉRALISÉ à N'IMPORTE QUEL calibre
    positif, jamais un whitelist figé sur 5/10. Un devis qui vend le VRAI
    Deye BOS-B-Pack16 (16 kWh, présent dans les gammes) perdait SILENCIEUSEMENT
    son pin sous l'ancien whitelist — retombant sur un re-choix catalogue,
    exactement la violation « la page suit les articles du devis » que F1
    corrige par ailleurs. Les lignes sont regroupées PAR CALIBRE LE PLUS
    PROCHE (tolérance ±1 kWh, la même que l'ancien couple 5/10) : deux
    lectures d'un même module à l'arrondi près (5.0 / 5.12) ne doivent
    JAMAIS ouvrir deux compartiments distincts.

    F6 — MÊME FILTRE DE VARIANTE que :func:`facteur_remise_du_devis`
    (``variante != 'sans'``) : une ligne réservée à l'option SANS batterie
    (L-2OPT) n'a, par construction, jamais de ligne batterie — mais aligner
    la lecture évite toute divergence future entre les deux fonctions.

    LECTURE, JAMAIS UNE RECOMPOSITION — même source que
    :func:`_compter_modules_batterie` (le nom des lignes déjà vendues). Un
    devis historique EXCEPTIONNELLEMENT mélangé (un devis composé avant ce
    correctif) retient le calibre qui porte la plus grande capacité totale —
    égalité tranchée par le PLUS PETIT calibre (jamais un chiffre inventé,
    la meilleure lecture d'un fait imparfait plutôt qu'un blocage).
    ``None`` (devis sans ligne batterie, ou un devis qui n'existe pas
    encore) ⇒ l'appelant retombe sur le choix ÉCONOMIQUE normal du
    catalogue (comportement inchangé)."""
    try:
        from apps.ventes.services import _is_battery, _parse_kwh

        capacites = {}  # calibre (kWh, ouvert par la 1re ligne) -> capacité
        for ligne in _lignes_produit_du_devis(devis):
            if (getattr(ligne, 'variante', '') or '') == 'sans':
                continue
            designation = getattr(ligne, 'designation', '') or ''
            if not _is_battery(designation):
                continue
            quantite = _num(ligne.quantite)
            if quantite <= 0:
                continue
            nominal = _num(_parse_kwh(designation))
            if nominal <= 0:
                continue
            calibre = next(
                (c for c in capacites if abs(c - nominal) < 1.0), nominal)
            capacites[calibre] = (
                capacites.get(calibre, 0.0) + nominal * quantite)
    except Exception:  # noqa: BLE001 — un aperçu ne casse jamais un écran
        logger.warning('module batterie du devis illisible sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None
    if not capacites:
        return None
    # Capacité totale DÉCROISSANTE, égalité tranchée par le calibre
    # CROISSANT (déterministe, jamais dépendant de l'ordre des lignes).
    return min(capacites, key=lambda c: (-capacites[c], c))


def echelle_paliers_batterie(devis):
    """L'ÉCHELLE des paliers de batterie proposables sur CE devis résidentiel.

    CONTRAT (PACT10 — écrit AVANT les deux moitiés qui le consomment). Renvoie
    une LISTE de dicts, capacité croissante, chacun portant EXACTEMENT :

    * ``capacite_kwh`` — capacité UTILE réellement livrée par la composition
      catalogue de ce palier (fiche technique, jamais l'étiquette) ;
    * ``nb_batteries_5`` / ``nb_batteries_10`` — combien de modules 5 kWh et
      10 kWh la composition contient, tels qu'on les COMPTE. UNE BANQUE EST
      TOUJOURS HOMOGÈNE (fondateur 26/08/2026) : ces deux compteurs ne sont
      JAMAIS non nuls tous les deux sur le MÊME palier — mélanger des
      calibres dans une même banque est électriquement interdit, et c'est ce
      mélange composé côté serveur qui a fait retirer le Dyness 10 kWh du
      stock de production (cf. ``apps.ventes.services.composition_
      residentielle``, ``apps.stock.management.commands.seed_catalogue``) ;
      restent ``0``/``0`` — MUETS, jamais faux — pour un calibre NI 5 NI
      10 kWh (le Deye BOS-B-Pack16, 16 kWh, un produit RÉEL des gammes) ;
    * ``nb_modules`` / ``module_kwh`` (A1, revue adversariale Fable
      26/08/2026, AJOUT ADDITIF) — la GÉNÉRALISATION de ce même compte à
      N'IMPORTE QUEL calibre : combien de modules IDENTIQUES la composition
      contient, et leur capacité NOMINALE (kWh, étiquette — même grandeur que
      ``nb_batteries_5``/``10``). ``(0, None)`` seulement si aucune batterie
      n'est composée sur ce palier. Pour un calibre 5 ou 10 kWh,
      ``nb_modules`` égale ``nb_batteries_5 + nb_batteries_10`` (un seul des
      deux est non nul) et ``module_kwh`` vaut ``5.0``/``10.0`` — ces deux
      nouvelles clés ne REMPLACENT PAS les anciennes, elles les complètent ;
    * ``nb_panneaux`` — le champ PV que ce palier EXIGE (voir plus bas) ;
    * ``puissance_kwc`` — ce champ en kWc, au wattage du panneau réel ;
    * ``prix_ttc`` — prix de VENTE TTC de la composition complète, **REMISE DU
      DEVIS APPLIQUÉE** (:func:`facteur_remise_du_devis`, la même chaîne que
      ``quote_engine.builder``) : les paliers se comparent alors entre eux ET
      avec le prix affiché sur la carte du devis, jamais un mélange de bases.
      Règle #4 : jamais un prix d'achat, jamais une marge ;
    * ``economies_annuelles`` — MAD/an du moteur horaire sur ce couple
      champ × stockage (une remise change le prix, jamais l'énergie) ;
    * ``payback_annees`` — ``prix_ttc / economies_annuelles``, ou ``None``
      quand l'économie n'est pas chiffrable (jamais un zéro fabriqué) ;
    * ``remplissage_ok`` — la batterie se remplit-elle TOUS LES JOURS ?
    * ``retenu`` — ce palier est-il celui des LIGNES BATTERIE RÉELLES de ce
      devis (:func:`capacite_batterie_des_lignes`) ? Aucune correspondance
      exacte ⇒ AUCUN palier retenu, jamais un marquage approché.

    LA RÈGLE FONDATEUR EST RETOURNÉE, PAS ABANDONNÉE. DIM2 demande « à champ
    donné, quel stockage se remplit ? » et REFUSE les paliers trop gros. Ici la
    question est « pour CETTE banque, que faut-il ? » : la même règle
    (« batteries toujours pleines », 24/08/2026) ne rejette plus le palier, elle
    TIRE LE CHAMP — ``nb_panneaux`` est le PLUS PETIT champ dont le surplus
    quotidien du mois le plus faible charge la banque entièrement. C'est
    exactement ce que le fondateur a autorisé le 25/08 : « extra batteries might
    add extra panels with extra cost, that is still fine ».

    LE CHAMP EST BORNÉ, ET CHAQUE BORNE EST JUSTIFIÉE : la CONTENANCE DU TOIT
    quand le devis porte un calepinage (:func:`contenance_toit_du_devis` — on ne
    propose pas des panneaux qui ne tiennent pas), ET :data:`FACTEUR_MAX_FALAISE`
    × la taille de parité de CE client, plafonnée par
    :data:`MAX_PANNEAUX_BALAYAGE`.

    LA BORNE DE TOIT SE MESURE, ELLE NE SE DÉCLARE PAS (26/08/2026). Elle lisait
    :func:`plafond_toit_du_devis`, qui rend le nombre de panneaux DESSINÉS par
    le commercial — pas ce que le toit tient. Sur un devis calepiné, un palier
    que le toit peut nourrir se retrouvait grisé « ne se remplit pas », et
    l'échelle S'ARRÊTAIT là (voir la boucle : ``champ_minimal`` rend ``None``,
    on rend le palier en ``remplissage_ok=False`` puis on ``break``) — les
    capacités supérieures ne s'affichaient jamais.

    ET SUR UN DEVIS AUTOMATIQUE, ELLE NE SE DÉCLARE PLUS DU TOUT (28/08/2026) :
    son layout est CONTOUR-SEUL — rien n'y est mesurable et ``result.panels``
    n'y porte que la cible vendue —, si bien que la borne retombe désormais sur
    le MUR PHYSIQUE du tracé (:func:`plafond_physique_du_devis`) au lieu de
    figer l'échelle sur ce qu'on venait de vendre.

    ``remplissage_ok=False`` n'apparaît QUE sur le premier palier que même le
    champ MAXIMAL ne remplit pas — il est montré (avec son prix et son champ)
    pour que la limite se LISE, puis l'échelle s'arrête.

    LES ENTRÉES SONT CELLES DU TABLEAU DÉJÀ RANGÉ SUR LE DEVIS
    (``services.entrees_dimensionnement_du_devis``, et les mêmes réglages par
    défaut que ``rafraichir_dimensionnement_devis``) : sans cela l'échelle
    désignerait un palier « retenu » calculé sur d'autres hypothèses que celles
    qui l'ont retenu.

    LISTE VIDE quand rien n'est dérivable — devis non résidentiel, sans société,
    sans profil de consommation, localisation non résolue, catalogue sans
    batterie. Jamais un chiffre inventé pour remplir l'écran. Ne lève JAMAIS et
    n'écrit RIEN (aucun statut, aucune ligne, aucun total — règle #4).
    """
    try:
        return _echelle_paliers_batterie(devis)
    except Exception:  # noqa: BLE001 — un aperçu ne casse jamais un écran
        logger.warning('échelle de paliers batterie indisponible sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return []


def _echelle_paliers_batterie(devis):
    """Le calcul de :func:`echelle_paliers_batterie`, sans son filet."""
    from apps.parametres.pvgis_profils import productible_mensuel
    from apps.ventes.etude_horaire import (
        balayer_stockage_horaire,
        # L-DECH — SOURCE UNIQUE des bornes de puissance batterie.
        puissances_batterie_des_lignes,
    )
    from apps.ventes.services import (
        _AUTO_PANEL_WATT,
        carte_marques_composition,
        catalogue_de_la_societe,
        composition_residentielle,
        entrees_dimensionnement_du_devis,
        ordre_lignes_societe,
    )

    entrees = entrees_dimensionnement_du_devis(devis)
    conso = (entrees or {}).get('conso_kwh_mensuelles')
    if not conso:
        return []
    conso_annuelle = sum(_num(v) for v in conso)
    if conso_annuelle <= 0:
        return []

    mensuel = productible_mensuel(ville=entrees['ville'], lat=entrees['lat'],
                                  lon=entrees['lon'])
    if not mensuel:
        return []
    productibles, _source = mensuel
    productible_annuel = sum(_num(v) for v in productibles)
    if productible_annuel <= 0:
        return []

    company = entrees['company']
    catalogue = catalogue_de_la_societe(company)
    marques = carte_marques_composition(company, None)
    ordre = ordre_lignes_societe(company)
    # MÊMES réglages par défaut que ``rafraichir_dimensionnement_devis`` : la
    # TVA du devis n'entre pas ici, chaque produit portant DÉJÀ son taux
    # (``_lire_composition``) et ce taux-ci n'étant que le repli.
    taux_tva = Decimal('20')
    # BATHOMO (fondateur 26/08/2026) — DÉNOMINATION PAR LE DEVIS. Un devis
    # qui vend déjà des batteries impose ce calibre à TOUTE l'échelle
    # sondée ci-dessous (``composition_residentielle(batterie_module_kwh=
    # …)``) : jamais un re-choix catalogue qui ferait basculer un rang de
    # l'échelle vers un autre calibre que celui réellement vendu. ``None``
    # (devis sans ligne batterie — le cas du tableau de dimensionnement
    # AVANT toute vente) ⇒ le choix ÉCONOMIQUE normal décide, inchangé.
    module_devis = module_batterie_du_devis(devis)

    def composer(panneaux, kwc, cible, journal):
        """Une composition catalogue AVEC batterie, ou ``None`` — jamais une
        exception : un palier impossible ne fait pas tomber l'échelle."""
        try:
            return composition_residentielle(
                catalogue, kwc=kwc, panel_watt=panel_watt,
                nb_panneaux=panneaux, avec_batterie=True,
                structure_type='acier', taux_tva=taux_tva,
                avertissements=journal, deux_options=False, marques=marques,
                ordre_lignes=ordre, batterie_cible_kwh=cible,
                batterie_module_kwh=module_devis)
        except Exception:  # noqa: BLE001
            logger.warning('composition impossible à %s panneaux / %s kWh',
                           panneaux, cible, exc_info=True)
            return None

    # Le wattage du panneau RÉELLEMENT retenu par le catalogue — lu, pas
    # supposé (même sonde que ``balayer_tailles``).
    sonde_avert = []
    sonde = composition_residentielle(
        catalogue, kwc=_AUTO_PANEL_WATT / 1000.0, panel_watt=_AUTO_PANEL_WATT,
        nb_panneaux=1, avec_batterie=False, structure_type='acier',
        taux_tva=taux_tva, avertissements=sonde_avert, deux_options=False,
        marques=marques, ordre_lignes=ordre)
    panel_watt = _num(getattr(sonde, 'panel_watt_reel', 0))
    if panel_watt <= 0:
        return []

    # ── LES BORNES DU CHAMP ──────────────────────────────────────────────────
    panneaux_parite = max(1, int(math.ceil(
        (conso_annuelle / productible_annuel) * 1000.0 / panel_watt)))
    max_champ = min(MAX_PANNEAUX_BALAYAGE,
                    int(math.ceil(panneaux_parite * FACTEUR_MAX_FALAISE)))
    # LA BORNE DE TOIT EST LA CONTENANCE, PAS LE DESSIN (fondateur, 26/08/2026).
    #
    # Elle valait ``plafond_toit_du_devis``, c'est-à-dire le nombre de panneaux
    # que le commercial a DESSINÉS. Or ``max_champ`` n'est pas un décor : c'est
    # le champ maximal que ``champ_minimal`` a le droit de tirer pour REMPLIR
    # une banque. Le caper au dessiné avait donc deux effets, tous deux faux sur
    # un devis calepiné — et c'est EXACTEMENT la conflation qui effondrait la
    # carte « Max » :
    #   1. un palier que le toit peut nourrir était rendu ``remplissage_ok =
    #      False``, grisé « ne se remplirait pas », alors que la géométrie le
    #      permet ;
    #   2. pire, l'échelle S'ARRÊTE à ce palier-là (``break``) — toutes les
    #      capacités au-dessus disparaissaient de l'écran.
    # Le commercial dessine ce dont le client a besoin, puis s'arrête : ce n'est
    # pas la limite du toit. La contenance, elle, est MESURÉE sur le polygone
    # réel. Sans calepinage exploitable, ``None`` ⇒ aucune borne de toit, le
    # comportement d'avant au panneau près.
    contenance_toit = contenance_toit_du_devis(devis)
    if contenance_toit:
        max_champ = min(max_champ, int(contenance_toit))
    max_champ = max(1, max_champ)

    # ── L'ÉCHELLE DES CAPACITÉS, DÉRIVÉE DU CATALOGUE ────────────────────────
    kwc_max = max_champ * panel_watt / 1000.0
    vivier_journal = []
    sonde_batterie = composer(max_champ, kwc_max, None, vivier_journal)
    if sonde_batterie is None:
        return []
    cibles = paliers_stockage_candidats(
        list(getattr(sonde_batterie, 'capacites_batterie_vivier', ()) or ()),
        maximum=MAX_PALIERS_STOCKAGE)
    if not cibles:
        return []

    etude_kwargs = {
        'conso_kwh_mensuelles': conso, 'ville': entrees['ville'],
        'lat': entrees['lat'], 'lon': entrees['lon'],
        'occupation': entrees['occupation'],
        'equipements': entrees['equipements'],
        # QJR45 — MÊME jour de référence que le tableau rangé sur le devis
        # (il vient du MÊME ``EntreesMoteur``) : l'échelle ne peut pas
        # désigner un palier « retenu » calculé sur un autre Ramadan.
        'jour_reference': entrees['jour_reference'],
        # QJR46 (R4-B2.23) — LE CINQUIÈME APPELANT. Cette échelle omettait le
        # barème : ses économies PAR BARREAU étaient calculées sur la grille
        # nationale alors qu'elles atteignent la charge utile PUBLIQUE
        # (``public_views``) à côté d'un tableau calculé, lui, sur la
        # surcharge de la société. Le barème vient maintenant du MÊME
        # ``EntreesMoteur`` que le tableau.
        'tranches': entrees['tranches'],
        'charges_fixes_mad': entrees['charges_fixes_mad'],
    }

    sondes = {}

    def sonder(panneaux):
        """Ce que CE champ sait faire de CHAQUE cible de l'échelle — mémoïsé.

        Un seul parcours des douze jours types sert toutes les capacités
        (``balayer_stockage_horaire``), et les bornes de puissance sont lues
        composition par composition : 15 kWh (TROIS modules de 5 — une banque
        est toujours HOMOGÈNE, fondateur 26/08/2026) et 20 kWh (deux 10)
        n'ont ni le même prix ni la même puissance de décharge.
        """
        if panneaux in sondes:
            return sondes[panneaux]
        if len(sondes) >= MAX_SONDES_ECHELLE:
            return None
        kwc = panneaux * panel_watt / 1000.0
        vues, bornes, reels = {}, {}, {}
        for cible in cibles:
            journal = []
            lignes = composer(panneaux, kwc, cible, journal)
            if lignes is None:
                continue
            vue = _lire_composition(lignes, taux_tva)
            capacite = round(_num(vue.get('batterie_kwh')), 3)
            if capacite <= 0:
                continue
            reels[cible] = capacite
            vues[cible] = vue
            puissances = puissances_batterie_des_lignes(
                lignes, roles=getattr(lignes, 'roles', None))
            bornes[capacite] = {
                'decharge_kw': puissances['packs_decharge_kw'],
                'decharge_onduleur_kw': puissances['ond_decharge_kw'],
                'charge_kw': puissances['charge_kw'],
            }
        if not reels:
            sondes[panneaux] = None
            return None
        energie = balayer_stockage_horaire(
            kwc=kwc, capacites_kwh=sorted(set(reels.values())),
            puissances_par_capacite=bornes, **etude_kwargs)
        if energie is None:
            sondes[panneaux] = None
            return None
        par_capacite = {p['capacite_kwh']: p for p in energie['paliers']}
        par_cible = {}
        for cible, capacite in reels.items():
            palier = par_capacite.get(round(capacite, 2))
            if palier is None:
                continue
            par_cible[cible] = {'capacite_kwh': capacite,
                                'vue': vues[cible], 'palier': palier}
        sondes[panneaux] = {'panneaux': panneaux, 'par_cible': par_cible}
        return sondes[panneaux]

    def remplit(panneaux, cible):
        """Ce champ charge-t-il CETTE banque tous les jours ? ``None`` = pas de
        réponse (palier non composable à cette taille)."""
        entree = ((sonder(panneaux) or {}).get('par_cible') or {}).get(cible)
        if entree is None:
            return None
        return bool(entree['palier']['se_remplit_tous_les_jours'])

    def champ_minimal(cible, depart):
        """Le PLUS PETIT champ qui remplit cette banque, ou ``None``.

        DICHOTOMIE — légitime parce que le surplus quotidien du mois le plus
        faible (LE plafond de remplissage) CROÎT avec la taille du champ : la
        production monte, l'autoconsommation directe est bornée par la
        consommation, donc ce qui reste pour charger ne peut que grandir. On
        vérifie d'abord le champ MAXIMAL : s'il ne remplit pas, aucun ne
        remplira, et c'est la réponse.
        """
        if remplit(max_champ, cible) is not True:
            return None
        bas, haut = max(1, int(depart)), max_champ
        while bas < haut:
            milieu = (bas + haut) // 2
            if remplit(milieu, cible) is True:
                haut = milieu
            else:
                bas = milieu + 1
        return haut

    # La capacité RÉELLEMENT vendue par ce devis (jamais l'optimum du moteur :
    # les lignes sont posées sur un champ arrondi et les deux divergent) et la
    # remise que ce devis applique — lues UNE fois, hors de la boucle.
    capacite_retenue = capacite_batterie_des_lignes(devis)
    facteur_remise = facteur_remise_du_devis(devis)

    def rendu(entree, panneaux, remplissage_ok):
        """Un palier de l'échelle, au format EXACT du contrat."""
        vue, palier = entree['vue'], entree['palier']
        capacite = round(_num(entree['capacite_kwh']), 2)
        # MÊME base de prix que la carte du devis : la composition catalogue
        # est brute, le devis est remisé. Sans ce facteur, l'écart entre deux
        # pilules d'un devis remisé était faux (bases mélangées).
        cout = round(_num(vue.get('cout_ttc')) * facteur_remise, 2)
        economie = round(_num(palier['economie_mad']), 2)
        cinq, dix = _compter_modules_batterie(vue.get('lignes'))
        # A1 (revue adversariale Fable, 26/08/2026) — GÉNÉRALISATION additive :
        # ``nb_modules``/``module_kwh`` couvrent N'IMPORTE QUEL calibre (le
        # Deye BOS-B-Pack16, 16 kWh) là où ``nb_batteries_5``/
        # ``nb_batteries_10`` restent CORRECTS mais MUETS hors 5/10 — les
        # anciennes clés ne bougent pas (rétrocompatibilité contrat PACT10).
        nb_modules, module_kwh = _compter_modules_batterie_generique(
            vue.get('lignes'))
        return {
            'capacite_kwh': capacite,
            'nb_batteries_5': cinq,
            'nb_batteries_10': dix,
            'nb_modules': nb_modules,
            'module_kwh': module_kwh,
            'nb_panneaux': int(panneaux),
            'puissance_kwc': round(panneaux * panel_watt / 1000.0, 3),
            'prix_ttc': cout,
            'economies_annuelles': economie,
            'payback_annees': _arrondi(_payback(cout, economie)),
            'remplissage_ok': bool(remplissage_ok),
            'retenu': bool(capacite_retenue is not None
                           and abs(capacite - _num(capacite_retenue)) < 0.05),
        }

    echelle = []
    capacites_vues = set()
    depart = 1
    apres_retenu = 0
    for cible in cibles:
        panneaux = champ_minimal(cible, depart)
        if panneaux is None:
            # MÊME LE CHAMP MAXIMAL NE REMPLIT PAS. On montre ce palier-là avec
            # son champ et son prix — la limite se lit —, puis on s'arrête : les
            # capacités au-dessus ne se rempliront pas davantage.
            entree = ((sonder(max_champ) or {}).get('par_cible')
                      or {}).get(cible)
            if entree is not None:
                palier = rendu(entree, max_champ, False)
                if palier['capacite_kwh'] not in capacites_vues:
                    capacites_vues.add(palier['capacite_kwh'])
                    echelle.append(palier)
            break
        depart = panneaux
        entree = ((sonder(panneaux) or {}).get('par_cible') or {}).get(cible)
        if entree is None:
            break
        palier = rendu(entree, panneaux, True)
        if palier['capacite_kwh'] in capacites_vues:
            # Deux cibles nominales servies par la MÊME banque réelle : un seul
            # palier à l'écran, jamais deux lignes identiques.
            continue
        capacites_vues.add(palier['capacite_kwh'])
        echelle.append(palier)
        if palier['retenu']:
            apres_retenu = 0
        elif any(p['retenu'] for p in echelle):
            apres_retenu += 1
            if apres_retenu >= MAX_PALIERS_ECHELLE:
                break
        elif len(echelle) >= MAX_PALIERS_ECHELLE + 1:
            # Aucun palier retenu (le moteur n'a désigné aucun optimum avec) :
            # l'écran reste tout de même borné.
            break
    return echelle


# ── LES OUTILS PURS DU BALAYAGE ─────────────────────────────────────────────
# EN BAS À DESSEIN (voir la docstring du module) : cet import et le bloc de
# ré-exports de ``dimensionnement.py`` ferment un cycle que seule cette
# position rend sûre dans les deux ordres de chargement. Ne pas le remonter.
from apps.ventes.dimensionnement import (  # noqa: E402
    FACTEUR_MAX_FALAISE,
    MAX_PALIERS_STOCKAGE,
    MAX_PANNEAUX_BALAYAGE,
    _arrondi,
    _lire_composition,
    _num,
    _payback,
    capacite_utile_batterie,
    paliers_stockage_candidats,
)

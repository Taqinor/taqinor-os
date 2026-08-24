"""L-PCMP (ordre fondateur, 24/08/2026) — « le client doit pouvoir CHANGER son
profil de consommation et voir DIRECTEMENT les économies de chaque
comportement, plus l'installation optimale pour chaque configuration ».

CE QUE CE MODULE EST — ET CE QU'IL N'EST PAS
--------------------------------------------
Il calcule, CÔTÉ SERVEUR et par le MOTEUR EXISTANT, les trois variantes
d'occupation (``presence_jour`` / ``absence_jour`` / ``presence_partielle``,
les trois silhouettes déjà servies par ``courbes_journalieres``) sur les
**mêmes factures RÉELLES** du même client. Aucun nouveau critère, aucun
forfait, aucune règle inventée :

* les économies / taux d'autoconsommation / couverture d'une variante viennent
  de ``etude_horaire.etude_horaire_pour_devis`` — le MÊME appel que le bloc
  canonique du devis, avec la seule silhouette changée (L-PCMP a ajouté pour
  cela un paramètre ``occupation`` à ce point d'entrée) ;
* l'installation OPTIMALE d'une variante vient de
  ``dimensionnement.recommander_taille`` — le MÊME balayage que celui déjà
  persisté sur le devis, avec la seule silhouette changée. On lit sa
  ``recommandation_avec`` quand le devis PORTE du stockage, sa
  ``recommandation`` sinon : « optimal » veut dire optimal POUR LA FAMILLE
  D'INSTALLATION QUE CE DEVIS PROPOSE, jamais un autre produit.

Le profil RÉELLEMENT déclaré par le client reste le bloc PRINCIPAL du devis
(``etude_params['etude_horaire']`` / ``['dimensionnement']``) : ce module ne le
touche jamais, il le RÉUTILISE tel quel (aucun recalcul, aucune dérive
possible) et n'ajoute que les DEUX autres variantes, étiquetées comme telles.

LE COÛT, DIT HONNÊTEMENT
------------------------
Un balayage de dimensionnement compose et fait tourner le moteur horaire sur
CHAQUE taille candidate (plus un mini-balayage de stockage par taille) : c'est
de loin le calcul le plus lourd du devis. Trois passes coûteraient trois fois
ce prix sur le chemin de création. Ce module en fait donc DEUX au maximum (le
profil réel est réutilisé, pas recalculé) et reste **best-effort** de bout en
bout, comme ``electrical_service.rafraichir_conception_electrique_devis`` :
il ne lève jamais, et un devis se crée normalement même si les variantes ne
sont pas calculables. Il ne produit JAMAIS de valeur approchée en remplacement
d'une valeur manquante — une variante non calculable est simplement ABSENTE.
"""
from __future__ import annotations

import logging

from apps.ventes.courbes_journalieres import (
    OCCUPATION_ABSENCE,
    OCCUPATION_PARTIELLE,
    OCCUPATION_PRESENCE,
    occupation_du_devis,
)

logger = logging.getLogger(__name__)

#: Les trois silhouettes proposées au client, dans l'ordre d'affichage de la
#: page (``apps/web/src/lib/dayProfiles.ts`` ``OCCUPANCY_IDS``). Ce n'est pas
#: une nouvelle liste : ce sont les drapeaux que ``courbes_journalieres``
#: possède déjà.
OCCUPATIONS_COMPAREES = (
    OCCUPATION_PRESENCE, OCCUPATION_ABSENCE, OCCUPATION_PARTIELLE,
)

#: Tolérance de comparaison « l'optimal est-il déjà ce que propose le devis ? »
#: en kWc — un demi-panneau du catalogue, donc jamais un écart d'arrondi
#: présenté comme une différence.
TOLERANCE_KWC = 0.30

#: Tolérance en kWh utiles sur la capacité de stockage (même esprit).
TOLERANCE_KWH = 0.30


def _num(valeur, defaut=None):
    """Nombre fini, ou ``defaut`` — jamais une chaîne, jamais un ``NaN``."""
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return defaut
    return nombre if nombre == nombre and nombre not in (
        float('inf'), float('-inf')) else defaut


def _kwc_du_devis(devis):
    """kWc LU sur les lignes du devis — même lecture que
    ``services.rafraichir_etude_horaire_devis`` (``panneaux_et_watt_lu`` sur les
    lignes produit non optionnelles), jamais une seconde dérivation."""
    from apps.ventes.quote_engine.builder import panneaux_et_watt_lu
    lignes = [
        li for li in devis.lignes.select_related(
            'produit', 'produit__fiche_technique').all()
        if getattr(li, 'type_ligne', 'produit') == 'produit'
        and not getattr(li, 'optionnelle', False)
    ]
    nb_panneaux, watt = panneaux_et_watt_lu(lignes)
    if nb_panneaux > 0 and watt:
        return round(nb_panneaux * watt / 1000, 2)
    return None


def _mesures_du_bloc(bloc):
    """Les six chiffres d'affichage d'un bloc horaire, ou ``None``.

    Whitelist STRICTE : rien d'autre que ces clés ne sort d'ici (aucun prix
    d'achat, aucune marge, aucune ligne de composition ne peut fuiter par
    construction)."""
    annuel = (bloc or {}).get('annuel')
    if not isinstance(annuel, dict):
        return None
    mesures = {
        'economie_sans_mad': _num(annuel.get('economie_sans_mad')),
        'economie_avec_mad': _num(annuel.get('economie_avec_mad')),
        'taux_autoconso_sans': _num(annuel.get('taux_autoconso_sans')),
        'taux_autoconso_avec': _num(annuel.get('taux_autoconso_avec')),
        'couverture_sans': _num(annuel.get('couverture_sans')),
        'couverture_avec': _num(annuel.get('couverture_avec')),
    }
    if mesures['economie_sans_mad'] is None:
        return None
    return mesures


def _optimal_du_dimensionnement(dimensionnement, *, avec_batterie,
                                kwc_devis, batterie_devis):
    """Le palier RETENU par le moteur pour cette silhouette, ou ``None``.

    ``avec_batterie`` — le devis porte-t-il du stockage ? Si oui, l'optimal est
    la meilleure combinaison champ + stockage (``recommandation_avec``) ; sinon
    c'est la recommandation SANS batterie (``recommandation``). On ne compare
    jamais une famille d'installation à une autre."""
    if not isinstance(dimensionnement, dict):
        return None
    cle = 'recommandation_avec' if avec_batterie else 'recommandation'
    reco = dimensionnement.get(cle)
    if not isinstance(reco, dict):
        return None
    kwc = _num(reco.get('kwc'))
    if kwc is None or kwc <= 0:
        return None
    batterie = _num(reco.get('batterie_kwh'), 0.0) if avec_batterie else 0.0
    optimal = {
        'panneaux': int(_num(reco.get('panneaux'), 0) or 0) or None,
        'kwc': round(kwc, 2),
        'batterie_kwh': round(batterie or 0.0, 2),
        'avec_batterie': bool(avec_batterie),
        'economie_mad': _num(reco.get(
            'economie_avec_mad' if avec_batterie else 'economie_sans_mad')),
        'motivation': dimensionnement.get(
            'motivation_avec' if avec_batterie else 'motivation') or None,
    }
    # « Votre devis est déjà optimal pour ce profil » — une comparaison
    # NUMÉRIQUE bornée, jamais une affirmation par défaut : sans kWc lisible sur
    # le devis, on ne prétend rien (``None``).
    if kwc_devis is None:
        optimal['identique_au_devis'] = None
    else:
        meme_champ = abs(kwc - kwc_devis) <= TOLERANCE_KWC
        meme_stockage = (
            abs((batterie or 0.0) - (batterie_devis or 0.0)) <= TOLERANCE_KWH)
        optimal['identique_au_devis'] = bool(meme_champ and meme_stockage)
    return optimal


def _dimensionnement_variante(devis, occupation):
    """``recommander_taille`` pour CETTE silhouette — mêmes entrées que
    ``services.rafraichir_dimensionnement_devis``, seule l'occupation change.

    Aucun écrit : le tableau d'une VARIANTE n'est jamais persisté comme le
    dimensionnement du devis (ce serait écraser le profil réel du client)."""
    from apps.crm.selectors import lead_bills_for_devis, site_location_for_devis
    from apps.ventes.courbes_journalieres import equipements_du_devis
    from apps.ventes.dimensionnement import recommander_taille
    from apps.ventes.etude_horaire import profil_depuis_factures

    company = getattr(devis, 'company', None)
    if company is None:
        return None
    bills = lead_bills_for_devis(devis) or {}
    etude_params = getattr(devis, 'etude_params', None) or {}
    conso, source_conso, _detail = profil_depuis_factures(
        facture_hiver_mad=bills.get('facture_hiver'),
        facture_ete_mad=bills.get('facture_ete'),
        ete_differente=bills.get('ete_differente'),
        factures_mensuelles_mad=etude_params.get('factures_mensuelles_reelles'),
        conso_kwh_mensuelles=etude_params.get('conso_kwh_mensuelles'))
    if not conso:
        return None
    localisation = site_location_for_devis(devis) or {}
    return recommander_taille(
        company=company, conso_kwh_mensuelles=conso,
        ville=localisation.get('site_ville'),
        lat=localisation.get('gps_lat'), lon=localisation.get('gps_lng'),
        occupation=occupation, equipements=equipements_du_devis(devis),
        source_conso=source_conso)


def calculer_profils_comparatifs(devis):
    """Le bloc ``profils_comparatifs``, ou ``None`` — jamais d'exception.

    ``None`` (⇒ clé ABSENTE) dès que l'ancrage réel manque : devis non
    résidentiel, pas de puissance lisible, pas de facture, pas de localisation.
    Une variante individuellement non calculable est OMISE de la liste, jamais
    remplie d'approximations.
    """
    try:
        return _calculer_profils_comparatifs(devis)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning('profils_comparatifs indisponible sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None


def _calculer_profils_comparatifs(devis):
    """Cœur de :func:`calculer_profils_comparatifs`."""
    from apps.ventes.etude_horaire import (
        capacite_batterie_du_devis, etude_horaire_pour_devis)

    mode = (getattr(devis, 'mode_installation', None) or '').strip().lower()
    if mode != 'residentiel':
        return None
    if getattr(devis, 'company', None) is None:
        return None

    kwc = _kwc_du_devis(devis)
    if not kwc:
        return None

    etude_params = getattr(devis, 'etude_params', None) or {}
    batterie_devis = _num(capacite_batterie_du_devis(devis), 0.0) or 0.0
    avec_batterie = batterie_devis > 0

    profil_reel, source_reelle = occupation_du_devis(
        devis, {'mode_installation': mode})

    profils = []
    for occupation in OCCUPATIONS_COMPAREES:
        est_reel = occupation == profil_reel
        # LE PROFIL RÉEL N'EST JAMAIS RECALCULÉ : on réutilise les blocs déjà
        # persistés (le principal reste inchangé, bit pour bit) — c'est aussi
        # ce qui ramène le coût de cette fonctionnalité de trois balayages à
        # deux.
        if est_reel:
            bloc = etude_params.get('etude_horaire')
            if not isinstance(bloc, dict):
                bloc = etude_horaire_pour_devis(devis, kwc=kwc)
            dimensionnement = etude_params.get('dimensionnement')
            if not isinstance(dimensionnement, dict):
                dimensionnement = _dimensionnement_variante(devis, occupation)
        else:
            bloc = etude_horaire_pour_devis(
                devis, kwc=kwc, occupation=occupation)
            dimensionnement = _dimensionnement_variante(devis, occupation)

        mesures = _mesures_du_bloc(bloc)
        if mesures is None:
            continue
        entree = {
            'occupation': occupation,
            'est_profil_reel': bool(est_reel),
            **mesures,
            'optimal': _optimal_du_dimensionnement(
                dimensionnement, avec_batterie=avec_batterie,
                kwc_devis=kwc, batterie_devis=batterie_devis),
        }
        profils.append(entree)

    if not profils:
        return None
    return {
        # Ce que le devis PROPOSE — le point de comparaison de tous les
        # « déjà optimal » ci-dessus.
        'kwc_devis': kwc,
        'batterie_kwh_devis': round(batterie_devis, 2),
        'avec_batterie': bool(avec_batterie),
        'profil_reel': profil_reel,
        'profil_reel_source': source_reelle,
        'profils': profils,
        'source': 'moteur_horaire_dimensionnement',
    }


def rafraichir_profils_comparatifs_devis(devis, *, force=False):
    """Pose ``etude_params['profils_comparatifs']`` — best-effort, jamais
    bloquant, n'écrit QUE ``etude_params`` (règle #4 : ni statut, ni lignes,
    ni totaux).

    Un bloc devenu incalculable est RETIRÉ plutôt que laissé périmé (règle Z2,
    même politique que ``rafraichir_etude_horaire``).
    """
    try:
        bloc = calculer_profils_comparatifs(devis)
        etude = dict(getattr(devis, 'etude_params', None) or {})
        if bloc is None:
            if 'profils_comparatifs' not in etude:
                return None
            etude.pop('profils_comparatifs', None)
        else:
            if not force and etude.get('profils_comparatifs') == bloc:
                return bloc
            etude['profils_comparatifs'] = bloc
        devis.etude_params = etude
        devis.save(update_fields=['etude_params'])
        return bloc
    except Exception:  # noqa: BLE001 — jamais bloquant pour un devis
        logger.warning('profils_comparatifs non rafraîchis sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None

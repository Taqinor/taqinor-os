"""ACAL997 (D-ACAL-36) — le RENDEMENT DE LA POSE RÉELLE servi au devis.

Module frère de ``selectors.py`` (lu par ``apps.ventes``) : forme du contrat
``contract_samples/calepinage_productible_pose.json`` (ACAL996). Lecture
PURE ; la tolérance de kWc vient TOUJOURS de l'appelant (registre de
cohérence de ventes), jamais d'ici. Un résultat incomplet n'est jamais servi
comme production (``perime: True``).
"""
from .selectors import (
    MOTIF_CONCEPTION_DIVERGENTE, _calepinage_lisible_pour_devis,
    resultat_servi, variante_portant_le_devis)

MOTIF_SURFACES = ('une surface posée n’a pas été simulée : '
                  'relancez la simulation')
#: ACAL1008 — rien d'une conception « rapide » (ACAL1006) ne sort côté client.
MOTIF_CONCEPTION_RAPIDE = ("conception rapide non vérifiée : "
                           "enregistrez-la dans l'atelier")


def conception_rapide(calepinage):
    """ACAL1008 — vrai si personne n'a encore vérifié ce calepinage."""
    return getattr(calepinage, 'etat_conception', None) == 'rapide'


_CLES_PAN = ('pan', 'kwc', 'inclinaison_deg', 'azimut_deg',
             'specific_yield_kwh_kwc')


def _f(valeur):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def contrat_depuis_servi(servi, kwc_document, *, tolerance_kwc_ratio):
    """Le contrat ACAL996 depuis un ``resultat_servi`` ; ``None`` sans
    simulation. Pure (testée sans base)."""
    servi = servi or {}
    rendu = {'perime': True, 'motif': '', 'source': 'calepinage_enregistre',
             'calcule_le': servi.get('calcule_le'), 'kwc_simule': None,
             'kwc_document': kwc_document, 'p50_kwh': None,
             'kwh_kwc_annuel': None, 'kwh_kwc_mensuel': [],
             'complete': False, 'etapes_omises': [],
             'pertes_et_ombrage_inclus': False,
             'couvre_toutes_les_surfaces': False, 'pans': []}
    if servi.get('simulation_perimee'):
        return dict(rendu, motif=servi.get('motif') or '')
    production = servi.get('production')
    production = production if isinstance(production, dict) else {}
    total = production.get('total') or {}
    kwc, p50 = _f(total.get('kwc')), _f(total.get('p50_kwh'))
    if not servi.get('simule') or not kwc or p50 is None:
        return None
    complete = total.get('complete') is True
    ecart = abs(kwc - kwc_document) / kwc_document if kwc_document else 1.0
    couvre = ecart <= tolerance_kwc_ratio
    motif = ''
    if not complete:
        motif = 'résultat incomplet : %d pertes non renseignées' % len(
            total.get('socle_manquant') or ())
    elif not couvre:
        motif = MOTIF_SURFACES
    cascade = servi.get('cascade') or {}
    rendu.update(
        perime=bool(motif), motif=motif, kwc_simule=kwc, p50_kwh=p50,
        kwh_kwc_annuel=round(p50 / kwc, 1),
        kwh_kwc_mensuel=[round((_f(m.get('p50_kwh')) or 0.0) / kwc, 1)
                         for m in production.get('mensuel') or ()],
        complete=complete, pertes_et_ombrage_inclus=complete,
        etapes_omises=list(cascade.get('etapes_omises') or ()),
        couvre_toutes_les_surfaces=couvre,
        pans=[{c: p.get(c) for c in _CLES_PAN}
              for p in production.get('par_pan') or ()
              if isinstance(p, dict)])
    return rendu


def _kwc_document(porteur):
    from .services.production import _pans_du_layout

    pans = _pans_du_layout(porteur.roof_layout)
    return round(sum(p['kwc'] or 0.0 for p in pans), 3)


def productible_pose_du_calepinage(calepinage, *, variante=None,
                                   tolerance_kwc_ratio):
    """Le productible posé d'un calepinage (sans devis) — même chiffre que
    le futur devis (C2)."""
    if conception_rapide(calepinage):  # ACAL1008 — jamais servi au devis
        return None
    return contrat_depuis_servi(
        resultat_servi(calepinage, variante=variante),
        _kwc_document(variante or calepinage),
        tolerance_kwc_ratio=tolerance_kwc_ratio)


def productible_pose_servi(devis_id, company, *, tolerance_kwc_ratio):
    """Le productible posé de la conception d'un devis, ``None`` ou périmé —
    mêmes verdicts de fraîcheur qu'``ombrage_servi`` (patron)."""
    calepinage = _calepinage_lisible_pour_devis(devis_id, company)
    if calepinage is None or conception_rapide(calepinage):
        return None
    variante = variante_portant_le_devis(calepinage, devis_id)
    porteur = variante or calepinage
    if str(calepinage.devis_id) == str(devis_id) or variante is not None:
        from apps.ventes.selectors import get_devis_by_pk
        from apps.ventes.selectors_calepinage import _conception_a_jour

        if _conception_a_jour(get_devis_by_pk(devis_id), porteur) is False:
            return contrat_depuis_servi(
                {'simulation_perimee': True,
                 'motif': MOTIF_CONCEPTION_DIVERGENTE},
                _kwc_document(porteur),
                tolerance_kwc_ratio=tolerance_kwc_ratio)
    return productible_pose_du_calepinage(
        calepinage, variante=variante,
        tolerance_kwc_ratio=tolerance_kwc_ratio)


def _reseau_interdit(fournisseur):
    """Vrai sous la suite de tests quand ``fournisseur`` est le fournisseur réel
    d'année type (PVGIS) : aucun test ne sort sur le réseau par le devis."""
    from django.conf import settings
    return bool(getattr(settings, 'TESTING', False)
                and getattr(fournisseur, '__name__', '') == 'temperatures_tmy')


def froid_dimensionnement_au_point(lat, lng, *, fournisseur=None):
    """ADEV122 (D-ACAL-80) — la température froide des chaînes au point d'un
    site, pour le devis : LA règle partagée
    (``core.electrique.types.froid_de_dimensionnement``) sur le minimum de
    l'année type lu par le MÊME fournisseur que le calcul électrique du
    calepinage (``services.electrique``, cache PVGIS partagé — jamais un
    second appel météo). Sans point ni année type : −5 °C, dit. Ne lève
    jamais (un service météo en panne ne bloque pas un devis)."""
    from core.electrique.types import froid_de_dimensionnement
    from .services import electrique
    if fournisseur is None:
        fournisseur = electrique._fournisseur_temperatures()
        # Sous la suite de tests, le fournisseur RÉEL (PVGIS) n'est jamais appelé par le devis : la longueur des
        # chaînes d'un test ne dépend pas du réseau (critique finale du 23/11). Un test qui veut le froid du site
        # injecte son fournisseur.
        if _reseau_interdit(fournisseur):
            return froid_de_dimensionnement(None)
    tmy = electrique._depuis_fournisseur({'lat': lat, 'lng': lng}, fournisseur)
    return froid_de_dimensionnement(tmy[0] if tmy else None)

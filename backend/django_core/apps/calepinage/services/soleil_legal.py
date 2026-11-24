"""ACAL730 — heure solaire vraie ↔ heure légale d'UN jour, au site du calepinage.

Le calcul est celui du noyau (``core.calepinage.soleil.correspondance_heure_legale``,
ACAL718) ; ce module ne fait que lui donner ses entrées RÉELLES : la longitude
de l'épingle (document, sinon lead — ``selectors.contexte_geographique``) et le
décalage UTC du jour lu dans ``zoneinfo`` pour le fuseau SAISI
(``site.fuseau_du_site``). Le fuseau n'est JAMAIS déduit d'une longitude :
absent, la correspondance est refusée en nommant ``site.fuseau``.
"""
from __future__ import annotations

import datetime

__all__ = ['SoleilLegalRefuse', 'MOTIF_SANS_FUSEAU', 'MOTIF_SANS_EPINGLE',
           'correspondance_du_jour']

#: Motifs servis tels quels (409) : la donnée manquante est NOMMÉE.
MOTIF_SANS_FUSEAU = ("fuseau du site non renseigné : aucune heure légale "
                     "n'est calculée")
MOTIF_SANS_EPINGLE = (
    "Position du site inconnue : cherchez l'adresse du client puis cliquez "
    "« Localiser » (ou zoomez jusqu'au toit avant de le tracer), ou "
    "renseignez la ville du lead — sans elle, aucune heure solaire n'est "
    "calculée.")


class SoleilLegalRefuse(ValueError):
    """Refus nommé : ``champ`` = la clé fautive (``site.pin``, ``site.fuseau``)."""

    def __init__(self, champ, motif):
        super().__init__(motif)
        self.champ, self.motif = champ, motif


def _site(calepinage):
    """``(longitude, reference)`` — T4-U4-013 : LA MÊME fonction que la
    simulation (``site.point_du_site``) : l'épingle posée, sinon la ville de
    référence du lead ou du client (dite), sinon ``(None, None)``."""
    from ..selectors import contexte_geographique
    from .site import point_du_site

    _lat, lon, reference = point_du_site(
        getattr(calepinage, 'roof_layout', None),
        lambda: contexte_geographique(calepinage))
    return lon, reference


def correspondance_du_jour(calepinage, jour, *, reglages=None):
    """Le dict servi par ``GET soleil-legal/`` pour ``jour`` (``datetime.date``).

    ``reglages`` : les réglages société déjà lus (tests) ; à défaut, lus par
    ``electrique.parametres_societe``. Lève ``SoleilLegalRefuse``.
    """
    from core.calepinage.exceptions import EntreeInvalide
    from core.calepinage.soleil import correspondance_heure_legale

    from .site import decalage_utc_minutes, fuseau_du_site

    longitude, reference = _site(calepinage)
    if longitude is None:
        raise SoleilLegalRefuse('site.pin', MOTIF_SANS_EPINGLE)
    if reglages is None:
        from .electrique import parametres_societe

        reglages = parametres_societe(calepinage)
    fuseau = fuseau_du_site(dict(reglages.get('imagerie') or {}),
                            company=getattr(calepinage, 'company', None))
    midi_local = datetime.datetime.combine(jour, datetime.time(12, 0))
    decalage = decalage_utc_minutes(fuseau['fuseau'], midi_local)
    if decalage is None:
        raise SoleilLegalRefuse('site.fuseau', MOTIF_SANS_FUSEAU)
    try:
        calcul = correspondance_heure_legale(
            longitude, annee=jour.year, mois=jour.month, jour=jour.day,
            decalage_utc_min=decalage)
    except EntreeInvalide as refus:  # longitude hors domaine
        raise SoleilLegalRefuse('site.pin', str(refus)) from refus
    return {
        'date': jour.isoformat(),
        'fuseau': fuseau['fuseau'],
        'fuseau_source': fuseau['provenance'],
        'longitude_deg': longitude,
        'decalage_utc_min': decalage,
        'equation_du_temps_min': round(calcul.equation_du_temps_min, 1),
        'ecart_legal_moins_solaire_min': round(
            calcul.ecart_legal_moins_solaire_min, 1),
        # Heure décimale au dixième de minute (1/600 h).
        'midi_solaire_legal_h': round(calcul.midi_solaire_legal_h * 600) / 600,
        'mention': fuseau['mention'],
        # T4-U4-013 — sans épingle posée, le site est la ville de référence :
        # DITE (``{ville_reference, libelle}``), ``None`` quand l'épingle sert.
        'site_reference': (None if reference is None else {
            'ville_reference': reference['ville_reference'],
            'libelle': reference['libelle']}),
    }

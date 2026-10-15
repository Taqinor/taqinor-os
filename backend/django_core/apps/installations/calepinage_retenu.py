"""ACAL274 — le bloc « calepinage retenu » d'un chantier : kWc et modules
VENDUS (lignes du devis), dessin du calepinage et écart.

Sorti de ``selectors.py`` (fichier-mur) ; ``selectors.calepinage_retenu_du_chantier``
délègue ici. Lecture seule ; cross-app par les sélecteurs/façades uniquement.
"""

import logging

logger = logging.getLogger(__name__)


def bloc_calepinage_retenu(installation):
    """Le bloc ``{calepinage_id, kwc, nb_modules, kwc_source, dessin_kwc,
    ecart_kwc, planche_url, plan_pose_url}`` d'UN chantier, ou ``None`` sans
    devis ou sans calepinage à variante retenue."""
    from apps.calepinage.selectors import calepinage_retenu_pour_devis

    if installation is None or not installation.devis_id:
        return None
    bloc = calepinage_retenu_pour_devis(installation.devis_id, installation.company)
    if bloc is None:
        return None
    # D-ACAL-2 — le chantier annonce ce qui est VENDU (lignes du devis) ; le
    # dessin du calepinage est donné comme tel, avec l'écart.
    vendu_kwc, vendu_modules = _vendu_du_devis(installation.devis)
    dessin_kwc = _dessin_kwc(installation)
    kwc, nb_modules, source = bloc['kwc'], bloc['nb_modules'], 'calepinage'
    if vendu_kwc is not None:
        kwc, source = vendu_kwc, 'devis'
        if vendu_modules is not None:
            nb_modules = vendu_modules
    ecart = (round(dessin_kwc - kwc, 2)
             if source == 'devis' and dessin_kwc is not None else None)
    return {
        'calepinage_id': bloc['id'],
        'kwc': kwc,
        'nb_modules': nb_modules,
        'kwc_source': source,
        'dessin_kwc': dessin_kwc,
        'ecart_kwc': ecart,
        'planche_url': bloc['planche_url'],
        'plan_pose_url': f'/ventes/devis/{installation.devis_id}/3d',
    }


def _vendu_du_devis(devis):
    """ACAL274 — ``(kwc, nb_modules)`` VENDUS, lus sur les lignes du devis par
    la règle unique ``ventes`` (``puissance_kwc_du_devis``) ; ``(None, None)``
    quand les lignes ne disent rien (jamais un chiffre supposé)."""
    from apps.ventes.services import puissance_kwc_du_devis

    if devis is None:
        return None, None
    try:
        kwc = puissance_kwc_du_devis(devis)
    except Exception:  # noqa: BLE001 — un bloc de fiche ne casse jamais le détail
        logger.warning("calepinage_retenu : kWc vendu illisible, bloc dégradé", exc_info=True)
        return None, None
    if not kwc:
        return None, None
    modules = None
    try:
        from apps.ventes.selectors import modules_vendus_du_devis

        modules = modules_vendus_du_devis(devis)
    except Exception:  # noqa: BLE001 — le compte de modules est facultatif
        logger.warning("calepinage_retenu : modules du devis illisibles", exc_info=True)
        modules = None
    return round(float(kwc), 2), modules


def _dessin_kwc(installation):
    """ACAL274 — kWc du DESSIN (``mesures_du_document`` sur le document du
    calepinage du devis), ou ``None`` ; lu par ``apps.calepinage.selectors``."""
    from apps.calepinage.selectors import (
        calepinage_du_devis, mesures_du_calepinage)

    calepinage = calepinage_du_devis(installation.devis_id, installation.company)
    if calepinage is None:
        return None
    kwc = (mesures_du_calepinage(calepinage) or {}).get('kwc')
    return round(float(kwc), 2) if kwc else None

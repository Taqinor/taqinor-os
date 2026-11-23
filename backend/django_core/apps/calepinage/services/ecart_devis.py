"""ACAL104 / ACAL1274 — l'écart entre la production IMPRIMÉE au client
(moteur du devis) et le P50 de l'étude technique du calepinage, servi par
``GET resultat/`` (``ecart_devis``, contrat ``calepinage_resultat.json``).
Extrait de ``electrique.py`` (fichier-mur) ; lecture pure, jamais un rendu."""
from __future__ import annotations


#: ACAL104 — la mention publiée avec l'écart (contrat
#: ``calepinage_resultat.json``, ``exemple_ecart_devis``), mot pour mot.
MENTION_ECART_DEVIS = ("Production imprimée au client = moteur du devis "
                       "(D-ACAL-6) ; P50 = étude technique du calepinage")


def _ecart_devis(calepinage, p50):
    """ACAL104 (C-ACAL-101) — ``{devis, reference, production_devis_kwh,
    p50_calepinage_kwh, ecart_pct, mention}`` ou ``None``.

    ``production_devis_kwh`` est la figure du devis (recalée sur les lignes —
    ``figure_production_du_devis``), LUE par ``apps.ventes.selectors.
    production_attendue_pour_devis`` — JAMAIS un rendu du devis ici (boucle
    devis → ombrage servi → ce résultat ; profil créé, ACON87) ; ``ecart_pct`` = (P50 − devis) /
    devis, au dixième. Jamais l'inverse : le devis ne lit pas le P50
    (D-ACAL-6). ``None`` sans devis lié (ou d'une autre société), sans P50
    servi (jamais simulé, ou périmé) ou sans production au devis. LECTURE
    PURE."""
    devis_id = getattr(calepinage, 'devis_id', None)
    if not devis_id or not isinstance(p50, (int, float)) or isinstance(p50, bool):
        return None
    from apps.ventes.selectors import get_devis_by_pk, production_attendue_pour_devis
    from apps.ventes.selectors_calepinage import _conception_a_jour

    if ((devis := get_devis_by_pk(devis_id)) is None
            or devis.company_id != getattr(calepinage, 'company_id', None)
            or _conception_a_jour(devis, calepinage) is False  # ACON27 — autre conception
            or not _figure_stockee_imprimee(devis)):  # ACAL1274
        return None
    production = production_attendue_pour_devis(devis_id)
    if production is None or production <= 0:
        return None
    production = float(production)
    p50 = float(p50)
    return {
        'devis': devis.pk,
        'reference': devis.reference or '',
        'production_devis_kwh': production,
        'p50_calepinage_kwh': p50,
        'ecart_pct': round((p50 - production) / production * 100.0, 1),
        'mention': MENTION_ECART_DEVIS,
    }


def _figure_stockee_imprimee(devis):
    """ACAL1274 (T2-F2-RESU-024) — la figure lue sans rendu
    (``production_attendue_pour_devis``) est-elle celle que le PDF imprime ?
    Non en C&I ou en agricole (moteur C&I / aucun kWh), ni quand le
    calepinage l'a posée aux règles corrigées (AMOT15 : le moteur du devis
    la recalcule) — le chiffre imprimé se lit alors dans ``chiffrage``."""
    from apps.ventes.domain.etude_schema import PRODUCTION_CALEPINAGE
    from apps.ventes.domain.regles_calcul import calcul_corrige
    if (getattr(devis, 'mode_installation', None) or 'residentiel') != 'residentiel':
        return False
    source = (getattr(devis, 'etude_params', None) or {}).get('production_source')
    return not (source == PRODUCTION_CALEPINAGE and calcul_corrige(devis))

"""ACAL104 + ACAL1915 — l'écart entre la production du DEVIS lié et le P50 de
la simulation de la pose, ou la phrase qui dit pourquoi il manque.

Extrait de ``services/electrique.py`` (ACAL1915 : le module dépasse 2 000
lignes). LECTURE PURE : la figure du devis est LUE par
``apps.ventes.selectors.production_attendue_pour_devis`` — jamais un rendu du
devis (boucle devis → ombrage servi → ce résultat ; profil créé, ACON87) —, et
le devis ne lit jamais le P50 (D-ACAL-6).
"""
from __future__ import annotations

#: ACAL104 + ACAL1755 (D-ACAL-86, D-ACAL-96) — la mention publiée avec l'écart
#: (contrat ``calepinage_resultat.json``, ``exemple_ecart_devis``), mot pour mot.
MENTION_ECART_DEVIS = ("Deux chiffres : celui du devis déjà remis au client et celui de la "
                       "simulation de la pose, le plus réaliste. Le devis envoyé n'est pas "
                       "modifié : une révision est proposée.")

#: ACAL1915 — la garde en cause quand un devis est LIÉ et qu'aucun écart n'est
#: servi, dans l'ordre où elles sont évaluées (contrat ``acal1915_motifs``).
_PREFIXE = 'Écart au devis non calculé : '
MOTIFS_ECART_DEVIS = {
    'simulation': _PREFIXE + "la pose n'a pas de simulation à jour. Lancez la simulation.",
    'devis_introuvable': _PREFIXE + 'le devis lié est introuvable dans votre société.',
    'a_resynchroniser': _PREFIXE + 'devis à resynchroniser, il décrit une autre conception que cette pose.',
    'production_recalculee_au_rendu': _PREFIXE + (
        'ce devis imprime une production recalculée à son rendu (règles corrigées, ou chiffrage '
        "C&I ou agricole) ; l'atelier ne la lit pas sans rendre le devis."),
    'sans_production': _PREFIXE + 'le devis ne porte aucune production annuelle.',
}


def ecart_devis_et_motif(calepinage, p50):
    """``(ecart_devis, ecart_devis_motif)``.

    ``ecart_devis`` = ``{devis, reference, production_devis_kwh,
    p50_calepinage_kwh, ecart_pct, mention}`` ou ``None`` ; ``ecart_pct`` =
    (P50 − devis) / devis, au dixième. ``ecart_devis_motif`` = ``''`` sans
    devis lié ou quand l'écart est servi ; sinon la phrase de la PREMIÈRE
    garde en cause : pas de P50 servi (jamais simulé, ou périmé), devis absent
    ou d'une autre société, conception différente (ACON27), figure que le PDF
    n'imprime pas (ACAL1274), aucune production au devis."""
    devis_id = getattr(calepinage, 'devis_id', None)
    if not devis_id:
        return None, ''
    if not isinstance(p50, (int, float)) or isinstance(p50, bool):
        return None, MOTIFS_ECART_DEVIS['simulation']
    from apps.ventes.selectors import get_devis_by_pk, production_attendue_pour_devis
    from apps.ventes.selectors_calepinage import _conception_a_jour, figure_stockee_imprimee

    devis = get_devis_by_pk(devis_id)
    if devis is None or devis.company_id != getattr(calepinage, 'company_id', None):
        return None, MOTIFS_ECART_DEVIS['devis_introuvable']
    if _conception_a_jour(devis, calepinage) is False:  # ACON27
        return None, MOTIFS_ECART_DEVIS['a_resynchroniser']
    if not figure_stockee_imprimee(devis):  # ACAL1274
        return None, MOTIFS_ECART_DEVIS['production_recalculee_au_rendu']
    production = production_attendue_pour_devis(devis_id)
    if production is None or production <= 0:
        return None, MOTIFS_ECART_DEVIS['sans_production']
    production, p50 = float(production), float(p50)
    return {
        'devis': devis.pk,
        'reference': devis.reference or '',
        'production_devis_kwh': production,
        'p50_calepinage_kwh': p50,
        'ecart_pct': round((p50 - production) / production * 100.0, 1),
        'mention': MENTION_ECART_DEVIS,
    }, ''


def cles_ecart_devis(calepinage, p50):
    """Les deux clés racine du résultat servi (``GET resultat/``)."""
    ecart, motif = ecart_devis_et_motif(calepinage, p50)
    return {'ecart_devis': ecart, 'ecart_devis_motif': motif}


def _ecart_devis(calepinage, p50):
    """ACAL104 (C-ACAL-101) — l'écart seul, ou ``None`` (voir
    :func:`ecart_devis_et_motif`)."""
    return ecart_devis_et_motif(calepinage, p50)[0]

"""ACAL565 — la feuille « Plan de lestage » (toit plat lesté), en PDF A3.

Même chaîne que le plan de pose (``planche.rendre_plan_pose_pdf``) : la
géométrie STOCKÉE (``geometrie_de_planche``), un SVG A3, ``html_de_planche``
puis ``core.pdf.render_pdf``. Chaque module d'un pan de toit est teinté
selon sa zone (centre, rive, coin — ``lestage_zones.repartir_modules``,
ACAL564) et porte le lest ADDITIONNEL saisi pour sa zone (hors centre).

Rien n'est calculé ici : les largeurs et les lests sont les VALEURS SAISIES
par la société, avec leur source, et la feuille le dit (« non calculées »).
Refus nommé (jamais une feuille muette) : conception absente, système non
lesté, paramètre non saisi, aucun module. Aucun montant (pièce de chantier).
"""
from __future__ import annotations

import textwrap
from html import escape

from .lestage_zones import (
    CLE_ZONES_DE_POSE, PARAMETRES_ZONES_DE_POSE, repartir_modules,
)
from .planche import (
    FORMAT_A3_MM, GRIS_TEXTE, MARGE_MM, NOIR, PlancheRefusee, _n, _polygone,
    _svg_a3, _transformation, _verifier_absence_d_argent, coins_du_module,
    geometrie_de_planche, html_de_planche, pied_du_calepinage,
)

__all__ = ['MODE_LESTE', 'PlanLestageRefuse', 'motif_plan_lestage',
           'rendre_plan_lestage_pdf', 'svg_de_plan_lestage']

#: ``SystemeFixation.ModePose.TOIT_PLAT_LESTE``.
MODE_LESTE = 'toit_plat_leste'

#: zone → (libellé, remplissage, contour) — trois teintes lisibles en N&B.
TEINTES = {
    'centre': ('Centre', '#e8f5e9', '#2e7d32'),
    'rive': ('Rive', '#fff3e0', '#ef6c00'),
    'coin': ('Coin', '#ffcdd2', '#c62828'),
}

SANS_CONCEPTION = ("Aucune conception enregistrée : le plan de lestage se "
                   "dessine sur la géométrie stockée.")
SANS_MODULE = ("Aucun module posé sur un pan de toit : aucun lest à "
               "répartir.")


class PlanLestageRefuse(PlancheRefusee):
    """Refus NOMMÉ du plan de lestage (409, champ fautif)."""


def _systeme(calepinage):
    from .fixation import resoudre_systeme

    systeme, refus = resoudre_systeme(
        getattr(calepinage, 'company', None), None, calepinage=calepinage)
    if systeme is None:
        message = refus[0]['message'] if refus else (
            "Aucun système de fixation retenu pour ce calepinage.")
        raise PlanLestageRefuse(message, champ='systeme')
    if systeme.mode_pose != MODE_LESTE:
        raise PlanLestageRefuse(
            f"Le système de fixation « {systeme.libelle or systeme.code} » "
            f"n'est pas lesté (mode de pose : {systeme.get_mode_pose_display()}"
            ") : aucun plan de lestage.", champ='systeme')
    return systeme


def _preparer(calepinage):
    """``(geometrie, repartition, zones_de_pose)`` ou :class:`PlanLestageRefuse`."""
    from ..selectors import parametres_de_societe

    try:
        geometrie = geometrie_de_planche(
            getattr(calepinage, 'roof_layout', None))
    except PlancheRefusee:
        raise PlanLestageRefuse(SANS_CONCEPTION, champ='roof_layout')
    _systeme(calepinage)
    section = (parametres_de_societe(getattr(calepinage, 'company', None))
               or {}).get('lestage') or {}
    zones = section.get(CLE_ZONES_DE_POSE) or {}
    repartition = repartir_modules(geometrie.get('pans') or [], zones)
    if not repartition['disponible']:
        noms = ', '.join(m['libelle'] for m in repartition['manquants'])
        raise PlanLestageRefuse(
            f"Paramètre(s) de lestage non saisi(s) : {noms} (Réglages › "
            "Lestage).", champ=repartition['manquants'][0]['cle'])
    if not repartition['pans']:
        raise PlanLestageRefuse(SANS_MODULE, champ='modules')
    return geometrie, repartition, zones


def motif_plan_lestage(calepinage):
    """``None`` si le plan se rend, sinon le motif (inventaire ``sorties/``)."""
    try:
        _preparer(calepinage)
    except PlancheRefusee as refus:
        return str(refus)
    return None


def _kg(valeur):
    """« 12,5 kg » — la valeur saisie, sans zéro inutile."""
    texte = ('%.3f' % float(valeur)).rstrip('0').rstrip('.')
    return texte.replace('.', ',') + ' kg'


def _corps(calepinage, geometrie, repartition, zones):
    vers_feuille, _echelle = _transformation(geometrie['etendue'])
    par_pan = {p['pan']: p for p in repartition['pans']}
    corps = []
    for pan in geometrie.get('pans') or []:
        corps.append(_polygone(pan['points'], vers_feuille, contour=NOIR))
        for module in (par_pan.get(pan['repere']) or {}).get('modules', []):
            _libelle, fond, trait = TEINTES[module['zone']]
            centre = tuple(module['centre'])
            coins = coins_du_module(pan, centre)
            if coins:
                corps.append(_polygone(coins, vers_feuille, contour=trait,
                                       remplissage=fond))
            x, y = vers_feuille(centre)
            if not coins:
                corps.append('<circle cx="%s" cy="%s" r="1.6" fill="%s" '
                             'stroke="%s" stroke-width="0.3" />'
                             % (_n(x), _n(y), fond, trait))
            if module['zone'] != 'centre':
                corps.append('<text x="%s" y="%s" font-size="2.2" '
                             'text-anchor="middle" fill="%s">%s</text>'
                             % (_n(x), _n(y + 0.8), NOIR,
                                escape(_kg(module['lest_kg']))))
    corps.extend(_bandeau(calepinage, repartition, zones))
    pied = pied_du_calepinage(calepinage)
    if pied:
        corps.append('<text x="%s" y="%s" font-size="3" fill="%s">%s</text>'
                     % (_n(MARGE_MM), _n(FORMAT_A3_MM[1] - 3.5), GRIS_TEXTE,
                        escape(pied.split('\n')[0])))
    return corps


def _bandeau(calepinage, repartition, zones):
    """Titre, légende des trois teintes avec le total par zone, mention."""
    totaux = {z: sum(p[{'centre': 'centres', 'rive': 'rives',
                        'coin': 'coins'}[z]] for p in repartition['pans'])
              for z in TEINTES}
    lest = {z: sum(m['lest_kg'] for p in repartition['pans']
                   for m in p['modules'] if m['zone'] == z) for z in TEINTES}
    societe = getattr(getattr(calepinage, 'company', None), 'nom', '') or \
        'la société'
    sources = '; '.join(
        f"{libelle} : {zones[cle]['source']}"
        for cle, (libelle, _s) in PARAMETRES_ZONES_DE_POSE.items())
    lignes = [f'Plan de lestage — {calepinage}'] + [
        f'{TEINTES[z][0]} : {totaux[z]} module(s), lest additionnel '
        f'{_kg(lest[z])}' for z in TEINTES] + [
        f"Lest additionnel total : {_kg(repartition['total_lest_kg'])}",
        f'Valeurs saisies par {societe}, référence {sources} — non '
        'calculées.']
    _verifier_absence_d_argent('\n'.join(lignes[1:]))
    # La mention (sources saisies) se replie dans la largeur du bandeau.
    lignes = lignes[:-1] + textwrap.wrap(lignes[-1], 52)
    x = FORMAT_A3_MM[0] - MARGE_MM - 80
    sortie = []
    for rang, ligne in enumerate(lignes):
        y = MARGE_MM + 6 + rang * 6
        zone = list(TEINTES)[rang - 1] if 1 <= rang <= len(TEINTES) else None
        if zone:
            sortie.append('<rect x="%s" y="%s" width="4" height="4" '
                          'fill="%s" stroke="%s" stroke-width="0.3" />'
                          % (_n(x), _n(y - 3.5), TEINTES[zone][1],
                             TEINTES[zone][2]))
        sortie.append('<text x="%s" y="%s" font-size="%s" fill="%s">%s</text>'
                      % (_n(x + (6 if zone else 0)), _n(y),
                         '4' if rang == 0 else '2.6', NOIR, escape(ligne)))
    return sortie


def svg_de_plan_lestage(calepinage, geometrie, zones):
    """PUR — le SVG A3 depuis une géométrie et des ``zones_de_pose`` déjà
    lues (aucune base) : la mise en page vérifiée sans montant (CALX327)."""
    repartition = repartir_modules(geometrie.get('pans') or [], zones)
    return _svg_a3(_corps(calepinage, geometrie, repartition, zones))


def svg_du_plan_lestage(calepinage):
    """Le SVG A3 du plan de lestage (refus nommé sinon)."""
    geometrie, _repartition, zones = _preparer(calepinage)
    return svg_de_plan_lestage(calepinage, geometrie, zones)


def rendre_plan_lestage_pdf(calepinage, *, company=None):
    """Octets PDF du plan de lestage, par ``core.pdf.render_pdf`` (ARC11)."""
    from core.pdf import render_pdf

    return render_pdf(html=html_de_planche(svg_du_plan_lestage(calepinage)),
                      company=company or getattr(calepinage, 'company', None))

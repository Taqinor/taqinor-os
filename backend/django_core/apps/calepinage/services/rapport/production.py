"""CALX301 — la section « Production » du rapport : mensuel, PR, P50/P90.

Le constat
==========
La note de calcul n'imprime que 5 lignes annuelles
(``services/note_calcul.py:558-566``) alors que le résultat publie déjà le
mensuel et le détail par pan (``contract_samples/calepinage_resultat.json`` :
``production.mensuel[]`` avec ``mois``/``p50_kwh``, ``production.par_pan[]``
avec ``p50_kwh``, ``performance_ratio``, ``specific_yield_kwh_kwc``,
``shading_annual_loss_pct``) — et ``construire_note_calcul`` COLLECTE
``par_pan`` (``:313``) sans jamais l'imprimer.

Ce que la section imprime — LU, jamais recalculé
==================================================
* une table 12 mois (``production.mensuel[]``, dans l'ordre SERVI) ;
* une table par pan (``production.par_pan[]``) ;
* le productible spécifique et le PR annuels (``production.total``) ;
* P50/P75/P90 (``production.total``) avec la variabilité interannuelle
  (``annual_variability``) et sa NATURE — mesurée sur N années ou hypothèse,
  le champ ``source`` de la composante ``variabilite_interannuelle`` du
  contrat d'incertitude (``resultat['incertitude']['composantes'][]``,
  CALX144) — jamais une nature devinée quand la composante manque ;
* une phrase qui dit que les quantiles ne valent QUE pour l'annuel (PVsyst :
  P50/P90 sont des valeurs de dépassement annuelles, jamais une garantie sur
  la durée de vie de l'installation).

Rien n'est inventé
===================
Une valeur absente imprime « — » (``nombre_tel_que_servi``), JAMAIS un 0 :
un ``p90_kwh`` non calculé n'est pas une production nulle.
"""
from __future__ import annotations

from html import escape

from . import nombre_tel_que_servi

__all__ = ['CSS_SECTION', 'MENTION_QUANTILES_ANNUELS', 'html_de_section']

CSS_SECTION = (
    '.production-mensuelle td.valeur,.production-par-pan td.valeur,'
    '.production-quantiles td.valeur{text-align:right;}'
    '.production-quantiles .detail{display:block;font-size:7.5pt;'
    'color:#555;}'
)

#: PVsyst : P50/P75/P90 sont des quantiles ANNUELS (valeurs de dépassement),
#: jamais une garantie sur la durée de vie de l'installation.
MENTION_QUANTILES_ANNUELS = (
    "Les valeurs P50, P75 et P90 ci-dessus sont des quantiles ANNUELS : "
    "elles décrivent la variabilité d'une année d'exploitation, pas une "
    "garantie sur la durée de vie de l'installation.")

#: La nature d'une composante d'incertitude (contrat ``calepinage_
#: incertitude.json``, CALX144) — trois origines seulement, aucune quatrième
#: inventée.
_NATURE_SOURCE = {
    'pvgis': 'mesurée sur la série météo',
    'societe': 'hypothèse saisie par la société',
    'texte': 'publication citée',
}

_LIBELLE_MOIS = {
    1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
    7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre',
    12: 'Décembre',
}


def _ligne(libelle_, valeur):
    return '<tr><th>%s</th><td>%s</td></tr>' % (escape(str(libelle_)), valeur)


def _mois_libelle(mois):
    if mois in _LIBELLE_MOIS:
        return _LIBELLE_MOIS[mois]
    return nombre_tel_que_servi(mois)


def _bloc_totaux(total):
    lignes = [
        _ligne('Production annuelle P50 (kWh)',
               nombre_tel_que_servi(total.get('p50_kwh'))),
        _ligne('Ratio de performance (PR)',
               nombre_tel_que_servi(total.get('performance_ratio'))),
        _ligne('Productible spécifique (kWh/kWc)',
               nombre_tel_que_servi(total.get('specific_yield_kwh_kwc'))),
    ]
    return '<table class="production-totaux generique">%s</table>' % \
        ''.join(lignes)


def _table_mensuelle(mensuel):
    lignes = ''.join(
        '<tr><td>%s</td><td class="valeur">%s</td></tr>'
        % (escape(_mois_libelle(m.get('mois'))),
           nombre_tel_que_servi(m.get('p50_kwh')))
        for m in mensuel)
    return ('<table class="production-mensuelle generique"><tr><th>Mois</th>'
            '<th>Production P50 (kWh)</th></tr>%s</table>' % lignes)


def _table_par_pan(par_pan):
    lignes = ''.join(
        '<tr><td>%s</td><td class="valeur">%s</td>'
        '<td class="valeur">%s</td><td class="valeur">%s</td>'
        '<td class="valeur">%s</td><td class="valeur">%s</td></tr>'
        % (escape(str(p.get('pan') or '')),
           nombre_tel_que_servi(p.get('modules')),
           nombre_tel_que_servi(p.get('kwc')),
           nombre_tel_que_servi(p.get('p50_kwh')),
           nombre_tel_que_servi(p.get('performance_ratio')),
           nombre_tel_que_servi(p.get('specific_yield_kwh_kwc')))
        for p in par_pan)
    entete = ('<th>Pan</th><th>Modules</th><th>Puissance (kWc)</th>'
              '<th>Production P50 (kWh)</th><th>PR</th>'
              '<th>Productible spécifique (kWh/kWc)</th>')
    return ('<table class="production-par-pan generique"><tr>%s</tr>%s'
            '</table>' % (entete, lignes))


def _composante_variabilite(incertitude):
    for composante in (incertitude or {}).get('composantes') or ():
        if isinstance(composante, dict) \
                and composante.get('nom') == 'variabilite_interannuelle':
            return composante
    return None


def _nature_variabilite(composante):
    if not composante:
        return escape('source non renseignée')
    source = composante.get('source')
    nature = _NATURE_SOURCE.get(source, escape(str(source)) if source
                                else 'source non renseignée')
    annees = composante.get('annees')
    if annees is not None:
        return escape('%s (%s années)' % (nature, nombre_tel_que_servi(
            annees)))
    return escape(nature)


def _bloc_quantiles(total, incertitude):
    composante = _composante_variabilite(incertitude)
    variabilite = '%s <span class="detail">%s</span>' % (
        nombre_tel_que_servi(total.get('annual_variability')),
        _nature_variabilite(composante))
    lignes = [
        _ligne('P50 (kWh)', nombre_tel_que_servi(total.get('p50_kwh'))),
        _ligne('P75 (kWh)', nombre_tel_que_servi(total.get('p75_kwh'))),
        _ligne('P90 (kWh)', nombre_tel_que_servi(total.get('p90_kwh'))),
        _ligne('Variabilité interannuelle', variabilite),
    ]
    return ('<table class="production-quantiles generique">%s</table>'
            '<p class="note">%s</p>'
            % (''.join(lignes), escape(MENTION_QUANTILES_ANNUELS)))


def html_de_section(contexte):
    """Le corps de la section ``production`` (le titre est posé par
    l'assembleur)."""
    resultat = contexte.get('resultat') or {}
    production = resultat.get('production') or {}
    total = production.get('total') or {}
    mensuel = [m for m in production.get('mensuel') or () if isinstance(
        m, dict)]
    par_pan = [p for p in production.get('par_pan') or () if isinstance(
        p, dict)]
    incertitude = resultat.get('incertitude') or {}

    blocs = [_bloc_totaux(total)]
    if mensuel:
        blocs.append(_table_mensuelle(mensuel))
    if par_pan:
        blocs.append(_table_par_pan(par_pan))
    blocs.append(_bloc_quantiles(total, incertitude))
    return ''.join(blocs)

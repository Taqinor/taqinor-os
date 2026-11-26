"""ACAL833 — la section « Hors réseau » du rapport d'étude.

Imprime, TELS QUE SERVIS par le bloc ``resultat['hors_reseau']`` (CALX191) :
la défaillance annuelle (kWh, heures, taux), les 12 mois avec le pire mois
marqué, le SOC minimal, la banque (capacité utile et nominale, jours
d'autonomie, profondeur de décharge et sa source) et chaque mention servie.

Aucun quantile P75/P90 : quand le bloc dit ``quantiles_publiables: false``,
son motif est republié. La section est OMISE pour une installation raccordée
(``SECTIONS_OMISES_SANS_DONNEES``, ACAL832). Aucun montant, aucun carburant.
"""
from __future__ import annotations

from html import escape

from . import nombre_tel_que_servi
from .production import _mois_libelle

__all__ = ['CSS_SECTION', 'html_de_section']

CSS_SECTION = (
    '.hors-reseau td.valeur{text-align:right;}'
    '.hors-reseau tr.pire-mois td,.hors-reseau tr.pire-mois th'
    '{font-weight:bold;}'
)


def _n(valeur):
    return nombre_tel_que_servi(valeur)


def _lignes(paires):
    return '<table class="hors-reseau generique">%s</table>' % ''.join(
        '<tr><th>%s</th><td class="valeur">%s</td></tr>' % (
            escape(libelle_), valeur) for libelle_, valeur in paires)


def _annuel(bloc):
    paires = [
        ('Défaillance annuelle (kWh)', _n(bloc.get('defaillance_kwh'))),
        ('Heures défaillantes', _n(bloc.get('heures_defaillantes'))),
        ('Taux de défaillance', _n(bloc.get('taux_defaillance'))),
    ]
    if 'soc_minimal_pct' in bloc:
        paires.append(('État de charge minimal (%)',
                       _n(bloc.get('soc_minimal_pct'))))
    return _lignes(paires)


def _mois(par_mois, pire):
    lignes = ''.join(
        '<tr%s><th>%s</th><td class="valeur">%s</td>'
        '<td class="valeur">%s</td></tr>' % (
            ' class="pire-mois"' if m.get('mois') == pire else '',
            _mois_libelle(m.get('mois')) + (  # ACAL1744 — le mois en lettres
                ' (mois le plus défavorable)' if m.get('mois') == pire else ''),
            _n(m.get('defaillance_kwh')), _n(m.get('heures_defaillantes')))
        for m in par_mois)
    return ('<table class="hors-reseau generique"><tr><th>Mois</th>'
            '<th>Défaillance (kWh)</th><th>Heures défaillantes</th></tr>'
            '%s</table>' % lignes)


def _banque(banque):
    source = banque.get('source_dod')
    dod = _n(banque.get('dod_pct'))
    if source:
        dod += ' <span class="detail">(%s)</span>' % escape(str(source))
    return _lignes([
        ('Capacité utile (kWh)', _n(banque.get('capacite_utile_kwh'))),
        ('Capacité nominale (kWh)', _n(banque.get('capacite_nominale_kwh'))),
        ("Jours d'autonomie", _n(banque.get('jours_autonomie'))),
        ('Profondeur de décharge (%)', dod),
    ])


def html_de_section(contexte):
    """Le corps de la section ``hors_reseau`` — servi, jamais recalculé."""
    bloc = (contexte.get('resultat') or {}).get('hors_reseau') or {}
    par_mois = [m for m in bloc.get('par_mois') or () if isinstance(m, dict)]
    pire = bloc.get('mois_le_plus_defavorable')
    blocs = [_annuel(bloc), _mois(par_mois, pire)]
    banque = bloc.get('banque')
    if isinstance(banque, dict):
        blocs.append(_banque(banque))
    for mention in bloc.get('mentions') or ():
        blocs.append('<p class="note">%s</p>' % escape(str(mention)))
    if bloc.get('quantiles_publiables') is False and bloc.get(
            'motif_quantiles'):
        blocs.append('<p class="note">%s</p>'
                     % escape(str(bloc['motif_quantiles'])))
    return ''.join(blocs)

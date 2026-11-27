"""ACAL475 — la section « Note de validation » du rapport d'étude.

Imprime, sans rien calculer, (1) la méthode du banc, (2) les sites et leurs
écarts annuels et mensuels contre PVcalc (et contre pvlib), LUS dans
``donnees/banc_validation.json`` (ACAL474) tels que figés, puis (3) la ligne
de CETTE étude : le bloc ``resultat['validation']`` (CALX195 — écart,
tolérance et sa source), ou « non calculé — lancez la simulation ».

Aucune phrase ne dit « validé » : l'écart est INFORMATIF, jamais un verdict de
conformité. Aucun montant (le pare-feu ``verifier_etancheite`` s'applique).
"""
from __future__ import annotations

import json
import pathlib
from html import escape

from . import nombre_tel_que_servi
from .champs_lisibles import _minuscule, libelle_de_poste

__all__ = ['CSS_SECTION', 'MENTION_ECART_INFORMATIF', 'html_de_section']

#: Chemin du dépôt, pas une mesure : ``parents[2]`` = le paquet ``apps/calepinage`` (ce
#: module vit dans ``services/rapport/``), où ACAL474 a figé ``donnees/banc_validation.json``.
BANC = (pathlib.Path(__file__).resolve().parents[2] / 'donnees'
        / 'banc_validation.json')

MENTION_ECART_INFORMATIF = (
    "Ces écarts sont INFORMATIFS : ils mesurent la distance entre notre "
    "chaîne de calcul et un outil de référence sur des sites types, ils ne "
    "garantissent pas la production d'une installation donnée. Aucune "
    "validation indépendante n'est revendiquée.")

NON_CALCULE = 'non calculé — lancez la simulation'

CSS_SECTION = (
    '.note-validation th,.note-validation td{padding:1.2mm;'
    'border:0.2mm solid #999;}'
    '.note-validation.mensuel td{font-size:7pt;text-align:center;}')


def _banc():
    return json.loads(BANC.read_text(encoding='utf-8'))


def _n(valeur):
    return nombre_tel_que_servi(valeur)


def _table_sites(sites):
    lignes = ''.join(
        '<tr><th>%s</th><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            escape(nom.capitalize()), _n(s.get('ecart_pvcalc_annuel_pct')),
            _n(s.get('ecart_pvlib_annuel_pct')), _n(s.get('total_moteur_kwh')))
        for nom, s in sites.items())
    return ('<table class="note-validation"><tr><th>Site</th>'
            '<th>Écart annuel contre PVcalc (%)</th>'
            '<th>Écart annuel contre pvlib (%)</th>'
            '<th>Total du moteur (kWh)</th></tr>' + lignes + '</table>')


def _table_mensuelle(sites):
    tete = ''.join('<td>%d</td>' % m for m in range(1, 13))
    lignes = ''.join(
        '<tr><th>%s</th>%s</tr>' % (escape(nom.capitalize()), ''.join(
            '<td>%s</td>' % _n((s.get('ecart_pvcalc_mensuel_pct') or {})
                               .get(str(m))) for m in range(1, 13)))
        for nom, s in sites.items())
    return ('<p class="grandeur">Écart mensuel contre PVcalc (%)</p>'
            '<table class="note-validation mensuel"><tr><th>Mois</th>'
            + tete + '</tr>' + lignes + '</table>')


def _ligne_etude(bloc):
    if not isinstance(bloc, dict) or bloc.get('ecart_pct') is None:
        return '<p class="note">Cette étude : %s.</p>' % escape(NON_CALCULE)
    tol = bloc.get('tolerance_pct')
    if tol is None:
        texte_tol = 'tolérance non saisie'
    else:
        texte_tol = 'tolérance %s %% (source : %s)' % (
            _n(tol), escape(str(bloc.get('tolerance_source') or '—')))
    return ('<p class="note">Cette étude : écart de %s %% contre PVcalc, %s.'
            '</p>' % (_n(bloc['ecart_pct']), texte_tol))


def html_de_section(contexte):
    """Le corps de la section ``validation`` — banc LU, jamais recalculé."""
    resultat = contexte.get('resultat') or {}
    banc = _banc()
    sites = banc.get('sites') or {}
    chaine = ', '.join(  # ACAL1716 — les postes en mots, pas leurs codes
        _minuscule(libelle_de_poste(c) or 'un poste de pertes')
        for c in banc.get('chaine_mesuree') or ())
    methode = ("Méthode : la production de notre chaîne (%s) est rejouée sur "
               "des sites marocains et comparée aux réponses PVGIS "
               "enregistrées (PVcalc) et à pvlib ; mesure du %s."
               % (chaine, banc.get('mesure_le', '—')))
    return ''.join((
        '<p class="note">%s</p>' % escape(methode),
        _table_sites(sites), _table_mensuelle(sites),
        '<p class="encart-preuve">%s</p>' % escape(MENTION_ECART_INFORMATIF),
        _ligne_etude(resultat.get('validation')),
    ))

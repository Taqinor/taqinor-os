"""CALX298 — la section « Site et source météo » du rapport.

Le constat
==========
La note de calcul imprime 5 lignes de site (``services/note_calcul.py:462-
470``) et ne dit ni l'altitude, ni le fuseau, ni le profil d'horizon — alors
que le module les détient : ``services/site.py`` (altitude et fuseau
SOURCÉS, jamais devinés), ``services/pvgis_serie.py::_bloc_meteo`` (la base
d'irradiance, la fenêtre d'années, le point PVGIS avec son altitude, le
profil d'horizon) et ``services/horizon.py``/``views/horizon.py:123-127``
(l'endpoint déjà servi).

Ce que la section imprime — LUE, jamais recalculée
====================================================
* ville, adresse : ``contexte['site']`` (``selectors.contexte_geographique``,
  CAL15) — jamais le résultat du moteur ;
* coordonnées et SOURCE DU REPÈRE : le même ``site`` (``pin``/``source`` —
  épingle posée par le client ou GPS du lead, jamais une troisième valeur
  devinée) ;
* altitude et fuseau, chacun avec sa source : ``resultat['meteo']['point']
  ['altitude_m']`` vient de LA MÊME réponse PVGIS que l'irradiance
  (``services/pvgis_serie.py::_bloc_meteo`` lit ``inputs.location.elevation``
  — exactement ce que ``services/site.py::altitude_pvgis`` lit ailleurs), sa
  source publiée est donc ``site.SOURCE_PVGIS`` ; le fuseau
  (``meteo.heure.fuseau_site``) n'entre dans le résultat qu'après avoir été
  validé contre la base IANA (``services/site.py::fuseau_du_site``), dont ce
  module RÉUTILISE le libellé de source plutôt que d'en inventer un ;
* base d'irradiance (``production.base.source``), via le même libellé que la
  note de calcul (``note_calcul._source_lisible``) — une base sans source
  imprime « source non renseignée », JAMAIS un nom de fournisseur ;
* fenêtre d'années (``production.base.fenetre_annees``) — imprimée TELLE
  QUELLE, jamais recalculée depuis ``meteo.annees`` ;
* perte déclarée passée à l'appel (``production.base.loss_passee_pct`` et son
  ``commentaire``, CAL238 — l'appel PVGIS reçoit toujours la somme explicite
  des postes, jamais un défaut caché) ;
* profil d'horizon (``meteo.horizon``) avec son origine — une origine absente
  ou ``'aucun'`` imprime le MOTIF (aucun profil publié), jamais un horizon
  plat supposé à 0°.

Rien n'est deviné
==================
Une grandeur sans source connue affiche « source non renseignée » (le
libellé de ``note_calcul._source_lisible``, repris tel quel) — jamais une
source inventée, jamais un fournisseur qui n'a pas été appelé.
"""
from __future__ import annotations

from html import escape

from . import nombre_tel_que_servi
from ..note_calcul import _source_lisible
from ..site import SOURCE_PVGIS, fuseau_du_site

__all__ = ['CSS_SECTION', 'MENTION_HORIZON_ABSENT', 'html_de_section']

#: La feuille de la section — RAMASSÉE par l'assembleur dans le ``<head>``.
CSS_SECTION = (
    '.site-meteo .detail{display:block;font-size:7.5pt;color:#555;}'
)

#: La mention de repli — aucun profil d'horizon publié, jamais un horizon
#: plat supposé.
MENTION_HORIZON_ABSENT = (
    "Aucun profil d'horizon publié pour ce calepinage : la simulation n'a "
    "pas employé de masque d'horizon — jamais un horizon plat supposé.")

#: Les provenances possibles de l'épingle (``selectors.SOURCE_ROOF_POINT`` /
#: ``SOURCE_GPS_LEAD``), lisibles — RECOPIÉES ici pour ne pas importer
#: ``selectors`` (qui lit le CRM) dans un rédacteur qui ne LIT que le
#: résultat et le contexte géographique déjà résolu.
_LIBELLE_SOURCE_REPERE = {
    'lead_roof_point': 'épingle posée par le client',
    'lead_gps': 'coordonnées GPS du lead',
}


def _ligne(libelle_, valeur):
    return '<tr><th>%s</th><td>%s</td></tr>' % (escape(str(libelle_)), valeur)


def _texte_ou_tiret(valeur):
    if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
        return '—'
    return escape(str(valeur))


def _source_repere(code):
    if not code:
        return escape(_source_lisible(''))
    return escape(_LIBELLE_SOURCE_REPERE.get(code, str(code)))


def _coordonnees(pin):
    if not isinstance(pin, dict) or pin.get('lat') is None \
            or pin.get('lng') is None:
        return '—'
    return '%s, %s' % (nombre_tel_que_servi(pin.get('lat')),
                       nombre_tel_que_servi(pin.get('lng')))


def _avec_source(valeur_html, source_html):
    return '%s <span class="detail">%s</span>' % (valeur_html, source_html)


def _altitude(point):
    point = point if isinstance(point, dict) else {}
    altitude = point.get('altitude_m')
    if altitude is None:
        return _avec_source(nombre_tel_que_servi(None),
                            escape(_source_lisible('')))
    return _avec_source(nombre_tel_que_servi(altitude) + ' m',
                        escape(SOURCE_PVGIS))


def _fuseau(heure):
    heure = heure if isinstance(heure, dict) else {}
    fuseau = heure.get('fuseau_site')
    if not fuseau:
        return _avec_source('—', escape(_source_lisible('')))
    source = fuseau_du_site({'fuseau': fuseau})['source']
    return _avec_source(escape(str(fuseau)), escape(str(source)))


def _horizon_disponible(meteo):
    horizon = meteo.get('horizon') if isinstance(meteo, dict) else None
    if not isinstance(horizon, dict):
        return None
    origine = str(horizon.get('origine') or '').strip()
    if not origine or origine == 'aucun':
        return None
    return horizon


def _ligne_horizon(horizon):
    origine = escape(str(horizon.get('origine')))
    hauteur = horizon.get('hauteur_max_deg')
    if hauteur is None:
        return origine
    return '%s <span class="detail">hauteur maximale %s°</span>' % (
        origine, nombre_tel_que_servi(hauteur))


def html_de_section(contexte):
    """Le corps de la section ``site_meteo`` (le titre est posé par
    l'assembleur)."""
    resultat = contexte.get('resultat') or {}
    site = contexte.get('site') or {}
    production = resultat.get('production') or {}
    base = production.get('base') or {}
    meteo = resultat.get('meteo') or {}

    lignes = [
        _ligne('Ville', _texte_ou_tiret(site.get('ville'))),
        _ligne('Adresse', _texte_ou_tiret(site.get('adresse'))),
        _ligne('Coordonnées', _coordonnees(site.get('pin'))),
        _ligne('Source du repère', _source_repere(site.get('source'))),
        _ligne('Altitude', _altitude(meteo.get('point'))),
        _ligne('Fuseau horaire', _fuseau(meteo.get('heure'))),
        # CAL238 — la source d'irradiance publiée TELLE QUELLE, jamais un
        # nom de fournisseur devinée quand elle manque.
        _ligne("Base d'irradiance",
               escape(_source_lisible(base.get('source')))),
    ]
    if base.get('fenetre_annees'):
        # La fenêtre est celle SERVIE par le résultat — jamais recalculée
        # depuis ``meteo.annees``.
        lignes.append(_ligne("Fenêtre d'années",
                             escape(str(base['fenetre_annees']))))
    if base.get('loss_passee_pct') is not None:
        detail = ('<span class="detail">%s</span>'
                  % escape(str(base['commentaire']))
                  if base.get('commentaire') else '')
        lignes.append(_ligne('Perte déclarée passée au calcul',
                             '%s %%%s' % (
                                 nombre_tel_que_servi(base['loss_passee_pct']),
                                 detail)))

    horizon = _horizon_disponible(meteo)
    if horizon is not None:
        lignes.append(_ligne("Profil d'horizon", _ligne_horizon(horizon)))

    table = '<table class="site-meteo generique">%s</table>' % ''.join(lignes)
    if horizon is None:
        table += '<p class="motif">%s</p>' % escape(MENTION_HORIZON_ABSENT)
    return table

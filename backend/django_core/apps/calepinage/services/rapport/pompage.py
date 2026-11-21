"""ACAL834 — la section « Pompage » du rapport d'étude.

Imprime, TELS QUE SERVIS, les champs du dernier dimensionnement enregistré
(``resultat_stocke['pompage_dernier']``, écrit par ``views/pompage.py``,
ACAL831) : les entrées, la HMT et ses composantes avec sa source, la pompe et
le variateur retenus, les douze volumes mensuels et leur source d'irradiation,
la couverture du besoin, l'autonomie, les avertissements et la date du calcul.

LU, jamais calculé : aucun arrondi, aucune somme. ``volumes`` à ``null`` imprime
« volumes mensuels : non calculés » et aucun m³. Section OMISE sans
dimensionnement enregistré (``SOURCE_STOCKEE``). Aucun montant.
"""
from __future__ import annotations

from html import escape

from . import nombre_tel_que_servi

__all__ = ['CSS_SECTION', 'html_de_section']

CSS_SECTION = '.pompage td.valeur{text-align:right;}'

_ENTREES = (
    ('hmt_saisie', 'HMT saisie (m)'),
    ('debit_souhaite_m3h', 'Débit souhaité (m³/h)'),
    ('heures_pompage', 'Heures de pompage par jour'),
    ('volume_reservoir_m3', 'Réservoir (m³)'),
    ('besoin_m3_jour', 'Besoin (m³/jour)'),
)

_COMPOSANTES = (
    ('niveau_dynamique_m', 'Niveau dynamique (m)'),
    ('denivele_m', 'Dénivelé (m)'),
    ('pertes_lineaires_m', 'Pertes linéaires (m)'),
    ('pertes_singulieres_m', 'Pertes singulières (m)'),
    ('pression_service_m', 'Pression de service (m)'),
)

_MOIS = ('janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août',
         'sept.', 'oct.', 'nov.', 'déc.')


def _n(valeur):
    return nombre_tel_que_servi(valeur)


def _table(paires):
    return '<table class="pompage generique">%s</table>' % ''.join(
        '<tr><th>%s</th><td class="valeur">%s</td></tr>' % (escape(nom), val)
        for nom, val in paires)


def _bloc_hmt(hmt):
    paires = [('HMT retenue (m)', _n(hmt.get('hmt_m'))),
              ('Source de la HMT', escape(str(hmt.get('source') or '—')))]
    composantes = hmt.get('composantes') or {}
    paires += [(nom, _n(composantes.get(cle))) for cle, nom in _COMPOSANTES
               if cle in composantes]
    return _table(paires)


def _bloc_materiel(pompe, variateur):
    paires = []
    if pompe:
        point = pompe.get('point_fonctionnement') or {}
        paires += [('Pompe', escape(str(pompe.get('nom') or '—'))),
                   ('Puissance de la pompe (kW)', _n(pompe.get('pompe_kw'))),
                   ('Point de fonctionnement : débit (m³/h)',
                    _n(point.get('debit_m3h'))),
                   ('Point de fonctionnement : HMT (m)',
                    _n(point.get('hmt_m')))]
    if variateur:
        paires += [('Variateur', escape(str(variateur.get('nom') or '—'))),
                   ('Variateur insuffisant',
                    'oui' if variateur.get('insuffisant') else 'non')]
    return _table(paires) if paires else ''


def _bloc_volumes(volumes, besoin):
    if not volumes:
        return '<p class="motif">Volumes mensuels : non calculés.</p>'
    serie = volumes.get('m3_mois_pvgis') or volumes.get('m3_mois_plat') or []
    couverture = (besoin or {}).get('couverture_pct_mois') or []
    entete = '<tr><th>Mois</th><th>Volume (m³)</th>%s</tr>' % (
        '<th>Couverture du besoin (%)</th>' if couverture else '')
    lignes = ''.join(
        '<tr><th>%s</th><td class="valeur">%s</td>%s</tr>' % (
            _MOIS[i] if i < 12 else i + 1, _n(valeur),
            '<td class="valeur">%s</td>' % _n(couverture[i])
            if i < len(couverture) else '')
        for i, valeur in enumerate(serie))
    source = volumes.get('source_irradiation')
    note = ('<p class="note">Source d\'irradiation : %s.</p>'
            % escape(str(source)) if source else '')
    return '<table class="pompage generique">%s%s</table>%s' % (
        entete, lignes, note)


def html_de_section(contexte):
    """Le corps de la section ``pompage`` — servi, jamais recalculé."""
    bloc = (contexte.get('resultat_stocke') or {}).get('pompage_dernier') or {}
    entrees = bloc.get('entrees') or {}
    corps = [_table([(nom, _n(entrees.get(cle))) for cle, nom in _ENTREES
                     if cle in entrees]),
             _bloc_hmt(bloc.get('hmt') or {}),
             _bloc_materiel(bloc.get('pompe'), bloc.get('variateur')),
             _bloc_volumes(bloc.get('volumes'), bloc.get('besoin'))]
    autonomie = (bloc.get('besoin') or {}).get('autonomie_jours')
    if autonomie is not None:
        corps.append(_table([("Autonomie (jours)", _n(autonomie))]))
    avertissements = [str(a) for a in bloc.get('avertissements') or ()
                      if str(a).strip()]
    if avertissements:
        corps.append('<ul>%s</ul>' % ''.join(
            '<li>%s</li>' % escape(a) for a in avertissements))
    if bloc.get('enregistre_le'):
        corps.append('<p class="note">Dimensionnement du %s.</p>'
                     % escape(str(bloc['enregistre_le'])))
    return ''.join(corps)

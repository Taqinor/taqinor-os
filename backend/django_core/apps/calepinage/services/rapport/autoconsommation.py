"""ACAL757 — la section « Autoconsommation et batterie » du rapport d'étude.

Imprime, tels que servis par ``GET resultat/`` (blocs ``autoconsommation`` et
``batterie``), les trois taux, le bilan d'énergie avec sa définition, le
plafond d'injection quand il est appliqué, la batterie (groupes et totaux) et
les douze mois.

LU, jamais calculé : la seule conversion est fraction × 100 pour les taux
(``synthese.pourcentage``). Un bloc dont ``motif_absence`` est rempli imprime
ce motif à la place de ses tables — jamais des zéros ; une valeur ``null``
s'imprime « non calculée ». Aucun tarif, aucune économie : pièce technique.
"""
from __future__ import annotations

from html import escape

from . import nombre_tel_que_servi
from .synthese import NON_CALCULEE, pourcentage

__all__ = ['CSS_SECTION', 'html_de_section']

CSS_SECTION = (
    '.autoconsommation td.valeur{text-align:right;}'
    '.autoconsommation .motif{font-style:italic;}'
)

_ENERGIE = (
    ('consommation_kwh', 'Consommation (kWh)'),
    ('production_kwh', 'Production (kWh)'),
    ('autoconsomme_kwh', 'Énergie autoconsommée (kWh)'),
    ('surplus_kwh', 'Surplus (kWh)'),
    ('import_reseau_kwh', 'Import réseau (kWh)'),
    ('export_reseau_kwh', 'Export réseau (kWh)'),
    ('production_brute_kwh', 'Production brute (kWh)'),
)

_TAUX = (
    ('taux_autoconsommation', "Taux d'autoconsommation"),
    ('taux_couverture', 'Taux de couverture'),
    ('taux_autonomie', "Taux d'autonomie"),
)

_BATTERIE = (
    ('groupe', 'Groupe'), ('packs', 'Packs'),
    ('capacite_utile_kwh', 'Capacité utile (kWh)'),
    ('cycles_an', 'Cycles par an'),
    ('energie_restituee_kwh', 'Énergie restituée (kWh)'),
    ('profondeur_decharge_pct', 'Profondeur de décharge (%)'),
    ('source', 'Source'),
)


def _n(valeur):
    if valeur is None:
        return NON_CALCULEE
    return nombre_tel_que_servi(valeur)


def _table(entetes, lignes):
    tete = ''.join('<th>%s</th>' % escape(e) for e in entetes)
    corps = ''.join('<tr>%s</tr>' % ''.join(
        '<td class="valeur">%s</td>' % c for c in ligne) for ligne in lignes)
    return '<table class="autoconsommation generique"><tr>%s</tr>%s</table>' \
        % (tete, corps)


def _motif(texte):
    return '<p class="motif">%s</p>' % escape(str(texte))


def _bloc_autoconsommation(bloc):
    taux = _table(['Indicateur', 'Valeur'], [
        [escape(lib), NON_CALCULEE if bloc.get(cle) is None
         else '%s %%' % nombre_tel_que_servi(pourcentage(bloc[cle]))]
        for cle, lib in _TAUX])
    energie = bloc.get('energie') or {}
    blocs = [taux, _table(['Énergie', 'Valeur'], [
        [escape(lib), _n(energie.get(cle))] for cle, lib in _ENERGIE])]
    if energie.get('apres_batterie') is True:
        blocs.append('<p class="note">Bilan établi après la batterie.</p>')
    if bloc.get('definition'):
        blocs.append('<p class="note">%s</p>' % escape(bloc['definition']))
    plafond = bloc.get('plafond') or {}
    if plafond.get('applique'):
        blocs.append(_table(["Plafond d'injection", 'Valeur'], [
            ['Plafond (kW)', _n(plafond.get('plafond_kw'))],
            ['Énergie écrêtée (kWh)', _n(plafond.get('energie_ecretee_kwh'))],
            ['Heures écrêtées', _n(plafond.get('heures_ecretees'))]]))
    mois = [m for m in bloc.get('par_mois') or () if isinstance(m, dict)]
    if mois:
        blocs.append(_table(
            ['Mois', 'Consommation (kWh)', 'Production (kWh)',
             'Autoconsommée (kWh)', 'Import (kWh)', 'Export (kWh)'],
            [[_n(m.get('mois')), _n(m.get('consommation_kwh')),
              _n(m.get('production_kwh')), _n(m.get('autoconsomme_kwh')),
              _n(m.get('import_reseau_kwh')), _n(m.get('export_reseau_kwh'))]
             for m in mois]))
    return ''.join(blocs)


def _bloc_batterie(bloc):
    groupes = [g for g in bloc.get('groupes') or () if isinstance(g, dict)]
    blocs = []
    if groupes:
        blocs.append(_table([lib for _, lib in _BATTERIE], [
            [escape(str(g.get(cle))) if cle in ('groupe', 'source')
             and g.get(cle) is not None else _n(g.get(cle))
             for cle, _ in _BATTERIE] for g in groupes]))
    total = bloc.get('total') or {}
    energie = total.get('energie') or {}
    blocs.append(_table(['Totaux de la batterie', 'Valeur'], [
        ['Énergie stockée (kWh)', _n(total.get('energie_stockee_kwh'))],
        ['Énergie restituée (kWh)', _n(total.get('energie_restituee_kwh'))],
        ['Pertes de la batterie (kWh)',
         _n(energie.get('pertes_batterie_kwh'))]]))
    return ''.join(blocs)


def html_de_section(contexte):
    """Le corps de la section ``autoconsommation`` (servi, non recalculé)."""
    resultat = contexte.get('resultat') or {}
    autoconso = resultat.get('autoconsommation')
    batterie = resultat.get('batterie')
    blocs = []
    if not isinstance(autoconso, dict):
        blocs.append(_motif('Autoconsommation %s : lancez la simulation avec '
                            'une courbe de charge.' % NON_CALCULEE))
    elif autoconso.get('motif_absence'):
        blocs.append(_motif(autoconso['motif_absence']))
    else:
        blocs.append(_bloc_autoconsommation(autoconso))
    if isinstance(batterie, dict):
        if batterie.get('motif_absence'):
            blocs.append(_motif(batterie['motif_absence']))
        else:
            blocs.append(_bloc_batterie(batterie))
    return ''.join(blocs)

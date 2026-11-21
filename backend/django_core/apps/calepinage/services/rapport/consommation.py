"""ACAL832 — la section « Consommation et hypothèses » du rapport d'étude.

Imprime, TELS QUE SERVIS (``nombre_tel_que_servi``), les hypothèses de charge
prises pour le client : l'origine de la courbe, le total annuel, la part base
et la part charges, une ligne par charge ajoutée (libellé, kWh/an, méthode,
source, hypothèses) et le profil mensuel.

La section est OMISE (ni imprimée, ni listée « non calculé » à l'annexe)
quand aucune consommation n'est servie : mécanisme
``SECTIONS_OMISES_SANS_DONNEES`` de l'assembleur. La date de saisie
(``saisi_le``) n'est pas servie : elle n'est jamais inventée. Aucun montant.
"""
from __future__ import annotations

from html import escape

from . import nombre_tel_que_servi

__all__ = ['CSS_SECTION', 'html_de_section']

CSS_SECTION = (
    '.consommation td.valeur{text-align:right;}'
    '.consommation .detail{display:block;font-size:7.5pt;color:#555;}'
)


def _n(valeur):
    return nombre_tel_que_servi(valeur)


def _table(entetes, lignes):
    tete = ''.join('<th>%s</th>' % escape(e) for e in entetes)
    corps = ''.join('<tr>%s</tr>' % ''.join(cellules) for cellules in lignes)
    return ('<table class="consommation generique"><tr>%s</tr>%s</table>'
            % (tete, corps))


def _texte(valeur):
    if valeur is None or valeur == '':
        return '—'
    return escape(str(valeur))


def _totaux(bloc):
    lignes = [
        ('Origine de la courbe', _texte(bloc.get('courbe_origine'))),
        ('Consommation annuelle (kWh)', _n(bloc.get('total_kwh'))),
        ('Part base (kWh)', _n(bloc.get('total_base_kwh'))),
        ('Part charges ajoutées (kWh)', _n(bloc.get('total_charges_kwh'))),
    ]
    return ''.join('<tr><th>%s</th><td>%s</td></tr>' % (escape(libelle_), v)
                   for libelle_, v in lignes)


def _charges(charges):
    if not charges:
        return '<p class="note">Aucune charge ajoutée.</p>'
    lignes = []
    for charge in charges:
        hypotheses = charge.get('hypotheses')
        lignes.append([
            '<td>%s</td>' % _texte(charge.get('libelle')),
            '<td class="valeur">%s</td>' % _n(charge.get('kwh_an')),
            '<td>%s</td>' % _texte(charge.get('methode')),
            '<td>%s</td>' % _texte(charge.get('source')),
            '<td>%s</td>' % (escape('; '.join(str(h) for h in hypotheses))
                             if hypotheses else '—'),
        ])
    return _table(['Charge ajoutée', 'kWh par an', 'Méthode', 'Source',
                   'Hypothèses'], lignes)


def _profil(profil):
    return _table(['Mois', 'Consommation (kWh)'], [
        ['<td class="valeur">%s</td>' % _n(m.get('mois')),
         '<td class="valeur">%s</td>' % _n(m.get('kwh'))]
        for m in profil])


def html_de_section(contexte):
    """Le corps de la section ``consommation`` — servi, jamais recalculé."""
    bloc = (contexte.get('resultat') or {}).get('consommation') or {}
    charges = [c for c in bloc.get('charges') or () if isinstance(c, dict)]
    profil = [m for m in bloc.get('profil_mensuel') or ()
              if isinstance(m, dict)]
    blocs = ['<table class="consommation generique">%s</table>'
             % _totaux(bloc), _charges(charges)]
    if profil:
        blocs.append(_profil(profil))
    return ''.join(blocs)

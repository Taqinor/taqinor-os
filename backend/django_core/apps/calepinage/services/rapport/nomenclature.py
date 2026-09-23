"""CALX304 — la section « Nomenclature » du rapport, SANS PRIX.

Le constat
==========
La nomenclature existante (``services/export_tableur.py::table_nomenclature``)
ne portait que deux familles de lignes — module et onduleurs — alors que la
structure de pose, les câbles, les protections et la mise à la terre sont
DÉJÀ calculées et servies par la clé racine ``resultat['nomenclature']``
(CALX246/247/227/230/232, ``core.electrique.nomenclature``). CALX304 étend
``table_nomenclature`` pour les AJOUTER (même fichier, mêmes trois colonnes,
gardé par la MÊME garde ``verifier_absence_de_prix``) ; cette section RÉUTILISE
cette table étendue plutôt que de la reconstruire une seconde fois — un
rapport et un export XLSX qui divergeraient sur la même donnée seraient
exactement l'incident du 27/07/2026 sous un autre nom.

AUCUN MONTANT
=============
``table_nomenclature`` n'a jamais lu ``Produit.prix_achat`` — ni cette
section. Le pare-feu ``export_tableur.verifier_absence_de_prix`` est
d'ailleurs REPASSÉ ici, sur la table telle qu'imprimée : un mot d'argent qui
se glisserait dans une désignation ferait échouer le rendu en le NOMMANT
plutôt que d'être filtré en silence — la même discipline que
``services/rapport/__init__.py::verifier_etancheite`` pour les autres
sections, appliquée à cette table-ci avec SON pare-feu propre (celui que la
tâche cite).
"""
from __future__ import annotations

from html import escape

from . import nombre_tel_que_servi, valeur_imprimable

__all__ = ['CSS_SECTION', 'html_de_section', 'html_de_table']

#: La feuille de la section — mêmes conventions visuelles que le reste du
#: rapport (voir ``pertes.CSS_SECTION``).
CSS_SECTION = (
    '.nomenclature-table td.num,.nomenclature-table th.num'
    '{text-align:right;}'
)


def html_de_table(entetes, lignes, langue='fr'):
    """Une table ``(entetes, lignes)`` — la forme de
    ``export_tableur.table_nomenclature`` — en HTML, valeurs imprimées
    TELLES QUE SERVIES (``nombre_tel_que_servi``/``valeur_imprimable`` :
    aucun arrondi, aucun total refait ici)."""
    entete = ''.join('<th>%s</th>' % escape(str(c)) for c in entetes)
    corps = []
    for ligne in lignes:
        cellules = []
        for valeur in ligne:
            if isinstance(valeur, (int, float)) and not isinstance(
                    valeur, bool):
                cellules.append('<td class="num">%s</td>'
                                % nombre_tel_que_servi(valeur, langue))
            else:
                cellules.append(
                    '<td>%s</td>' % valeur_imprimable(valeur, langue))
        corps.append('<tr>%s</tr>' % ''.join(cellules))
    return '<table class="nomenclature-table"><tr>%s</tr>%s</table>' % (
        entete, ''.join(corps))


def html_de_section(contexte):
    """Le corps de la section ``nomenclature`` (le titre est posé par
    l'assembleur). PUR — délègue la construction de la table à
    ``export_tableur.table_nomenclature(resultat)``, qui ne lit, elle
    aussi, que ``resultat`` : la MÊME table que le XLSX exporté, jamais une
    seconde lecture.
    """
    from ..export_tableur import table_nomenclature, verifier_absence_de_prix

    resultat = contexte.get('resultat') or {}
    langue = contexte.get('langue') or 'fr'
    entetes, lignes = table_nomenclature(resultat)
    if not lignes:
        return ''
    verifier_absence_de_prix(entetes, lignes)
    return html_de_table(entetes, lignes, langue)

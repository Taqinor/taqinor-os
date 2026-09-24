"""CALX305 — la section « Régime de preuve et empreinte » du rapport.

Le constat
==========
Le régime de preuve du moteur (méthode, optimalité, borne supérieure, marges
mesurées) n'était imprimé QUE dans la note de calcul
(``services/note_calcul.py:401-432``, ``CLES_VERDICT``/``CLES_MARGES``
``:105-112``) ; l'empreinte (``hash_entree`` + ``version_moteur``) n'était
posée en marge que de cette même pièce (``:356-365``) ; la planche a sa
propre empreinte (``services/planche.py:732-772``) et les exports CSV leur
propre bloc de provenance (``services/export_csv.py:69-94``) — trois
graphies pour la même chose, et le rapport d'étude (CALX297) n'en portait
aucune.

La règle est l'ÉGALITÉ, PAS une seconde rédaction
==================================================
Cette section RÉUTILISE ``note_calcul.verdict_de_preuve`` — la fonction qui
garantit, depuis CAL177, que le régime imprimé est identique à celui que
l'API des variantes affiche pour le MÊME résultat (incident du 27/07/2026 :
264 modules annoncés, 314 dans la donnée). Réécrire ce calcul ici aurait
recréé exactement le risque que CAL177 a fermé. Pour la même raison, les
libellés du régime (``LIBELLE_VERDICT``/``LIBELLE_MARGE``) et le formatage
« non mesuré » (``_valeur_verdict`` — une marge NON MESURÉE reste ``None``,
jamais ``0``, qui se lirait « au ras ») sont repris de ``note_calcul``, pas
reformulés : deux glossaires qui divergeraient tromperaient le lecteur qui
compare la note et le rapport.

Ce que la section imprime
==========================
1. un encart qui dit, en une phrase, ce que « optimum prouvé » signifie et
   ce qu'il ne signifie pas (D-CALX « zéro chiffre inventé » appliqué à un
   MOT : « prouvé » engage autant qu'un nombre) ;
2. le régime (``CLES_VERDICT``) et les marges mesurées (``CLES_MARGES``),
   REPORTÉS clé par clé ;
3. les contrôles passés, les cotes encore à confirmer et les motifs de
   non-engageabilité publiés par le moteur, quand il y en a ;
4. les avertissements du moteur.

L'empreinte (``hash_entree`` + ``version_moteur`` + date de calcul) n'est
PAS reposée ici : ``gabarit_document`` la pose déjà en pied de CHAQUE page
du document (boîte ``@bottom-left`` en élément courant) — la reposer dans le
corps de cette section la dupliquerait sans la rendre plus vraie.
"""
from __future__ import annotations

from html import escape

from ..note_calcul import (
    CLES_MARGES, CLES_VERDICT, LIBELLE_MARGE, LIBELLE_VERDICT,
    _valeur_verdict, verdict_de_preuve,
)

__all__ = ['CSS_SECTION', 'ENCART_OPTIMUM_PROUVE', 'html_de_section']

#: La feuille de la section — mêmes gris que la charte d'impression
#: (``CSS_RAPPORT``), aucune couleur de plus.
CSS_SECTION = (
    '.regime-preuve th{width:55%;}'
    '.regime-preuve td,.regime-preuve th{padding:1.2mm;'
    'border:0.2mm solid #999;}'
    '.encart-preuve{border-left:0.8mm solid #999;padding:1.5mm 2.5mm;'
    'background:#f2f2f2;font-size:8pt;color:#333;margin-bottom:3mm;}'
)

#: L'encart qui dit ce que « optimum prouvé » signifie — et ce qu'il ne
#: signifie pas. Rédigé une fois ici plutôt que laissé à l'interprétation du
#: lecteur : c'est le même mot que la barre de verdict de l'atelier
#: (``RemplissageProuve.jsx``) et que la phrase générée
#: (``views/moteur.py::verdict_de_pose``), pour la même méthode et la même
#: exactitude de méthode.
ENCART_OPTIMUM_PROUVE = (
    "« Optimum prouvé » signifie que la méthode de pose a établi, par "
    "recherche exhaustive dans le pas de recherche publié ci-dessous, "
    "qu'aucune disposition ne pose davantage de modules que le nombre "
    "retenu — c'est ce que portent conjointement « optimal » et « méthode "
    "exacte ». Cela NE signifie PAS que la pose retenue soit la seule "
    "physiquement réalisable, ni qu'elle intègre une cote encore à "
    "confirmer : sans cette preuve, seule une borne supérieure encadre le "
    "nombre de modules atteignable, et le régime le dit alors explicitement.")


def _ligne(libelle, valeur):
    return '<tr><th>%s</th><td>%s</td></tr>' % (
        escape(str(libelle)), escape(str(valeur)))


def _table_regime(verdict):
    regime = verdict.get('regime') or {}
    lignes = ''.join(_ligne(LIBELLE_VERDICT[cle], _valeur_verdict(
        regime.get(cle))) for cle in CLES_VERDICT)
    return '<table class="regime-preuve">%s</table>' % lignes


def _table_marges(verdict):
    marges = verdict.get('marges') or {}
    lignes = ''.join(_ligne(LIBELLE_MARGE[cle], _valeur_verdict(
        marges.get(cle))) for cle in CLES_MARGES)
    return '<table class="regime-preuve">%s</table>' % lignes


def _bloc_liste(titre, entrees):
    entrees = [str(e) for e in entrees or () if str(e).strip()]
    if not entrees:
        return ''
    return ('<p class="grandeur">%s</p><ul>%s</ul>'
            % (escape(titre),
               ''.join('<li>%s</li>' % escape(e) for e in entrees)))


def html_de_section(contexte):
    """Le corps de la section ``preuve`` (le titre est posé par l'assembleur).

    Le régime imprimé est celui que rend ``verdict_de_preuve(resultat)`` —
    LU, jamais recalculé : la même garantie d'égalité que la note de calcul.
    """
    resultat = contexte.get('resultat') or {}
    verdict = verdict_de_preuve(resultat)

    blocs = [
        '<p class="encart-preuve">%s</p>' % escape(ENCART_OPTIMUM_PROUVE),
        _table_regime(verdict),
    ]
    controles = [str(c) for c in verdict.get('controles') or ()
                 if str(c).strip()]
    if controles:
        blocs.append('<p class="note">Contrôles passés : %s</p>'
                     % escape(', '.join(controles)))
    blocs.append(_table_marges(verdict))
    blocs.append(_bloc_liste('Cotes à confirmer',
                             verdict.get('cotes_a_confirmer')))
    blocs.append(_bloc_liste("Motifs de non-engageabilité",
                             verdict.get('motifs_non_engageable')))

    avertissements = [str(a) for a in resultat.get('avertissements') or ()
                      if str(a).strip()]
    if avertissements:
        blocs.append('<p class="grandeur">Avertissements du moteur</p>'
                     '<ul>%s</ul>' % ''.join(
                         '<li>%s</li>' % escape(a) for a in avertissements))
    return ''.join(bloc for bloc in blocs if bloc)

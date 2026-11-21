"""ACAL463 — ÉTAPE « neige » : douze pertes mensuelles SAISIES, jamais devinées.

La neige est un poste d'irradiance à part entière (Aurora — System Losses :
« Snow (default 0%) », saisi par an ou par mois,
https://help.aurorasolar.com/hc/en-us/articles/220450107-System-Losses). Elle
se saisit exactement comme la salissure : le réglage société
``simulation.neige_mensuelle_pct`` porte douze valeurs (ou une seule, assumée,
pour les douze mois) AVEC sa source, et le facteur du mois de chaque heure
multiplie les mêmes colonnes que la salissure (énergie, ``gi``, ``gb``,
``gd``, ``gr``) — la machinerie de ``etapes/salissure.py`` est réemployée
telle quelle.

CE QUI LA FAIT SE TAIRE (jamais un 0 % supposé)
------------------------------------------------
* réglage absent, ou saisi sans source ⇒ étape OMISE en nommant la clé ;
* douze valeurs incomplètes (onze, un mois vide) ⇒ OMISE en nommant le mois ;
* des points sans mois ⇒ OMISE en nommant la colonne.

Un modèle physique de neige (``pvlib.snow``, Marion et al. 2013) exigerait une
série de chutes de neige que PVGIS ne donne pas : hors périmètre. Une neige
non saisie ne compte PAS comme « perte non renseignée » (voir
``chaine_pertes.completude_de_la_chaine``).

Module PUR : aucune base, aucun réseau.
"""
from __future__ import annotations

from apps.calepinage.services import etapes as _etapes
from apps.calepinage.services.etapes import salissure
from apps.calepinage.services.pertes import MOIS_LIBELLES

#: La clé de réglage société lue ici (registre CALX145).
CLE_REGLAGE = 'neige_mensuelle_pct'

LIBELLE = 'Couverture de neige'

REFERENCE = (
    'Aurora — System Losses : « Shading, snow, and soiling losses can all be '
    'specified on an annual OR monthly basis. » ; neige par défaut 0 % chez '
    'Aurora, jamais supposée ici '
    '(https://help.aurorasolar.com/hc/en-us/articles/220450107-System-Losses)'
    '.')

__all__ = ['CLE_REGLAGE', 'LIBELLE', 'REFERENCE', 'appliquer']


def appliquer(serie, contexte):
    """``(serie, etape)`` — le facteur de neige du MOIS de chaque heure."""
    contexte = contexte if isinstance(contexte, dict) else {}
    champ = f'simulation.{CLE_REGLAGE}'
    saisie = _etapes.reglage(contexte, CLE_REGLAGE)
    if not saisie:
        return serie, _etapes.etape_omise(
            LIBELLE,
            'Aucune valeur mensuelle de neige saisie (avec sa source) pour '
            "cette société : l'étape figure dans la cascade pour être VUE, "
            'et reste omise tant que les mois ne sont pas renseignés (0 % '
            'par défaut ferait croire à un calcul).',
            champ=champ)

    valeurs, mode, motif = salissure.valeurs_mensuelles(
        saisie.get('valeur'), champ=champ, poste='la neige')
    if valeurs is None:
        return serie, _etapes.etape_omise(LIBELLE, motif, champ=champ)

    rendue = salissure.appliquer_mensuel(serie, valeurs)
    if rendue is None:
        return serie, _etapes.etape_omise(
            LIBELLE,
            'La série horaire ne porte pas le mois de chacune de ses '
            'heures : la neige du mois ne peut être attribuée à aucune '
            'heure.', champ='serie_horaire.mois')

    entree = {
        'mode': mode,
        'valeurs_pct': list(valeurs),
        'mois': list(MOIS_LIBELLES),
        'moyenne_pct': round(sum(valeurs) / 12.0, 3),
        'source_du_reglage': saisie.get('source'),
        'origine_du_reglage': saisie.get('origine') or 'societe',
        'reference_saisie': saisie.get('reference') or '',
    }
    return rendue, _etapes.etape_appliquee(
        LIBELLE, source=saisie.get('source'), entree=entree,
        reference=REFERENCE)

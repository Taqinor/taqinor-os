# -*- coding: utf-8 -*-
"""ACAL57 — L'ÉCRIVAIN UNIQUE de ``Calepinage.resultat``.

LE CONSTAT (C-ACAL-055)
-----------------------
Six écrivains (fin de simulation, entrée électrique, verdict rejoué après
dessin, journal d'écart de longueur, édition du schéma unifilaire, saisie de
raccordement) faisaient chacun ``dict(calepinage.resultat)`` → une clé →
``save()``. Chacun reportait donc l'INSTANTANÉ lu au début de sa requête : une
simulation de 30 s lancée avant que l'utilisateur ne saisisse ``dc_m`` effaçait
la saisie en se terminant, et deux onglets s'écrasaient l'un l'autre.

LA RÈGLE
--------
UNE fonction, :func:`modifier_resultat` : sous ``transaction.atomic`` + verrou
de LIGNE (``select_for_update``, patron ``services/variantes.py`` /
``services/asbuilt.py``), elle RELIT ``resultat`` en base AU MOMENT D'ÉCRIRE,
laisse l'appelant modifier ce dictionnaire FRAIS, puis l'enregistre. Une
écriture ne reporte donc jamais une copie périmée ; un ``modifier`` qui lève
n'écrit RIEN (la transaction est annulée).

Seule la colonne ``resultat`` (et ``updated_at``) est écrite — AUCUN statut
(règle #4). Le remplacement VOULU de ``resultat`` à la restauration d'une
version (``services/layout.py``) n'est pas un écrivain de clé : il reste à part.
"""
from __future__ import annotations

__all__ = ['CLES_SAISIES', 'CLES_SORTIES', 'modifier_resultat']

#: Les clés de ``resultat`` qui portent une SAISIE (ou un geste) de
#: l'utilisateur — par opposition aux sorties du moteur, recalculables.
#: Consommée ensuite par la restauration de version et l'export projet.
CLES_SAISIES = (
    'entree_electrique',     # CAL125 — matériel, longueurs, températures…
    'sld_edition',           # CALX234 — édition du schéma unifilaire
    'raccordement_saisie',   # CALX205 — saisie du point de raccordement
    'journal_derogations',   # CALX215 — dérogations d'alerte (gestes)
)

#: Les clés écrites par les MOTEURS (jamais saisies) par ces écrivains.
#: ACAL325 — ``verdict_electrique`` n'en est plus : le verdict est servi à
#: la demande, jamais déposé (lot 2 critique #21).
CLES_SORTIES = (
    'journal_longueur_chaine',   # CAL170 — fil des écarts de longueur
    'simulation',                # CALX5 — en-tête de la simulation
)


def _est_un_modele(calepinage):
    from django.db import models

    return isinstance(calepinage, models.Model)


def modifier_resultat(calepinage, modifier):
    """Applique ``modifier`` au ``resultat`` FRAIS de ``calepinage``.

    Args:
        calepinage: l'instance (éventuellement lue il y a longtemps — son
            ``resultat`` en mémoire n'est JAMAIS la base de l'écriture).
        modifier: ``modifier(resultat) -> valeur``. ``resultat`` est un
            ``dict`` relu en base sous verrou ; ``modifier`` le modifie EN
            PLACE. Sa valeur de retour est rendue telle quelle.

    Après l'écriture, ``calepinage.resultat`` porte le document ÉCRIT (l'état
    de la base), pour que l'appelant relise ce qui est vraiment enregistré.

    Sans ``pk`` (calcul hors base), ``modifier`` s'applique à la copie en
    mémoire et rien n'est enregistré. Un double de test qui n'est pas un
    modèle Django garde le chemin historique ``save(update_fields=…)``.
    """
    pk = getattr(calepinage, 'pk', None)
    if not pk or not _est_un_modele(calepinage):
        resultat = getattr(calepinage, 'resultat', None)
        resultat = dict(resultat) if isinstance(resultat, dict) else {}
        valeur = modifier(resultat)
        calepinage.resultat = resultat
        if pk:
            calepinage.save(update_fields=['resultat', 'updated_at'])
        return valeur

    from django.db import transaction

    modele = type(calepinage)
    with transaction.atomic():
        frais = (modele._base_manager.select_for_update()
                 .get(pk=pk))
        resultat = frais.resultat
        resultat = dict(resultat) if isinstance(resultat, dict) else {}
        valeur = modifier(resultat)
        frais.resultat = resultat
        frais.save(update_fields=['resultat', 'updated_at'])
    calepinage.resultat = resultat
    if hasattr(calepinage, 'updated_at'):
        calepinage.updated_at = frais.updated_at
    return valeur

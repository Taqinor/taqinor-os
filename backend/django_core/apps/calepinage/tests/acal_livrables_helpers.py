"""ACAL214 — un calepinage SIMULÉ par les VRAIS écrivains, sans base.

Les livrables (note de calcul, présentation, plan de pose, classeur…) lisent
le résultat SERVI ; un essai qui leur donnerait ``calepinage_resultat.json``
collé dans ``Calepinage.resultat`` prouverait la lecture d'un dictionnaire
que RIEN n'écrit (l'incident ACAL, C-ACAL-124). Ce module fabrique donc le
pivot par les écrivains de production : ``enregistrer_entree`` (entrée
électrique) puis ``simuler_calepinage`` (météo REJOUÉE en entrée, jamais le
lecteur patché). Aucun ORM : ``pk`` reste ``None``, donc rien n'est écrit en
base ni annoncé sur le bus.

Le matériel (fiches module/onduleur) est le seam documenté des tests
(``materiel=``) ; l'appelant l'injecte aussi côté lecture avec
``patch_materiel()``.
"""
import copy
from unittest import mock

from apps.calepinage.services.electrique import enregistrer_entree
from apps.calepinage.services.simulation import simuler_calepinage

from .test_calx5_simulation import (
    LAYOUT as LAYOUT_SIMULABLE, MATERIEL, REGLAGES, _ClientRejoue,
)

__all__ = ['LAYOUT_SIMULABLE', 'MATERIEL', 'PivotSansBase',
           'calepinage_simule_reel', 'modifier_la_conception',
           'patch_materiel']


class PivotSansBase:
    """Le strict minimum d'un ``Calepinage`` que les écrivains lisent."""

    pk = None
    devis_id = None
    company = None
    titre = 'Calepinage d essai'
    roof_image = ''
    layout_hash = ''
    version_moteur = ''

    def __init__(self, layout, resultat=None):
        self.roof_layout = layout
        self.resultat = resultat
        self.pertes = []

    def save(self, update_fields=None):  # pragma: no cover - pk None
        raise AssertionError('un livrable ne doit RIEN enregistrer')


def patch_materiel():
    """Injecte les fiches matériel du cas (le stock n'a pas de base ici)."""
    return mock.patch(
        'apps.calepinage.services.electrique.resoudre_materiel',
        return_value=MATERIEL)


def calepinage_simule_reel(layout=None):
    """Un calepinage conçu, désigné, puis SIMULÉ — par les vrais écrivains.

    ``Calepinage.resultat`` porte alors ``entree_electrique``, ``simulation``,
    ``production``, ``pertes``… et NI ``pose`` NI ``electrique`` : ces deux
    blocs n'existent que dans le résultat SERVI.
    """
    pivot = PivotSansBase(copy.deepcopy(layout or LAYOUT_SIMULABLE))
    with patch_materiel():
        enregistrer_entree(pivot, {'module_produit': 1, 'onduleur_produit': 2})
        simuler_calepinage(pivot, client=_ClientRejoue(), materiel=MATERIEL,
                           reglages=REGLAGES, enregistrer=True)
    return pivot


def modifier_la_conception(pivot):
    """Ajoute un module au premier pan SANS relancer la simulation."""
    pivot.roof_layout = copy.deepcopy(pivot.roof_layout)
    pivot.roof_layout['zones'][0]['geometry']['count'] += 1
    return pivot

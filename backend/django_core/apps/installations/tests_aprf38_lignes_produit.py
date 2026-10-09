"""APRF38 (C-APRF-018) — les 11 listes d'installations qui sérialisent des
lignes imbriquées précharge le PRODUIT des lignes (`lignes__produit`, plus
`lignes__bin` pour les pick-lists, `composants__produit` pour les kits) : un
document à 12 lignes ne coûte plus 12 requêtes `stock_produit` de plus qu'à 1.

Le test lit les préchargements déclarés de chaque queryset de viewset (sans
base) : retirer `lignes__produit` d'une seule vue fait échouer son cas.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_aprf38_lignes_produit"
"""
from django.test import SimpleTestCase

from apps.installations.views.colisage import ColisViewSet
from apps.installations.views.comptage import SessionComptageViewSet
from apps.installations.views.commande_cadre import CommandeCadreViewSet
from apps.installations.views.contrat_prix import (
    ContratPrixFournisseurViewSet,
)
from apps.installations.views.demande_achat import DemandeAchatViewSet
from apps.installations.views.kitting import KitViewSet, OrdreDemontageViewSet
from apps.installations.views.livraison import LivraisonViewSet
from apps.installations.views.picklist import PickListViewSet
from apps.installations.views.retour_livraison import RetourLivraisonViewSet
from apps.installations.views.retour_materiel import RetourMaterielViewSet

ATTENDUS = (
    (PickListViewSet, ('lignes__produit', 'lignes__bin')),
    (ColisViewSet, ('lignes__produit',)),
    (SessionComptageViewSet, ('lignes__produit',)),
    (LivraisonViewSet, ('lignes__produit',)),
    (RetourMaterielViewSet, ('lignes__produit',)),
    (RetourLivraisonViewSet, ('lignes__produit',)),
    (DemandeAchatViewSet, ('lignes__produit',)),
    (CommandeCadreViewSet, ('lignes__produit',)),
    (ContratPrixFournisseurViewSet, ('lignes__produit',)),
    (KitViewSet, ('composants__produit',)),
    (OrdreDemontageViewSet, ('lignes__produit',)),
)


class LignesProduitPrechargeesTests(SimpleTestCase):
    def test_onze_listes_prechargent_le_produit_des_lignes(self):
        manquants = []
        for viewset, lookups in ATTENDUS:
            declares = set(viewset.queryset._prefetch_related_lookups)
            for lookup in lookups:
                if lookup not in declares:
                    manquants.append(f'{viewset.__name__} : {lookup}')
        self.assertEqual(manquants, [], manquants)

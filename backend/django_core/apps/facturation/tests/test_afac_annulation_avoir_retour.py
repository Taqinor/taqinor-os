"""AFAC28 (C-AFAC-025) — annuler un avoir de retour RE-STOCKÉ contre-passe son
entrée de stock (une SORTIE miroir, référence = l'avoir) dans la même
transaction, ou refuse en 400 si les unités sont déjà ressorties — jamais
deux entrées pour une unité physique.

Rejoue FCOR-2 (annuler → stock reste 11 ; second retour → 12 ; deux
mouvements `entree`). Endpoints réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_annulation_avoir_retour"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class AnnulationAvoirRetourTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from apps.ventes.models import Facture, LigneFacture
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC28 Co', slug=f'afac28-co-{_nxt()}')
        self.admin = User.objects.create_user(
            username=f'afac28_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        client = Client.objects.create(
            company=self.company, nom='Stock', prenom='AFAC28',
            email=f'afac28-{_nxt()}@example.invalid')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie', sku=f'AFAC28-{_nxt()}',
            prix_vente=Decimal('1000'), quantite_stock=10)
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC28-{_nxt()}',
            client=client, statut='emise', taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Batterie', quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _retour(self):
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/retour-client/',
            {'motif': 'défaut', 'restocker': True,
             'lignes': [{'produit': self.produit.id, 'quantite': 1}]},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def _annuler(self, avoir_id):
        return self.api.post(f'/api/django/ventes/avoirs/{avoir_id}/annuler/',
                             {}, format='json')

    def _stock(self):
        self.produit.refresh_from_db()
        return self.produit.quantite_stock

    def _mouvements(self, reference, type_mouvement):
        from apps.stock.models import MouvementStock
        return MouvementStock.objects.filter(
            produit=self.produit, reference=reference,
            type_mouvement=type_mouvement)

    def test_annuler_retour_restocke_sort_le_stock(self):
        avoir = self._retour()
        self.assertEqual(self._stock(), 11)
        r = self._annuler(avoir['id'])
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'annulee')
        self.assertEqual(self._stock(), 10)
        self.assertEqual(
            self._mouvements(avoir['reference'], 'sortie').count(), 1)

    def test_annuler_deux_fois_un_seul_mouvement(self):
        avoir = self._retour()
        self.assertEqual(self._annuler(avoir['id']).status_code, 200)
        self.assertEqual(self._annuler(avoir['id']).status_code, 200)
        self.assertEqual(self._stock(), 10)
        self.assertEqual(
            self._mouvements(avoir['reference'], 'sortie').count(), 1)

    def test_nouveau_retour_apres_annulation_une_entree(self):
        avoir = self._retour()
        self.assertEqual(self._annuler(avoir['id']).status_code, 200)
        self._retour()
        self.assertEqual(self._stock(), 11)

    def test_refus_si_unites_ressorties(self):
        from apps.stock.services import (
            mouvement_type_sortie, record_stock_movement,
        )
        from apps.ventes.models import Avoir
        avoir = self._retour()
        # Une vente fait retomber le stock à 10 avant l'annulation.
        record_stock_movement(
            company=self.company, produit=self.produit,
            type_mouvement=mouvement_type_sortie(), quantite=1,
            quantite_avant=11, quantite_apres=10, reference='VENTE-AFAC28',
            note='vente', created_by=self.admin)
        self.assertEqual(self._stock(), 10)
        r = self._annuler(avoir['id'])
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('déjà ressorties du stock', r.data['detail'])
        self.assertEqual(Avoir.objects.get(pk=avoir['id']).statut, 'emise')
        self.assertEqual(self._stock(), 10)
        self.assertFalse(
            self._mouvements(avoir['reference'], 'sortie').exists())

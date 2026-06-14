"""Tests recouvrement (workstream E) : impayés, balance âgée, relevé, relance.

Vue / consigne / impression uniquement — aucun envoi.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import (
    Facture, LigneFacture, FollowupLevel, RelanceLog,
)

User = get_user_model()


def make_company(slug='rec-co', nom='Rec Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestRecouvrement(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='rec_resp', password='x', role_legacy='responsable',
            company=self.company)
        for ordre, nom, delai in [(1, 'Rappel', 7), (2, 'Relance', 15),
                                  (3, 'Ferme', 30)]:
            FollowupLevel.objects.create(
                company=self.company, ordre=ordre, nom=nom, delai_jours=delai)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Débiteur', telephone='+212600000002')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-R',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'))
        # Facture émise, échéance dépassée de 45 jours, due 6000 TTC.
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-REC-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'),
            date_echeance=date.today() - timedelta(days=45))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_overdue_in_relances_list_with_level(self):
        resp = self.api.get('/api/django/ventes/relances/')
        self.assertEqual(resp.status_code, 200, resp.data)
        row = next(r for r in resp.data if r['id'] == self.facture.id)
        self.assertEqual(row['jours_retard'], 45)
        # 45 jours → niveau le plus haut atteint (J+30).
        self.assertEqual(row['niveau']['delai_jours'], 30)

    def test_overdue_in_aged_balance_bucket(self):
        resp = self.api.get('/api/django/ventes/balance-agee/')
        self.assertEqual(resp.status_code, 200, resp.data)
        row = next(r for r in resp.data if r['client_id'] == self.client_obj.id)
        # 45 jours → bucket 31–60.
        self.assertEqual(row['b31_60'], '6000.00')
        self.assertEqual(row['b0_30'], '0.00')
        self.assertEqual(row['total'], '6000.00')

    def test_client_statement_lists_facture(self):
        resp = self.api.get(
            f'/api/django/ventes/clients/{self.client_obj.id}/releve/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['lignes']), 1)
        self.assertEqual(resp.data['lignes'][0]['du'], '6000.00')
        self.assertEqual(resp.data['totaux']['du'], '6000.00')

    def test_relancer_logs_and_sets_next(self):
        nxt = (date.today() + timedelta(days=7)).isoformat()
        resp = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/relancer/',
            {'niveau': 3, 'note': 'Appel client', 'prochaine_relance': nxt},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(RelanceLog.objects.filter(
            facture=self.facture, note='Appel client').exists())
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.prochaine_relance.isoformat(), nxt)

    def test_exclude_removes_from_relances(self):
        self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/exclure-relance/',
            {'exclu': True}, format='json')
        resp = self.api.get('/api/django/ventes/relances/')
        ids = [r['id'] for r in resp.data]
        self.assertNotIn(self.facture.id, ids)

    def test_paid_facture_not_in_relances(self):
        # Une facture payée ne doit pas figurer dans les impayés.
        from apps.ventes.models import Paiement
        Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('6000'), date_paiement=date.today())
        resp = self.api.get('/api/django/ventes/relances/')
        ids = [r['id'] for r in resp.data]
        self.assertNotIn(self.facture.id, ids)

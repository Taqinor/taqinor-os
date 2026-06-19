"""Tests des Avoirs (notes de crédit) — workstream D.

Couvre : création depuis une facture émise (admin), avoir partiel qui réduit
le montant dû avec le split TVA 10/20 intact, garde admin sur la création.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Avoir, Facture, LigneFacture

User = get_user_model()


def make_company(slug='avo-co', nom='Avo Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestAvoirs(TestCase):
    def setUp(self):
        from apps.roles.models import Role, ALL_PERMISSIONS, RESPONSABLE_PERMISSIONS
        self.company = make_company()
        admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        resp_role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=RESPONSABLE_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username='avo_admin', password='x', role=admin_role,
            role_legacy='admin', company=self.company)
        self.resp = User.objects.create_user(
            username='avo_resp', password='x', role=resp_role,
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Avo',
            telephone='+212600000001')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau PV', sku='PV1',
            prix_vente=Decimal('1000'), quantite_stock=100, tva=Decimal('10.00'))
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND1',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'))
        # Facture émise : 10×1000 (TVA10) + 1×5000 (TVA20) = 15000 HT,
        # TVA = 1000 + 1000 = 2000 → 17000 TTC.
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-TEST-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.panneau, designation='Panneau PV',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('10.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.onduleur, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_facture_baseline_due(self):
        self.assertEqual(self.facture.total_ttc, Decimal('17000.00'))
        self.assertEqual(self.facture.montant_du, Decimal('17000.00'))

    def test_partial_avoir_lowers_due_with_tva_split(self):
        # Avoir partiel : on crédite uniquement l'onduleur (5000 HT, TVA 20 %
        # = 1000 → 6000 TTC).
        api = self._api(self.admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'Onduleur retourné',
             'lignes': [{'designation': 'Onduleur', 'quantite': '1',
                         'prix_unitaire': '5000', 'taux_tva': '20'}]},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        avoir = Avoir.objects.get(id=resp.data['id'])
        self.assertEqual(avoir.total_ht, Decimal('5000.00'))
        self.assertEqual(avoir.total_tva, Decimal('1000.00'))
        self.assertEqual(avoir.total_ttc, Decimal('6000.00'))
        # Le split TVA est présent (un seul taux ici, 20 %).
        bucket = avoir.tva_par_taux
        self.assertEqual(len(bucket), 1)
        self.assertEqual(bucket[0]['taux'], Decimal('20.00'))
        # Le dû de la facture baisse de 6000 → 11000.
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.avoirs_total, Decimal('6000.00'))
        self.assertEqual(self.facture.montant_du, Decimal('11000.00'))
        # Référence en séquence AVO.
        self.assertTrue(avoir.reference.startswith('AVO-'))

    def test_full_avoir_copies_lines_and_zeroes_due(self):
        api = self._api(self.admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'Annulation totale'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        avoir = Avoir.objects.get(id=resp.data['id'])
        self.assertEqual(avoir.total_ttc, Decimal('17000.00'))
        # Split 10/20 préservé sur l'avoir complet.
        taux = sorted(b['taux'] for b in avoir.tva_par_taux)
        self.assertEqual(taux, [Decimal('10.00'), Decimal('20.00')])
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.montant_du, Decimal('0.00'))

    def test_commerciale_cannot_create_avoir(self):
        api = self._api(self.resp)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)
        # Mais peut le lister/voir.
        self.assertEqual(
            api.get('/api/django/ventes/avoirs/').status_code, 200)

    def test_cannot_avoir_draft_facture(self):
        self.facture.statut = Facture.Statut.BROUILLON
        self.facture.save(update_fields=['statut'])
        api = self._api(self.admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'x'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_avoir_exceeding_remaining_rejected(self):
        # Une ligne d'avoir à 20 000 HT (24 000 TTC) dépasse les 17 000 TTC
        # créditables de la facture → 400, aucun avoir persisté.
        api = self._api(self.admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'Trop gros',
             'lignes': [{'designation': 'X', 'quantite': '1',
                         'prix_unitaire': '20000', 'taux_tva': '20'}]},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('dépasse', resp.data['detail'])
        self.assertEqual(Avoir.objects.count(), 0)

    def test_second_avoir_capped_by_first(self):
        # 1er avoir total (17 000 TTC) → plus rien de créditable ; un 2e avoir
        # partiel est refusé.
        api = self._api(self.admin)
        r1 = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'Total'}, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'lignes': [{'designation': 'Onduleur', 'quantite': '1',
                         'prix_unitaire': '5000', 'taux_tva': '20'}]},
            format='json')
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(Avoir.objects.count(), 1)

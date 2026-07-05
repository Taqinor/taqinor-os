"""Tests ZFAC1 — Reset to Draft (émise → brouillon) : une facture émise SANS
paiement ni avoir repasse en brouillon (référence conservée), une facture
avec paiement OU avec immutabilité XFAC24 activée est refusée (400), un
avoir actif refuse aussi, scoping cross-company 404."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.stock.models import Produit
from apps.ventes.models import Facture, FactureActivity, LigneFacture

User = get_user_model()


def make_company(slug='zfac1-co', nom='ZFAC1 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestRemettreBrouillon(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='zfac1_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        # creer-avoir est réservé à l'admin (cf. test_avoirs.py
        # test_commerciale_cannot_create_avoir) — un utilisateur distinct est
        # nécessaire pour poser l'avoir actif dans
        # test_remettre_brouillon_avoir_actif_refuse ; remettre-brouillon
        # reste testé via self.user/self.api (responsable).
        self.admin = User.objects.create_user(
            username='zfac1_admin', password='x', role_legacy='admin',
            company=self.company)
        self.admin_api = auth(self.admin)
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='F1',
            email='zfac1@example.com', telephone='+212600000015')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-ZFAC1',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'))

    def _facture(self, num=1):
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-ZFAC1-{num:04d}',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))
        return facture

    def test_remettre_brouillon_sans_paiement_ok(self):
        facture = self._facture(1)
        original_ref = facture.reference
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/remettre-brouillon/')
        self.assertEqual(r.status_code, 200, r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)
        self.assertEqual(facture.reference, original_ref)
        self.assertTrue(
            FactureActivity.objects.filter(
                facture=facture, field='statut',
                field_label='Remise en brouillon').exists())

    def test_remettre_brouillon_avec_paiement_refuse(self):
        facture = self._facture(2)
        r0 = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/'
            f'enregistrer-paiement/',
            {'montant': '1000', 'date_paiement': '2026-01-01',
             'mode': 'virement'}, format='json')
        self.assertEqual(r0.status_code, 201, r0.data)
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/remettre-brouillon/')
        self.assertEqual(r.status_code, 400, r.data)
        facture.refresh_from_db()
        self.assertNotEqual(facture.statut, Facture.Statut.BROUILLON)

    def test_remettre_brouillon_immutabilite_active_refuse(self):
        facture = self._facture(3)
        profile = CompanyProfile.get(company=self.company)
        profile.factures_immuables = True
        profile.save(update_fields=['factures_immuables'])
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/remettre-brouillon/')
        self.assertEqual(r.status_code, 400, r.data)

    def test_remettre_brouillon_avoir_actif_refuse(self):
        facture = self._facture(4)
        # creer-avoir est réservé à l'admin — self.user (responsable) ne
        # peut pas poser l'avoir de préparation ; le reste du test (l'assertion
        # sous test) continue d'utiliser self.api/self.user.
        r0 = self.admin_api.post(
            f'/api/django/ventes/factures/{facture.id}/creer-avoir/',
            {'motif': 'erreur'}, format='json')
        self.assertEqual(r0.status_code, 201, r0.data)
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/remettre-brouillon/')
        self.assertEqual(r.status_code, 400, r.data)

    def test_remettre_brouillon_non_emise_refuse(self):
        facture = self._facture(5)
        facture.statut = Facture.Statut.BROUILLON
        facture.save(update_fields=['statut'])
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/remettre-brouillon/')
        self.assertEqual(r.status_code, 400, r.data)

    def test_cross_company_404(self):
        other = make_company(slug='zfac1-co2', nom='ZFAC1 Co2')
        other_user = User.objects.create_user(
            username='zfac1_other', password='x', role_legacy='responsable',
            company=other)
        other_api = auth(other_user)
        facture = self._facture(6)
        r = other_api.post(
            f'/api/django/ventes/factures/{facture.id}/remettre-brouillon/')
        self.assertEqual(r.status_code, 404)

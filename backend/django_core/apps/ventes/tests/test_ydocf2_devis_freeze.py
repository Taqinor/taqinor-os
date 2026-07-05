"""Tests YDOCF2 — un devis figé (accepté/refusé/expiré) n'est plus librement
éditable : PATCH direct refusé sur DevisViewSet et LigneDevisViewSet, sauf
désactivation (is_active=False, révision superseded). Un devis brouillon reste
librement éditable (non-régression)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='ydocf2-co', nom='YDOCF2 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestDevisFreezeOnUpdate(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ydocf2_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='F2',
            email='ydocf2@example.com', telephone='+212600000002')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='YDOCF2-P',
            prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
            quantite_stock=100)

    def _devis(self, num, statut):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{9000 + num}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'))

    def test_patch_accepted_devis_rejected(self):
        devis = self._devis(1, Devis.Statut.ACCEPTE)
        r = self.api.patch(
            f'/api/django/ventes/devis/{devis.id}/', {'note': 'edit'},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        devis.refresh_from_db()
        self.assertNotEqual(devis.note, 'edit')

    def test_patch_refused_devis_rejected(self):
        devis = self._devis(2, Devis.Statut.REFUSE)
        r = self.api.patch(
            f'/api/django/ventes/devis/{devis.id}/', {'note': 'edit'},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_patch_expired_devis_rejected(self):
        devis = self._devis(3, Devis.Statut.EXPIRE)
        r = self.api.patch(
            f'/api/django/ventes/devis/{devis.id}/', {'note': 'edit'},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_patch_draft_devis_still_editable(self):
        devis = self._devis(4, Devis.Statut.BROUILLON)
        r = self.api.patch(
            f'/api/django/ventes/devis/{devis.id}/', {'note': 'edit ok'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.note, 'edit ok')

    def test_deactivating_accepted_devis_still_allowed(self):
        """Superseded revision path (reviser) must remain possible."""
        devis = self._devis(5, Devis.Statut.ACCEPTE)
        r = self.api.patch(
            f'/api/django/ventes/devis/{devis.id}/', {'is_active': False},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertFalse(devis.is_active)

    def test_patch_ligne_of_accepted_devis_rejected(self):
        devis = self._devis(6, Devis.Statut.ACCEPTE)
        ligne = LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='Panneau',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        r = self.api.patch(
            f'/api/django/ventes/devis-lignes/{ligne.id}/',
            {'quantite': '2'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite, Decimal('1'))

    def test_patch_ligne_of_draft_devis_still_editable(self):
        devis = self._devis(7, Devis.Statut.BROUILLON)
        ligne = LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='Panneau',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        r = self.api.patch(
            f'/api/django/ventes/devis-lignes/{ligne.id}/',
            {'quantite': '3'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite, Decimal('3'))

    def test_create_ligne_on_accepted_devis_rejected(self):
        devis = self._devis(8, Devis.Statut.ACCEPTE)
        r = self.api.post(
            '/api/django/ventes/devis-lignes/',
            {'devis': devis.id, 'produit': self.produit.id,
             'designation': 'Extra', 'quantite': '1',
             'prix_unitaire': '1000', 'remise': '0'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_delete_ligne_of_accepted_devis_rejected(self):
        devis = self._devis(9, Devis.Statut.ACCEPTE)
        ligne = LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='Panneau',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        r = self.api.delete(f'/api/django/ventes/devis-lignes/{ligne.id}/')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertTrue(LigneDevis.objects.filter(id=ligne.id).exists())

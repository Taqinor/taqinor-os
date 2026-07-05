"""Tests YLEDG3 — le verrou de période comptable (FG115) s'applique désormais
aux documents ventes : PATCH d'une facture émise datée dans une période
clôturée, paiement anti-daté dedans, annulation, et création d'avoir sont
refusés en 400 ; une période ouverte laisse tout passer ; une société sans
période comptable reste inchangée (garde silencieuse)."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta.models import PeriodeComptable
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Avoir, Facture, LigneFacture

User = get_user_model()


def make_company(slug='yledg3-co', nom='YLEDG3 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestPeriodeVerrouilleeVentes(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='yledg3_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='L3',
            email='yledg3@example.com', telephone='+212600000007')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-YLEDG3',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'))
        # Facture émise datée DANS février 2026 (date_emission auto_now_add —
        # on la force après coup via update() pour tomber dans la période).
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-YLEDG3-0001',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        Facture.objects.filter(pk=self.facture.pk).update(
            date_emission=date(2026, 2, 10))
        self.facture.refresh_from_db()
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))

    def _lock_february(self):
        return PeriodeComptable.objects.create(
            company=self.company, date_debut=date(2026, 2, 1),
            date_fin=date(2026, 2, 28), verrouillee=True)

    def test_patch_facture_in_locked_period_rejected(self):
        self._lock_february()
        r = self.api.patch(
            f'/api/django/ventes/factures/{self.facture.id}/',
            {'note': 'edit'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_patch_facture_open_period_still_works(self):
        r = self.api.patch(
            f'/api/django/ventes/factures/{self.facture.id}/',
            {'note': 'edit ok'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_paiement_antidate_dans_periode_verrouillee_rejected(self):
        self._lock_february()
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            f'enregistrer-paiement/',
            {'montant': '1000', 'date_paiement': '2026-02-15',
             'mode': 'virement'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_paiement_hors_periode_verrouillee_ok(self):
        self._lock_february()
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            f'enregistrer-paiement/',
            {'montant': '1000', 'date_paiement': '2026-03-15',
             'mode': 'virement'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_annuler_facture_in_locked_period_rejected(self):
        self._lock_february()
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/annuler/')
        self.assertEqual(r.status_code, 400, r.data)
        self.facture.refresh_from_db()
        self.assertNotEqual(self.facture.statut, Facture.Statut.ANNULEE)

    def test_creer_avoir_in_locked_period_rejected(self):
        self._lock_february()
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'erreur'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_annuler_avoir_in_locked_period_rejected(self):
        # Créer l'avoir HORS période verrouillée, puis verrouiller ensuite
        # pour tester l'annulation seule.
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'erreur'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        avoir_id = r.data['id']
        avoir = Avoir.objects.get(pk=avoir_id)
        Avoir.objects.filter(pk=avoir.pk).update(date_emission=date(2026, 2, 10))
        PeriodeComptable.objects.create(
            company=self.company, date_debut=date(2026, 2, 1),
            date_fin=date(2026, 2, 28), verrouillee=True)
        r2 = self.api.post(
            f'/api/django/ventes/avoirs/{avoir_id}/annuler/')
        self.assertEqual(r2.status_code, 400, r2.data)

    def test_no_periode_at_all_unaffected(self):
        """Société sans aucune PeriodeComptable — comportement inchangé."""
        r = self.api.patch(
            f'/api/django/ventes/factures/{self.facture.id}/',
            {'note': 'sans compta'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

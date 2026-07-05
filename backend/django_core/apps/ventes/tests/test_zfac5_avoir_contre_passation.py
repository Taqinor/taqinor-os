"""
ZFAC5 — Mode « annuler & contre-passer » sur l'assistant d'avoir
(reverse-and-cancel).

``creer-avoir`` gagne un paramètre ``mode`` ∈ {``correction`` (défaut,
comportement inchangé), ``contre_passation``} : en ``contre_passation``
l'avoir reprend TOUTES les lignes de la facture et, à son émission, la
facture d'origine passe ``annulee`` avec un ``FactureActivity`` liant les
deux pièces ; refusé (400) si la facture a déjà des paiements.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_zfac5_avoir_contre_passation -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Avoir, Facture, FactureActivity, LigneFacture, Paiement

User = get_user_model()


def make_company(slug='zfac5-co', nom='ZFAC5 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestAvoirContrePassation(TestCase):
    def setUp(self):
        from apps.roles.models import ALL_PERMISSIONS, Role
        self.company = make_company()
        admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username='zfac5_admin', password='x', role=admin_role,
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZFAC5',
            telephone='+212600000003')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau PV', sku='PVZ5',
            prix_vente=Decimal('1000'), quantite_stock=100, tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-ZFAC5-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.panneau, designation='Panneau PV',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_contre_passation_creates_mirror_avoir_and_cancels_facture(self):
        api = self._api(self.admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'mode': 'contre_passation', 'motif': 'Erreur de facturation'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        avoir = Avoir.objects.get(id=resp.data['id'])
        # Avoir miroir : mêmes montants que la facture d'origine.
        self.assertEqual(avoir.total_ttc, self.facture.total_ttc)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.ANNULEE)
        # FactureActivity lie les deux pièces.
        link = FactureActivity.objects.filter(
            facture=self.facture, field='statut',
            new_value=Facture.Statut.ANNULEE).first()
        self.assertIsNotNone(link)
        self.assertIn(avoir.reference, link.body)

    def test_correction_mode_unchanged(self):
        api = self._api(self.admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'Retour partiel',
             'lignes': [{'produit': self.panneau.id, 'designation': 'Panneau PV',
                         'quantite': '1', 'prix_unitaire': '1000',
                         'taux_tva': '20'}]},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.facture.refresh_from_db()
        # Mode par défaut ('correction') : la facture reste émise.
        self.assertEqual(self.facture.statut, Facture.Statut.EMISE)

    def test_contre_passation_refused_if_facture_has_payments(self):
        Paiement.objects.create(
            company=self.company, facture=self.facture, montant=Decimal('1000'),
            date_paiement=timezone.now().date(), mode='virement',
            created_by=self.admin,
        )
        api = self._api(self.admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'mode': 'contre_passation'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.EMISE)

    def test_invalid_mode_rejected(self):
        api = self._api(self.admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'mode': 'bogus'}, format='json')
        self.assertEqual(resp.status_code, 400)

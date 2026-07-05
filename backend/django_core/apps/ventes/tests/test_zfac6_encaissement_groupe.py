"""
ZFAC6 — Encaissement groupé : un paiement couvrant plusieurs factures d'un
même client (Group Payments).

Un montant réparti sur plusieurs factures (FIFO par échéance) crée un
``Paiement`` par facture, factures d'un autre client refusées (400),
atomicité (échec → rollback total).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_zfac6_encaissement_groupe -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Facture, Paiement

User = get_user_model()


def make_company(slug='zfac6-co', nom='ZFAC6 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestEncaissementGroupe(TestCase):
    def setUp(self):
        from apps.roles.models import RESPONSABLE_PERMISSIONS, Role
        self.company = make_company()
        resp_role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=RESPONSABLE_PERMISSIONS, est_systeme=True)
        self.resp = User.objects.create_user(
            username='zfac6_resp', password='x', role=resp_role,
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZFAC6',
            telephone='+212600000004')
        today = timezone.now().date()
        self.f1 = Facture.objects.create(
            company=self.company, reference='FAC-ZFAC6-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('4166.67'), montant_tva=Decimal('833.33'),
            montant_ttc=Decimal('5000'),
            date_echeance=today.replace(day=1) if today.day > 1 else today)
        self.f2 = Facture.objects.create(
            company=self.company, reference='FAC-ZFAC6-0002',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('2500'), montant_tva=Decimal('500'),
            montant_ttc=Decimal('3000'), date_echeance=today)
        self.f3 = Facture.objects.create(
            company=self.company, reference='FAC-ZFAC6-0003',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('1666.67'), montant_tva=Decimal('333.33'),
            montant_ttc=Decimal('2000'), date_echeance=today)

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_fifo_split_across_three_factures(self):
        api = self._api(self.resp)
        # 5000 + 3000 + 2000 = 10000, on règle 10000 → les trois soldées.
        resp = api.post(
            '/api/django/ventes/factures/encaissement-groupe/',
            {'client': self.client_obj.id, 'montant': '10000',
             'mode': 'virement', 'date': str(timezone.now().date()),
             'factures': [self.f1.id, self.f2.id, self.f3.id]},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Paiement.objects.filter(
            facture__in=[self.f1, self.f2, self.f3]).count(), 3)
        for f in (self.f1, self.f2, self.f3):
            f.refresh_from_db()
            self.assertEqual(f.statut, Facture.Statut.PAYEE)
            self.assertEqual(f.montant_du, Decimal('0'))

    def test_partial_split_settles_only_what_amount_covers(self):
        api = self._api(self.resp)
        # 6000 réglés sur f1(5000)+f2(3000)+f3(2000) → f1 soldée, f2 partielle
        # (1000/3000), f3 non touchée.
        resp = api.post(
            '/api/django/ventes/factures/encaissement-groupe/',
            {'client': self.client_obj.id, 'montant': '6000',
             'mode': 'virement', 'date': str(timezone.now().date()),
             'factures': [self.f1.id, self.f2.id, self.f3.id]},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.f1.refresh_from_db()
        self.f2.refresh_from_db()
        self.f3.refresh_from_db()
        self.assertEqual(self.f1.statut, Facture.Statut.PAYEE)
        self.assertEqual(self.f2.montant_du, Decimal('2000.00'))
        self.assertEqual(self.f3.montant_du, Decimal('2000.00'))

    def test_other_client_facture_rejected(self):
        other_client = Client.objects.create(
            company=self.company, nom='Autre', prenom='Client',
            telephone='+212600000005')
        other_facture = Facture.objects.create(
            company=self.company, reference='FAC-ZFAC6-9999',
            client=other_client, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('1000'))
        api = self._api(self.resp)
        resp = api.post(
            '/api/django/ventes/factures/encaissement-groupe/',
            {'client': self.client_obj.id, 'montant': '1000',
             'mode': 'virement', 'date': str(timezone.now().date()),
             'factures': [self.f1.id, other_facture.id]},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Paiement.objects.filter(facture=self.f1).count(), 0)

    def test_atomic_rollback_on_invalid_facture_id(self):
        api = self._api(self.resp)
        resp = api.post(
            '/api/django/ventes/factures/encaissement-groupe/',
            {'client': self.client_obj.id, 'montant': '5000',
             'mode': 'virement', 'date': str(timezone.now().date()),
             'factures': [self.f1.id, 999999]},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Paiement.objects.filter(facture=self.f1).count(), 0)

    def test_explicit_repartition(self):
        api = self._api(self.resp)
        resp = api.post(
            '/api/django/ventes/factures/encaissement-groupe/',
            {'client': self.client_obj.id, 'montant': '5000',
             'mode': 'cheque', 'date': str(timezone.now().date()),
             'factures': [self.f1.id, self.f2.id],
             'repartition': {str(self.f1.id): '3000', str(self.f2.id): '2000'}},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.f1.refresh_from_db()
        self.f2.refresh_from_db()
        self.assertEqual(self.f1.montant_du, Decimal('2000.00'))
        self.assertEqual(self.f2.montant_du, Decimal('1000.00'))

"""
ZFAC10 — Analyse de facturation (rapport dédié CA facturé par
période/client/statut).

L'endpoint renvoie les totaux HT/TVA/TTC par mois/client/statut sur la
période, l'export CSV se télécharge, cross-company isolé, factures annulées
exclues du CA.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_zfac10_analyse_facturation -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()
TODAY = timezone.now().date()
MONTH = TODAY.strftime('%Y-%m')


def make_company(slug='zfac10-co', nom='ZFAC10 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestAnalyseFacturation(TestCase):
    def setUp(self):
        from apps.roles.models import RESPONSABLE_PERMISSIONS, Role
        self.company = make_company()
        resp_role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=RESPONSABLE_PERMISSIONS, est_systeme=True)
        self.resp = User.objects.create_user(
            username='zfac10_resp', password='x', role=resp_role,
            role_legacy='responsable', company=self.company)
        self.client_a = Client.objects.create(
            company=self.company, nom='A', prenom='Client',
            telephone='+212600000010')
        Facture.objects.create(
            company=self.company, reference='FAC-ZFAC10-0001',
            client=self.client_a, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'), date_emission=TODAY)
        Facture.objects.create(
            company=self.company, reference='FAC-ZFAC10-0002',
            client=self.client_a, statut=Facture.Statut.PAYEE,
            montant_ht=Decimal('2000'), montant_tva=Decimal('400'),
            montant_ttc=Decimal('2400'), date_emission=TODAY)
        # Facture annulée : EXCLUE du CA.
        Facture.objects.create(
            company=self.company, reference='FAC-ZFAC10-0003',
            client=self.client_a, statut=Facture.Statut.ANNULEE,
            montant_ht=Decimal('9999'), montant_tva=Decimal('1999.8'),
            montant_ttc=Decimal('11998.8'), date_emission=TODAY)

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_aggregates_by_month_client_statut(self):
        api = self._api(self.resp)
        resp = api.get(
            f'/api/django/ventes/etats/analyse-facturation/?month={MONTH}')
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data
        # Deux lignes distinctes (statuts différents), la 3e (annulée) exclue.
        self.assertEqual(len(rows), 2)
        statuts = {r['statut'] for r in rows}
        self.assertEqual(statuts, {'emise', 'payee'})
        total_ttc = sum(Decimal(r['total_ttc']) for r in rows)
        self.assertEqual(total_ttc, Decimal('3600.00'))

    def test_csv_export_downloads(self):
        api = self._api(self.resp)
        resp = api.get(
            f'/api/django/ventes/etats/analyse-facturation/'
            f'?month={MONTH}&export=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        content = resp.content.decode('utf-8')
        self.assertIn('Mois', content)
        self.assertIn('Total TTC', content)

    def test_cross_company_isolation(self):
        other_company = make_company(slug='zfac10-other', nom='Other Co')
        from apps.roles.models import RESPONSABLE_PERMISSIONS, Role
        other_role = Role.objects.create(
            company=other_company, nom='Responsable',
            permissions=RESPONSABLE_PERMISSIONS, est_systeme=True)
        other_resp = User.objects.create_user(
            username='zfac10_other', password='x', role=other_role,
            role_legacy='responsable', company=other_company)
        api = self._api(other_resp)
        resp = api.get(
            f'/api/django/ventes/etats/analyse-facturation/?month={MONTH}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [])

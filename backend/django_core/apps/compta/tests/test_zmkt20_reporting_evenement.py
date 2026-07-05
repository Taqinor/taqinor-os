"""ZMKT20 — Reporting événement (participants & billetterie).

Couvre : le report agrège présence + billetterie + leads par événement
company-scoped, la recette théorique somme correctement, groupements
type/mois, export XLSX, tests des agrégats.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.compta.models import BilletEvenement, EvenementMarketing


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ReportingEvenementTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt20', 'ZMKT20')
        self.evt = EvenementMarketing.objects.create(
            company=self.co, nom='Salon', type_evenement='salon',
            date_debut=timezone.now())

    def test_agrege_presence(self):
        present = services.inscrire_evenement(self.evt, nom='Present')
        services.pointer_presence(present)
        services.inscrire_evenement(self.evt, nom='Absent')
        rapport = services.reporting_evenements(self.co)
        entry = rapport[0]
        self.assertEqual(entry['nb_inscrits'], 2)
        self.assertEqual(entry['nb_presents'], 1)
        self.assertEqual(entry['taux_presence_pct'], 50.0)

    def test_recette_theorique_correcte(self):
        billet = BilletEvenement.objects.create(
            company=self.co, evenement=self.evt, libelle='Standard',
            prix_ttc_mad=Decimal('100'))
        services.inscrire_evenement(self.evt, nom='A', billet=billet)
        services.inscrire_evenement(self.evt, nom='B', billet=billet)
        rapport = services.reporting_evenements(self.co)
        self.assertEqual(
            Decimal(rapport[0]['recette_theorique_mad']), Decimal('200'))

    def test_leads_generes_comptes(self):
        services.inscrire_evenement(self.evt, nom='LeadGen')
        rapport = services.reporting_evenements(self.co)
        self.assertEqual(rapport[0]['nb_leads'], 1)

    def test_groupby_type(self):
        EvenementMarketing.objects.create(
            company=self.co, nom='Webinaire', type_evenement='webinaire',
            date_debut=timezone.now())
        rapport = services.reporting_evenements(self.co, groupby='type')
        self.assertIn('salon', rapport)
        self.assertIn('webinaire', rapport)

    def test_isolation_multi_tenant(self):
        other = make_company('zmkt20-b', 'ZMKT20-B')
        rapport_other = services.reporting_evenements(other)
        self.assertEqual(rapport_other, [])

    def test_endpoint_export_xlsx(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()
        user = User.objects.create_user(
            username='zmkt20-user', password='x', company=self.co,
            role_legacy='responsable')
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.get(
            '/api/django/compta/evenements-marketing/reporting/export/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheet', resp['Content-Type'])

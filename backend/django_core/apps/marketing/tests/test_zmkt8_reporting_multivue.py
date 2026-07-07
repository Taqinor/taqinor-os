"""ZMKT8 — Reporting SMS/campagnes multi-vue (Graph / Cohorte / Pivot) avec
mesures CTR/CTOR/délivrabilité.

Couvre : l'endpoint renvoie les mesures groupables demandées company-
scoped, CTR/CTOR corrects (division par zéro = 0), export XLSX, tests des
agrégats.
"""
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import Campagne, EnvoiCampagne


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ReportingMultivueTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt8', 'ZMKT8')

    def test_reporting_par_canal(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        for i in range(10):
            EnvoiCampagne.objects.create(
                company=self.co, campagne=camp, destinataire=f'u{i}@x.ma',
                statut=EnvoiCampagne.Statut.ENVOYE)
        rapport = services.reporting_campagnes(self.co, groupby='canal')
        self.assertEqual(len(rapport), 1)
        self.assertEqual(rapport[0]['delivres'], 10)

    def test_ctr_ctor_corrects(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C2', canal=Campagne.Canal.EMAIL)
        for i in range(10):
            EnvoiCampagne.objects.create(
                company=self.co, campagne=camp, destinataire=f'u{i}@x.ma',
                statut=EnvoiCampagne.Statut.ENVOYE)
        maintenant = timezone.now()
        for i in range(4):
            EnvoiCampagne.objects.filter(
                campagne=camp, destinataire=f'u{i}@x.ma').update(
                ouvert_le=maintenant)
        for i in range(2):
            EnvoiCampagne.objects.filter(
                campagne=camp, destinataire=f'u{i}@x.ma').update(
                clique_le=maintenant)
        rapport = services.reporting_campagnes(self.co, groupby='canal')
        entry = rapport[0]
        self.assertEqual(entry['ctr_pct'], 20.0)
        self.assertEqual(entry['ctor_pct'], 50.0)

    def test_division_par_zero_sans_donnees(self):
        rapport = services.reporting_campagnes(self.co, groupby='canal')
        self.assertEqual(rapport, [])

    def test_groupby_campagne(self):
        camp1 = Campagne.objects.create(
            company=self.co, nom='C3', canal=Campagne.Canal.EMAIL)
        camp2 = Campagne.objects.create(
            company=self.co, nom='C4', canal=Campagne.Canal.SMS)
        EnvoiCampagne.objects.create(
            company=self.co, campagne=camp1, destinataire='a@x.ma',
            statut=EnvoiCampagne.Statut.ENVOYE)
        EnvoiCampagne.objects.create(
            company=self.co, campagne=camp2, destinataire='b@x.ma',
            statut=EnvoiCampagne.Statut.ENVOYE)
        rapport = services.reporting_campagnes(self.co, groupby='campagne')
        self.assertEqual(len(rapport), 2)

    def test_isolation_multi_tenant(self):
        other = make_company('zmkt8-b', 'ZMKT8-B')
        camp = Campagne.objects.create(
            company=self.co, nom='C5', canal=Campagne.Canal.EMAIL)
        EnvoiCampagne.objects.create(
            company=self.co, campagne=camp, destinataire='a@x.ma',
            statut=EnvoiCampagne.Statut.ENVOYE)
        rapport_other = services.reporting_campagnes(other, groupby='canal')
        self.assertEqual(rapport_other, [])

    def test_endpoint_reporting(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()
        camp = Campagne.objects.create(
            company=self.co, nom='C6', canal=Campagne.Canal.EMAIL)
        EnvoiCampagne.objects.create(
            company=self.co, campagne=camp, destinataire='a@x.ma',
            statut=EnvoiCampagne.Statut.ENVOYE)
        user = User.objects.create_user(
            username='zmkt8-user', password='x', company=self.co,
            role_legacy='responsable')
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.get('/api/django/compta/campagnes/reporting/')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_endpoint_export_xlsx(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()
        user = User.objects.create_user(
            username='zmkt8-user2', password='x', company=self.co,
            role_legacy='responsable')
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.get('/api/django/compta/campagnes/reporting/export/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheet', resp['Content-Type'])

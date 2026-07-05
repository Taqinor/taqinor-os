"""XMKT31 — Conteneur de campagne multi-canal.

Couvre : rattacher N objets à une campagne mère, la vue mère agrège
KPI/coûts/ROI de tous les enfants, tests.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import Campagne


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class CampagneParenteTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt31', 'XMKT31')
        self.mere = Campagne.objects.create(
            company=self.co, nom='Opération SIAM', canal=Campagne.Canal.EMAIL,
            cout_reel_mad=Decimal('500'))

    def test_rattacher_enfant_campagne(self):
        enfant = Campagne.objects.create(
            company=self.co, nom='SIAM SMS', canal=Campagne.Canal.SMS,
            parente=self.mere)
        self.assertEqual(self.mere.enfants.count(), 1)
        self.assertEqual(enfant.parente_id, self.mere.id)

    def test_rattacher_objet_opaque_idempotent(self):
        services.rattacher_a_campagne_mere(
            self.mere, type_objet='sequence', objet_id=7)
        services.rattacher_a_campagne_mere(
            self.mere, type_objet='sequence', objet_id=7)
        self.mere.refresh_from_db()
        self.assertEqual(len(self.mere.rattachements), 1)

    def test_rattacher_plusieurs_types(self):
        services.rattacher_a_campagne_mere(
            self.mere, type_objet='sequence', objet_id=1)
        services.rattacher_a_campagne_mere(
            self.mere, type_objet='evenement', objet_id=2)
        services.rattacher_a_campagne_mere(
            self.mere, type_objet='code_promo', objet_id=3)
        self.mere.refresh_from_db()
        self.assertEqual(len(self.mere.rattachements), 3)

    def test_kpi_mere_agrege_destinataires(self):
        Campagne.objects.create(
            company=self.co, nom='Enfant1', canal=Campagne.Canal.EMAIL,
            parente=self.mere, nb_destinataires=10, nb_envois=10)
        Campagne.objects.create(
            company=self.co, nom='Enfant2', canal=Campagne.Canal.SMS,
            parente=self.mere, nb_destinataires=5, nb_envois=5)
        kpi = services.kpi_campagne_mere(self.mere)
        self.assertEqual(kpi['nb_enfants'], 2)
        self.assertEqual(kpi['nb_destinataires'], 15)
        self.assertEqual(kpi['nb_envois'], 15)

    def test_kpi_mere_agrege_couts(self):
        Campagne.objects.create(
            company=self.co, nom='EnfantCout', canal=Campagne.Canal.EMAIL,
            parente=self.mere, cout_reel_mad=Decimal('300'))
        kpi = services.kpi_campagne_mere(self.mere)
        self.assertEqual(Decimal(kpi['cout_total_mad']), Decimal('800'))

    def test_kpi_mere_sans_enfants(self):
        seule = Campagne.objects.create(
            company=self.co, nom='Seule', canal=Campagne.Canal.EMAIL)
        kpi = services.kpi_campagne_mere(seule)
        self.assertEqual(kpi['nb_enfants'], 0)

    def test_endpoint_rattacher(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()
        user = User.objects.create_user(
            username='xmkt31-user', password='x', company=self.co,
            role_legacy='responsable')
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.post(
            f'/api/django/compta/campagnes/{self.mere.id}/rattacher/',
            data={'type': 'formulaire', 'id': 5}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.mere.refresh_from_db()
        self.assertEqual(len(self.mere.rattachements), 1)

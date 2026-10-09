"""ACRM9 (C-ACRM-005) — les LECTURES des viewsets enfants d'un lead ou d'un
client sont bornées à la PORTÉE du rôle.

Sonde V_VA LVIEW2-1 : ``concurrents-perte/?lead=L1`` rendait ``count 1`` et
``lead_nom`` « HorsPortee » à un Commercial qui ne peut pas ouvrir L1 ;
points de contact, attribution et playbook répondaient 200 sur L1.
Désormais : aucune ligne de L1 (ni son nom), attribution et playbook en 404 ;
un admin voit tout comme avant.

Rôles réels ; aucun mock.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import (
    Client, ConcurrentPerte, ForecastEntry, Lead, Parrainage, PointContact,
    SiteProfile)
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    COMMERCIAL_PERMISSIONS, DIRECTEUR_PERMISSIONS)

User = get_user_model()
BASE = '/api/django/crm/'
NOM_HORS = 'HorsPortee'


def _lignes(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class PorteeEnfantsLecturesTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM9 Solaire', slug='acrm9-lectures')
        commercial = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS), est_systeme=True)
        directeur = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.moi = User.objects.create_user(
            username='acrm9-moi', password='x', company=self.company,
            role=commercial)
        self.collegue = User.objects.create_user(
            username='acrm9-collegue', password='x', company=self.company,
            role=commercial)
        self.admin = User.objects.create_user(
            username='acrm9-admin', password='x', company=self.company,
            role=directeur)
        self.client_h = Client.objects.create(
            company=self.company, nom=NOM_HORS, prenom='Client')
        self.l1 = Lead.objects.create(
            company=self.company, nom=NOM_HORS, owner=self.collegue,
            client=self.client_h)
        self.cp = ConcurrentPerte.objects.create(
            company=self.company, lead=self.l1, concurrent_nom='Rival')
        self.pc = PointContact.objects.create(
            company=self.company, lead=self.l1, canal='telephone',
            date_contact=timezone.now())
        self.fe = ForecastEntry.objects.create(
            company=self.company, lead=self.l1,
            montant_prevu=Decimal('1000'))
        self.sp = SiteProfile.objects.create(
            company=self.company, client=self.client_h)
        self.pa = Parrainage.objects.create(
            company=self.company, parrain=self.client_h,
            filleul_lead=self.l1, filleul_nom='Filleul')

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(user)}'))
        return api

    def _listes(self, user):
        api = self._api(user)
        routes = {
            'concurrents': f'{BASE}concurrents-perte/?lead={self.l1.pk}',
            'points_contact': f'{BASE}points-contact/?lead={self.l1.pk}',
            'forecast': f'{BASE}forecast-entries/',
            'site_profiles': f'{BASE}site-profiles/',
            'parrainages': f'{BASE}parrainages/',
        }
        out = {}
        for nom, url in routes.items():
            resp = api.get(url)
            self.assertEqual(resp.status_code, 200, (nom, resp.content))
            out[nom] = resp
        return out

    def test_listes_sans_l1_pour_le_commercial(self):
        for nom, resp in self._listes(self.moi).items():
            self.assertEqual(len(_lignes(resp)), 0, nom)
            self.assertNotIn(NOM_HORS, resp.content.decode(), nom)

    def test_details_hors_portee_404(self):
        api = self._api(self.moi)
        for url in (f'{BASE}concurrents-perte/{self.cp.pk}/',
                    f'{BASE}points-contact/{self.pc.pk}/',
                    f'{BASE}forecast-entries/{self.fe.pk}/',
                    f'{BASE}site-profiles/{self.sp.pk}/',
                    f'{BASE}parrainages/{self.pa.pk}/',
                    f'{BASE}points-contact/attribution/?lead={self.l1.pk}',
                    f'{BASE}leads/{self.l1.pk}/playbook/'):
            self.assertEqual(api.get(url).status_code, 404, url)

    def test_admin_voit_tout(self):
        for nom, resp in self._listes(self.admin).items():
            self.assertEqual(len(_lignes(resp)), 1, nom)
        api = self._api(self.admin)
        self.assertEqual(api.get(
            f'{BASE}points-contact/attribution/?lead={self.l1.pk}'
        ).status_code, 200)
        self.assertEqual(
            api.get(f'{BASE}leads/{self.l1.pk}/playbook/').status_code, 200)

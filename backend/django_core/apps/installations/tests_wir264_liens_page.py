"""WIR264 — les liens publics d'intervention mènent à des PAGES.

Constat corrigé : `lien-client` et `lien-rapport` renvoyaient un `path` amputé
(`/public/installations/intervention/<token>/`) — ni une page, ni même un
chemin d'API valide (le préfixe `/api/django` manquait). Les deux actions
renvoient désormais le chemin de la PAGE publique (`/intervention/<token>`,
`/intervention-rapport/<token>`) plus son URL absolue, comme
`sav.views.lien_client` (FG86).

Run :
    python manage.py test apps.installations.tests_wir264_liens_page -v2
"""
import itertools
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations.models import Intervention
from apps.installations.services import create_installation_from_devis

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'wir264-co-{n}', defaults={'nom': f'WIR264 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'wir264-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_chantier(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'wir264-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-WIR264-{company.id}-{n}',
        client=client, lead=lead, statut=Devis.Statut.ACCEPTE,
        taux_tva=Decimal('20'), mode_installation='residentiel')
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


class TestLiensPublicsPointentVersDesPages(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)
        self.interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user, date_prevue=date.today())

    def test_lien_client_renvoie_le_chemin_de_la_page(self):
        resp = self.api.get(
            f'{BASE}/interventions/{self.interv.id}/lien-client/')
        self.assertEqual(resp.status_code, 200, resp.content)
        token = resp.data['token']
        self.assertEqual(resp.data['path'], f'/intervention/{token}')
        self.assertTrue(resp.data['url'].endswith(f'/intervention/{token}'))
        # Ni l'ancien chemin amputé, ni un chemin d'API.
        self.assertNotIn('/public/installations/', resp.data['path'])
        self.assertNotIn('/api/django/', resp.data['path'])

    def test_lien_rapport_renvoie_le_chemin_de_la_page(self):
        resp = self.api.get(
            f'{BASE}/interventions/{self.interv.id}/lien-rapport/')
        self.assertEqual(resp.status_code, 200, resp.content)
        token = resp.data['token']
        self.assertEqual(
            resp.data['path'], f'/intervention-rapport/{token}')
        self.assertTrue(
            resp.data['url'].endswith(f'/intervention-rapport/{token}'))
        self.assertNotIn('/public/installations/', resp.data['path'])
        self.assertNotIn('/api/django/', resp.data['path'])

    def test_les_deux_jetons_sont_distincts(self):
        suivi = self.api.get(
            f'{BASE}/interventions/{self.interv.id}/lien-client/').data
        rapport = self.api.get(
            f'{BASE}/interventions/{self.interv.id}/lien-rapport/').data
        self.assertNotEqual(suivi['token'], rapport['token'])

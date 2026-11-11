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
from django.test import TestCase, override_settings
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

    @override_settings(
        PUBLIC_BASE_URL='https://erp.example.invalid',
        ALLOWED_HOSTS=['ancien.example.invalid', 'testserver'],
        ANYMAIL={'SENDGRID_API_KEY': 'sg-test-key'},
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_liens_sur_base_publique_et_non_sur_l_hote(self):
        """AMSG69 — requête entrée par l'ANCIEN hôte : chaque lien client
        (lien-client, lien-rapport, livraison, invitation et lien d'accès du
        portail, rapport diffusé par le beat) commence par PUBLIC_BASE_URL."""
        from types import SimpleNamespace
        from django.core import mail
        from django.test import RequestFactory
        from apps.installations.livraison_client_notify import _livraison_lien
        from apps.portail.models import ComptePortailClient
        from apps.portail.services import provisionner_compte_portail_client
        from apps.reporting.diffusion_views import lien_rapport
        base, hote = 'https://erp.example.invalid/', 'ancien.example.invalid'
        liens = [self.api.get(
            f'{BASE}/interventions/{self.interv.id}/{action}/',
            HTTP_HOST=hote).data['url']
            for action in ('lien-client', 'lien-rapport')]
        liens.append(_livraison_lien(
            None, request=RequestFactory().get('/', HTTP_HOST=hote)))
        liens.append(lien_rapport(SimpleNamespace(pk=1)))  # beat, sans requête
        liens.append(lien_rapport(SimpleNamespace(pk=1),
                                  base_url=f'http://{hote}'))
        admin_portail, _ = provisionner_compte_portail_client(
            self.company, self.inst.client_id)
        admin_portail.must_change_password = False
        admin_portail.save(update_fields=['must_change_password'])
        portail = APIClient()
        portail.force_authenticate(user=admin_portail)
        r = portail.post('/api/django/portail/mon-equipe/', {
            'email': 'membre@example.invalid', 'role': 'lecture'},
            format='json', HTTP_HOST=hote)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIn(f'{base}portail/invitation/accepter', mail.outbox[-1].body)
        compte = ComptePortailClient.objects.get(
            company=self.company, client_id=self.inst.client_id)
        liens.append(auth(make_user(self.company, role='admin')).post(
            f'/api/django/portail/comptes-portail/{compte.id}/lien-acces/',
            HTTP_HOST=hote).data['lien'])
        for lien in liens:
            self.assertTrue(lien.startswith(base), lien)
            self.assertNotIn(hote, lien)

    def test_les_deux_jetons_sont_distincts(self):
        suivi = self.api.get(
            f'{BASE}/interventions/{self.interv.id}/lien-client/').data
        rapport = self.api.get(
            f'{BASE}/interventions/{self.interv.id}/lien-rapport/').data
        self.assertNotEqual(suivi['token'], rapport['token'])

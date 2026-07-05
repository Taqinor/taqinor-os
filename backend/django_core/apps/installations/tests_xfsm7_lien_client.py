"""
XFSM7 — Lien public « technicien en route » (suivi de visite).

Couvre :
  * la génération lazy/idempotente du jeton via l'action ``lien-client`` ;
  * la page publique (sans login) renvoie statut, technicien, fenêtre XFSM5 ;
  * aucune donnée interne (coûts) ne fuite dans le payload ;
  * un token invalide/expiré renvoie 404 ;
  * l'ETA n'est calculée QUE si le statut est « En route » et qu'une position
    de départ + le GPS du chantier sont connus.

Run :
    python manage.py test apps.installations.tests_xfsm7_lien_client -v2
"""
import itertools
from datetime import date, timedelta
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
PUBLIC_BASE = '/api/django/public/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xfsm7-co-{n}', defaults={'nom': nom or f'XFSM7 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xfsm7-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_chantier(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'xfsm7-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-XFSM7-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    inst, _ = create_installation_from_devis(devis, user, company)
    inst.gps_lat = Decimal('33.573110')
    inst.gps_lng = Decimal('-7.589843')
    inst.save(update_fields=['gps_lat', 'gps_lng'])
    return inst


class TestLienClientToken(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)
        self.interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user, technicien=self.user,
            fenetre_debut='08:00', fenetre_fin='10:00',
            date_prevue=date.today())

    def test_lien_client_action_generates_token(self):
        resp = self.api.get(f'{BASE}/interventions/{self.interv.id}/lien-client/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['token'])
        self.interv.refresh_from_db()
        self.assertEqual(self.interv.lien_client_token, resp.data['token'])

    def test_lien_client_action_idempotent(self):
        resp1 = self.api.get(f'{BASE}/interventions/{self.interv.id}/lien-client/')
        resp2 = self.api.get(f'{BASE}/interventions/{self.interv.id}/lien-client/')
        self.assertEqual(resp1.data['token'], resp2.data['token'])

    def test_public_page_no_login(self):
        token = self.interv.ensure_lien_client_token()
        pub = APIClient()
        resp = pub.get(f'{PUBLIC_BASE}/intervention/{token}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], Intervention.Statut.A_PREPARER)
        self.assertEqual(resp.data['fenetre_debut'], '08:00:00')
        self.assertIn('technicien_nom', resp.data)
        # Aucune donnée interne (coûts) — payload restreint aux clés attendues.
        self.assertNotIn('prix', resp.data)
        self.assertNotIn('cout', resp.data)

    def test_public_page_unknown_token_404(self):
        pub = APIClient()
        resp = pub.get(f'{PUBLIC_BASE}/intervention/does-not-exist/')
        self.assertEqual(resp.status_code, 404)

    def test_eta_absent_without_en_route(self):
        token = self.interv.ensure_lien_client_token()
        self.interv.depart_gps_lat = Decimal('33.589886')
        self.interv.depart_gps_lng = Decimal('-7.603869')
        self.interv.save(update_fields=['depart_gps_lat', 'depart_gps_lng'])
        pub = APIClient()
        resp = pub.get(f'{PUBLIC_BASE}/intervention/{token}/')
        self.assertIsNone(resp.data['eta_minutes'])

    def test_eta_present_when_en_route_with_gps(self):
        token = self.interv.ensure_lien_client_token()
        self.interv.statut = Intervention.Statut.EN_ROUTE
        self.interv.depart_gps_lat = Decimal('33.589886')
        self.interv.depart_gps_lng = Decimal('-7.603869')
        self.interv.save(
            update_fields=['statut', 'depart_gps_lat', 'depart_gps_lng'])
        pub = APIClient()
        resp = pub.get(f'{PUBLIC_BASE}/intervention/{token}/')
        self.assertIsNotNone(resp.data['distance_km'])
        self.assertIsNotNone(resp.data['eta_minutes'])
        self.assertGreater(resp.data['eta_minutes'], 0)

    def test_expired_link_returns_404(self):
        token = self.interv.ensure_lien_client_token()
        self.interv.date_prevue = date.today() - timedelta(days=5)
        self.interv.save(update_fields=['date_prevue'])
        pub = APIClient()
        resp = pub.get(f'{PUBLIC_BASE}/intervention/{token}/')
        self.assertEqual(resp.status_code, 404)

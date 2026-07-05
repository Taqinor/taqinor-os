"""XSAV19 — Page publique « Signaler un problème » via QR équipement.

Couvre :
  * scan (public_token valide) -> ticket créé lié au bon équipement/société ;
  * token invalide/absent -> 404 sans fuite ;
  * honeypot rempli -> 201 factice, aucun ticket créé ;
  * aucune donnée interne exposée dans la réponse publique ;
  * étiquettes régénérées avec l'URL publique (?public=1).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav19 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.sav.models import Equipement, Ticket

User = get_user_model()


def make_company(slug='sav-xsav19', nom='Sav Co XSAV19'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV19PublicSignalerTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xsav19_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav19-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV19', client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Pompe QR', sku='POMPE-QR-XSAV19',
            prix_achat=300, prix_vente=600)
        self.equip = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst,
            created_by=self.admin)
        self.public_client = APIClient()

    def test_scan_cree_ticket_lie_bon_equipement(self):
        token = self.equip.ensure_public_token()
        resp = self.public_client.post(
            f'/api/django/public/sav/equipement/{token}/signaler/',
            {'description': 'La pompe ne démarre plus.', 'telephone': '0600000000'})
        self.assertEqual(resp.status_code, 201, resp.content)
        ref = resp.data['reference']
        ticket = Ticket.objects.get(reference=ref)
        self.assertEqual(ticket.equipement_id, self.equip.id)
        self.assertEqual(ticket.company_id, self.company.id)
        self.assertEqual(ticket.client_id, self.client_obj.id)
        self.assertEqual(ticket.type, Ticket.Type.CORRECTIF)

    def test_token_invalide_404(self):
        resp = self.public_client.post(
            '/api/django/public/sav/equipement/token-inexistant/signaler/',
            {'description': 'Panne'})
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_token_absent_404(self):
        resp = self.public_client.post(
            '/api/django/public/sav/equipement//signaler/',
            {'description': 'Panne'})
        self.assertIn(resp.status_code, (404, 301))

    def test_honeypot_rempli_aucun_ticket_cree(self):
        token = self.equip.ensure_public_token()
        nb_avant = Ticket.objects.count()
        resp = self.public_client.post(
            f'/api/django/public/sav/equipement/{token}/signaler/',
            {'description': 'Panne', 'site_web': 'http://spam.example'})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(Ticket.objects.count(), nb_avant)

    def test_description_vide_400(self):
        token = self.equip.ensure_public_token()
        resp = self.public_client.post(
            f'/api/django/public/sav/equipement/{token}/signaler/', {})
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_aucune_donnee_interne_exposee(self):
        token = self.equip.ensure_public_token()
        resp = self.public_client.post(
            f'/api/django/public/sav/equipement/{token}/signaler/',
            {'description': 'Panne'})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(set(resp.data.keys()), {'reference'})

    def test_ensure_public_token_idempotent(self):
        t1 = self.equip.ensure_public_token()
        t2 = self.equip.ensure_public_token()
        self.assertEqual(t1, t2)

    def test_public_token_distinct_de_equipement_token(self):
        self.equip.set_token()
        public_token = self.equip.ensure_public_token()
        self.assertNotEqual(public_token, self.equip.equipement_token)
        # Le jeton interne (devinable EQUIP:<id>) ne doit jamais fonctionner
        # sur l'endpoint public.
        resp = self.public_client.post(
            f'/api/django/public/sav/equipement/{self.equip.equipement_token}/signaler/',
            {'description': 'Panne'})
        self.assertEqual(resp.status_code, 404, resp.content)

    # ── Étiquettes régénérées avec l'URL publique ───────────────────────────

    def test_etiquettes_public_encode_url(self):
        api = auth(self.admin)
        resp = api.get(
            '/api/django/sav/equipements/etiquettes/',
            {'ids': str(self.equip.id), 'public': '1'})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.equip.refresh_from_db()
        self.assertIsNotNone(self.equip.public_token)
        self.assertIn(f'/e/{self.equip.public_token}', resp.content.decode())

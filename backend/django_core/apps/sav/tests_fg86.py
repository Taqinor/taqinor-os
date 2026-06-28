"""Tests FG86 — Lien de suivi public tokenisé des tickets SAV.

Couvre :
  * ensure_share_token() : génère le jeton la première fois, idempotent ensuite.
  * endpoint public /api/django/public/sav/ticket/<token>/ :
      – retourne reference, statut, date_modification, statut_display ;
      – ne fuit JAMAIS cout, chatter (TicketActivity), ni aucun champ interne ;
      – token inconnu → 404 sans fuite ;
  * action /lien-client/ (requête authentifiée) :
      – retourne token + url absolue ;
      – idempotent (même token au second appel) ;
  * les endpoints normaux (/tickets/) restent company-scopés (isolation).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_fg86 -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.installations.models import Installation
from apps.sav.models import Ticket, TicketActivity

User = get_user_model()

# ── helpers ────────────────────────────────────────────────────────────────────


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(username, company, role='admin'):
    return User.objects.create_user(
        username=username, password='x', role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_installation(company, ref_suffix='1'):
    client = Client.objects.create(
        company=company, nom='Test', prenom='Client',
        email=f'tc-fg86-{company.id}-{ref_suffix}@example.invalid')
    inst = Installation.objects.create(
        company=company, reference=f'CHT-FG86-{company.id}-{ref_suffix}',
        client=client)
    return inst, client


def make_ticket(company, user, inst, client, ref_suffix='001'):
    return Ticket.objects.create(
        company=company,
        reference=f'SAV-FG86-{company.id}-{ref_suffix}',
        client=client,
        installation=inst,
        created_by=user,
        cout=Decimal('999.99'),
    )


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestEnsureShareToken(TestCase):
    """Teste la génération et l'idempotence du share_token."""

    def setUp(self):
        self.company = make_company('fg86-tok', 'FG86 Token Co')
        self.user = make_user('fg86_tok_admin', self.company)
        self.inst, self.client_obj = make_installation(self.company, 'tok')
        self.ticket = make_ticket(
            self.company, self.user, self.inst, self.client_obj, '001')

    def test_token_initially_null(self):
        """Le champ share_token est None avant toute génération."""
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.share_token)

    def test_ensure_share_token_generates_token(self):
        token = self.ticket.ensure_share_token()
        self.assertIsNotNone(token)
        self.assertTrue(len(token) >= 32)

    def test_ensure_share_token_persists(self):
        token = self.ticket.ensure_share_token()
        # Relire depuis la DB.
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.share_token, token)

    def test_ensure_share_token_idempotent(self):
        token_first = self.ticket.ensure_share_token()
        token_second = self.ticket.ensure_share_token()
        self.assertEqual(token_first, token_second)

    def test_tokens_unique_across_tickets(self):
        inst2, client2 = make_installation(self.company, 'tok2')
        ticket2 = make_ticket(self.company, self.user, inst2, client2, '002')
        t1 = self.ticket.ensure_share_token()
        t2 = ticket2.ensure_share_token()
        self.assertNotEqual(t1, t2)


class TestPublicEndpoint(TestCase):
    """Teste l'endpoint public /api/django/public/sav/ticket/<token>/."""

    PUBLIC_URL = '/api/django/public/sav/ticket/{}/'

    def setUp(self):
        self.company = make_company('fg86-pub', 'FG86 Pub Co')
        self.user = make_user('fg86_pub_admin', self.company)
        self.inst, self.client_obj = make_installation(self.company, 'pub')
        self.ticket = make_ticket(
            self.company, self.user, self.inst, self.client_obj, 'P001')
        self.token = self.ticket.ensure_share_token()
        self.anon = APIClient()

    def test_valid_token_returns_200(self):
        resp = self.anon.get(self.PUBLIC_URL.format(self.token))
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_response_contains_required_fields(self):
        resp = self.anon.get(self.PUBLIC_URL.format(self.token))
        data = resp.data
        self.assertIn('reference', data)
        self.assertIn('statut', data)
        self.assertIn('date_modification', data)
        self.assertIn('statut_display', data)
        self.assertEqual(data['reference'], self.ticket.reference)

    def test_cout_never_exposed(self):
        """Le cout interne ne doit JAMAIS apparaître dans la réponse publique."""
        resp = self.anon.get(self.PUBLIC_URL.format(self.token))
        self.assertNotIn('cout', resp.data)
        # Vérification supplémentaire : la valeur brute non plus.
        response_str = str(resp.data)
        self.assertNotIn('999.99', response_str)

    def test_chatter_never_exposed(self):
        """Les activités chatter (TicketActivity) ne doivent pas fuiter."""
        TicketActivity.objects.create(
            company=self.company, ticket=self.ticket,
            kind=TicketActivity.Kind.NOTE, body='Note confidentielle interne',
            user=self.user)
        resp = self.anon.get(self.PUBLIC_URL.format(self.token))
        response_str = str(resp.data)
        self.assertNotIn('confidentielle', response_str)
        self.assertNotIn('activites', resp.data)
        self.assertNotIn('chatter', resp.data)

    def test_no_internal_fields_exposed(self):
        """Aucun champ interne sensible ne doit apparaître."""
        resp = self.anon.get(self.PUBLIC_URL.format(self.token))
        forbidden = [
            'cout', 'company', 'client', 'installation', 'equipement',
            'technicien_responsable', 'created_by', 'sla_due_at',
            'sla_breach', 'sous_garantie', 'activites', 'annule',
            'custom_data', 'share_token',
        ]
        for field in forbidden:
            self.assertNotIn(field, resp.data,
                             msg=f"Champ interdit exposé : {field!r}")

    def test_invalid_token_returns_404(self):
        resp = self.anon.get(self.PUBLIC_URL.format('jeton-inexistant-fg86'))
        self.assertEqual(resp.status_code, 404)

    def test_unknown_token_no_data_leak(self):
        resp = self.anon.get(self.PUBLIC_URL.format('jeton-inexistant-fg86'))
        self.assertNotIn('reference', resp.data)
        self.assertNotIn('cout', resp.data)

    def test_no_auth_required(self):
        """L'endpoint public est accessible sans aucune authentification."""
        anon = APIClient()  # aucun header
        resp = anon.get(self.PUBLIC_URL.format(self.token))
        self.assertEqual(resp.status_code, 200)

    def test_noindex_header(self):
        resp = self.anon.get(self.PUBLIC_URL.format(self.token))
        self.assertIn('noindex', resp.get('X-Robots-Tag', ''))


class TestLienClientAction(TestCase):
    """Teste l'action /lien-client/ (authentifiée) sur TicketViewSet."""

    def setUp(self):
        self.company = make_company('fg86-act', 'FG86 Action Co')
        self.user = make_user('fg86_act_admin', self.company)
        self.inst, self.client_obj = make_installation(self.company, 'act')
        self.ticket = make_ticket(
            self.company, self.user, self.inst, self.client_obj, 'A001')
        self.api = auth(self.user)
        self.url = f'/api/django/sav/tickets/{self.ticket.pk}/lien-client/'

    def test_returns_200_with_token_and_url(self):
        resp = self.api.get(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('token', resp.data)
        self.assertIn('url', resp.data)

    def test_url_contains_token(self):
        resp = self.api.get(self.url)
        self.assertIn(resp.data['token'], resp.data['url'])

    def test_url_points_to_public_endpoint(self):
        resp = self.api.get(self.url)
        self.assertIn('/api/django/public/sav/ticket/', resp.data['url'])

    def test_idempotent_token(self):
        """Deux appels successifs renvoient le même token."""
        r1 = self.api.get(self.url)
        r2 = self.api.get(self.url)
        self.assertEqual(r1.data['token'], r2.data['token'])

    def test_requires_auth(self):
        anon = APIClient()
        resp = anon.get(self.url)
        self.assertIn(resp.status_code, [401, 403])


class TestCompanyScopePreserved(TestCase):
    """Vérifie que l'isolation par société reste intacte sur les endpoints normaux."""

    def setUp(self):
        self.co1 = make_company('fg86-scope1', 'FG86 Scope1')
        self.co2 = make_company('fg86-scope2', 'FG86 Scope2')
        self.u1 = make_user('fg86_u1', self.co1)
        self.u2 = make_user('fg86_u2', self.co2)
        inst1, cl1 = make_installation(self.co1, 's1')
        inst2, cl2 = make_installation(self.co2, 's2')
        self.t1 = make_ticket(self.co1, self.u1, inst1, cl1, 'S001')
        self.t2 = make_ticket(self.co2, self.u2, inst2, cl2, 'S002')

    def test_user_of_co1_cannot_see_co2_ticket(self):
        api = auth(self.u1)
        resp = api.get(f'/api/django/sav/tickets/{self.t2.pk}/')
        self.assertIn(resp.status_code, [403, 404])

    def test_user_of_co1_cannot_get_lien_client_of_co2_ticket(self):
        api = auth(self.u1)
        resp = api.get(
            f'/api/django/sav/tickets/{self.t2.pk}/lien-client/')
        self.assertIn(resp.status_code, [403, 404])

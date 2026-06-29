"""Tests FG280 — Alarmes / défauts onduleur (acquittement / escalade).

Couvre :
  * création d'alarme (company posée côté serveur, date_detection auto) ;
  * acquitter : pose acquittee_par (acteur serveur) + date_acquittement +
    statut=acquittee, idempotent, NE touche PAS au ticket ;
  * escalader : ouvre un ticket SAV depuis l'équipement (statut=escaladee +
    lien ticket), relie un ticket existant fourni en body, idempotent ;
  * filtres gravite / statut / equipement ;
  * isolation multi-société (une société ne voit pas les alarmes d'une autre) ;
  * garde de rôle : lecture tout rôle, écriture + actions responsable/admin.

L'alarme est DISTINCTE du ticket : son cycle de vie (active → acquittée →
escaladée) est séparé du cycle de vie du Ticket SAV.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_fg280 -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.sav.models import AlarmeOnduleur, Equipement, Ticket

User = get_user_model()

BASE = '/api/django/sav/alarmes-onduleur/'

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


def make_equipement(company, suffix='1'):
    client = Client.objects.create(
        company=company, nom='Cli', prenom='Ent',
        email=f'eq-fg280-{company.id}-{suffix}@example.invalid')
    inst = Installation.objects.create(
        company=company, reference=f'CHT-FG280-{company.id}-{suffix}',
        client=client)
    produit = Produit.objects.create(
        company=company, nom=f'Onduleur {suffix}',
        sku=f'OND-{company.id}-{suffix}',
        prix_achat=Decimal('100'), prix_vente=Decimal('200'))
    eq = Equipement.objects.create(
        company=company, produit=produit, installation=inst,
        numero_serie=f'SN-{company.id}-{suffix}')
    return eq, inst, client


def make_alarme(company, equipement=None, **kw):
    defaults = dict(
        company=company, code='E07',
        gravite=AlarmeOnduleur.Gravite.WARNING,
        date_detection=timezone.now())
    defaults.update(kw)
    return AlarmeOnduleur.objects.create(equipement=equipement, **defaults)


# ── création ───────────────────────────────────────────────────────────────────


class TestCreateAlarme(TestCase):
    def setUp(self):
        self.company = make_company('fg280-create', 'FG280 Create')
        self.user = make_user('fg280_create_admin', self.company)
        self.eq, self.inst, self.client_obj = make_equipement(self.company, 'c')
        self.api = auth(self.user)

    def test_create_sets_company_server_side(self):
        # company envoyé dans le corps doit être IGNORÉ (read-only).
        other = make_company('fg280-other-co', 'Other Co')
        resp = self.api.post(BASE, {
            'code': 'F12', 'gravite': 'critique',
            'equipement': self.eq.id, 'company': other.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        alarme = AlarmeOnduleur.objects.get(id=resp.data['id'])
        self.assertEqual(alarme.company_id, self.company.id)

    def test_create_defaults_statut_active_and_detection(self):
        resp = self.api.post(BASE, {'code': 'E10'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        alarme = AlarmeOnduleur.objects.get(id=resp.data['id'])
        self.assertEqual(alarme.statut, AlarmeOnduleur.Statut.ACTIVE)
        self.assertIsNotNone(alarme.date_detection)
        self.assertEqual(alarme.created_by_id, self.user.id)

    def test_create_rejects_foreign_equipement(self):
        other = make_company('fg280-foreign-eq', 'Foreign Eq')
        oeq, _, _ = make_equipement(other, 'f')
        resp = self.api.post(BASE, {
            'code': 'E01', 'equipement': oeq.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


# ── acquitter ──────────────────────────────────────────────────────────────────


class TestAcquitter(TestCase):
    def setUp(self):
        self.company = make_company('fg280-ack', 'FG280 Ack')
        self.user = make_user('fg280_ack_admin', self.company)
        self.eq, self.inst, self.client_obj = make_equipement(self.company, 'a')
        self.alarme = make_alarme(self.company, self.eq)
        self.api = auth(self.user)

    def test_acquitter_sets_user_date_and_statut(self):
        resp = self.api.post(f'{BASE}{self.alarme.id}/acquitter/', {},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.alarme.refresh_from_db()
        self.assertEqual(self.alarme.statut, AlarmeOnduleur.Statut.ACQUITTEE)
        self.assertEqual(self.alarme.acquittee_par_id, self.user.id)
        self.assertIsNotNone(self.alarme.date_acquittement)
        # N'ouvre PAS de ticket.
        self.assertIsNone(self.alarme.ticket_id)

    def test_acquitter_idempotent_keeps_first_actor(self):
        self.api.post(f'{BASE}{self.alarme.id}/acquitter/', {}, format='json')
        self.alarme.refresh_from_db()
        first_date = self.alarme.date_acquittement
        # Un second utilisateur tente d'acquitter — l'acteur ne change pas.
        user2 = make_user('fg280_ack_admin2', self.company)
        auth(user2).post(f'{BASE}{self.alarme.id}/acquitter/', {},
                         format='json')
        self.alarme.refresh_from_db()
        self.assertEqual(self.alarme.acquittee_par_id, self.user.id)
        self.assertEqual(self.alarme.date_acquittement, first_date)


# ── escalader ──────────────────────────────────────────────────────────────────


class TestEscalader(TestCase):
    def setUp(self):
        self.company = make_company('fg280-esc', 'FG280 Esc')
        self.user = make_user('fg280_esc_admin', self.company)
        self.eq, self.inst, self.client_obj = make_equipement(self.company, 'e')
        self.api = auth(self.user)

    def test_escalader_opens_ticket_from_equipement(self):
        alarme = make_alarme(
            self.company, self.eq, gravite=AlarmeOnduleur.Gravite.CRITIQUE)
        resp = self.api.post(f'{BASE}{alarme.id}/escalader/', {},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        alarme.refresh_from_db()
        self.assertEqual(alarme.statut, AlarmeOnduleur.Statut.ESCALADEE)
        self.assertIsNotNone(alarme.ticket_id)
        ticket = Ticket.objects.get(id=alarme.ticket_id)
        self.assertEqual(ticket.company_id, self.company.id)
        self.assertEqual(ticket.client_id, self.client_obj.id)
        self.assertEqual(ticket.equipement_id, self.eq.id)
        # Gravité critique → priorité urgente.
        self.assertEqual(ticket.priorite, Ticket.Priorite.URGENTE)

    def test_escalader_links_existing_ticket(self):
        alarme = make_alarme(self.company, self.eq)
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-FG280-X1',
            client=self.client_obj, installation=self.inst,
            created_by=self.user)
        resp = self.api.post(f'{BASE}{alarme.id}/escalader/',
                             {'ticket': ticket.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        alarme.refresh_from_db()
        self.assertEqual(alarme.ticket_id, ticket.id)
        self.assertEqual(alarme.statut, AlarmeOnduleur.Statut.ESCALADEE)
        # Aucun ticket supplémentaire créé.
        self.assertEqual(Ticket.objects.filter(company=self.company).count(), 1)

    def test_escalader_idempotent_no_second_ticket(self):
        alarme = make_alarme(self.company, self.eq)
        self.api.post(f'{BASE}{alarme.id}/escalader/', {}, format='json')
        alarme.refresh_from_db()
        first_ticket = alarme.ticket_id
        self.api.post(f'{BASE}{alarme.id}/escalader/', {}, format='json')
        alarme.refresh_from_db()
        self.assertEqual(alarme.ticket_id, first_ticket)
        self.assertEqual(Ticket.objects.filter(company=self.company).count(), 1)

    def test_escalader_rejects_foreign_ticket(self):
        alarme = make_alarme(self.company, self.eq)
        other = make_company('fg280-esc-foreign', 'Esc Foreign')
        ouser = make_user('fg280_esc_foreign_u', other)
        oeq, oinst, ocli = make_equipement(other, 'ef')
        oticket = Ticket.objects.create(
            company=other, reference='SAV-FG280-OT1',
            client=ocli, installation=oinst, created_by=ouser)
        resp = self.api.post(f'{BASE}{alarme.id}/escalader/',
                             {'ticket': oticket.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


# ── filtres + scoping ───────────────────────────────────────────────────────────


class TestFiltersAndScoping(TestCase):
    def setUp(self):
        self.company = make_company('fg280-flt', 'FG280 Filters')
        self.user = make_user('fg280_flt_admin', self.company)
        self.eq, _, _ = make_equipement(self.company, 'f1')
        self.eq2, _, _ = make_equipement(self.company, 'f2')
        self.crit = make_alarme(
            self.company, self.eq, code='C1',
            gravite=AlarmeOnduleur.Gravite.CRITIQUE)
        self.info = make_alarme(
            self.company, self.eq2, code='I1',
            gravite=AlarmeOnduleur.Gravite.INFO,
            statut=AlarmeOnduleur.Statut.RESOLUE)
        self.api = auth(self.user)

    def test_filter_gravite(self):
        resp = self.api.get(f'{BASE}?gravite=critique')
        self.assertEqual(resp.status_code, 200)
        # gère paginé ou non.
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        codes = [a['code'] for a in rows]
        self.assertIn('C1', codes)
        self.assertNotIn('I1', codes)

    def test_filter_statut(self):
        resp = self.api.get(f'{BASE}?statut=resolue')
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        codes = [a['code'] for a in rows]
        self.assertIn('I1', codes)
        self.assertNotIn('C1', codes)

    def test_filter_equipement(self):
        resp = self.api.get(f'{BASE}?equipement={self.eq.id}')
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        codes = [a['code'] for a in rows]
        self.assertEqual(codes, ['C1'])

    def test_scoping_isolates_companies(self):
        other = make_company('fg280-flt-other', 'Filters Other')
        oeq, _, _ = make_equipement(other, 'fo')
        make_alarme(other, oeq, code='OTHER')
        resp = self.api.get(BASE)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        codes = [a['code'] for a in rows]
        self.assertNotIn('OTHER', codes)


# ── garde de rôle ───────────────────────────────────────────────────────────────


class TestRoleGate(TestCase):
    def setUp(self):
        self.company = make_company('fg280-role', 'FG280 Role')
        self.admin = make_user('fg280_role_admin', self.company)
        # role_legacy='normal' → is_responsable False → bloqué en écriture.
        self.viewer = make_user('fg280_role_viewer', self.company, role='normal')
        self.eq, _, _ = make_equipement(self.company, 'r')
        self.alarme = make_alarme(self.company, self.eq)

    def test_viewer_can_read(self):
        resp = auth(self.viewer).get(BASE)
        self.assertEqual(resp.status_code, 200)

    def test_viewer_cannot_create(self):
        resp = auth(self.viewer).post(BASE, {'code': 'X'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_viewer_cannot_acquitter(self):
        resp = auth(self.viewer).post(
            f'{BASE}{self.alarme.id}/acquitter/', {}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_viewer_cannot_escalader(self):
        resp = auth(self.viewer).post(
            f'{BASE}{self.alarme.id}/escalader/', {}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_admin_can_acquitter(self):
        resp = auth(self.admin).post(
            f'{BASE}{self.alarme.id}/acquitter/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

"""FG242 — ConcurrentPerte (suivi des concurrents sur deals perdus) tests.

Couvre :
  - Modèle : création (société forcée), prix/devise optionnels, motif réutilisé
  - API : saisie du concurrent gagnant sur un lead perdu (POST 201)
  - Multi-tenant : société + saisi_par forcés côté serveur (jamais du body)
  - Isolation société : co1 ne voit/édite pas les enregistrements de co2
  - Filtre ?lead=<id>
  - Prix négatif rejeté (garde Decimal)
  - Garde de rôle : un utilisateur sans droit d'écriture est refusé en POST
  - Chatter : une note est écrite sur le lead à la création
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model

from authentication.models import Company
from apps.crm.models import ConcurrentPerte, Lead, LeadActivity

User = get_user_model()


# ── helpers ──────────────────────────────────────────────────────────────────

def make_company(slug, nom=None):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom or slug})
    return c


def make_user(company, username, role='responsable'):
    """Crée un utilisateur portant un vrai rôle système (admin/responsable) ou
    un rôle limité (utilisateur) pour tester la garde d'écriture."""
    from apps.roles.models import (
        Role, ADMIN_PERMISSIONS, RESPONSABLE_PERMISSIONS,
    )
    _defs = {
        'admin': ('Administrateur', ADMIN_PERMISSIONS),
        'responsable': ('Responsable', RESPONSABLE_PERMISSIONS),
    }
    if role in _defs:
        nom, perms = _defs[role]
        role_obj, _ = Role.objects.get_or_create(
            company=company, nom=nom,
            defaults={'permissions': perms, 'est_systeme': True},
        )
        return User.objects.create_user(
            username=username, password='x',
            role=role_obj, role_legacy=role, company=company,
        )
    # Rôle limité : aucun rôle système ni legacy responsable → pas de droit
    # d'écriture CRM (is_responsable False).
    return User.objects.create_user(
        username=username, password='x', company=company,
    )


def make_api(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


def make_lost_lead(company, **kw):
    """Lead marqué PERDU (lost-flag — voir STAGES.py, pas une étape)."""
    defaults = dict(nom='Lead perdu', perdu=True, motif_perte='Prix trop élevé')
    defaults.update(kw)
    return Lead.objects.create(company=company, **defaults)


BASE = '/api/django/crm/concurrents-perte/'


# ── Modèle ───────────────────────────────────────────────────────────────────

class TestConcurrentPerteModel(TestCase):
    def setUp(self):
        self.co = make_company('fg242-model')
        self.lead = make_lost_lead(self.co)

    def test_create_minimal(self):
        cp = ConcurrentPerte.objects.create(
            company=self.co, lead=self.lead, concurrent_nom='SolarCorp')
        self.assertIsNotNone(cp.pk)
        self.assertEqual(cp.company, self.co)
        self.assertEqual(cp.lead, self.lead)
        self.assertEqual(cp.concurrent_nom, 'SolarCorp')
        # Prix optionnel, devise par défaut MAD.
        self.assertIsNone(cp.concurrent_prix)
        self.assertEqual(cp.devise, 'MAD')

    def test_create_with_price_and_devise(self):
        cp = ConcurrentPerte.objects.create(
            company=self.co, lead=self.lead, concurrent_nom='SolarCorp',
            concurrent_prix=Decimal('85000.00'), devise='EUR',
            motif='Prix trop élevé')
        self.assertEqual(cp.concurrent_prix, Decimal('85000.00'))
        self.assertEqual(cp.devise, 'EUR')
        # Motif réutilise le vocabulaire Lead.motif_perte (texte libre).
        self.assertEqual(cp.motif, 'Prix trop élevé')

    def test_str(self):
        cp = ConcurrentPerte.objects.create(
            company=self.co, lead=self.lead, concurrent_nom='ACME Solar')
        self.assertIn('ACME Solar', str(cp))


# ── API : saisie + multi-tenant ──────────────────────────────────────────────

class TestConcurrentPerteAPI(TestCase):
    def setUp(self):
        self.co = make_company('fg242-api')
        self.user = make_user(self.co, 'fg242-resp', role='responsable')
        self.api = make_api(self.user)
        self.lead = make_lost_lead(self.co)

    def test_capture_competitor_on_lost_lead(self):
        resp = self.api.post(BASE, {
            'lead': self.lead.pk,
            'concurrent_nom': 'SolarCorp',
            'concurrent_prix': '85000.00',
            'devise': 'MAD',
            'motif': 'Prix trop élevé',
            'notes': 'Devis 12% moins cher.',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['concurrent_nom'], 'SolarCorp')
        self.assertEqual(resp.data['lead'], self.lead.pk)
        cp = ConcurrentPerte.objects.get(pk=resp.data['id'])
        self.assertEqual(cp.concurrent_prix, Decimal('85000.00'))

    def test_company_and_user_forced_server_side(self):
        """Société + saisi_par jamais lus du corps : on tente de les usurper."""
        other_co = make_company('fg242-other-co')
        resp = self.api.post(BASE, {
            'lead': self.lead.pk,
            'concurrent_nom': 'SolarCorp',
            # Tentative d'injection — doivent être ignorés.
            'company': other_co.pk,
            'saisi_par': 99999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cp = ConcurrentPerte.objects.get(pk=resp.data['id'])
        self.assertEqual(cp.company, self.co)          # pas other_co
        self.assertEqual(cp.saisi_par, self.user)      # acteur, pas 99999

    def test_chatter_note_written_on_create(self):
        before = LeadActivity.objects.filter(lead=self.lead).count()
        resp = self.api.post(BASE, {
            'lead': self.lead.pk,
            'concurrent_nom': 'SolarCorp',
            'concurrent_prix': '85000.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        after = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE).count()
        self.assertGreater(after, before)
        note = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE).latest('created_at')
        self.assertIn('SolarCorp', note.body)

    def test_negative_price_rejected(self):
        resp = self.api.post(BASE, {
            'lead': self.lead.pk,
            'concurrent_nom': 'SolarCorp',
            'concurrent_prix': '-1.00',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('concurrent_prix', resp.data)

    def test_nom_required(self):
        resp = self.api.post(BASE, {
            'lead': self.lead.pk,
            'concurrent_nom': '',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('concurrent_nom', resp.data)


# ── Filtre ?lead= ────────────────────────────────────────────────────────────

class TestConcurrentPerteFilter(TestCase):
    def setUp(self):
        self.co = make_company('fg242-filter')
        self.user = make_user(self.co, 'fg242-filter-u', role='responsable')
        self.api = make_api(self.user)
        self.lead_a = make_lost_lead(self.co, nom='Lead A')
        self.lead_b = make_lost_lead(self.co, nom='Lead B')
        ConcurrentPerte.objects.create(
            company=self.co, lead=self.lead_a, concurrent_nom='A1')
        ConcurrentPerte.objects.create(
            company=self.co, lead=self.lead_a, concurrent_nom='A2')
        ConcurrentPerte.objects.create(
            company=self.co, lead=self.lead_b, concurrent_nom='B1')

    def _ids(self, data):
        results = data['results'] if isinstance(data, dict) else data
        return {r['id'] for r in results}

    def test_filter_by_lead(self):
        resp = self.api.get(BASE, {'lead': self.lead_a.pk})
        self.assertEqual(resp.status_code, 200)
        results = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r['lead'], self.lead_a.pk)

    def test_filter_other_lead(self):
        resp = self.api.get(BASE, {'lead': self.lead_b.pk})
        self.assertEqual(resp.status_code, 200)
        results = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['concurrent_nom'], 'B1')


# ── Isolation multi-tenant ───────────────────────────────────────────────────

class TestConcurrentPerteScoping(TestCase):
    def setUp(self):
        self.co1 = make_company('fg242-co1')
        self.co2 = make_company('fg242-co2')
        self.u1 = make_user(self.co1, 'fg242-u1', role='responsable')
        self.u2 = make_user(self.co2, 'fg242-u2', role='responsable')
        self.lead1 = make_lost_lead(self.co1)
        self.lead2 = make_lost_lead(self.co2)
        self.cp2 = ConcurrentPerte.objects.create(
            company=self.co2, lead=self.lead2, concurrent_nom='Co2 Competitor')

    def test_company_isolation_list(self):
        api1 = make_api(self.u1)
        resp = api1.get(BASE)
        self.assertEqual(resp.status_code, 200)
        ids = {
            r['id'] for r in (
                resp.data['results'] if isinstance(resp.data, dict) else resp.data
            )
        }
        self.assertNotIn(self.cp2.pk, ids)

    def test_company_isolation_detail(self):
        api1 = make_api(self.u1)
        resp = api1.get(f'{BASE}{self.cp2.pk}/')
        self.assertEqual(resp.status_code, 404)

    def test_cannot_attach_to_other_company_lead(self):
        """co1 ne peut pas saisir un concurrent sur un lead de co2."""
        api1 = make_api(self.u1)
        resp = api1.post(BASE, {
            'lead': self.lead2.pk,
            'concurrent_nom': 'Sneaky',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('lead', resp.data)


# ── Garde de rôle (écriture) ─────────────────────────────────────────────────

class TestConcurrentPerteRoleGate(TestCase):
    def setUp(self):
        self.co = make_company('fg242-role')
        self.lead = make_lost_lead(self.co)
        self.reader = make_user(self.co, 'fg242-reader', role='utilisateur')
        self.writer = make_user(self.co, 'fg242-writer', role='responsable')

    def test_reader_cannot_create(self):
        api = make_api(self.reader)
        resp = api.post(BASE, {
            'lead': self.lead.pk,
            'concurrent_nom': 'SolarCorp',
        }, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_reader_can_list(self):
        ConcurrentPerte.objects.create(
            company=self.co, lead=self.lead, concurrent_nom='SolarCorp')
        api = make_api(self.reader)
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 200)

    def test_writer_can_create(self):
        api = make_api(self.writer)
        resp = api.post(BASE, {
            'lead': self.lead.pk,
            'concurrent_nom': 'SolarCorp',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

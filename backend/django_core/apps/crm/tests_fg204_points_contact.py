"""FG204 — PointContact (tableau d'attribution multi-touch) tests.

Couvre :
  - Modèle : création (société forcée), canal réutilise Lead.Canal, cout optionnel
  - API : ajout d'un point de contact (POST 201), date_contact défaut now, ordre auto
  - Multi-tenant : société + saisi_par forcés côté serveur (jamais du body)
  - Isolation société : co1 ne voit/édite pas les enregistrements de co2
  - Filtre ?lead=<id>
  - Timeline ORDONNÉE (ordre puis date_contact) par lead
  - Résumé d'attribution first-touch vs last-touch (endpoint + action lead)
  - cout négatif rejeté (garde Decimal) + coût total des canaux payants
  - Garde de rôle : un utilisateur sans droit d'écriture est refusé en POST
  - Chatter : une note est écrite sur le lead à la création
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity, PointContact

User = get_user_model()


# ── helpers ──────────────────────────────────────────────────────────────────

def make_company(slug, nom=None):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom or slug})
    return c


def make_user(company, username, role='responsable'):
    """Vrai rôle système (admin/responsable) ou rôle limité (utilisateur) pour
    tester la garde d'écriture."""
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
    return User.objects.create_user(
        username=username, password='x', company=company,
    )


def make_api(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


def make_lead(company, **kw):
    defaults = dict(nom='Lead Multi-touch')
    defaults.update(kw)
    return Lead.objects.create(company=company, **defaults)


def _now():
    return timezone.now()


BASE = '/api/django/crm/points-contact/'
ATTR = '/api/django/crm/points-contact/attribution/'


# ── Modèle ───────────────────────────────────────────────────────────────────

class TestPointContactModel(TestCase):
    def setUp(self):
        self.co = make_company('fg204-model')
        self.lead = make_lead(self.co)

    def test_create_minimal(self):
        pc = PointContact.objects.create(
            company=self.co, lead=self.lead,
            canal=Lead.Canal.META_ADS, date_contact=_now())
        self.assertIsNotNone(pc.pk)
        self.assertEqual(pc.company, self.co)
        self.assertEqual(pc.lead, self.lead)
        self.assertEqual(pc.canal, 'meta_ads')
        # cout optionnel.
        self.assertIsNone(pc.cout)

    def test_canal_reuses_lead_vocabulary(self):
        # Toutes les clés Lead.Canal sont acceptées (max_length=20 couvre la
        # plus longue, 'whatsapp_ctwa').
        for choice in Lead.Canal.values:
            pc = PointContact.objects.create(
                company=self.co, lead=self.lead,
                canal=choice, date_contact=_now())
            self.assertEqual(pc.canal, choice)

    def test_str(self):
        pc = PointContact.objects.create(
            company=self.co, lead=self.lead,
            canal=Lead.Canal.WHATSAPP_CTWA, date_contact=_now())
        self.assertIn('lead', str(pc))


# ── API : saisie + multi-tenant ──────────────────────────────────────────────

class TestPointContactAPI(TestCase):
    def setUp(self):
        self.co = make_company('fg204-api')
        self.user = make_user(self.co, 'fg204-resp', role='responsable')
        self.api = make_api(self.user)
        self.lead = make_lead(self.co)

    def test_add_touchpoint(self):
        resp = self.api.post(BASE, {
            'lead': self.lead.pk,
            'canal': 'meta_ads',
            'source': 'Campagne Été 2026',
            'cout': '12.50',
            'detail': 'Clic sur publicité.',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['canal'], 'meta_ads')
        self.assertEqual(resp.data['lead'], self.lead.pk)
        self.assertEqual(resp.data['canal_libelle'], 'Publicité Meta')
        pc = PointContact.objects.get(pk=resp.data['id'])
        self.assertEqual(pc.cout, Decimal('12.50'))
        # date_contact par défaut posée côté serveur.
        self.assertIsNotNone(pc.date_contact)
        # ordre auto = 1 (premier point du lead).
        self.assertEqual(pc.ordre, 1)

    def test_ordre_auto_increments(self):
        for _ in range(3):
            resp = self.api.post(BASE, {
                'lead': self.lead.pk, 'canal': 'site_web',
            }, format='json')
            self.assertEqual(resp.status_code, 201, resp.data)
        ordres = list(
            PointContact.objects.filter(lead=self.lead)
            .order_by('ordre').values_list('ordre', flat=True))
        self.assertEqual(ordres, [1, 2, 3])

    def test_company_and_user_forced_server_side(self):
        """Société + saisi_par jamais lus du corps : on tente de les usurper."""
        other_co = make_company('fg204-other-co')
        resp = self.api.post(BASE, {
            'lead': self.lead.pk,
            'canal': 'whatsapp_ctwa',
            'company': other_co.pk,
            'saisi_par': 99999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        pc = PointContact.objects.get(pk=resp.data['id'])
        self.assertEqual(pc.company, self.co)        # pas other_co
        self.assertEqual(pc.saisi_par, self.user)    # acteur, pas 99999

    def test_chatter_note_written_on_create(self):
        before = LeadActivity.objects.filter(lead=self.lead).count()
        resp = self.api.post(BASE, {
            'lead': self.lead.pk, 'canal': 'meta_ads', 'source': 'Été',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        after = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE).count()
        self.assertGreater(after, before)
        note = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE).latest('created_at')
        self.assertIn('Publicité Meta', note.body)

    def test_negative_cout_rejected(self):
        resp = self.api.post(BASE, {
            'lead': self.lead.pk, 'canal': 'meta_ads', 'cout': '-1.00',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('cout', resp.data)


# ── Filtre ?lead= + timeline ordonnée ────────────────────────────────────────

class TestPointContactTimeline(TestCase):
    def setUp(self):
        self.co = make_company('fg204-timeline')
        self.user = make_user(self.co, 'fg204-tl', role='responsable')
        self.api = make_api(self.user)
        self.lead_a = make_lead(self.co, nom='Lead A')
        self.lead_b = make_lead(self.co, nom='Lead B')
        base = _now() - timedelta(days=10)
        # Insérés DANS LE DÉSORDRE (ordre 3 puis 1 puis 2) pour vérifier le tri.
        PointContact.objects.create(
            company=self.co, lead=self.lead_a, canal='whatsapp_ctwa',
            ordre=3, date_contact=base + timedelta(days=2))
        PointContact.objects.create(
            company=self.co, lead=self.lead_a, canal='meta_ads',
            ordre=1, date_contact=base)
        PointContact.objects.create(
            company=self.co, lead=self.lead_a, canal='site_web',
            ordre=2, date_contact=base + timedelta(days=1))
        PointContact.objects.create(
            company=self.co, lead=self.lead_b, canal='telephone',
            ordre=1, date_contact=base)

    def _results(self, data):
        return data['results'] if isinstance(data, dict) else data

    def test_filter_by_lead(self):
        resp = self.api.get(BASE, {'lead': self.lead_a.pk})
        self.assertEqual(resp.status_code, 200)
        results = self._results(resp.data)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertEqual(r['lead'], self.lead_a.pk)

    def test_timeline_is_ordered(self):
        resp = self.api.get(BASE, {'lead': self.lead_a.pk})
        results = self._results(resp.data)
        canaux = [r['canal'] for r in results]
        # ordre 1 (meta) → 2 (site) → 3 (whatsapp).
        self.assertEqual(canaux, ['meta_ads', 'site_web', 'whatsapp_ctwa'])

    def test_other_lead_isolated(self):
        resp = self.api.get(BASE, {'lead': self.lead_b.pk})
        results = self._results(resp.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['canal'], 'telephone')


# ── Résumé d'attribution first-touch vs last-touch ───────────────────────────

class TestPointContactAttribution(TestCase):
    def setUp(self):
        self.co = make_company('fg204-attr')
        self.user = make_user(self.co, 'fg204-attr-u', role='responsable')
        self.api = make_api(self.user)
        self.lead = make_lead(self.co)
        base = _now() - timedelta(days=5)
        # Parcours : Meta (payant) → site → WhatsApp → signature (autre).
        PointContact.objects.create(
            company=self.co, lead=self.lead, canal='meta_ads', ordre=1,
            date_contact=base, cout=Decimal('20.00'))
        PointContact.objects.create(
            company=self.co, lead=self.lead, canal='site_web', ordre=2,
            date_contact=base + timedelta(days=1))
        PointContact.objects.create(
            company=self.co, lead=self.lead, canal='whatsapp_ctwa', ordre=3,
            date_contact=base + timedelta(days=2), cout=Decimal('5.00'))
        PointContact.objects.create(
            company=self.co, lead=self.lead, canal='autre', ordre=4,
            date_contact=base + timedelta(days=3))

    def test_attribution_endpoint(self):
        resp = self.api.get(ATTR, {'lead': self.lead.pk})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['count'], 4)
        self.assertEqual(resp.data['first_touch']['canal'], 'meta_ads')
        self.assertEqual(resp.data['last_touch']['canal'], 'autre')
        self.assertEqual(
            resp.data['first_touch']['canal_libelle'], 'Publicité Meta')
        # Coût total des canaux payants = 20 + 5.
        self.assertEqual(Decimal(str(resp.data['cout_total'])),
                         Decimal('25.00'))
        # Timeline ordonnée renvoyée.
        canaux = [p['canal'] for p in resp.data['timeline']]
        self.assertEqual(
            canaux, ['meta_ads', 'site_web', 'whatsapp_ctwa', 'autre'])

    def test_attribution_requires_lead_param(self):
        resp = self.api.get(ATTR)
        self.assertEqual(resp.status_code, 400)

    def test_attribution_unknown_lead_404(self):
        resp = self.api.get(ATTR, {'lead': 999999})
        self.assertEqual(resp.status_code, 404)

    def test_lead_action_points_contact(self):
        url = f'/api/django/crm/leads/{self.lead.pk}/points-contact/'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['count'], 4)
        self.assertEqual(resp.data['first_touch']['canal'], 'meta_ads')
        self.assertEqual(resp.data['last_touch']['canal'], 'autre')

    def test_empty_journal_has_no_touches(self):
        empty_lead = make_lead(self.co, nom='Sans contact')
        resp = self.api.get(ATTR, {'lead': empty_lead.pk})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['count'], 0)
        self.assertIsNone(resp.data['first_touch'])
        self.assertIsNone(resp.data['last_touch'])


# ── Isolation multi-tenant ───────────────────────────────────────────────────

class TestPointContactScoping(TestCase):
    def setUp(self):
        self.co1 = make_company('fg204-co1')
        self.co2 = make_company('fg204-co2')
        self.u1 = make_user(self.co1, 'fg204-u1', role='responsable')
        self.u2 = make_user(self.co2, 'fg204-u2', role='responsable')
        self.lead1 = make_lead(self.co1)
        self.lead2 = make_lead(self.co2)
        self.pc2 = PointContact.objects.create(
            company=self.co2, lead=self.lead2,
            canal='meta_ads', date_contact=_now())

    def _ids(self, data):
        results = data['results'] if isinstance(data, dict) else data
        return {r['id'] for r in results}

    def test_company_isolation_list(self):
        api1 = make_api(self.u1)
        resp = api1.get(BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(self.pc2.pk, self._ids(resp.data))

    def test_company_isolation_detail(self):
        api1 = make_api(self.u1)
        resp = api1.get(f'{BASE}{self.pc2.pk}/')
        self.assertEqual(resp.status_code, 404)

    def test_cannot_attach_to_other_company_lead(self):
        """co1 ne peut pas ajouter un point de contact sur un lead de co2."""
        api1 = make_api(self.u1)
        resp = api1.post(BASE, {
            'lead': self.lead2.pk, 'canal': 'meta_ads',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('lead', resp.data)

    def test_attribution_other_company_lead_404(self):
        api1 = make_api(self.u1)
        resp = api1.get(ATTR, {'lead': self.lead2.pk})
        self.assertEqual(resp.status_code, 404)


# ── Garde de rôle (écriture) ─────────────────────────────────────────────────

class TestPointContactRoleGate(TestCase):
    def setUp(self):
        self.co = make_company('fg204-role')
        self.lead = make_lead(self.co)
        self.reader = make_user(self.co, 'fg204-reader', role='utilisateur')
        self.writer = make_user(self.co, 'fg204-writer', role='responsable')

    def test_reader_cannot_create(self):
        api = make_api(self.reader)
        resp = api.post(BASE, {
            'lead': self.lead.pk, 'canal': 'meta_ads',
        }, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_reader_can_list(self):
        PointContact.objects.create(
            company=self.co, lead=self.lead,
            canal='meta_ads', date_contact=_now())
        api = make_api(self.reader)
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 200)

    def test_reader_can_view_attribution(self):
        PointContact.objects.create(
            company=self.co, lead=self.lead,
            canal='meta_ads', date_contact=_now())
        api = make_api(self.reader)
        resp = api.get(ATTR, {'lead': self.lead.pk})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['count'], 1)

    def test_writer_can_create(self):
        api = make_api(self.writer)
        resp = api.post(BASE, {
            'lead': self.lead.pk, 'canal': 'meta_ads',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

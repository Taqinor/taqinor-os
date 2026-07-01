"""N94 — tests des surcharges de traduction de l'interface (TranslationOverride).

Couvre : CRUD company-scopé, unicité (company, locale, key), l'endpoint de
lecture ``effective`` qui ne renvoie QUE les surcharges de la société courante,
le bulk (upsert + suppression sur valeur vide), et la company forcée côté
serveur (jamais lue du corps)."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models_translations import TranslationOverride

User = get_user_model()

BASE = '/api/django/parametres/traductions/'


def _company(slug='trad-co', nom='Trad Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _auth(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


class TranslationOverrideTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.other = _company(slug='trad-other', nom='Autre Co')
        self.admin = User.objects.create_user(
            username='trad_admin', password='x',
            role_legacy='admin', company=self.company)
        self.api = _auth(self.admin)

    # ── Effective (rien d'enregistré → aucune régression) ─────────────────
    def test_effective_empty_when_no_override(self):
        r = self.api.get(BASE + 'effective/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['overrides'], {})

    # ── Création + company forcée serveur ─────────────────────────────────
    def test_create_forces_company_server_side(self):
        # On tente d'injecter une AUTRE company dans le corps : ignorée.
        r = self.api.post(BASE, {
            'locale': 'en', 'key': 'nav.stock', 'value': 'Inventory',
            'company': self.other.id,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        obj = TranslationOverride.objects.get(id=r.data['id'])
        self.assertEqual(obj.company_id, self.company.id)
        self.assertEqual(obj.locale, 'en')
        self.assertEqual(obj.key, 'nav.stock')
        self.assertEqual(obj.value, 'Inventory')

    def test_create_rejects_unknown_locale(self):
        r = self.api.post(BASE, {
            'locale': 'de', 'key': 'nav.stock', 'value': 'x'},
            format='json')
        self.assertEqual(r.status_code, 400)

    def test_create_rejects_blank_key(self):
        r = self.api.post(BASE, {
            'locale': 'fr', 'key': '   ', 'value': 'x'},
            format='json')
        self.assertEqual(r.status_code, 400)

    # ── Unicité (company, locale, key) ────────────────────────────────────
    def test_unique_per_company_locale_key(self):
        TranslationOverride.objects.create(
            company=self.company, locale='fr', key='common.save', value='X')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TranslationOverride.objects.create(
                    company=self.company, locale='fr',
                    key='common.save', value='Y')

    def test_same_key_allowed_across_locales_and_companies(self):
        TranslationOverride.objects.create(
            company=self.company, locale='fr', key='common.save', value='A')
        # Même clé, autre locale → OK.
        TranslationOverride.objects.create(
            company=self.company, locale='en', key='common.save', value='B')
        # Même clé+locale, autre company → OK.
        TranslationOverride.objects.create(
            company=self.other, locale='fr', key='common.save', value='C')
        self.assertEqual(TranslationOverride.objects.count(), 3)

    # ── Scoping : effective/list ne voient QUE la société courante ────────
    def test_effective_returns_only_own_company(self):
        TranslationOverride.objects.create(
            company=self.company, locale='fr', key='nav.leads', value='Pistes')
        TranslationOverride.objects.create(
            company=self.company, locale='en', key='nav.leads', value='Leads!')
        # Surcharge d'une AUTRE société : ne doit jamais apparaître.
        TranslationOverride.objects.create(
            company=self.other, locale='fr', key='nav.leads', value='SECRET')
        r = self.api.get(BASE + 'effective/')
        self.assertEqual(r.status_code, 200)
        ov = r.data['overrides']
        self.assertEqual(ov['fr']['nav.leads'], 'Pistes')
        self.assertEqual(ov['en']['nav.leads'], 'Leads!')
        # La valeur de l'autre société n'a pas fuité.
        self.assertNotIn('SECRET', str(ov))

    def test_list_scoped_to_company(self):
        TranslationOverride.objects.create(
            company=self.company, locale='fr', key='a.b', value='mine')
        TranslationOverride.objects.create(
            company=self.other, locale='fr', key='a.b', value='theirs')
        r = self.api.get(BASE)
        self.assertEqual(r.status_code, 200)
        results = r.data['results'] if isinstance(r.data, dict) else r.data
        keys = {row['value'] for row in results}
        self.assertIn('mine', keys)
        self.assertNotIn('theirs', keys)

    def test_list_filter_by_locale(self):
        TranslationOverride.objects.create(
            company=self.company, locale='fr', key='a', value='fr')
        TranslationOverride.objects.create(
            company=self.company, locale='en', key='a', value='en')
        r = self.api.get(BASE, {'locale': 'en'})
        results = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertEqual({row['locale'] for row in results}, {'en'})

    # ── Bulk : upsert + suppression sur valeur vide ───────────────────────
    def test_bulk_upsert_and_delete(self):
        r = self.api.put(BASE + 'bulk/', {'items': [
            {'locale': 'en', 'key': 'nav.stock', 'value': 'Inventory'},
            {'locale': 'ar', 'key': 'nav.stock', 'value': 'المخزون'},
            {'locale': 'fr', 'key': 'bad', 'value': ''},  # vide → no-op
        ]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['overrides']['en']['nav.stock'], 'Inventory')
        self.assertEqual(r.data['overrides']['ar']['nav.stock'], 'المخزون')
        self.assertNotIn('fr', r.data['overrides'])
        # Toutes company-scopées.
        self.assertTrue(all(
            o.company_id == self.company.id
            for o in TranslationOverride.objects.all()))
        # Deuxième passe : une valeur vide SUPPRIME la surcharge existante.
        r2 = self.api.put(BASE + 'bulk/', {'items': [
            {'locale': 'en', 'key': 'nav.stock', 'value': ''},
        ]}, format='json')
        self.assertEqual(r2.status_code, 200)
        self.assertNotIn('nav.stock', r2.data['overrides'].get('en', {}))
        self.assertFalse(TranslationOverride.objects.filter(
            company=self.company, locale='en', key='nav.stock').exists())

    def test_bulk_requires_items_list(self):
        r = self.api.put(BASE + 'bulk/', {'items': 'nope'}, format='json')
        self.assertEqual(r.status_code, 400)

    # ── Delete = retour au catalogue statique ─────────────────────────────
    def test_delete_reverts_to_catalog(self):
        obj = TranslationOverride.objects.create(
            company=self.company, locale='fr', key='common.save', value='X')
        r = self.api.delete(f'{BASE}{obj.id}/')
        self.assertEqual(r.status_code, 204)
        self.assertFalse(
            TranslationOverride.objects.filter(id=obj.id).exists())

    def test_cannot_delete_other_company_row(self):
        obj = TranslationOverride.objects.create(
            company=self.other, locale='fr', key='common.save', value='X')
        r = self.api.delete(f'{BASE}{obj.id}/')
        # Hors scope → introuvable (404), la ligne survit.
        self.assertEqual(r.status_code, 404)
        self.assertTrue(
            TranslationOverride.objects.filter(id=obj.id).exists())

    # ── Écriture réservée admin/responsable (palier limité interdit) ──────
    def test_limited_role_cannot_write(self):
        limited = User.objects.create_user(
            username='trad_limited', password='x',
            role_legacy='commercial', company=self.company)
        api = _auth(limited)
        r = api.post(BASE, {
            'locale': 'fr', 'key': 'common.save', 'value': 'X'},
            format='json')
        self.assertIn(r.status_code, (403, 401))
        # Mais la lecture (effective) reste permise.
        r2 = api.get(BASE + 'effective/')
        self.assertEqual(r2.status_code, 200)

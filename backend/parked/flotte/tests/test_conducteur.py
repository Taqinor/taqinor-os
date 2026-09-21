"""Tests FLOTTE7 — Conducteur + permis (lien authentication.User).

Couvre :
- Création d'un Conducteur (company forcée côté serveur).
- Isolation multi-tenant (société A ne voit pas les conducteurs de société B).
- Lien utilisateur facultatif (conducteur sans compte ERP autorisé).
- Validation cross-société : un utilisateur d'une autre société est refusé.
- Filtre ``?actif=true|false``.
- Filtre ``?permis_expirant=<jours>`` (conducteurs dont le permis expire bientôt).
- Sélecteurs ``conducteurs_de_la_societe`` et ``conducteurs_permis_expirant``.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import Conducteur
from apps.flotte.selectors import (
    conducteurs_de_la_societe,
    conducteurs_permis_expirant,
)

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


URL = '/api/django/flotte/conducteurs/'


# ── Modèle (unité) ────────────────────────────────────────────────────────────

class ConducteurModelTests(TestCase):
    def setUp(self):
        self.co_a = make_company('cond-model-a', 'Cond Model A')
        self.user_a = make_user(self.co_a, 'cond-model-ua', 'admin')

    def test_create_without_user(self):
        """Un conducteur peut exister sans lien utilisateur ERP."""
        c = Conducteur.objects.create(
            company=self.co_a, nom='Chauffeur Externe')
        self.assertIsNone(c.user_id)
        self.assertEqual(str(c), 'Chauffeur Externe')

    def test_create_with_user(self):
        c = Conducteur.objects.create(
            company=self.co_a, nom='Ali Benali', user=self.user_a)
        self.assertEqual(c.user_id, self.user_a.id)

    def test_defaults(self):
        c = Conducteur.objects.create(company=self.co_a, nom='Test')
        self.assertTrue(c.actif)
        self.assertEqual(c.numero_permis, '')
        self.assertEqual(c.categorie_permis, '')
        self.assertEqual(c.telephone, '')
        self.assertIsNone(c.date_obtention)
        self.assertIsNone(c.date_expiration)


# ── Sélecteurs ────────────────────────────────────────────────────────────────

class ConducteurSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company('cond-sel-a', 'Cond Sel A')
        self.co_b = make_company('cond-sel-b', 'Cond Sel B')
        today = datetime.date.today()
        self.cond_actif = Conducteur.objects.create(
            company=self.co_a, nom='Actif A', actif=True,
            date_expiration=today + datetime.timedelta(days=10))
        self.cond_inactif = Conducteur.objects.create(
            company=self.co_a, nom='Inactif A', actif=False,
            date_expiration=today + datetime.timedelta(days=20))
        self.cond_b = Conducteur.objects.create(
            company=self.co_b, nom='Cond B', actif=True)

    def test_conducteurs_de_la_societe_scope(self):
        qs_a = conducteurs_de_la_societe(self.co_a)
        self.assertEqual(qs_a.count(), 2)
        qs_b = conducteurs_de_la_societe(self.co_b)
        self.assertEqual(qs_b.count(), 1)

    def test_conducteurs_de_la_societe_actif_only(self):
        qs = conducteurs_de_la_societe(self.co_a, actif_only=True)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().nom, 'Actif A')

    def test_conducteurs_permis_expirant(self):
        # Les deux conducteurs de co_a ont un permis (10 et 20 jours).
        qs = conducteurs_permis_expirant(self.co_a, jours=15)
        # Seulement celui qui expire dans 10 jours est dans la fenêtre de 15 j.
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().nom, 'Actif A')

    def test_conducteurs_permis_expirant_both(self):
        qs = conducteurs_permis_expirant(self.co_a, jours=30)
        self.assertEqual(qs.count(), 2)

    def test_conducteurs_permis_expirant_no_date_excluded(self):
        """Un conducteur sans date_expiration ne doit pas apparaître."""
        Conducteur.objects.create(company=self.co_a, nom='Sans permis')
        qs = conducteurs_permis_expirant(self.co_a, jours=365)
        # Le conducteur sans date_expiration est toujours exclu.
        noms = list(qs.values_list('nom', flat=True))
        self.assertNotIn('Sans permis', noms)

    def test_conducteurs_permis_expirant_past_excluded(self):
        """Un permis déjà expiré ne doit pas apparaître."""
        today = datetime.date.today()
        Conducteur.objects.create(
            company=self.co_a, nom='Expiré',
            date_expiration=today - datetime.timedelta(days=1))
        qs = conducteurs_permis_expirant(self.co_a, jours=365)
        noms = list(qs.values_list('nom', flat=True))
        self.assertNotIn('Expiré', noms)


# ── API ───────────────────────────────────────────────────────────────────────

class ConducteurApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('cond-api-a', 'Cond API A')
        self.co_b = make_company('cond-api-b', 'Cond API B')
        self.admin_a = make_user(self.co_a, 'cond-api-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'cond-api-admin-b', 'admin')
        self.user_a = make_user(self.co_a, 'cond-api-user-a', 'normal')
        self.user_b = make_user(self.co_b, 'cond-api-user-b', 'admin')

    # ── Création ─────────────────────────────────────────────────────────────

    def test_create_forces_company_server_side(self):
        """La société est posée côté serveur ; l'injection dans le corps est
        ignorée."""
        api = auth(self.admin_a)
        resp = api.post(URL, {
            'nom': 'Test Conducteur',
            'company': self.co_b.id,  # tentative d'injection — doit être ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        c = Conducteur.objects.get(id=resp.data['id'])
        self.assertEqual(c.company_id, self.co_a.id)

    def test_create_without_user_link(self):
        """Un conducteur sans lien utilisateur ERP est autorisé."""
        api = auth(self.admin_a)
        resp = api.post(URL, {'nom': 'Chauffeur Externe'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data['user'])
        self.assertIsNone(resp.data['user_display'])

    def test_create_with_user_link(self):
        """Un conducteur peut être lié à un utilisateur ERP de la même société."""
        api = auth(self.admin_a)
        resp = api.post(URL, {
            'nom': 'Ali Benali',
            'user': self.admin_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['user'], self.admin_a.id)

    def test_create_with_user_other_company_rejected(self):
        """Un utilisateur d'une autre société est refusé (400)."""
        api = auth(self.admin_a)
        resp = api.post(URL, {
            'nom': 'Mauvais Lien',
            'user': self.user_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_create_with_permis_fields(self):
        api = auth(self.admin_a)
        resp = api.post(URL, {
            'nom': 'Permis Complet',
            'numero_permis': 'MA-123456',
            'categorie_permis': 'C',
            'date_obtention': '2015-03-01',
            'date_expiration': '2025-03-01',
            'telephone': '0600000000',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['numero_permis'], 'MA-123456')
        self.assertEqual(resp.data['categorie_permis'], 'C')
        self.assertEqual(resp.data['date_obtention'], '2015-03-01')
        self.assertEqual(resp.data['date_expiration'], '2025-03-01')
        self.assertEqual(resp.data['telephone'], '0600000000')

    def test_create_with_xflt27_fields(self):
        """WIR4 — les 4 champs XFLT27 (carte de conducteur professionnel +
        formation continue NARSA) sont écrits ET exposés par l'API."""
        api = auth(self.admin_a)
        resp = api.post(URL, {
            'nom': 'Chauffeur Poids Lourd',
            'carte_conducteur_pro_numero': 'CCP-000123',
            'carte_conducteur_pro_expiration': '2027-01-01',
            'formation_continue_narsa_date': '2026-01-01',
            'formation_continue_narsa_validite': '2031-01-01',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['carte_conducteur_pro_numero'], 'CCP-000123')
        self.assertEqual(resp.data['carte_conducteur_pro_expiration'], '2027-01-01')
        self.assertEqual(resp.data['formation_continue_narsa_date'], '2026-01-01')
        self.assertEqual(resp.data['formation_continue_narsa_validite'], '2031-01-01')
        c = Conducteur.objects.get(id=resp.data['id'])
        self.assertEqual(c.carte_conducteur_pro_numero, 'CCP-000123')

    def test_create_with_employe_id(self):
        """Le lien vers le dossier employé RH (id numérique, string-FK) est
        accepté et exposé sans exiger de compte ERP (`user`)."""
        api = auth(self.admin_a)
        resp = api.post(URL, {
            'nom': 'Lié RH',
            'employe_id': 42,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['employe_id'], 42)

    # ── Isolation multi-tenant ────────────────────────────────────────────────

    def test_tenant_isolation_list(self):
        Conducteur.objects.create(company=self.co_a, nom='Cond A')
        Conducteur.objects.create(company=self.co_b, nom='Cond B')
        resp = auth(self.admin_a).get(URL)
        noms = [r['nom'] for r in rows(resp)]
        self.assertIn('Cond A', noms)
        self.assertNotIn('Cond B', noms)

    def test_cannot_retrieve_other_company_conducteur(self):
        c_b = Conducteur.objects.create(company=self.co_b, nom='Cond B Only')
        resp = auth(self.admin_a).get(f'{URL}{c_b.id}/')
        self.assertEqual(resp.status_code, 404)

    # ── Filtres ───────────────────────────────────────────────────────────────

    def test_filter_actif(self):
        Conducteur.objects.create(company=self.co_a, nom='Actif', actif=True)
        Conducteur.objects.create(company=self.co_a, nom='Inactif', actif=False)
        api = auth(self.admin_a)
        resp = api.get(f'{URL}?actif=true')
        noms = [r['nom'] for r in rows(resp)]
        self.assertIn('Actif', noms)
        self.assertNotIn('Inactif', noms)

    def test_filter_permis_expirant(self):
        today = datetime.date.today()
        Conducteur.objects.create(
            company=self.co_a, nom='Expire Bientot',
            date_expiration=today + datetime.timedelta(days=5))
        Conducteur.objects.create(
            company=self.co_a, nom='Expire Tard',
            date_expiration=today + datetime.timedelta(days=60))
        api = auth(self.admin_a)
        resp = api.get(f'{URL}?permis_expirant=10')
        noms = [r['nom'] for r in rows(resp)]
        self.assertIn('Expire Bientot', noms)
        self.assertNotIn('Expire Tard', noms)

    def test_filter_permis_expirant_default_30(self):
        """Sans paramètre numérique valide, la fenêtre par défaut est 30 jours."""
        today = datetime.date.today()
        Conducteur.objects.create(
            company=self.co_a, nom='Dans 20j',
            date_expiration=today + datetime.timedelta(days=20))
        Conducteur.objects.create(
            company=self.co_a, nom='Dans 60j',
            date_expiration=today + datetime.timedelta(days=60))
        api = auth(self.admin_a)
        resp = api.get(f'{URL}?permis_expirant=abc')  # valeur non numérique → 30
        noms = [r['nom'] for r in rows(resp)]
        self.assertIn('Dans 20j', noms)
        self.assertNotIn('Dans 60j', noms)

    # ── Permissions ───────────────────────────────────────────────────────────

    def test_read_allowed_for_any_role(self):
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.status_code, 200)

    def test_write_requires_responsable_or_admin(self):
        resp = auth(self.user_a).post(URL, {'nom': 'X'}, format='json')
        self.assertEqual(resp.status_code, 403)

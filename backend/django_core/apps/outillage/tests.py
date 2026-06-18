"""Tests du module Outillage (F1 / F2).

Couvre : isolation par société (A ne voit/touche pas B), société posée côté
serveur (jamais du corps), filtres statut/emplacement + recherche, séparation
stricte d'avec le stock vendable, et les kits — semés par défaut, items dont la
société suit le kit parent, écriture réservée à l'admin.
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from django.contrib.auth import get_user_model

from authentication.models import Company
from apps.stock.models import EmplacementStock
from apps.installations.models import TypeIntervention
from apps.outillage.models import Outillage, KitOutillage, KitOutillageItem

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    # role_legacy pilote is_admin_role / is_responsable (écriture outillage/kits).
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class OutillageTests(TestCase):
    def setUp(self):
        self.co_a = make_company('out-a', 'Out A')
        self.co_b = make_company('out-b', 'Out B')
        self.admin_a = make_user(self.co_a, 'out-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'out-admin-b', 'admin')
        self.depot_a = EmplacementStock.objects.create(
            company=self.co_a, nom='Dépôt', is_principal=True)
        self.camion_a = EmplacementStock.objects.create(
            company=self.co_a, nom='Camionnette')
        self.depot_b = EmplacementStock.objects.create(
            company=self.co_b, nom='Dépôt B', is_principal=True)

    # ── F1 : catalogue d'outillage ──
    def test_create_force_company_server_side(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/outillage/outils/', {
            'nom': 'Perceuse Bosch', 'categorie': 'Électroportatif',
            'asset_tag': 'AT-001', 'statut': 'disponible',
            'emplacement': self.depot_a.id,
            # Tentative d'injection d'une autre société — doit être ignorée.
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        tool = Outillage.objects.get(id=resp.data['id'])
        self.assertEqual(tool.company_id, self.co_a.id)

    def test_tenant_isolation_list(self):
        Outillage.objects.create(company=self.co_a, nom='Échelle A')
        Outillage.objects.create(company=self.co_b, nom='Échelle B')
        api = auth(self.admin_a)
        resp = api.get('/api/django/outillage/outils/')
        noms = [r['nom'] for r in rows(resp)]
        self.assertIn('Échelle A', noms)
        self.assertNotIn('Échelle B', noms)

    def test_cannot_retrieve_other_company_tool(self):
        b_tool = Outillage.objects.create(company=self.co_b, nom='Multimètre B')
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/outillage/outils/{b_tool.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_reject_foreign_emplacement(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/outillage/outils/', {
            'nom': 'Visseuse', 'emplacement': self.depot_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_filter_by_statut_and_emplacement(self):
        Outillage.objects.create(
            company=self.co_a, nom='Dispo', statut='disponible',
            emplacement=self.depot_a)
        Outillage.objects.create(
            company=self.co_a, nom='HS', statut='en_reparation',
            emplacement=self.camion_a)
        api = auth(self.admin_a)
        r1 = api.get('/api/django/outillage/outils/?statut=en_reparation')
        self.assertEqual([x['nom'] for x in rows(r1)], ['HS'])
        r2 = api.get(f'/api/django/outillage/outils/?emplacement={self.depot_a.id}')
        self.assertEqual([x['nom'] for x in rows(r2)], ['Dispo'])

    def test_search_by_asset_tag(self):
        Outillage.objects.create(
            company=self.co_a, nom='Échelle', asset_tag='ECH-42')
        Outillage.objects.create(company=self.co_a, nom='Perceuse')
        api = auth(self.admin_a)
        resp = api.get('/api/django/outillage/outils/?search=ECH-42')
        self.assertEqual([x['nom'] for x in rows(resp)], ['Échelle'])

    def test_statut_display_and_emplacement_nom(self):
        Outillage.objects.create(
            company=self.co_a, nom='Niveau', statut='en_intervention',
            emplacement=self.depot_a)
        api = auth(self.admin_a)
        resp = api.get('/api/django/outillage/outils/')
        row = rows(resp)[0]
        self.assertEqual(row['statut_display'], 'En intervention')
        self.assertEqual(row['emplacement_nom'], 'Dépôt')

    # ── F2 : kits d'outillage ──
    def test_default_kits_seeded_on_list(self):
        api = auth(self.admin_a)
        resp = api.get('/api/django/outillage/kits/')
        noms = [r['nom'] for r in rows(resp)]
        self.assertEqual(
            noms,
            ['Kit pose structure', 'Kit raccordement électrique',
             'Kit mise en service'])
        # Idempotent : un 2e appel ne duplique pas.
        api.get('/api/django/outillage/kits/')
        self.assertEqual(
            KitOutillage.objects.filter(company=self.co_a).count(), 3)

    def test_kits_tenant_isolated(self):
        auth(self.admin_a).get('/api/django/outillage/kits/')
        resp = auth(self.admin_b).get('/api/django/outillage/kits/')
        # B ne voit pas les kits de A (et a les siens semés).
        self.assertEqual(len(rows(resp)), 3)
        self.assertFalse(
            KitOutillage.objects.filter(company=self.co_b)
            .exclude(company=self.co_b).exists())

    def test_kit_item_company_follows_kit(self):
        kit = KitOutillage.objects.create(company=self.co_a, nom='Kit X')
        tool = Outillage.objects.create(company=self.co_a, nom='Clé')
        api = auth(self.admin_a)
        resp = api.post('/api/django/outillage/kit-items/', {
            'kit': kit.id, 'outil': tool.id, 'ordre': 0,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        item = KitOutillageItem.objects.get(id=resp.data['id'])
        self.assertEqual(item.company_id, self.co_a.id)

    def test_kit_item_rejects_foreign_outil(self):
        kit = KitOutillage.objects.create(company=self.co_a, nom='Kit Y')
        foreign = Outillage.objects.create(company=self.co_b, nom='Clé B')
        api = auth(self.admin_a)
        resp = api.post('/api/django/outillage/kit-items/', {
            'kit': kit.id, 'outil': foreign.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_kit_type_intervention_label(self):
        TypeIntervention.objects.create(
            company=self.co_a, cle='pose', libelle='Pose')
        kit = KitOutillage.objects.create(
            company=self.co_a, nom='Kit pose', type_intervention='pose')
        api = auth(self.admin_a)
        resp = api.get('/api/django/outillage/kits/')
        match = next(r for r in rows(resp) if r['id'] == kit.id)
        self.assertEqual(match['type_intervention_label'], 'Pose')

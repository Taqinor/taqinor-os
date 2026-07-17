"""Tests apps.entites (NTADM1/30/40/47)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from ..models import Entite
from ..services import CycleEntiteError, creer_entite, changer_parent

User = get_user_model()


def _company(nom='EntiteCo'):
    return Company.objects.create(nom=nom)


def _admin(company, username='admin'):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy='admin', is_staff=True)


class EntiteModelTests(TestCase):
    def setUp(self):
        self.company = _company()

    def test_creer_hierarchie_deux_niveaux(self):
        holding = creer_entite(self.company, nom='Holding', code='H')
        f1 = creer_entite(self.company, nom='Filiale 1', code='F1', parent=holding)
        f2 = creer_entite(self.company, nom='Filiale 2', code='F2', parent=holding)
        self.assertEqual(set(holding.enfants.values_list('code', flat=True)),
                         {'F1', 'F2'})
        self.assertEqual(f1.parent_id, holding.id)
        self.assertEqual(f2.parent_id, holding.id)

    def test_code_unique_par_company(self):
        creer_entite(self.company, nom='A', code='DUP')
        with self.assertRaises(Exception):
            creer_entite(self.company, nom='B', code='DUP')

    def test_code_reutilisable_entre_companies(self):
        other = _company('Autre')
        creer_entite(self.company, nom='A', code='X')
        # même code, autre société = OK
        e = creer_entite(other, nom='A', code='X')
        self.assertIsNotNone(e.pk)

    def test_anti_cycle_parent_descendant(self):
        a = creer_entite(self.company, nom='A', code='A')
        b = creer_entite(self.company, nom='B', code='B', parent=a)
        with self.assertRaises(CycleEntiteError):
            changer_parent(a, b)

    def test_anti_cycle_self_parent(self):
        a = creer_entite(self.company, nom='A', code='A')
        with self.assertRaises(CycleEntiteError):
            changer_parent(a, a)


class EntiteSignalTests(TestCase):
    def setUp(self):
        self.company = _company()

    def test_entite_created_signal_emis(self):
        from core.events import entite_created
        recu = []
        entite_created.connect(
            lambda sender, entite, **kw: recu.append(entite), weak=False)
        e = creer_entite(self.company, nom='A', code='A')
        self.assertIn(e, recu)

    def test_entite_deactivated_signal_emis(self):
        from core.events import entite_deactivated
        from ..services import desactiver_entite
        recu = []
        entite_deactivated.connect(
            lambda sender, entite, **kw: recu.append(entite), weak=False)
        e = creer_entite(self.company, nom='A', code='A')
        desactiver_entite(e)
        self.assertIn(e, recu)
        e.refresh_from_db()
        self.assertFalse(e.actif)


class EntiteApiTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.admin)

    def test_tree_endpoint(self):
        holding = creer_entite(self.company, nom='Holding', code='H')
        creer_entite(self.company, nom='F1', code='F1', parent=holding)
        resp = self.client_api.get('/api/django/entites/entites/?tree=1')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['code'], 'H')
        self.assertEqual(len(resp.data[0]['enfants']), 1)

    def test_create_via_api(self):
        resp = self.client_api.post(
            '/api/django/entites/entites/',
            {'nom': 'Agence', 'code': 'AG'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Entite.objects.filter(company=self.company, code='AG').exists())

    def test_isolation_multi_tenant(self):
        other = _company('Autre')
        creer_entite(other, nom='Foreign', code='FGN')
        resp = self.client_api.get('/api/django/entites/entites/')
        codes = [e['code'] for e in resp.data.get('results', resp.data)]
        self.assertNotIn('FGN', codes)

    def test_non_admin_refuse(self):
        normal = User.objects.create_user(
            username='u', password='pw', company=self.company, role_legacy='normal')
        c = APIClient()
        c.force_authenticate(normal)
        resp = c.post('/api/django/entites/entites/',
                      {'nom': 'X', 'code': 'X'}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_chatter_sur_renommage(self):
        e = creer_entite(self.company, nom='Ancien', code='E1')
        self.client_api.patch(
            f'/api/django/entites/entites/{e.id}/',
            {'nom': 'Nouveau'}, format='json')
        resp = self.client_api.get(f'/api/django/entites/entites/{e.id}/historique/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(any(a['field_label'] == 'Nom' for a in resp.data))


class EntiteImportTests(TestCase):
    """NTADM43 — import CSV 2 passes (holding→filiale→agence)."""

    def setUp(self):
        self.company = _company()

    def test_import_hierarchie_trois_niveaux(self):
        from ..import_service import commit
        csv_bytes = (
            'code,nom,code_parent\n'
            'AG,Agence,F1\n'   # enfant AVANT son parent
            'F1,Filiale,H\n'
            'H,Holding,\n'
        ).encode('utf-8')
        result = commit(csv_bytes, 'e.csv', self.company)
        self.assertEqual(result['created'], 3)
        self.assertEqual(result['erreurs'], [])
        ag = Entite.objects.get(company=self.company, code='AG')
        self.assertEqual(ag.parent.code, 'F1')
        self.assertEqual(ag.parent.parent.code, 'H')

    def test_import_parent_inconnu_dry_run(self):
        from ..import_service import dry_run
        csv_bytes = b'code,nom,code_parent\nA,Alpha,ZZZ\n'
        result = dry_run(csv_bytes, 'e.csv', self.company)
        self.assertTrue(any('ZZZ' in e['motif'] for e in result['erreurs']))


class EntiteExportTests(TestCase):
    """NTADM28 — export xlsx du référentiel."""

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.admin)

    def test_export_xlsx(self):
        creer_entite(self.company, nom='Holding', code='H')
        resp = self.client_api.get('/api/django/entites/entites/export/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheet', resp['Content-Type'])

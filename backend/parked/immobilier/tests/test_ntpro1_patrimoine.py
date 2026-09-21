"""NTPRO1 — App immobilier + patrimoine hiérarchique (Site→Bâtiment→Niveau→Local).

Couvre : société posée côté serveur (jamais lue du corps de requête),
isolation tenant (A ne voit/touche pas B), et la navigation arborescente
Site → Bâtiment → Niveau → Local (4 clics depuis la racine).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.immobilier.models import Batiment, Local, Niveau, Site

User = get_user_model()


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


class Ntpro1PatrimoineTests(TestCase):
    def setUp(self):
        self.co_a = make_company('immo-a', 'Immo A')
        self.co_b = make_company('immo-b', 'Immo B')
        self.admin_a = make_user(self.co_a, 'immo-admin-a')
        self.admin_b = make_user(self.co_b, 'immo-admin-b')

    def _build_tree(self, company):
        site = Site.objects.create(company=company, nom='Résidence Anfa')
        batiment = Batiment.objects.create(
            company=company, site=site, nom='Bâtiment A')
        niveau = Niveau.objects.create(
            company=company, batiment=batiment, numero='RDC')
        local = Local.objects.create(
            company=company, niveau=niveau, reference='RDC-01')
        return site, batiment, niveau, local

    def test_create_force_company_server_side(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/immobilier/sites/', {
            'nom': 'Résidence Anfa', 'ville': 'Casablanca',
            # Tentative d'injection d'une autre société — doit être ignorée.
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        site = Site.objects.get(id=resp.data['id'])
        self.assertEqual(site.company_id, self.co_a.id)

    def test_tenant_isolation_list(self):
        self._build_tree(self.co_a)
        self._build_tree(self.co_b)
        resp = auth(self.admin_a).get('/api/django/immobilier/sites/')
        noms = [r['nom'] for r in rows(resp)]
        self.assertEqual(len(noms), 1)

    def test_cannot_retrieve_other_company_local(self):
        _, _, _, local_b = self._build_tree(self.co_b)
        resp = auth(self.admin_a).get(
            f'/api/django/immobilier/locaux/{local_b.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_local_localisable_en_quatre_clics_depuis_racine(self):
        """Site → Bâtiment(?site=) → Niveau(?batiment=) → Local(?niveau=)."""
        site, batiment, niveau, local = self._build_tree(self.co_a)
        api = auth(self.admin_a)

        # Clic 1 : liste des sites.
        r1 = api.get('/api/django/immobilier/sites/')
        self.assertEqual(rows(r1)[0]['id'], site.id)

        # Clic 2 : bâtiments du site.
        r2 = api.get(f'/api/django/immobilier/batiments/?site={site.id}')
        self.assertEqual(rows(r2)[0]['id'], batiment.id)

        # Clic 3 : niveaux du bâtiment.
        r3 = api.get(f'/api/django/immobilier/niveaux/?batiment={batiment.id}')
        self.assertEqual(rows(r3)[0]['id'], niveau.id)

        # Clic 4 : locaux du niveau.
        r4 = api.get(f'/api/django/immobilier/locaux/?niveau={niveau.id}')
        self.assertEqual(rows(r4)[0]['id'], local.id)
        self.assertEqual(rows(r4)[0]['reference'], 'RDC-01')

    def test_locaux_filter_by_batiment_and_site(self):
        site, batiment, niveau, local = self._build_tree(self.co_a)
        api = auth(self.admin_a)
        r_bat = api.get(f'/api/django/immobilier/locaux/?batiment={batiment.id}')
        self.assertEqual(rows(r_bat)[0]['id'], local.id)
        r_site = api.get(f'/api/django/immobilier/locaux/?site={site.id}')
        self.assertEqual(rows(r_site)[0]['id'], local.id)

    def test_locaux_filter_by_statut(self):
        _, _, niveau, local = self._build_tree(self.co_a)
        Local.objects.create(
            company=self.co_a, niveau=niveau, reference='RDC-02',
            statut=Local.Statut.LOUE)
        api = auth(self.admin_a)
        resp = api.get('/api/django/immobilier/locaux/?statut=loue')
        refs = [r['reference'] for r in rows(resp)]
        self.assertEqual(refs, ['RDC-02'])

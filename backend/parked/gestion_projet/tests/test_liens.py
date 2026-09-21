"""Tests API + sélecteur des liens projet (``ProjetLien``).

Couvre : société posée côté serveur (jamais du corps), garde-fou même-société
sur le ``projet`` (un lien vers le projet d'une AUTRE société est refusé),
isolation de la liste entre sociétés, et l'enrichissement par sélecteur — qui
DÉGRADE proprement (libellé stocké, ``source='stored'``) quand l'app cible
n'expose pas de sélecteur (cas ``ticket`` → sav sans selectors.py).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import Projet, ProjetLien

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class ProjetLienApiTests(TestCase):
    BASE = '/api/django/gestion-projet/projet-liens/'

    def setUp(self):
        self.co_a = make_company('gp-liens-a', 'A')
        self.co_b = make_company('gp-liens-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-liens-a')
        self.user_b = make_user(self.co_b, 'gp-liens-b')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-A', nom='Projet A')
        self.projet_b = Projet.objects.create(
            company=self.co_b, code='P-B', nom='Projet B')

    def _payload(self, projet):
        return {
            'projet': projet.id,
            'type_cible': 'ticket',
            'cible_id': 42,
            'libelle': 'Ticket SAV #42',
        }

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(self.projet_a), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ProjetLien.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.projet, self.projet_a)
        self.assertEqual(obj.type_cible, 'ticket')

    def test_create_rejects_cross_tenant_projet(self):
        # user A tries to link to company B's project -> validation error.
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(self.projet_b), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('projet', resp.data)
        self.assertFalse(ProjetLien.objects.filter(cible_id=42).exists())

    def test_list_isolation(self):
        ProjetLien.objects.create(
            company=self.co_a, projet=self.projet_a,
            type_cible='facture', cible_id=7, libelle='F7')
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_list_filter_by_projet_and_type(self):
        ProjetLien.objects.create(
            company=self.co_a, projet=self.projet_a,
            type_cible='facture', cible_id=7, libelle='F7')
        ProjetLien.objects.create(
            company=self.co_a, projet=self.projet_a,
            type_cible='ticket', cible_id=8, libelle='T8')
        resp = auth(self.user_a).get(
            self.BASE + '?projet=%d&type_cible=ticket' % self.projet_a.id)
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['cible_id'], 8)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'gp-liens-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)


class ProjetLienSelectorTests(TestCase):
    """Le sélecteur d'enrichissement dégrade proprement sans app cible."""

    def setUp(self):
        self.co = make_company('gp-sel', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-S', nom='Projet S')

    def test_enrichment_degrades_to_stored_label(self):
        # A 'ticket' link: sav exposes no selectors.py -> stored label kept,
        # no import of another app's models, no crash.
        ProjetLien.objects.create(
            company=self.co, projet=self.projet,
            type_cible='ticket', cible_id=99, libelle='Ticket stocké')
        result = selectors.liens_enrichis(self.projet)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['type_cible'], 'ticket')
        self.assertEqual(row['cible_id'], 99)
        self.assertEqual(row['libelle'], 'Ticket stocké')
        self.assertEqual(row['source'], 'stored')

    def test_enrichment_devis_missing_target_degrades(self):
        # A 'devis' link whose target devis does not exist: ventes selector is
        # called but returns None -> degrade to stored label, never crash.
        ProjetLien.objects.create(
            company=self.co, projet=self.projet,
            type_cible='devis', cible_id=123456, libelle='Devis stocké')
        result = selectors.liens_enrichis(self.projet)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['type_cible'], 'devis')
        self.assertEqual(row['libelle'], 'Devis stocké')
        self.assertEqual(row['source'], 'stored')

    def test_liens_for_projet_is_company_scoped(self):
        ProjetLien.objects.create(
            company=self.co, projet=self.projet,
            type_cible='achat', cible_id=5, libelle='Achat 5')
        qs = selectors.liens_for_projet(self.projet)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().cible_id, 5)

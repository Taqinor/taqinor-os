"""ZGED8 — Recherches/filtres GED enregistrés et partageables.

Couvre :
  * enregistrer une vue « Contrats à approuver ce mois », la rappeler
    ré-applique les filtres (les critères sont renvoyés tels quels) ;
  * une vue partagée apparaît chez les collègues (lecture), une vue privée
    non ;
  * suppression réservée au créateur/admin.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged.models import VueGedEnregistree

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


class ZGed8Base(TestCase):
    def setUp(self):
        self.co_a = make_company('zged8-a', 'Zged8 A')
        self.admin_a = make_user(self.co_a, 'zged8-admin-a', 'admin')
        self.autre_a = make_user(self.co_a, 'zged8-autre-a', 'normal')


class ViewTests(ZGed8Base):
    def test_enregistrer_et_rappeler_une_vue(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/vues/', {
            'nom': 'Contrats à approuver ce mois',
            'criteres': {'statut': 'en_attente', 'tag': 3},
            'partagee': False,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        vue_id = resp.data['id']
        resp2 = api.get(f'/api/django/ged/vues/{vue_id}/')
        self.assertEqual(
            resp2.data['criteres'], {'statut': 'en_attente', 'tag': 3})

    def test_vue_partagee_visible_chez_collegue_privee_non(self):
        VueGedEnregistree.objects.create(
            company=self.co_a, utilisateur=self.admin_a,
            nom='Partagée', partagee=True)
        VueGedEnregistree.objects.create(
            company=self.co_a, utilisateur=self.admin_a,
            nom='Privée', partagee=False)
        api_autre = auth(self.autre_a)
        resp = api_autre.get('/api/django/ged/vues/')
        noms = {v['nom'] for v in resp.data['results']} \
            if isinstance(resp.data, dict) and 'results' in resp.data \
            else {v['nom'] for v in resp.data}
        self.assertIn('Partagée', noms)
        self.assertNotIn('Privée', noms)

    def test_suppression_reservee_createur_ou_admin(self):
        vue = VueGedEnregistree.objects.create(
            company=self.co_a, utilisateur=self.admin_a,
            nom='À moi', partagee=True)
        api_autre = auth(self.autre_a)
        resp = api_autre.delete(f'/api/django/ged/vues/{vue.pk}/')
        self.assertEqual(resp.status_code, 403)
        # Le créateur peut supprimer sa propre vue.
        api_admin = auth(self.admin_a)
        resp2 = api_admin.delete(f'/api/django/ged/vues/{vue.pk}/')
        self.assertEqual(resp2.status_code, 204)

    def test_admin_peut_supprimer_vue_dautrui(self):
        vue = VueGedEnregistree.objects.create(
            company=self.co_a, utilisateur=self.autre_a,
            nom='Autre', partagee=True)
        api_admin = auth(self.admin_a)
        resp = api_admin.delete(f'/api/django/ged/vues/{vue.pk}/')
        self.assertEqual(resp.status_code, 204)

    def test_isolation_societe(self):
        co_b = make_company('zged8-b', 'Zged8 B')
        admin_b = make_user(co_b, 'zged8-admin-b', 'admin')
        VueGedEnregistree.objects.create(
            company=self.co_a, utilisateur=self.admin_a,
            nom='A', partagee=True)
        api_b = auth(admin_b)
        resp = api_b.get('/api/django/ged/vues/')
        data = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(data), 0)

"""ZSAL3 — CRUD des équipes commerciales (Paramètres → CRM), distinct du
dashboard « Mes équipes » (tests_zsal3_equipes.py, qui couvre stats_equipe()).

Covers:
  - Lecture ouverte à tout rôle, écriture réservée responsable/admin.
  - Société forcée côté serveur (jamais acceptée du corps de la requête).
  - Isolation multi-tenant (une équipe d'une autre société n'apparaît jamais,
    n'est jamais modifiable/supprimable via l'API).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import EquipeCommerciale

User = get_user_model()


def make_company(slug='zsal3crud-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': slug})[0]


class TestEquipeCommercialeCRUD(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other_company = make_company('zsal3crud-other')
        self.resp = User.objects.create_user(
            username='zsal3cruresp', password='x', role_legacy='responsable',
            company=self.company)
        self.commercial = User.objects.create_user(
            username='zsal3crucommercial', password='x', company=self.company)
        self.api = APIClient()

    def auth_as(self, user):
        token = AccessToken.for_user(user)
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_responsable_cree_une_equipe_societe_forcee(self):
        self.auth_as(self.resp)
        resp = self.api.post('/api/django/crm/equipes/', {
            'nom': 'Équipe Sud',
            'company': self.other_company.id,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        equipe = EquipeCommerciale.objects.get(id=resp.data['id'])
        self.assertEqual(equipe.company_id, self.company.id)

    def test_commercial_peut_lire_mais_pas_creer(self):
        EquipeCommerciale.objects.create(company=self.company, nom='Équipe Nord')
        self.auth_as(self.commercial)
        resp = self.api.get('/api/django/crm/equipes/')
        self.assertEqual(resp.status_code, 200)
        create_resp = self.api.post(
            '/api/django/crm/equipes/', {'nom': 'Tentative'}, format='json')
        self.assertEqual(create_resp.status_code, 403)

    def test_membres_et_nb_membres_reflete_la_composition(self):
        equipe = EquipeCommerciale.objects.create(
            company=self.company, nom='Équipe Ouest')
        equipe.membres.set([self.commercial])
        self.auth_as(self.resp)
        resp = self.api.get(f'/api/django/crm/equipes/{equipe.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['nb_membres'], 1)
        self.assertIn(self.commercial.id, resp.data['membres'])

    def test_cross_company_404_sur_detail_update_delete(self):
        equipe_autre = EquipeCommerciale.objects.create(
            company=self.other_company, nom='Équipe Ailleurs')
        self.auth_as(self.resp)
        get_resp = self.api.get(f'/api/django/crm/equipes/{equipe_autre.id}/')
        self.assertEqual(get_resp.status_code, 404)
        patch_resp = self.api.patch(
            f'/api/django/crm/equipes/{equipe_autre.id}/',
            {'nom': 'Renommée'}, format='json')
        self.assertEqual(patch_resp.status_code, 404)
        del_resp = self.api.delete(f'/api/django/crm/equipes/{equipe_autre.id}/')
        self.assertEqual(del_resp.status_code, 404)
        equipe_autre.refresh_from_db()
        self.assertEqual(equipe_autre.nom, 'Équipe Ailleurs')

    def test_responsable_archive_une_equipe(self):
        equipe = EquipeCommerciale.objects.create(
            company=self.company, nom='Équipe À archiver')
        self.auth_as(self.resp)
        resp = self.api.patch(
            f'/api/django/crm/equipes/{equipe.id}/', {'actif': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        equipe.refresh_from_db()
        self.assertFalse(equipe.actif)

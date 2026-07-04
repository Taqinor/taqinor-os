"""Tests XPRJ14 — checklist d'une tâche.

Couvre : CRUD + toggle (isolation tenant), le % coché exposé au sérialiseur de
tâche (``pct_checklist_fait``, SUGGESTION jamais un écrasement silencieux de
``avancement_pct``), et le refus d'une tâche d'une AUTRE société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet.models import ItemChecklistTache, Projet, Tache

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


class ItemChecklistTacheTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj14', 'S')
        self.user = make_user(self.co, 'resp-xprj14')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X14', nom='Projet X14')
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Tâche checklist',
            avancement_pct=40)

    def test_creation_scoping(self):
        api = auth(self.user)
        resp = api.post('/api/django/gestion-projet/items-checklist/', {
            'tache': self.tache.id,
            'libelle': 'Vérifier onduleur',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        item = ItemChecklistTache.objects.get(id=resp.data['id'])
        self.assertEqual(item.company_id, self.co.id)
        self.assertFalse(item.fait)

    def test_tache_autre_societe_refusee(self):
        autre_co = make_company('gp-xprj14-autre', 'Autre')
        autre_projet = Projet.objects.create(
            company=autre_co, code='P-AUTRE14', nom='Autre projet')
        autre_tache = Tache.objects.create(
            company=autre_co, projet=autre_projet, libelle='Autre tâche')
        api = auth(self.user)
        resp = api.post('/api/django/gestion-projet/items-checklist/', {
            'tache': autre_tache.id,
            'libelle': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_toggle_pose_fait_par_et_fait_le(self):
        item = ItemChecklistTache.objects.create(
            company=self.co, tache=self.tache, libelle='Item 1')
        api = auth(self.user)
        resp = api.post(
            f'/api/django/gestion-projet/items-checklist/{item.id}/toggle/')
        self.assertEqual(resp.status_code, 200)
        item.refresh_from_db()
        self.assertTrue(item.fait)
        self.assertEqual(item.fait_par_id, self.user.id)
        self.assertIsNotNone(item.fait_le)

        # Re-toggle → réinitialise fait_par/fait_le.
        resp2 = api.post(
            f'/api/django/gestion-projet/items-checklist/{item.id}/toggle/')
        self.assertEqual(resp2.status_code, 200)
        item.refresh_from_db()
        self.assertFalse(item.fait)
        self.assertIsNone(item.fait_par_id)
        self.assertIsNone(item.fait_le)

    def test_isolation_tenant_toggle(self):
        autre_co = make_company('gp-xprj14-toggle-autre', 'Autre')
        autre_user = make_user(autre_co, 'user-toggle-autre')
        item = ItemChecklistTache.objects.create(
            company=self.co, tache=self.tache, libelle='Item privé')
        api = auth(autre_user)
        resp = api.post(
            f'/api/django/gestion-projet/items-checklist/{item.id}/toggle/')
        self.assertEqual(resp.status_code, 404)

    def test_pct_checklist_fait_expose_sur_tache(self):
        ItemChecklistTache.objects.create(
            company=self.co, tache=self.tache, libelle='A', fait=True)
        ItemChecklistTache.objects.create(
            company=self.co, tache=self.tache, libelle='B', fait=False)
        api = auth(self.user)
        resp = api.get(
            f'/api/django/gestion-projet/taches/{self.tache.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['pct_checklist_fait'], 50)
        # Suggestion uniquement : l'avancement saisi n'est jamais écrasé.
        self.assertEqual(resp.data['avancement_pct'], 40)

    def test_pct_checklist_fait_none_sans_item(self):
        api = auth(self.user)
        resp = api.get(
            f'/api/django/gestion-projet/taches/{self.tache.id}/')
        self.assertIsNone(resp.data['pct_checklist_fait'])

"""LB48 — vues enregistrées de compte (crm.SavedView).

Vue PERSONNELLE (filtres + disposition) par utilisateur, pour une page
applicative donnée (ex. 'crm.leads'). Double scoping systématique : société
ET utilisateur — un utilisateur ne voit/modifie jamais les vues d'un
collègue, même dans la même société. company/user sont toujours posés côté
serveur (jamais lus du corps de requête).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import SavedView
from apps.roles.models import Role

User = get_user_model()

LIST_URL = '/api/django/crm/vues-enregistrees/'


def _detail_url(pk):
    return f'{LIST_URL}{pk}/'


class SavedViewApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor LB48', slug='taqinor-lb48')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial LB48',
            permissions=['crm_voir', 'crm_creer', 'crm_modifier'])
        self.user_a = User.objects.create_user(
            username='user_a_lb48', password='x',
            company=self.company, role=self.role)
        self.user_b = User.objects.create_user(
            username='user_b_lb48', password='x',
            company=self.company, role=self.role)

        self.other_company = Company.objects.create(
            nom='Taqinor LB48 Autre', slug='taqinor-lb48-autre')
        self.other_role = Role.objects.create(
            company=self.other_company, nom='Commercial LB48 Autre',
            permissions=['crm_voir', 'crm_creer', 'crm_modifier'])
        self.user_c = User.objects.create_user(
            username='user_c_lb48', password='x',
            company=self.other_company, role=self.other_role)

        self.client_a = APIClient()
        self.client_a.force_authenticate(self.user_a)
        self.client_b = APIClient()
        self.client_b.force_authenticate(self.user_b)

    # (a) company/user toujours forcés côté serveur ─────────────────────────
    def test_create_force_company_et_user_meme_si_le_corps_tente_d_injecter_autre_chose(self):
        resp = self.client_a.post(LIST_URL, {
            'page': 'crm.leads',
            'name': 'Ma vue',
            'rank': 0,
            'payload': {'filters': {'stage': 'NEW'}, 'view': 'kanban'},
            # Tentatives d'injection — doivent être ignorées (pas de champ
            # company/user exposé par le serializer).
            'company': self.other_company.id,
            'user': self.user_c.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        view = SavedView.objects.get(pk=resp.data['id'])
        self.assertEqual(view.company_id, self.company.id)
        self.assertEqual(view.user_id, self.user_a.id)
        # Le serializer n'expose jamais company/user.
        self.assertNotIn('company', resp.data)
        self.assertNotIn('user', resp.data)

    # (b) isolation stricte par utilisateur (même société) ──────────────────
    def test_user_b_ne_voit_ni_ne_modifie_les_vues_de_user_a(self):
        resp = self.client_a.post(LIST_URL, {
            'page': 'crm.leads', 'name': 'Vue de A', 'payload': {},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        view_id = resp.data['id']

        # Absent de la liste de B.
        list_resp = self.client_b.get(LIST_URL, {'page': 'crm.leads'})
        self.assertEqual(list_resp.status_code, 200)
        results = list_resp.data['results'] if isinstance(list_resp.data, dict) else list_resp.data
        self.assertFalse(any(r['id'] == view_id for r in results))

        # 404 en détail pour B (jamais 403 — l'objet n'existe pas dans SON
        # queryset scopé).
        detail_resp = self.client_b.get(_detail_url(view_id))
        self.assertEqual(detail_resp.status_code, 404)

        # 404 en modification/suppression pour B.
        patch_resp = self.client_b.patch(
            _detail_url(view_id), {'name': 'Piratée'}, format='json')
        self.assertEqual(patch_resp.status_code, 404)
        delete_resp = self.client_b.delete(_detail_url(view_id))
        self.assertEqual(delete_resp.status_code, 404)

        # Toujours visible/modifiable pour A elle-même.
        self.assertEqual(self.client_a.get(_detail_url(view_id)).status_code, 200)

    # (c) unicité (user, page, name) ─────────────────────────────────────────
    def test_nom_duplique_meme_page_meme_utilisateur_renvoie_400(self):
        first = self.client_a.post(LIST_URL, {
            'page': 'crm.leads', 'name': 'Mes leads chauds', 'payload': {},
        }, format='json')
        self.assertEqual(first.status_code, 201, first.data)

        duplicate = self.client_a.post(LIST_URL, {
            'page': 'crm.leads', 'name': 'Mes leads chauds', 'payload': {},
        }, format='json')
        self.assertEqual(duplicate.status_code, 400, duplicate.data)

        # Le même nom sur une AUTRE page reste permis (contrainte scoped page).
        other_page = self.client_a.post(LIST_URL, {
            'page': 'crm.autre', 'name': 'Mes leads chauds', 'payload': {},
        }, format='json')
        self.assertEqual(other_page.status_code, 201, other_page.data)

    # (d) reorder ────────────────────────────────────────────────────────────
    def test_reorder_pose_le_rang_selon_l_ordre_des_ids_et_ignore_les_ids_etrangers(self):
        ids = []
        for name in ['Vue 1', 'Vue 2', 'Vue 3']:
            resp = self.client_a.post(LIST_URL, {
                'page': 'crm.leads', 'name': name, 'payload': {},
            }, format='json')
            self.assertEqual(resp.status_code, 201, resp.data)
            ids.append(resp.data['id'])

        # Vue de B (même page) — ne doit jamais être affectée ni réordonnée
        # par l'appel de A même si son id est glissé dans la liste.
        foreign_resp = self.client_b.post(LIST_URL, {
            'page': 'crm.leads', 'name': 'Vue de B', 'payload': {},
        }, format='json')
        foreign_id = foreign_resp.data['id']

        new_order = [ids[2], foreign_id, ids[0], ids[1], 999999]
        reorder_resp = self.client_a.post(f'{LIST_URL}reorder/', {
            'page': 'crm.leads', 'ids': new_order,
        }, format='json')
        self.assertEqual(reorder_resp.status_code, 200, reorder_resp.data)

        returned_ids = [row['id'] for row in reorder_resp.data]
        self.assertEqual(returned_ids, [ids[2], ids[0], ids[1]])

        self.assertEqual(SavedView.objects.get(pk=ids[2]).rank, 0)
        self.assertEqual(SavedView.objects.get(pk=ids[0]).rank, 2)
        self.assertEqual(SavedView.objects.get(pk=ids[1]).rank, 3)
        # La vue de B n'a pas bougé.
        self.assertEqual(SavedView.objects.get(pk=foreign_id).rank, 0)

    # (e) liste ordonnée par rang ─────────────────────────────────────────────
    def test_liste_ordonnee_par_rang(self):
        created_ids = []
        for name in ['Zèbre', 'Alpha', 'Milieu']:
            resp = self.client_a.post(LIST_URL, {
                'page': 'crm.leads', 'name': name, 'payload': {},
            }, format='json')
            created_ids.append(resp.data['id'])

        # Rangs volontairement dans le désordre du nom pour prouver le tri.
        SavedView.objects.filter(pk=created_ids[0]).update(rank=2)  # Zèbre
        SavedView.objects.filter(pk=created_ids[1]).update(rank=0)  # Alpha
        SavedView.objects.filter(pk=created_ids[2]).update(rank=1)  # Milieu

        list_resp = self.client_a.get(LIST_URL, {'page': 'crm.leads'})
        self.assertEqual(list_resp.status_code, 200)
        results = list_resp.data['results'] if isinstance(list_resp.data, dict) else list_resp.data
        self.assertEqual(
            [row['id'] for row in results],
            [created_ids[1], created_ids[2], created_ids[0]],
        )

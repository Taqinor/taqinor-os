"""ZSAL3 — CRUD des équipes commerciales (Paramètres → CRM), distinct du
dashboard « Mes équipes » (tests_zsal3_equipes.py, qui couvre stats_equipe()).

Covers:
  - Lecture ouverte à tout rôle, écriture réservée au palier ADMIN
    (ACRM26 : une équipe pilote une portée — un responsable non admin ne
    s'y nomme plus).
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
        # ACRM26 — l'écriture des équipes est réservée au palier admin.
        self.resp = User.objects.create_user(
            username='zsal3cruresp', password='x', role_legacy='admin',
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


class TestEquipeStructurePersonnel(TestCase):
    """Fondateur 26/10/2026 — l'équipe est la source de « qui encadre qui » :
    son responsable devient le superviseur de ses membres, une personne
    n'appartient qu'à une équipe, et une seule équipe reçoit les leads."""

    URL = '/api/django/crm/equipes/'

    def setUp(self):
        self.company = make_company('structure-co')
        self.admin = User.objects.create_user(
            username='struct_admin', password='x', role_legacy='admin',
            company=self.company)
        self.chef = User.objects.create_user(
            username='struct_chef', password='x', company=self.company)
        self.m1 = User.objects.create_user(
            username='struct_m1', password='x', company=self.company)
        self.m2 = User.objects.create_user(
            username='struct_m2', password='x', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _creer(self, nom, membres, responsable=None, **extra):
        r = self.api.post(self.URL, {
            'nom': nom, 'membres': [u.id for u in membres],
            'responsable': responsable.id if responsable else None, **extra,
        }, format='json')
        return r

    def _sup(self, user):
        user.refresh_from_db()
        return user.supervisor_id

    def test_responsable_devient_superviseur_des_membres(self):
        r = self._creer('Casa', [self.m1, self.m2], self.chef)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self._sup(self.m1), self.chef.id)
        self.assertEqual(self._sup(self.m2), self.chef.id)
        self.assertIsNone(self._sup(self.chef))

    def test_membre_retire_ou_equipe_supprimee_libere_le_superviseur(self):
        r = self._creer('Casa', [self.m1, self.m2], self.chef)
        eid = r.data['id']
        r = self.api.patch(f'{self.URL}{eid}/', {'membres': [self.m2.id]},
                           format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(self._sup(self.m1))
        self.assertEqual(self._sup(self.m2), self.chef.id)
        self.assertEqual(self.api.delete(f'{self.URL}{eid}/').status_code, 204)
        self.assertIsNone(self._sup(self.m2))

    def test_une_personne_une_seule_equipe(self):
        self.assertEqual(self._creer('Casa', [self.m1], self.chef).status_code, 201)
        r = self._creer('Rabat', [self.m1])
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('membres', r.data)

    def test_cycle_refuse(self):
        # m1 encadre déjà le chef : il ne peut pas devenir membre de son équipe.
        self.chef.supervisor = self.m1
        self.chef.save(update_fields=['supervisor'])
        r = self._creer('Casa', [self.m1], self.chef)
        self.assertEqual(r.status_code, 400, r.content)

    def test_une_seule_equipe_recoit_les_leads(self):
        a = self._creer('Casa', [self.m1], self.chef, recoit_leads=True)
        b = self._creer('Rabat', [self.m2], recoit_leads=True)
        self.assertEqual(b.status_code, 201, b.content)
        self.assertFalse(
            EquipeCommerciale.objects.get(pk=a.data['id']).recoit_leads)
        self.assertTrue(
            EquipeCommerciale.objects.get(pk=b.data['id']).recoit_leads)


class TestVisibiliteMembreEquipe(TestCase):
    """Fondateur 26/10/2026 — un Commercial (``records_scope_soi``) ne voit
    pas les leads de ses coéquipiers ; le responsable d'équipe les voit."""

    def test_membre_voit_les_siens_responsable_voit_l_equipe(self):
        from apps.crm.models import Lead
        from apps.crm.selectors import leads_visibles
        from apps.roles.models import Role
        from apps.roles.permissions_registre import (
            COMMERCIAL_PERMISSIONS, SCOPE_SELF, SCOPE_TEAM)

        self.assertIn(SCOPE_SELF, COMMERCIAL_PERMISSIONS)
        self.assertNotIn(SCOPE_TEAM, COMMERCIAL_PERMISSIONS)
        company = make_company('visibilite-co')
        role = Role.objects.create(
            company=company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS))
        chef = User.objects.create_user(
            username='vis_chef', password='x', company=company, role=role)
        a = User.objects.create_user(
            username='vis_a', password='x', company=company, role=role,
            supervisor=chef)
        b = User.objects.create_user(
            username='vis_b', password='x', company=company, role=role,
            supervisor=chef)
        la = Lead.objects.create(company=company, nom='A', owner=a)
        lb = Lead.objects.create(company=company, nom='B', owner=b)
        self.assertEqual(
            set(leads_visibles(a, company).values_list('id', flat=True)),
            {la.id})
        self.assertEqual(
            set(leads_visibles(chef, company).values_list('id', flat=True)),
            {la.id, lb.id})

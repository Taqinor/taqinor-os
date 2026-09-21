"""Tests XKB22 — Parcours de lecture d'intégration.

Couvre :
* créer un parcours + ses articles ordonnés ;
* assigner un parcours à un utilisateur trace sa progression article par
  article (via les KbLecture déjà existantes) ;
* la complétion passe à True seulement quand TOUS les articles sont lus ;
* isolation cross-tenant (parcours/article/utilisateur d'une autre société
  refusés à l'assignation).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb import selectors, services
from apps.kb.models import (
    KbArticle, KbParcours, KbParcoursArticle, KbParcoursAssignation,
)

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


class KbParcoursProgressionTests(TestCase):
    def setUp(self):
        self.co = make_company('kb-parcours', 'P')
        self.admin = make_user(self.co, 'kb-parcours-admin', role='admin')
        self.nouvel_embauche = make_user(
            self.co, 'kb-parcours-newbie', role='normal')
        self.parcours = KbParcours.objects.create(
            company=self.co, nom='Onboarding poseur', metier='poseur')
        self.art1 = KbArticle.objects.create(
            company=self.co, titre='Sécurité chantier', corps='X',
            statut=KbArticle.Statut.PUBLIE)
        self.art2 = KbArticle.objects.create(
            company=self.co, titre='Procédure pose', corps='Y',
            statut=KbArticle.Statut.PUBLIE)
        KbParcoursArticle.objects.create(
            company=self.co, parcours=self.parcours, article=self.art1, ordre=1)
        KbParcoursArticle.objects.create(
            company=self.co, parcours=self.parcours, article=self.art2, ordre=2)
        self.assignation = KbParcoursAssignation.objects.create(
            company=self.co, parcours=self.parcours,
            utilisateur=self.nouvel_embauche)

    def test_progression_starts_at_zero(self):
        progression = selectors.progression_parcours(self.assignation)
        self.assertEqual(progression['nombre_lus'], 0)
        self.assertEqual(progression['nombre_total'], 2)
        self.assertFalse(progression['complet'])

    def test_progression_tracks_each_article_read(self):
        services.marquer_lu(self.art1, utilisateur=self.nouvel_embauche)
        progression = selectors.progression_parcours(self.assignation)
        self.assertEqual(progression['nombre_lus'], 1)
        self.assertFalse(progression['complet'])
        lus = {a['article']: a['lu'] for a in progression['articles']}
        self.assertTrue(lus[self.art1.id])
        self.assertFalse(lus[self.art2.id])

    def test_progression_complete_when_all_read(self):
        services.marquer_lu(self.art1, utilisateur=self.nouvel_embauche)
        services.marquer_lu(self.art2, utilisateur=self.nouvel_embauche)
        progression = selectors.progression_parcours(self.assignation)
        self.assertEqual(progression['nombre_lus'], 2)
        self.assertTrue(progression['complet'])

    def test_articles_ordonnes_respects_ordre(self):
        membres = list(selectors.articles_ordonnes_parcours(self.parcours))
        attendu = [self.art1.id, self.art2.id]
        self.assertEqual([m.article_id for m in membres], attendu)

    def test_assignations_pour_utilisateur_scoped(self):
        assigns = selectors.assignations_pour_utilisateur(
            self.co, self.nouvel_embauche)
        self.assertEqual(list(assigns), [self.assignation])


class KbParcoursApiTests(TestCase):
    PARCOURS = '/api/django/kb/parcours/'
    ASSIGNATIONS = '/api/django/kb/parcours-assignations/'

    def setUp(self):
        self.co = make_company('kb-parcours-api', 'A')
        self.admin = make_user(self.co, 'kb-parcours-api-admin', role='admin')
        self.employe = make_user(
            self.co, 'kb-parcours-api-emp', role='normal')
        self.article = KbArticle.objects.create(
            company=self.co, titre='Intro', corps='X')

    def test_create_parcours_forces_company_and_creator(self):
        resp = auth(self.admin).post(
            self.PARCOURS, {'nom': 'Onboarding commercial', 'metier': 'commercial'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        parcours = KbParcours.objects.get(id=resp.data['id'])
        self.assertEqual(parcours.company, self.co)
        self.assertEqual(parcours.created_by, self.admin)

    def test_assign_and_track_progression_via_api(self):
        parcours = KbParcours.objects.create(company=self.co, nom='P1')
        KbParcoursArticle.objects.create(
            company=self.co, parcours=parcours, article=self.article, ordre=1)

        resp = auth(self.admin).post(
            self.ASSIGNATIONS,
            {'parcours': parcours.id, 'utilisateur': self.employe.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        assignation_id = resp.data['id']

        prog_resp = auth(self.admin).get(
            f'{self.ASSIGNATIONS}{assignation_id}/progression/')
        self.assertEqual(prog_resp.status_code, 200)
        self.assertEqual(prog_resp.data['nombre_total'], 1)
        self.assertFalse(prog_resp.data['complet'])

        services.marquer_lu(self.article, utilisateur=self.employe)
        prog_resp2 = auth(self.admin).get(
            f'{self.ASSIGNATIONS}{assignation_id}/progression/')
        self.assertTrue(prog_resp2.data['complet'])

    def test_cross_tenant_assignation_rejected(self):
        other_co = make_company('kb-parcours-other', 'O')
        other_user = make_user(other_co, 'kb-parcours-other-u1')
        parcours = KbParcours.objects.create(company=self.co, nom='P2')
        resp = auth(self.admin).post(
            self.ASSIGNATIONS,
            {'parcours': parcours.id, 'utilisateur': other_user.id},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_parcours_articles_endpoint_ordered(self):
        parcours = KbParcours.objects.create(company=self.co, nom='P3')
        art2 = KbArticle.objects.create(company=self.co, titre='2e', corps='Y')
        KbParcoursArticle.objects.create(
            company=self.co, parcours=parcours, article=art2, ordre=2)
        KbParcoursArticle.objects.create(
            company=self.co, parcours=parcours, article=self.article, ordre=1)
        resp = auth(self.admin).get(f'{self.PARCOURS}{parcours.id}/articles/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            [r['article'] for r in resp.data], [self.article.id, art2.id])

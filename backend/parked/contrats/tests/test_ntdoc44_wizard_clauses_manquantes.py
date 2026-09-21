"""Tests NTDOC44 — Wizard « Résoudre les clauses manquantes ».

Critère d'acceptation :
- un contrat avec 3 clauses obligatoires manquantes les ajoute TOUTES en un
  seul appel ;
- le contrat ressort ensuite HORS de la liste ``clauses-manquantes/``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats.models import Clause, ClauseContrat, Contrat

User = get_user_model()

BASE = '/api/django/contrats/contrats/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class WizardClausesManquantesTests(TestCase):
    def setUp(self):
        self.co = make_company('ntdoc44', 'Wizard clauses')
        self.admin = User.objects.create_user(
            username='ntdoc44-admin', password='x', company=self.co,
            role_legacy='admin')
        self.contrat = Contrat.objects.create(
            company=self.co, objet='Maintenance',
            type_contrat=Contrat.TypeContrat.MAINTENANCE)
        self.clauses = [
            Clause.objects.create(
                company=self.co, titre=titre, corps=f'Texte de {titre}.',
                ordre=rang,
                obligatoire_pour_types=[Contrat.TypeContrat.MAINTENANCE])
            for rang, titre in enumerate(
                ['Responsabilité', 'Confidentialité', 'Résiliation'])
        ]
        self.url = f'{BASE}{self.contrat.id}/wizard-clauses-manquantes/'
        self.manquantes_url = f'{BASE}{self.contrat.id}/clauses-manquantes/'

    def test_get_propose_le_texte_gabarit(self):
        api = auth(self.admin)
        resp = api.get(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['count'], 3)
        premier = resp.data['results'][0]
        self.assertEqual(premier['titre'], 'Responsabilité')
        self.assertEqual(premier['corps'], 'Texte de Responsabilité.')
        self.assertEqual(premier['ordre_propose'], 1)

    def test_trois_clauses_ajoutees_en_un_appel(self):
        """Le critère : 3 manquantes → toutes ajoutées en un clic."""
        api = auth(self.admin)
        resp = api.post(self.url, {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['ajoutees'], 3)
        self.assertEqual(resp.data['restantes'], 0)
        self.assertEqual(
            ClauseContrat.objects.filter(contrat=self.contrat).count(), 3)

    def test_contrat_sort_de_la_liste_des_manquantes(self):
        api = auth(self.admin)
        api.post(self.url, {}, format='json')
        resp = api.get(self.manquantes_url)
        self.assertEqual(resp.data['count'], 0)
        self.assertEqual(resp.data['results'], [])

    def test_texte_resolu_depuis_la_clause_source(self):
        """Aucune duplication de logique : le texte vient de la clause-source."""
        api = auth(self.admin)
        api.post(self.url, {}, format='json')
        ligne = ClauseContrat.objects.get(
            contrat=self.contrat, clause=self.clauses[0])
        self.assertEqual(ligne.titre, 'Responsabilité')
        self.assertEqual(ligne.corps, 'Texte de Responsabilité.')
        self.assertFalse(ligne.surchargee)
        self.assertEqual(ligne.company_id, self.co.id)

    def test_selection_partielle(self):
        api = auth(self.admin)
        resp = api.post(
            self.url, {'clauses': [self.clauses[1].id]}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['ajoutees'], 1)
        self.assertEqual(resp.data['restantes'], 2)

    def test_clause_non_manquante_refusee(self):
        api = auth(self.admin)
        api.post(self.url, {}, format='json')
        resp = api.post(
            self.url, {'clauses': [self.clauses[0].id]}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('clauses', resp.data['detail'])

    def test_ordre_reprend_apres_les_clauses_existantes(self):
        ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat, titre='Préambule',
            corps='…', ordre=7)
        api = auth(self.admin)
        resp = api.post(self.url, {}, format='json')
        self.assertEqual(
            [ligne['ordre'] for ligne in resp.data['results']], [8, 9, 10])

    def test_appel_repete_est_sans_effet(self):
        api = auth(self.admin)
        api.post(self.url, {}, format='json')
        resp = api.post(self.url, {}, format='json')
        self.assertEqual(resp.data['ajoutees'], 0)
        self.assertEqual(
            ClauseContrat.objects.filter(contrat=self.contrat).count(), 3)

    def test_contrat_d_une_autre_societe_404(self):
        autre = make_company('ntdoc44-b', 'B')
        user_b = User.objects.create_user(
            username='ntdoc44-b-admin', password='x', company=autre,
            role_legacy='admin')
        resp = auth(user_b).post(self.url, {}, format='json')
        self.assertEqual(resp.status_code, 404)

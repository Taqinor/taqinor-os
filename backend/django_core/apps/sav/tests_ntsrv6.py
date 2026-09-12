"""NTSRV6 — Compétences requises par catégorie de ticket (additif, optionnel).

Critère d'acceptation : une catégorie SANS compétence définie garde le
comportement actuel (aucun filtre) — la liste est vide, jamais None, et rien
dans l'affectation ne change.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv6 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import Competence
from apps.sav.models import CategorieTicket

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTSRV6CompetencesCategorieTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv6', defaults={'nom': 'Sav Co NTSRV6'})
        self.autre, _ = Company.objects.get_or_create(
            slug='sav-ntsrv6-b', defaults={'nom': 'Autre Co'})
        self.admin = User.objects.create_user(
            username='ntsrv6_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.competence = Competence.objects.create(
            company=self.company, code='raccordement_ac',
            libelle='Raccordement AC', domaine=Competence.Domaine.RACCORDEMENT_AC)
        self.competence_autre = Competence.objects.create(
            company=self.autre, code='raccordement_ac',
            libelle='Raccordement AC', domaine=Competence.Domaine.RACCORDEMENT_AC)

    def test_categorie_sans_competence_ne_filtre_rien(self):
        categorie = CategorieTicket.objects.create(
            company=self.company, libelle='Question')
        self.assertEqual(categorie.competences_requises_ids(), [])
        self.assertEqual(categorie.niveau_competence_min, 1)

    def test_competence_attachee_et_relue(self):
        categorie = CategorieTicket.objects.create(
            company=self.company, libelle='Onduleur Huawei',
            niveau_competence_min=2)
        categorie.competences_requises.add(self.competence)
        self.assertEqual(categorie.competences_requises_ids(),
                         [self.competence.pk])
        self.assertEqual(
            list(self.competence.categories_ticket_sav.all()), [categorie])

    def test_api_expose_et_ecrit_les_competences(self):
        resp = self.api.post('/api/django/sav/categories-ticket/', {
            'libelle': 'Onduleur', 'competences_requises': [self.competence.pk],
            'niveau_competence_min': 2,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        categorie = CategorieTicket.objects.get(libelle='Onduleur')
        self.assertEqual(categorie.company, self.company)
        self.assertEqual(categorie.competences_requises_ids(),
                         [self.competence.pk])
        self.assertEqual(resp.json()['niveau_competence_min'], 2)

    def test_competence_d_une_autre_societe_refusee(self):
        resp = self.api.post('/api/django/sav/categories-ticket/', {
            'libelle': 'Fuite tenant',
            'competences_requises': [self.competence_autre.pk],
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('competences_requises', resp.json())

    def test_niveau_hors_echelle_refuse_en_francais(self):
        resp = self.api.post('/api/django/sav/categories-ticket/', {
            'libelle': 'Niveau fou', 'niveau_competence_min': 9,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('niveau_competence_min', resp.json())

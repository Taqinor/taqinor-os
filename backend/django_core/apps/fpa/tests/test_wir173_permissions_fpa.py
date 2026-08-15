"""Tests WIR173 — FP&A n'est plus ouvert à tout utilisateur authentifié.

Les 14 ViewSets FP&A (cycles budgétaires, lignes de budget, prévisions
glissantes, scénarios, consolidation, variance, drivers de masse salariale,
export XLSX) ne portaient AUCUNE ``permission_classes`` : le défaut projet
« authentifié » suffisait à LIRE et à ÉCRIRE toute la planification financière
de la société. Les quatre codes ``fpa_*`` existaient dans
``apps/fpa/permissions.py`` mais n'étaient ni au catalogue ni posés en garde.

Couvre :
* les 4 codes sont au catalogue ``ALL_PERMISSIONS`` ;
* un rôle SANS aucun code FP&A → 403 partout (lecture ET écriture) ;
* ``fpa_consulter_tout`` = lecture seule (403 en écriture) ;
* ``fpa_saisir`` écrit ;
* les 4 actions de pilotage du cycle (ouvrir-saisie, clore, dupliquer, export)
  exigent ``fpa_administrer`` — un porteur ``fpa_saisir`` reçoit 403 ;
* Directeur (``ALL_PERMISSIONS``) passe partout ;
* la porte NTFPA26 est préservée : un responsable de département sans code
  ``fpa_*`` garde l'accès à SON périmètre.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.fpa.models import CycleBudgetaire, Departement
from apps.fpa.permissions import (
    FPA_ADMINISTRER, FPA_CONSULTER_TOUT, FPA_SAISIR, FPA_VALIDER,
)
from apps.roles.models import ALL_PERMISSIONS, Role

User = get_user_model()

URL_CYCLES = '/api/django/fpa/cycles-budgetaires/'
URL_DEPARTEMENTS = '/api/django/fpa/departements/'
URL_LIGNES = '/api/django/fpa/lignes-budget-departement/'
URL_CONSOLIDATION = '/api/django/fpa/consolidation/'


class CatalogueFpaTests(TestCase):
    def test_les_quatre_codes_sont_au_catalogue(self):
        for code in (FPA_SAISIR, FPA_VALIDER, FPA_CONSULTER_TOUT,
                     FPA_ADMINISTRER):
            self.assertIn(code, ALL_PERMISSIONS, code)


class GardeFpaTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='wir173-co', defaults={'nom': 'WIR173 Co'})
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2028',
            date_debut=date(2028, 1, 1), date_fin=date(2028, 12, 31),
            statut=CycleBudgetaire.Statut.BROUILLON)

    def _user(self, username, permissions):
        role = Role.objects.create(
            company=self.company, nom=f'role-{username}',
            permissions=list(permissions))
        return User.objects.create_user(
            username=username, password='x', company=self.company, role=role)

    def _api(self, user):
        api = APIClient()
        api.force_authenticate(user)
        return api

    # ── Le trou comblé ────────────────────────────────────────────────────
    def test_role_sans_code_fpa_403_partout(self):
        intrus = self._user('wir173-intrus', ['crm_voir', 'crm_creer'])
        api = self._api(intrus)
        for url in (URL_CYCLES, URL_DEPARTEMENTS, URL_LIGNES,
                    URL_CONSOLIDATION):
            self.assertEqual(api.get(url).status_code, 403, url)
        resp = api.post(URL_DEPARTEMENTS, {'code': 'X', 'nom': 'X'})
        self.assertEqual(resp.status_code, 403)

    def test_drivers_masse_salariale_ferme_aux_non_fpa(self):
        intrus = self._user('wir173-intrus-drivers', ['crm_voir'])
        resp = self._api(intrus).post(
            '/api/django/fpa/drivers/masse-salariale/projeter/',
            {'mois_debut': '2028-01-01', 'mois_fin': '2028-03-01'},
            format='json')
        self.assertEqual(resp.status_code, 403)

    # ── Lecture ≠ écriture ────────────────────────────────────────────────
    def test_consulter_tout_lit_mais_n_ecrit_pas(self):
        lecteur = self._user('wir173-lecteur', [FPA_CONSULTER_TOUT])
        api = self._api(lecteur)
        self.assertEqual(api.get(URL_CYCLES).status_code, 200)
        self.assertEqual(api.get(URL_DEPARTEMENTS).status_code, 200)
        resp = api.post(URL_DEPARTEMENTS, {'code': 'Y', 'nom': 'Y'})
        self.assertEqual(resp.status_code, 403)

    def test_saisir_ecrit(self):
        saisisseur = self._user('wir173-saisie', [FPA_SAISIR])
        resp = self._api(saisisseur).post(
            URL_DEPARTEMENTS, {'code': 'Z', 'nom': 'Z'})
        self.assertEqual(resp.status_code, 201)

    # ── Pilotage du cycle = administration FP&A ───────────────────────────
    def test_actions_cycle_reservees_a_fpa_administrer(self):
        saisisseur = self._user('wir173-saisie-cycle', [FPA_SAISIR])
        api = self._api(saisisseur)
        base = f'{URL_CYCLES}{self.cycle.pk}/'
        self.assertEqual(api.post(f'{base}ouvrir-saisie/').status_code, 403)
        self.assertEqual(api.post(f'{base}clore/').status_code, 403)
        self.assertEqual(api.post(f'{base}dupliquer/').status_code, 403)
        self.assertEqual(api.get(f'{base}export/').status_code, 403)

    def test_administrer_pilote_le_cycle(self):
        admin_fpa = self._user('wir173-adm', [FPA_ADMINISTRER])
        resp = self._api(admin_fpa).post(
            f'{URL_CYCLES}{self.cycle.pk}/ouvrir-saisie/')
        self.assertEqual(resp.status_code, 200)

    def test_directeur_passe_partout(self):
        directeur = self._user('wir173-directeur', ALL_PERMISSIONS)
        api = self._api(directeur)
        self.assertEqual(api.get(URL_CYCLES).status_code, 200)
        self.assertEqual(
            api.post(f'{URL_CYCLES}{self.cycle.pk}/ouvrir-saisie/')
            .status_code, 200)

    # ── La porte NTFPA26 reste ouverte ────────────────────────────────────
    def test_responsable_de_departement_garde_son_perimetre(self):
        """Être responsable d'un département EST la seconde porte FP&A."""
        chef = self._user('wir173-chef-dept', ['crm_voir'])
        Departement.objects.create(
            company=self.company, code='D1', nom='Dept 1', responsable=chef)
        api = self._api(chef)
        self.assertEqual(api.get(URL_LIGNES).status_code, 200)

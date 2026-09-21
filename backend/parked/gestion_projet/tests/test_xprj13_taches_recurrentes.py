"""Tests XPRJ13 — tâches récurrentes.

Couvre : génération à échéance (hebdomadaire/mensuelle), IDEMPOTENCE d'un
re-run le même jour (jamais deux occurrences pour la même échéance), fin de
récurrence respectée (``date_fin`` et ``nb_occurrences``), et le CRUD
company-scopé du gabarit.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet.models import Projet, RecurrenceTache, Tache
from apps.gestion_projet.services import generer_taches_recurrentes

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


class GenererTachesRecurrentesTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj13', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X13', nom='Projet X13')

    def test_generation_hebdomadaire_a_echeance(self):
        rec = RecurrenceTache.objects.create(
            company=self.co, projet=self.projet, libelle='Relevé hebdo',
            regle=RecurrenceTache.Regle.HEBDOMADAIRE, intervalle=1,
            prochaine_echeance=date(2026, 7, 1))
        crees = generer_taches_recurrentes(
            self.co, aujourd_hui=date(2026, 7, 3))
        self.assertEqual(len(crees), 1)
        self.assertEqual(crees[0].libelle, 'Relevé hebdo')
        rec.refresh_from_db()
        self.assertEqual(rec.prochaine_echeance, date(2026, 7, 8))
        self.assertEqual(rec.nb_generees, 1)

    def test_generation_mensuelle_clamp_jour(self):
        rec = RecurrenceTache.objects.create(
            company=self.co, projet=self.projet, libelle='Facture mensuelle',
            regle=RecurrenceTache.Regle.MENSUELLE, intervalle=1,
            prochaine_echeance=date(2026, 1, 31))
        generer_taches_recurrentes(self.co, aujourd_hui=date(2026, 1, 31))
        rec.refresh_from_db()
        # Février 2026 n'a que 28 jours → clamp.
        self.assertEqual(rec.prochaine_echeance, date(2026, 2, 28))

    def test_idempotence_rerun_meme_jour(self):
        RecurrenceTache.objects.create(
            company=self.co, projet=self.projet, libelle='Idempotente',
            regle=RecurrenceTache.Regle.HEBDOMADAIRE, intervalle=1,
            prochaine_echeance=date(2026, 7, 1))
        generer_taches_recurrentes(self.co, aujourd_hui=date(2026, 7, 3))
        crees2 = generer_taches_recurrentes(
            self.co, aujourd_hui=date(2026, 7, 3))
        self.assertEqual(crees2, [])
        self.assertEqual(
            Tache.objects.filter(libelle='Idempotente').count(), 1)

    def test_fin_de_recurrence_date_fin_respectee(self):
        rec = RecurrenceTache.objects.create(
            company=self.co, projet=self.projet, libelle='Limitée',
            regle=RecurrenceTache.Regle.HEBDOMADAIRE, intervalle=1,
            prochaine_echeance=date(2026, 7, 1),
            date_fin=date(2026, 7, 1))
        generer_taches_recurrentes(self.co, aujourd_hui=date(2026, 8, 1))
        rec.refresh_from_db()
        self.assertFalse(rec.actif)
        self.assertEqual(
            Tache.objects.filter(libelle='Limitée').count(), 1)

    def test_fin_de_recurrence_nb_occurrences_respecte(self):
        rec = RecurrenceTache.objects.create(
            company=self.co, projet=self.projet, libelle='Deux fois',
            regle=RecurrenceTache.Regle.HEBDOMADAIRE, intervalle=1,
            prochaine_echeance=date(2026, 7, 1), nb_occurrences=2)
        generer_taches_recurrentes(self.co, aujourd_hui=date(2026, 9, 1))
        rec.refresh_from_db()
        self.assertFalse(rec.actif)
        self.assertEqual(rec.nb_generees, 2)
        self.assertEqual(
            Tache.objects.filter(libelle='Deux fois').count(), 2)

    def test_recurrence_inactive_non_generee(self):
        RecurrenceTache.objects.create(
            company=self.co, projet=self.projet, libelle='Inactive',
            regle=RecurrenceTache.Regle.HEBDOMADAIRE, intervalle=1,
            prochaine_echeance=date(2026, 7, 1), actif=False)
        crees = generer_taches_recurrentes(
            self.co, aujourd_hui=date(2026, 7, 3))
        self.assertEqual(crees, [])


class RecurrenceTacheViewSetTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj13-crud', 'S')
        self.user = make_user(self.co, 'resp-xprj13')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X13B', nom='Projet X13 CRUD')

    def test_creation_scoping(self):
        api = auth(self.user)
        resp = api.post('/api/django/gestion-projet/recurrences-tache/', {
            'projet': self.projet.id,
            'libelle': 'Contrôle qualité',
            'regle': RecurrenceTache.Regle.MENSUELLE,
            'intervalle': 1,
            'prochaine_echeance': '2026-08-01',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        rec = RecurrenceTache.objects.get(id=resp.data['id'])
        self.assertEqual(rec.company_id, self.co.id)

    def test_isolation_tenant(self):
        autre_co = make_company('gp-xprj13-autre', 'Autre')
        autre_user = make_user(autre_co, 'user-autre-x13')
        RecurrenceTache.objects.create(
            company=self.co, projet=self.projet, libelle='Privée',
            regle=RecurrenceTache.Regle.HEBDOMADAIRE,
            prochaine_echeance=date(2026, 7, 1))
        api = auth(autre_user)
        resp = api.get('/api/django/gestion-projet/recurrences-tache/')
        data = resp.data
        rows = data['results'] if isinstance(data, dict) and 'results' in data \
            else data
        self.assertEqual(rows, [])

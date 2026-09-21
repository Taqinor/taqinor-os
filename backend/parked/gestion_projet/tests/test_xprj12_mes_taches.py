"""Tests XPRJ12 — vue « Mes tâches » transverse.

Couvre : isolation stricte (un user ne voit QUE ses tâches, tenant + user),
assignation directe (XPRJ10) vs affectation (directe ou via équipe), exclusion
des tâches terminées, et le tri d'urgence (retard > échéance proche >
priorité).
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import (
    AffectationRessource, Equipe, Projet, RessourceProfil, Tache,
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


class MesTachesSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj12', 'S')
        self.user = make_user(self.co, 'user-xprj12')
        self.autre_user = make_user(self.co, 'autre-xprj12')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X12', nom='Projet X12')
        self.ressource = RessourceProfil.objects.create(
            company=self.co, nom='Moi', user=self.user)
        self.aujourd_hui = date(2026, 7, 3)

    def test_isolation_user_ne_voit_que_ses_taches(self):
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Ma tâche',
            assigne=self.ressource)
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Pas ma tâche')
        res = selectors.mes_taches(self.user, aujourd_hui=self.aujourd_hui)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['libelle'], 'Ma tâche')

    def test_isolation_tenant(self):
        autre_co = make_company('gp-xprj12-autre', 'Autre')
        autre_ressource = RessourceProfil.objects.create(
            company=autre_co, nom='Autre moi')
        autre_user = make_user(autre_co, 'user-autre-co')
        autre_projet = Projet.objects.create(
            company=autre_co, code='P-AUTRE', nom='Autre projet')
        Tache.objects.create(
            company=autre_co, projet=autre_projet, libelle='Tâche autre co',
            assigne=autre_ressource)
        res = selectors.mes_taches(autre_user, aujourd_hui=self.aujourd_hui)
        self.assertEqual(res, [])

    def test_tache_terminee_exclue(self):
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Finie',
            assigne=self.ressource, statut=Tache.Statut.TERMINE)
        res = selectors.mes_taches(self.user, aujourd_hui=self.aujourd_hui)
        self.assertEqual(res, [])

    def test_affectation_directe(self):
        tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Affectée')
        AffectationRessource.objects.create(
            company=self.co, tache=tache, ressource=self.ressource,
            date_debut=self.aujourd_hui, date_fin=self.aujourd_hui)
        res = selectors.mes_taches(self.user, aujourd_hui=self.aujourd_hui)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['id'], tache.id)

    def test_affectation_via_equipe(self):
        tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Via équipe')
        equipe = Equipe.objects.create(company=self.co, nom='Équipe A')
        equipe.membres.add(self.ressource)
        AffectationRessource.objects.create(
            company=self.co, tache=tache, equipe=equipe,
            date_debut=self.aujourd_hui, date_fin=self.aujourd_hui)
        res = selectors.mes_taches(self.user, aujourd_hui=self.aujourd_hui)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['id'], tache.id)

    def test_tri_urgence_retard_puis_echeance_puis_priorite(self):
        en_retard = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='En retard',
            assigne=self.ressource,
            date_fin_prevue=self.aujourd_hui - timedelta(days=5))
        echeance_proche = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Proche',
            assigne=self.ressource,
            date_fin_prevue=self.aujourd_hui + timedelta(days=1))
        urgente_sans_date = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Urgente sans date',
            assigne=self.ressource, priorite=Tache.Priorite.URGENTE)
        res = selectors.mes_taches(self.user, aujourd_hui=self.aujourd_hui)
        ids = [r['id'] for r in res]
        self.assertEqual(
            ids, [en_retard.id, echeance_proche.id, urgente_sans_date.id])
        self.assertEqual(res[0]['retard_jours'], 5)

    def test_endpoint_api_isole(self):
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Ma tâche API',
            assigne=self.ressource)
        api = auth(self.autre_user)
        resp = api.get('/api/django/gestion-projet/taches/mes-taches/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [])

        api_moi = auth(self.user)
        resp2 = api_moi.get('/api/django/gestion-projet/taches/mes-taches/')
        self.assertEqual(len(resp2.data), 1)

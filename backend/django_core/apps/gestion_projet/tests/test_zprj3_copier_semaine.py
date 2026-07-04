"""Tests de la copie du plan de ressources de la semaine précédente (ZPRJ3).

Couvre : décalage correct des dates (7 j × N) ; exclusion des créneaux qui
tomberaient sur une indisponibilité de la ressource ou un conflit, avec
rapport détaillé ; aucun doublon si ré-exécutée deux fois de suite ; filtre
optionnel par ressource/équipe ; statut BROUILLON (ZPRJ2) sur les copies ;
isolation tenant ; fenêtre nulle (source == cible) ne fait rien.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import services
from apps.gestion_projet.models import (
    AffectationRessource, Indisponibilite, Projet, RessourceProfil, Tache,
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


class CopierSemaineServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-z3-svc', 'S')
        self.projet = Projet.objects.create(company=self.co, code='P-Z3', nom='P')
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T', ordre=1)
        self.ressource = RessourceProfil.objects.create(
            company=self.co, nom='R1', actif=True)
        self.aff = AffectationRessource.objects.create(
            company=self.co, tache=self.tache, ressource=self.ressource,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 3),
            charge_jours=Decimal('2'), note='Semaine 1')

    def test_copie_decale_les_dates_de_7_jours(self):
        resultat = services.copier_semaine_precedente(
            self.co, semaine_source=date(2026, 6, 1),
            semaine_cible=date(2026, 6, 8))
        self.assertEqual(resultat['nb_copiees'], 1)
        nouvelle_id = resultat['copiees'][0]['affectation_creee']
        nouvelle = AffectationRessource.objects.get(id=nouvelle_id)
        self.assertEqual(nouvelle.date_debut, date(2026, 6, 8))
        self.assertEqual(nouvelle.date_fin, date(2026, 6, 10))
        self.assertEqual(
            nouvelle.statut_publication,
            AffectationRessource.StatutPublication.BROUILLON)
        self.assertEqual(nouvelle.charge_jours, Decimal('2'))
        self.assertEqual(nouvelle.note, 'Semaine 1')

    def test_decalage_multiple_de_7(self):
        # 2 semaines plus tard (14 jours = 7 x 2).
        resultat = services.copier_semaine_precedente(
            self.co, semaine_source=date(2026, 6, 1),
            semaine_cible=date(2026, 6, 15))
        nouvelle_id = resultat['copiees'][0]['affectation_creee']
        nouvelle = AffectationRessource.objects.get(id=nouvelle_id)
        self.assertEqual(nouvelle.date_debut, date(2026, 6, 15))
        self.assertEqual(nouvelle.date_fin, date(2026, 6, 17))

    def test_saute_creneau_sur_indisponibilite(self):
        Indisponibilite.objects.create(
            company=self.co, ressource=self.ressource,
            date_debut=date(2026, 6, 8), date_fin=date(2026, 6, 10),
            type_indispo='conge')
        resultat = services.copier_semaine_precedente(
            self.co, semaine_source=date(2026, 6, 1),
            semaine_cible=date(2026, 6, 8))
        self.assertEqual(resultat['nb_copiees'], 0)
        self.assertEqual(resultat['nb_sautees'], 1)
        self.assertEqual(resultat['sautees'][0]['motif'], 'indisponible')

    def test_saute_creneau_en_conflit(self):
        tache2 = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T2', ordre=2)
        # Affectation déjà présente sur la fenêtre cible.
        AffectationRessource.objects.create(
            company=self.co, tache=tache2, ressource=self.ressource,
            date_debut=date(2026, 6, 9), date_fin=date(2026, 6, 9))
        resultat = services.copier_semaine_precedente(
            self.co, semaine_source=date(2026, 6, 1),
            semaine_cible=date(2026, 6, 8))
        self.assertEqual(resultat['nb_copiees'], 0)
        self.assertEqual(resultat['nb_sautees'], 1)
        self.assertEqual(resultat['sautees'][0]['motif'], 'conflit')

    def test_aucun_doublon_si_reexecutee(self):
        services.copier_semaine_precedente(
            self.co, semaine_source=date(2026, 6, 1),
            semaine_cible=date(2026, 6, 8))
        resultat2 = services.copier_semaine_precedente(
            self.co, semaine_source=date(2026, 6, 1),
            semaine_cible=date(2026, 6, 8))
        self.assertEqual(resultat2['nb_copiees'], 0)
        self.assertEqual(resultat2['nb_sautees'], 1)
        self.assertEqual(
            AffectationRessource.objects.filter(ressource=self.ressource)
            .count(), 2)  # source + 1 copie, pas de doublon

    def test_filtre_par_ressource(self):
        ressource2 = RessourceProfil.objects.create(
            company=self.co, nom='R2', actif=True)
        AffectationRessource.objects.create(
            company=self.co, tache=self.tache, ressource=ressource2,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 3))
        resultat = services.copier_semaine_precedente(
            self.co, semaine_source=date(2026, 6, 1),
            semaine_cible=date(2026, 6, 8), ressource_id=self.ressource.id)
        self.assertEqual(resultat['nb_copiees'], 1)
        self.assertFalse(
            AffectationRessource.objects.filter(
                ressource=ressource2,
                date_debut=date(2026, 6, 8)).exists())

    def test_fenetre_nulle_ne_fait_rien(self):
        resultat = services.copier_semaine_precedente(
            self.co, semaine_source=date(2026, 6, 1),
            semaine_cible=date(2026, 6, 1))
        self.assertEqual(resultat['nb_copiees'], 0)
        self.assertEqual(resultat['nb_sautees'], 0)


class CopierSemaineApiTests(TestCase):
    BASE = '/api/django/gestion-projet/affectations/copier-semaine/'

    def setUp(self):
        self.co_a = make_company('gp-z3-a', 'A')
        self.co_b = make_company('gp-z3-b', 'B')
        self.user_a = make_user(self.co_a, 'z3-api-a')
        self.user_b = make_user(self.co_b, 'z3-api-b')
        self.projet = Projet.objects.create(company=self.co_a, code='P-Z3A', nom='A')
        self.tache = Tache.objects.create(
            company=self.co_a, projet=self.projet, libelle='T', ordre=1)
        self.ressource = RessourceProfil.objects.create(
            company=self.co_a, nom='R', actif=True)
        self.aff = AffectationRessource.objects.create(
            company=self.co_a, tache=self.tache, ressource=self.ressource,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 3))

    def test_copier_endpoint(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'semaine_source': '2026-06-01', 'semaine_cible': '2026-06-08',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_copiees'], 1)

    def test_dates_manquantes_400(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_tenant(self):
        api = auth(self.user_b)
        resp = api.post(self.BASE, {
            'semaine_source': '2026-06-01', 'semaine_cible': '2026-06-08',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['nb_copiees'], 0)
        self.assertEqual(
            AffectationRessource.objects.filter(company=self.co_a).count(), 1)

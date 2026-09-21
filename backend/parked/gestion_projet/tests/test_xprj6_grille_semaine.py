"""Tests de la grille hebdomadaire de saisie des temps (XPRJ6).

Couvre : le sélecteur ``grille_semaine_temps`` (lignes projet/tâche × 7 jours,
totaux jour/semaine, suggestions depuis les affectations JAMAIS
auto-enregistrées, aucune suggestion sur un jour déjà saisi), l'endpoint
``timesheets/semaine/`` et l'action ``timesheets/copier-semaine/`` (copie en
brouillon, idempotence anti-doublon, isolation multi-société).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors, services
from apps.gestion_projet.models import (
    AffectationRessource,
    Projet,
    RessourceProfil,
    Tache,
    Timesheet,
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


class GrilleSemaineSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj6-sel', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-1', nom='Projet 1')
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Pose', ordre=1)
        self.ressource = RessourceProfil.objects.create(
            company=self.co, nom='Amine', cout_horaire=Decimal('100'))
        self.lundi = date(2026, 1, 5)  # lundi

    def test_grille_agrege_par_projet_tache_et_jour(self):
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.ressource, date=self.lundi, heures=Decimal('4'))
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.ressource, date=self.lundi + timedelta(days=1), heures=Decimal('3'))
        data = selectors.grille_semaine_temps(self.ressource, self.lundi)
        self.assertEqual(len(data['lignes']), 1)
        ligne = data['lignes'][0]
        self.assertEqual(ligne['heures'][0], Decimal('4'))
        self.assertEqual(ligne['heures'][1], Decimal('3'))
        self.assertEqual(ligne['total_ligne'], Decimal('7'))
        self.assertEqual(data['total_par_jour'][0], Decimal('4'))
        self.assertEqual(data['total_semaine'], Decimal('7'))
        self.assertEqual(len(data['jours']), 7)
        self.assertEqual(data['jours'][0], self.lundi.isoformat())

    def test_suggestions_depuis_affectations_jamais_sur_jour_deja_saisi(self):
        # Affectation couvrant toute la semaine → suggestion chaque jour.
        AffectationRessource.objects.create(
            company=self.co, tache=self.tache, ressource=self.ressource,
            date_debut=self.lundi,
            date_fin=self.lundi + timedelta(days=6),
            charge_jours=Decimal('1'))
        # Une saisie réelle le lundi : aucune suggestion ce jour-là.
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.ressource, date=self.lundi, heures=Decimal('8'))
        data = selectors.grille_semaine_temps(self.ressource, self.lundi)
        jours_suggeres = {s['jour_index'] for s in data['suggestions']}
        self.assertNotIn(0, jours_suggeres)  # lundi déjà saisi
        self.assertIn(1, jours_suggeres)
        self.assertEqual(len(data['suggestions']), 6)
        for s in data['suggestions']:
            self.assertEqual(s['tache'], self.tache.id)
            self.assertEqual(s['projet'], self.projet.id)

    def test_aucune_suggestion_sans_affectation(self):
        data = selectors.grille_semaine_temps(self.ressource, self.lundi)
        self.assertEqual(data['suggestions'], [])

    def test_suggestion_ignore_affectation_sans_tache(self):
        from apps.gestion_projet.models import Equipe
        equipe = Equipe.objects.create(company=self.co, nom='Eq1')
        AffectationRessource.objects.create(
            company=self.co, tache=self.tache, equipe=equipe,
            date_debut=self.lundi,
            date_fin=self.lundi + timedelta(days=1),
            charge_jours=Decimal('1'))
        # Affectation d'équipe (pas de ressource directe) : pas prise en
        # compte par le sélecteur ressource (aucune erreur, aucune suggestion).
        data = selectors.grille_semaine_temps(self.ressource, self.lundi)
        self.assertEqual(data['suggestions'], [])


class GrilleSemaineEndpointTests(TestCase):
    BASE = '/api/django/gestion-projet/timesheets/'

    def setUp(self):
        self.co = make_company('gp-xprj6-ep', 'E')
        self.user = make_user(self.co, 'xprj6-user')
        self.projet = Projet.objects.create(
            company=self.co, code='P-E', nom='E')
        self.ressource = RessourceProfil.objects.create(
            company=self.co, nom='Res E')
        self.lundi = date(2026, 2, 2)

    def test_endpoint_requiert_ressource_et_debut(self):
        api = auth(self.user)
        resp = api.get(f'{self.BASE}semaine/')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_renvoie_grille(self):
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.ressource,
            date=self.lundi, heures=Decimal('2'))
        api = auth(self.user)
        resp = api.get(
            f'{self.BASE}semaine/',
            {'ressource': self.ressource.id, 'debut': self.lundi.isoformat()})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['jours']), 7)
        self.assertEqual(resp.data['total_semaine'], '2.00')

    def test_endpoint_ressource_autre_societe_404(self):
        autre_co = make_company('gp-xprj6-ep2', 'E2')
        autre_res = RessourceProfil.objects.create(company=autre_co, nom='X')
        api = auth(self.user)
        resp = api.get(
            f'{self.BASE}semaine/',
            {'ressource': autre_res.id, 'debut': self.lundi.isoformat()})
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_interdit(self):
        normal = make_user(self.co, 'xprj6-normal', role='normal')
        api = auth(normal)
        resp = api.get(
            f'{self.BASE}semaine/',
            {'ressource': self.ressource.id, 'debut': self.lundi.isoformat()})
        self.assertEqual(resp.status_code, 403)


class CopierSemaineServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj6-copy', 'C')
        self.projet = Projet.objects.create(
            company=self.co, code='P-C', nom='C')
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T', ordre=1)
        self.ressource = RessourceProfil.objects.create(
            company=self.co, nom='Res C', cout_horaire=Decimal('50'))
        self.semaine_1 = date(2026, 3, 2)  # lundi
        self.semaine_2 = date(2026, 3, 9)  # lundi suivant

    def test_copie_decale_les_dates_en_brouillon(self):
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.ressource, date=self.semaine_1, heures=Decimal('5'),
            statut=Timesheet.Statut.APPROUVEE)
        rapport = services.copier_semaine_precedente_timesheets(
            self.ressource, semaine_source=self.semaine_1,
            semaine_cible=self.semaine_2)
        self.assertEqual(rapport['nb_copiees'], 1)
        self.assertEqual(rapport['nb_sautees'], 0)
        creee = Timesheet.objects.get(id=rapport['copiees'][0]['timesheet_creee'])
        self.assertEqual(creee.date, self.semaine_2)
        self.assertEqual(creee.heures, Decimal('5'))
        # Jamais le statut source (approuvée) — toujours brouillon.
        self.assertEqual(creee.statut, Timesheet.Statut.BROUILLON)
        self.assertEqual(creee.cout, Decimal('250.00'))

    def test_reexecution_ne_duplique_pas(self):
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.ressource, date=self.semaine_1, heures=Decimal('5'))
        services.copier_semaine_precedente_timesheets(
            self.ressource, semaine_source=self.semaine_1,
            semaine_cible=self.semaine_2)
        rapport2 = services.copier_semaine_precedente_timesheets(
            self.ressource, semaine_source=self.semaine_1,
            semaine_cible=self.semaine_2)
        self.assertEqual(rapport2['nb_copiees'], 0)
        self.assertEqual(rapport2['nb_sautees'], 1)
        self.assertEqual(rapport2['sautees'][0]['motif'], 'existe_deja')
        self.assertEqual(
            Timesheet.objects.filter(
                ressource=self.ressource, date=self.semaine_2).count(), 1)

    def test_semaine_identique_ne_fait_rien(self):
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.ressource, date=self.semaine_1, heures=Decimal('5'))
        rapport = services.copier_semaine_precedente_timesheets(
            self.ressource, semaine_source=self.semaine_1,
            semaine_cible=self.semaine_1)
        self.assertEqual(rapport, {
            'nb_copiees': 0, 'nb_sautees': 0, 'copiees': [], 'sautees': []})

    def test_periode_verrouillee_cible_est_sautee(self):
        from apps.gestion_projet.models import PeriodeVerrouilleeTemps
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.ressource, date=self.semaine_1, heures=Decimal('5'))
        PeriodeVerrouilleeTemps.objects.create(
            company=self.co, mois=services.mois_de(self.semaine_2))
        rapport = services.copier_semaine_precedente_timesheets(
            self.ressource, semaine_source=self.semaine_1,
            semaine_cible=self.semaine_2)
        self.assertEqual(rapport['nb_copiees'], 0)
        self.assertEqual(rapport['nb_sautees'], 1)
        self.assertEqual(
            rapport['sautees'][0]['motif'], 'periode_verrouillee')

    def test_admin_contourne_verrou(self):
        from apps.gestion_projet.models import PeriodeVerrouilleeTemps
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.ressource, date=self.semaine_1, heures=Decimal('5'))
        PeriodeVerrouilleeTemps.objects.create(
            company=self.co, mois=services.mois_de(self.semaine_2))
        rapport = services.copier_semaine_precedente_timesheets(
            self.ressource, semaine_source=self.semaine_1,
            semaine_cible=self.semaine_2, admin=True)
        self.assertEqual(rapport['nb_copiees'], 1)


class CopierSemaineEndpointTests(TestCase):
    BASE = '/api/django/gestion-projet/timesheets/'

    def setUp(self):
        self.co = make_company('gp-xprj6-cep', 'CE')
        self.user = make_user(self.co, 'xprj6-cep-user')
        self.projet = Projet.objects.create(
            company=self.co, code='P-CE', nom='CE')
        self.ressource = RessourceProfil.objects.create(
            company=self.co, nom='Res CE')
        self.semaine_1 = date(2026, 4, 6)
        self.semaine_2 = date(2026, 4, 13)

    def test_copier_semaine_endpoint(self):
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.ressource,
            date=self.semaine_1, heures=Decimal('6'))
        api = auth(self.user)
        resp = api.post(f'{self.BASE}copier-semaine/', {
            'ressource': self.ressource.id,
            'semaine_source': self.semaine_1.isoformat(),
            'semaine_cible': self.semaine_2.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_copiees'], 1)

    def test_copier_semaine_ressource_manquante_400(self):
        api = auth(self.user)
        resp = api.post(f'{self.BASE}copier-semaine/', {
            'semaine_source': self.semaine_1.isoformat(),
            'semaine_cible': self.semaine_2.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_copier_semaine_ressource_autre_societe_404(self):
        autre_co = make_company('gp-xprj6-cep2', 'CE2')
        autre_res = RessourceProfil.objects.create(company=autre_co, nom='X')
        api = auth(self.user)
        resp = api.post(f'{self.BASE}copier-semaine/', {
            'ressource': autre_res.id,
            'semaine_source': self.semaine_1.isoformat(),
            'semaine_cible': self.semaine_2.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 404)

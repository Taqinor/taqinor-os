"""Tests de l'auto-affectation à partir des propositions de nivellement (ZPRJ4).

Couvre : simulation (``simuler=True`` par défaut) ne mute rien ; confirmation
déplace les affectations sur-chargées vers les ressources sous-chargées
disponibles (statut BROUILLON) ; crée des affectations pour les tâches SANS
AFFECTATION vers la ressource la moins chargée disponible ; tâche sans
candidat valide rapportée dans ``non_resolues`` ; jamais de conflit créé ;
isolation tenant.
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


class AutoAffecterCreationTests(TestCase):
    """Tâches SANS affectation -> nouvelle affectation vers ressource dispo."""

    def setUp(self):
        self.co = make_company('gp-z4-creat', 'S')
        self.projet = Projet.objects.create(company=self.co, code='P-Z4', nom='P')
        self.ressource = RessourceProfil.objects.create(
            company=self.co, nom='R1', actif=True)
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Sans affect',
            ordre=1,
            date_debut_prevue=date(2026, 6, 1),
            date_fin_prevue=date(2026, 6, 3))

    def test_simulation_ne_mute_rien(self):
        resultat = services.auto_affecter(
            self.co, date(2026, 6, 1), date(2026, 6, 5), confirmer=False)
        self.assertTrue(resultat['simule'])
        self.assertEqual(len(resultat['creations']), 1)
        self.assertFalse(
            AffectationRessource.objects.filter(tache=self.tache).exists())

    def test_confirmation_cree_affectation(self):
        resultat = services.auto_affecter(
            self.co, date(2026, 6, 1), date(2026, 6, 5), confirmer=True)
        self.assertFalse(resultat['simule'])
        self.assertEqual(len(resultat['creations']), 1)
        aff = AffectationRessource.objects.get(tache=self.tache)
        self.assertEqual(aff.ressource_id, self.ressource.id)
        self.assertEqual(
            aff.statut_publication,
            AffectationRessource.StatutPublication.BROUILLON)

    def test_tache_sans_candidat_rapportee(self):
        Indisponibilite.objects.create(
            company=self.co, ressource=self.ressource,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 3),
            type_indispo='conge')
        resultat = services.auto_affecter(
            self.co, date(2026, 6, 1), date(2026, 6, 5), confirmer=False)
        self.assertEqual(len(resultat['creations']), 0)
        self.assertEqual(len(resultat['non_resolues']), 1)
        self.assertEqual(resultat['non_resolues'][0]['tache'], self.tache.id)

    def test_tache_sans_dates_ignoree(self):
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Sans dates',
            ordre=2)
        resultat = services.auto_affecter(
            self.co, date(2026, 6, 1), date(2026, 6, 5), confirmer=False)
        # Seule la tâche datée (self.tache) est candidate.
        self.assertEqual(len(resultat['creations']), 1)


class AutoAffecterDeplacementTests(TestCase):
    """Ressource sur-chargée -> déplacement vers sous-chargée (nivellement)."""

    def setUp(self):
        self.co = make_company('gp-z4-depl', 'S')
        self.projet = Projet.objects.create(company=self.co, code='P-Z4D', nom='P')
        self.surchargee = RessourceProfil.objects.create(
            company=self.co, nom='Surchargée', actif=True)
        self.souschargee = RessourceProfil.objects.create(
            company=self.co, nom='Sous-chargée', actif=True)
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T', ordre=1)
        # Charge énorme sur la ressource sur-chargée (semaine complète,
        # charge_jours largement > capacité).
        self.aff = AffectationRessource.objects.create(
            company=self.co, tache=self.tache, ressource=self.surchargee,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 5),
            charge_jours=Decimal('20'))

    def test_simulation_propose_deplacement_sans_muter(self):
        resultat = services.auto_affecter(
            self.co, date(2026, 6, 1), date(2026, 6, 5), confirmer=False)
        self.assertTrue(resultat['simule'])
        self.assertEqual(len(resultat['deplacements']), 1)
        self.aff.refresh_from_db()
        self.assertEqual(self.aff.ressource_id, self.surchargee.id)

    def test_confirmation_deplace_vers_sous_chargee(self):
        resultat = services.auto_affecter(
            self.co, date(2026, 6, 1), date(2026, 6, 5), confirmer=True)
        self.assertEqual(len(resultat['deplacements']), 1)
        self.aff.refresh_from_db()
        self.assertEqual(self.aff.ressource_id, self.souschargee.id)
        self.assertEqual(
            self.aff.statut_publication,
            AffectationRessource.StatutPublication.BROUILLON)


class AutoAffecterApiTests(TestCase):
    BASE = '/api/django/gestion-projet/affectations/auto-affecter/'

    def setUp(self):
        self.co_a = make_company('gp-z4-a', 'A')
        self.co_b = make_company('gp-z4-b', 'B')
        self.user_a = make_user(self.co_a, 'z4-api-a')
        self.user_b = make_user(self.co_b, 'z4-api-b')
        self.projet = Projet.objects.create(company=self.co_a, code='P-Z4A', nom='A')
        self.ressource = RessourceProfil.objects.create(
            company=self.co_a, nom='R', actif=True)
        self.tache = Tache.objects.create(
            company=self.co_a, projet=self.projet, libelle='T', ordre=1,
            date_debut_prevue=date(2026, 6, 1),
            date_fin_prevue=date(2026, 6, 2))

    def test_defaut_simule(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'debut': '2026-06-01', 'fin': '2026-06-05',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['simule'])
        self.assertFalse(
            AffectationRessource.objects.filter(tache=self.tache).exists())

    def test_confirm_applique(self):
        api = auth(self.user_a)
        resp = api.post(
            f'{self.BASE}?confirm=1',
            {'debut': '2026-06-01', 'fin': '2026-06-05'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['simule'])
        self.assertTrue(
            AffectationRessource.objects.filter(tache=self.tache).exists())

    def test_dates_manquantes_400(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_tenant(self):
        api = auth(self.user_b)
        resp = api.post(
            f'{self.BASE}?confirm=1',
            {'debut': '2026-06-01', 'fin': '2026-06-05'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            AffectationRessource.objects.filter(
                tache=self.tache).exists())

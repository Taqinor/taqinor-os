"""Tests du cycle brouillon -> publié + notification (ZPRJ2).

Couvre : publication d'un lot par ``ids`` passe le statut + horodate serveur +
notifie une fois par ressource ; publication par ``ressource``+période ;
ré-exécution idempotente (déjà publié ignoré, jamais renotifié) ; ressource
sans compte utilisateur ignorée proprement côté notification ; isolation
tenant ; ``plan_de_charge`` expose le statut de publication par affectation.
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors, services
from apps.gestion_projet.models import (
    AffectationRessource, Projet, RessourceProfil, Tache,
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


class PublierAffectationsServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-z2-svc', 'S')
        self.owner = make_user(self.co, 'z2-svc-owner')
        self.projet = Projet.objects.create(company=self.co, code='P-Z2', nom='P')
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T', ordre=1)
        self.ressource = RessourceProfil.objects.create(
            company=self.co, nom='R1', user=self.owner)
        self.aff = AffectationRessource.objects.create(
            company=self.co, tache=self.tache, ressource=self.ressource,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 5),
            charge_jours=Decimal('3'))

    @mock.patch('apps.notifications.services.notify')
    def test_publier_par_ids_passe_statut_et_notifie(self, mock_notify):
        resultat = services.publier_affectations(
            self.co, ids=[self.aff.id], auteur=self.owner)
        self.aff.refresh_from_db()
        self.assertEqual(
            self.aff.statut_publication,
            AffectationRessource.StatutPublication.PUBLIE)
        self.assertIsNotNone(self.aff.publie_le)
        self.assertEqual(self.aff.publie_par_id, self.owner.id)
        self.assertEqual(resultat['nb_publiees'], 1)
        self.assertEqual(resultat['nb_notifies'], 1)
        mock_notify.assert_called_once()

    @mock.patch('apps.notifications.services.notify')
    def test_reexecution_idempotente(self, mock_notify):
        services.publier_affectations(
            self.co, ids=[self.aff.id], auteur=self.owner)
        mock_notify.reset_mock()
        resultat = services.publier_affectations(
            self.co, ids=[self.aff.id], auteur=self.owner)
        self.assertEqual(resultat['nb_publiees'], 0)
        self.assertEqual(resultat['nb_deja_publiees'], 1)
        self.assertEqual(resultat['nb_notifies'], 0)
        mock_notify.assert_not_called()

    @mock.patch('apps.notifications.services.notify')
    def test_publier_par_ressource_et_periode(self, mock_notify):
        resultat = services.publier_affectations(
            self.co, ressource_id=self.ressource.id,
            debut=date(2026, 6, 1), fin=date(2026, 6, 5), auteur=self.owner)
        self.aff.refresh_from_db()
        self.assertEqual(
            self.aff.statut_publication,
            AffectationRessource.StatutPublication.PUBLIE)
        self.assertEqual(resultat['nb_publiees'], 1)

    @mock.patch('apps.notifications.services.notify')
    def test_une_notification_par_ressource_pas_par_affectation(
            self, mock_notify):
        aff2 = AffectationRessource.objects.create(
            company=self.co, tache=self.tache, ressource=self.ressource,
            date_debut=date(2026, 7, 1), date_fin=date(2026, 7, 5),
            charge_jours=Decimal('2'))
        resultat = services.publier_affectations(
            self.co, ids=[self.aff.id, aff2.id], auteur=self.owner)
        self.assertEqual(resultat['nb_publiees'], 2)
        self.assertEqual(resultat['nb_notifies'], 1)
        mock_notify.assert_called_once()

    @mock.patch('apps.notifications.services.notify')
    def test_ressource_sans_user_ignoree_proprement(self, mock_notify):
        ressource_sans_user = RessourceProfil.objects.create(
            company=self.co, nom='R2')
        aff = AffectationRessource.objects.create(
            company=self.co, tache=self.tache, ressource=ressource_sans_user,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 5))
        resultat = services.publier_affectations(
            self.co, ids=[aff.id], auteur=self.owner)
        self.assertEqual(resultat['nb_publiees'], 1)
        self.assertEqual(resultat['nb_notifies'], 0)
        mock_notify.assert_not_called()

    def test_sans_criteres_ne_publie_rien(self):
        resultat = services.publier_affectations(self.co, auteur=self.owner)
        self.assertEqual(resultat['nb_publiees'], 0)
        self.aff.refresh_from_db()
        self.assertEqual(
            self.aff.statut_publication,
            AffectationRessource.StatutPublication.BROUILLON)


class PublierAffectationsApiTests(TestCase):
    BASE = '/api/django/gestion-projet/affectations/publier/'

    def setUp(self):
        self.co_a = make_company('gp-z2-a', 'A')
        self.co_b = make_company('gp-z2-b', 'B')
        self.user_a = make_user(self.co_a, 'z2-api-a')
        self.user_b = make_user(self.co_b, 'z2-api-b')
        self.projet = Projet.objects.create(company=self.co_a, code='P-Z2A', nom='A')
        self.tache = Tache.objects.create(
            company=self.co_a, projet=self.projet, libelle='T', ordre=1)
        self.ressource = RessourceProfil.objects.create(
            company=self.co_a, nom='R', user=self.user_a)
        self.aff = AffectationRessource.objects.create(
            company=self.co_a, tache=self.tache, ressource=self.ressource,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 5))

    @mock.patch('apps.notifications.services.notify')
    def test_publier_endpoint(self, mock_notify):
        api = auth(self.user_a)
        resp = api.post(
            self.BASE, {'ids': [self.aff.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_publiees'], 1)

    def test_sans_criteres_400(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_tenant_autre_societe_ne_publie_rien(self):
        api = auth(self.user_b)
        resp = api.post(
            self.BASE, {'ids': [self.aff.id]}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['nb_publiees'], 0)
        self.aff.refresh_from_db()
        self.assertEqual(
            self.aff.statut_publication,
            AffectationRessource.StatutPublication.BROUILLON)


class PlanDeChargeExposePublicationTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-z2-plan', 'S')
        self.projet = Projet.objects.create(company=self.co, code='P-Z2P', nom='P')
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T', ordre=1)
        self.ressource = RessourceProfil.objects.create(
            company=self.co, nom='R', actif=True)
        self.aff = AffectationRessource.objects.create(
            company=self.co, tache=self.tache, ressource=self.ressource,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 5),
            charge_jours=Decimal('2'))

    def test_plan_de_charge_expose_statut_publication(self):
        data = selectors.plan_de_charge(
            self.co, date(2026, 6, 1), date(2026, 6, 5))
        ligne = next(
            ln for ln in data['lignes'] if ln['ressource'] == self.ressource.id)
        self.assertIn('affectations', ligne)
        self.assertEqual(len(ligne['affectations']), 1)
        self.assertEqual(
            ligne['affectations'][0]['statut_publication'], 'brouillon')

    def test_apres_publication_statut_expose_publie(self):
        services.publier_affectations(self.co, ids=[self.aff.id])
        data = selectors.plan_de_charge(
            self.co, date(2026, 6, 1), date(2026, 6, 5))
        ligne = next(
            ln for ln in data['lignes'] if ln['ressource'] == self.ressource.id)
        self.assertEqual(
            ligne['affectations'][0]['statut_publication'], 'publie')

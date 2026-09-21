"""Tests YHIRE14 — Approbation de réquisition avant ouverture au recrutement.

Cycle amont ``brouillon -> en_approbation -> ouvert`` sur ``OuverturePoste`` :
actions ``soumettre``/``approuver``/``refuser``, SoD (approbateur != demandeur),
et une ``Candidature`` sur une ouverture non OUVERTE est refusée (400).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import OuverturePoste

User = get_user_model()

OUVERTURES_URL = '/api/django/rh/ouvertures-poste/'
CANDIDATURES_URL = '/api/django/rh/candidatures/'


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


class ApprobationOuvertureTests(TestCase):
    def setUp(self):
        self.company = make_company('yh14-a', 'A')
        self.demandeur = make_user(self.company, 'yh14-demandeur')
        self.approbateur = make_user(self.company, 'yh14-approbateur')

    def test_defaut_creation_brouillon(self):
        ouverture = OuverturePoste.objects.create(
            company=self.company, intitule='Poseur solaire')
        self.assertEqual(ouverture.statut, OuverturePoste.Statut.BROUILLON)

    def test_cycle_brouillon_approbation_ouvert(self):
        ouverture = OuverturePoste.objects.create(
            company=self.company, intitule='Poseur solaire')
        resp = auth(self.demandeur).post(
            f'{OUVERTURES_URL}{ouverture.id}/soumettre/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ouverture.refresh_from_db()
        self.assertEqual(ouverture.statut, OuverturePoste.Statut.EN_APPROBATION)
        self.assertEqual(ouverture.demandeur_id, self.demandeur.id)

        resp2 = auth(self.approbateur).post(
            f'{OUVERTURES_URL}{ouverture.id}/approuver/')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        ouverture.refresh_from_db()
        self.assertEqual(ouverture.statut, OuverturePoste.Statut.OUVERT)
        self.assertEqual(ouverture.approbateur_id, self.approbateur.id)
        self.assertIsNotNone(ouverture.date_decision)

    def test_auto_approbation_refusee(self):
        ouverture = OuverturePoste.objects.create(
            company=self.company, intitule='Poseur solaire')
        services.soumettre_ouverture(ouverture, demandeur=self.demandeur)
        resp = auth(self.demandeur).post(
            f'{OUVERTURES_URL}{ouverture.id}/approuver/')
        self.assertEqual(resp.status_code, 400, resp.data)
        ouverture.refresh_from_db()
        self.assertEqual(ouverture.statut, OuverturePoste.Statut.EN_APPROBATION)

    def test_refus_ramene_brouillon_avec_motif(self):
        ouverture = OuverturePoste.objects.create(
            company=self.company, intitule='Poseur solaire')
        services.soumettre_ouverture(ouverture, demandeur=self.demandeur)
        resp = auth(self.approbateur).post(
            f'{OUVERTURES_URL}{ouverture.id}/refuser/',
            {'motif_refus': 'Budget non validé'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ouverture.refresh_from_db()
        self.assertEqual(ouverture.statut, OuverturePoste.Statut.BROUILLON)
        self.assertEqual(ouverture.motif_refus, 'Budget non validé')

    def test_auto_refus_refuse(self):
        ouverture = OuverturePoste.objects.create(
            company=self.company, intitule='Poseur solaire')
        services.soumettre_ouverture(ouverture, demandeur=self.demandeur)
        resp = auth(self.demandeur).post(
            f'{OUVERTURES_URL}{ouverture.id}/refuser/')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_candidature_sur_brouillon_refusee(self):
        ouverture = OuverturePoste.objects.create(
            company=self.company, intitule='Poseur solaire')
        resp = auth(self.demandeur).post(CANDIDATURES_URL, {
            'ouverture': ouverture.id, 'nom': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('ouverture', resp.data)

    def test_candidature_sur_ouvert_acceptee(self):
        ouverture = OuverturePoste.objects.create(
            company=self.company, intitule='Poseur solaire',
            statut=OuverturePoste.Statut.OUVERT)
        resp = auth(self.demandeur).post(CANDIDATURES_URL, {
            'ouverture': ouverture.id, 'nom': 'Y',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_donnees_existantes_intactes(self):
        # Une ouverture créée AVANT YHIRE14 (simulée : statut explicite
        # 'ouvert') reste ouverte, jamais rétrogradée par la migration.
        ouverture = OuverturePoste.objects.create(
            company=self.company, intitule='Ancienne ouverture',
            statut=OuverturePoste.Statut.OUVERT)
        self.assertEqual(ouverture.statut, OuverturePoste.Statut.OUVERT)

    def test_soumission_hors_brouillon_refusee(self):
        ouverture = OuverturePoste.objects.create(
            company=self.company, intitule='Poseur solaire',
            statut=OuverturePoste.Statut.OUVERT)
        resp = auth(self.demandeur).post(
            f'{OUVERTURES_URL}{ouverture.id}/soumettre/')
        self.assertEqual(resp.status_code, 400, resp.data)

"""NTPRO6 — Échéancier de loyers.

Couvre : un bail actif génère ses échéances sans doublon à chaque exécution,
montant_total = loyer + charges, et la commande de management idempotente.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.immobilier.models import (
    Bail, Batiment, EcheanceLoyer, Local, Locataire, Niveau, Site,
)
from apps.immobilier.services import creer_bail, generer_echeancier

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntpro6EcheancierTests(TestCase):
    def setUp(self):
        self.co_a = make_company('immo-ech-a', 'Immo Ech A')
        self.admin_a = make_user(self.co_a, 'immo-ech-admin-a')
        site = Site.objects.create(company=self.co_a, nom='Résidence')
        batiment = Batiment.objects.create(
            company=self.co_a, site=site, nom='Bât A')
        niveau = Niveau.objects.create(
            company=self.co_a, batiment=batiment, numero='RDC')
        local = Local.objects.create(
            company=self.co_a, niveau=niveau, reference='RDC-01')
        locataire = Locataire.objects.create(company=self.co_a, nom='Bennani')
        self.bail = creer_bail(
            company=self.co_a, local=local, locataire=locataire,
            type_bail=Bail.TypeBail.HABITATION, date_debut='2026-01-01',
            duree_mois=3, loyer_mensuel_ht=Decimal('3000.00'),
            charges_mensuelles_provisions=Decimal('200.00'))

    def test_generer_echeancier_cree_n_mois(self):
        creees = generer_echeancier(self.bail)
        self.assertEqual(len(creees), 3)
        self.assertEqual(
            EcheanceLoyer.objects.filter(bail=self.bail).count(), 3)
        premiere = EcheanceLoyer.objects.filter(bail=self.bail).earliest(
            'periode_debut')
        self.assertEqual(str(premiere.periode_debut), '2026-01-01')
        self.assertEqual(premiere.montant_total, Decimal('3200.00'))

    def test_generer_echeancier_idempotent(self):
        generer_echeancier(self.bail)
        creees_2 = generer_echeancier(self.bail)
        self.assertEqual(creees_2, [])
        self.assertEqual(
            EcheanceLoyer.objects.filter(bail=self.bail).count(), 3)

    def test_bail_non_actif_ne_genere_rien(self):
        self.bail.statut = Bail.Statut.BROUILLON
        self.bail.save(update_fields=['statut'])
        creees = generer_echeancier(self.bail)
        self.assertEqual(creees, [])

    def test_management_command_idempotent(self):
        call_command('generer_echeances_loyer', company=self.co_a.slug)
        self.assertEqual(
            EcheanceLoyer.objects.filter(bail=self.bail).count(), 3)
        call_command('generer_echeances_loyer', company=self.co_a.slug)
        self.assertEqual(
            EcheanceLoyer.objects.filter(bail=self.bail).count(), 3)

    def test_api_generer_echeancier_action(self):
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/immobilier/baux/{self.bail.id}/generer-echeancier/',
            {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data), 3)

    def test_api_echeances_loyer_create_forbidden(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/immobilier/echeances-loyer/', {
            'bail': self.bail.id, 'periode_debut': '2026-01-01',
            'periode_fin': '2026-01-31', 'montant_loyer_ht': '3000.00',
            'montant_total': '3000.00',
        }, format='json')
        self.assertEqual(resp.status_code, 405)

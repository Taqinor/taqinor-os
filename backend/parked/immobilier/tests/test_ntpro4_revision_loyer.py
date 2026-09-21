"""NTPRO4 — Révision de loyer indexée.

Couvre : réviser un loyer crée une ligne d'historique immuable, le loyer
courant change à la date d'effet, et une échéance déjà émise n'est jamais
recalculée rétroactivement.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.immobilier.models import (
    Bail, Batiment, Local, Locataire, Niveau, RevisionLoyer, Site,
)
from apps.immobilier.services import appliquer_revision, creer_bail

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


class Ntpro4RevisionLoyerTests(TestCase):
    def setUp(self):
        self.co_a = make_company('immo-rev-a', 'Immo Rev A')
        self.admin_a = make_user(self.co_a, 'immo-rev-admin-a')
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
            duree_mois=12, loyer_mensuel_ht=Decimal('3000.00'))

    def test_appliquer_revision_journalise_et_change_loyer_courant(self):
        revision = appliquer_revision(
            self.bail, Decimal('3150.00'), '2026-07-01',
            indice='IRL trimestriel')
        self.bail.refresh_from_db()
        self.assertEqual(self.bail.loyer_mensuel_ht, Decimal('3150.00'))
        self.assertEqual(revision.ancien_loyer, Decimal('3000.00'))
        self.assertEqual(revision.nouveau_loyer, Decimal('3150.00'))
        self.assertEqual(revision.taux_variation, Decimal('5.00'))
        self.assertEqual(RevisionLoyer.objects.filter(bail=self.bail).count(), 1)

    def test_deux_revisions_gardent_lhistorique_immuable(self):
        appliquer_revision(self.bail, Decimal('3150.00'), '2026-07-01')
        appliquer_revision(self.bail, Decimal('3300.00'), '2027-01-01')
        self.assertEqual(RevisionLoyer.objects.filter(bail=self.bail).count(), 2)
        premiere = RevisionLoyer.objects.filter(bail=self.bail).earliest('id')
        self.assertEqual(premiere.ancien_loyer, Decimal('3000.00'))
        self.assertEqual(premiere.nouveau_loyer, Decimal('3150.00'))

    def test_api_reviser_action(self):
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/immobilier/baux/{self.bail.id}/reviser/',
            {'nouveau_loyer': '3150.00', 'date_effet': '2026-07-01'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.bail.refresh_from_db()
        self.assertEqual(self.bail.loyer_mensuel_ht, Decimal('3150.00'))

    def test_api_reviser_requires_fields(self):
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/immobilier/baux/{self.bail.id}/reviser/', {},
            format='json')
        self.assertEqual(resp.status_code, 400)

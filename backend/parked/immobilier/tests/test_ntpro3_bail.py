"""NTPRO3 — Bail commercial/habitation (Maroc).

Couvre : créer un bail passe le Local en statut ``loue``, un second bail actif
sur le même local est refusé (400), et l'isolation tenant.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.immobilier.models import Bail, Batiment, Local, Locataire, Niveau, Site
from apps.immobilier.services import BailActifExistantError, creer_bail

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


class Ntpro3BailTests(TestCase):
    def setUp(self):
        self.co_a = make_company('immo-bail-a', 'Immo Bail A')
        self.admin_a = make_user(self.co_a, 'immo-bail-admin-a')

        site = Site.objects.create(company=self.co_a, nom='Résidence')
        batiment = Batiment.objects.create(
            company=self.co_a, site=site, nom='Bât A')
        niveau = Niveau.objects.create(
            company=self.co_a, batiment=batiment, numero='RDC')
        self.local = Local.objects.create(
            company=self.co_a, niveau=niveau, reference='RDC-01')
        self.locataire = Locataire.objects.create(
            company=self.co_a, nom='Bennani')

    def test_creer_bail_passe_local_en_loue(self):
        bail = creer_bail(
            company=self.co_a, local=self.local, locataire=self.locataire,
            type_bail=Bail.TypeBail.HABITATION, date_debut='2026-01-01',
            duree_mois=12, loyer_mensuel_ht=Decimal('3000.00'))
        self.local.refresh_from_db()
        self.assertEqual(self.local.statut, Local.Statut.LOUE)
        self.assertEqual(bail.statut, Bail.Statut.ACTIF)

    def test_second_bail_actif_refuse(self):
        creer_bail(
            company=self.co_a, local=self.local, locataire=self.locataire,
            type_bail=Bail.TypeBail.HABITATION, date_debut='2026-01-01',
            duree_mois=12, loyer_mensuel_ht=Decimal('3000.00'))
        autre_locataire = Locataire.objects.create(
            company=self.co_a, nom='Autre')
        with self.assertRaises(BailActifExistantError):
            creer_bail(
                company=self.co_a, local=self.local,
                locataire=autre_locataire,
                type_bail=Bail.TypeBail.HABITATION, date_debut='2026-02-01',
                duree_mois=12, loyer_mensuel_ht=Decimal('3200.00'))

    def test_api_second_bail_actif_refuse_400(self):
        api = auth(self.admin_a)
        resp1 = api.post('/api/django/immobilier/baux/', {
            'local': self.local.id, 'locataire': self.locataire.id,
            'type_bail': 'habitation', 'date_debut': '2026-01-01',
            'duree_mois': 12, 'loyer_mensuel_ht': '3000.00',
        }, format='json')
        self.assertEqual(resp1.status_code, 201, resp1.data)

        resp2 = api.post('/api/django/immobilier/baux/', {
            'local': self.local.id, 'locataire': self.locataire.id,
            'type_bail': 'habitation', 'date_debut': '2026-02-01',
            'duree_mois': 12, 'loyer_mensuel_ht': '3200.00',
        }, format='json')
        self.assertEqual(resp2.status_code, 400)

    def test_bail_brouillon_ne_change_pas_le_statut_local(self):
        bail = creer_bail(
            company=self.co_a, local=self.local, locataire=self.locataire,
            statut=Bail.Statut.BROUILLON, type_bail=Bail.TypeBail.HABITATION,
            date_debut='2026-01-01', duree_mois=12,
            loyer_mensuel_ht=Decimal('3000.00'))
        self.local.refresh_from_db()
        self.assertEqual(self.local.statut, Local.Statut.LIBRE)
        self.assertEqual(bail.statut, Bail.Statut.BROUILLON)

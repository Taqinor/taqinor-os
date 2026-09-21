"""NTPRO5 — Dépôt de garantie, cycle de vie.

Couvre : la restitution ne peut jamais excéder le dépôt initial, l'historique
horodaté est conservé (dates de réception/restitution).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.immobilier.models import Bail, Batiment, Local, Locataire, Niveau, Site
from apps.immobilier.services import (
    DepotGarantieError, creer_bail, encaisser_depot, montant_restitue_depot,
    restituer_depot,
)

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


class Ntpro5DepotGarantieTests(TestCase):
    def setUp(self):
        self.co_a = make_company('immo-depot-a', 'Immo Depot A')
        self.admin_a = make_user(self.co_a, 'immo-depot-admin-a')
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
            duree_mois=12, loyer_mensuel_ht=Decimal('3000.00'),
            depot_garantie=Decimal('6000.00'))

    def test_encaisser_depot_horodate(self):
        encaisser_depot(self.bail, date_reception='2026-01-05')
        self.bail.refresh_from_db()
        self.assertTrue(self.bail.depot_garantie_recu)
        self.assertEqual(str(self.bail.date_reception_depot), '2026-01-05')

    def test_restituer_depot_sans_retenue(self):
        encaisser_depot(self.bail, date_reception='2026-01-05')
        restituer_depot(self.bail, date_restitution='2027-01-05')
        self.bail.refresh_from_db()
        self.assertTrue(self.bail.depot_garantie_restitue)
        self.assertEqual(montant_restitue_depot(self.bail), Decimal('6000.00'))

    def test_restitution_avec_retenue_justifiee(self):
        encaisser_depot(self.bail)
        restituer_depot(
            self.bail, montant_retenu=Decimal('1500.00'),
            motif_retenue='Réparations peinture')
        self.bail.refresh_from_db()
        self.assertEqual(montant_restitue_depot(self.bail), Decimal('4500.00'))
        self.assertEqual(self.bail.motif_retenue, 'Réparations peinture')

    def test_retenue_superieure_au_depot_refusee(self):
        encaisser_depot(self.bail)
        with self.assertRaises(DepotGarantieError):
            restituer_depot(self.bail, montant_retenu=Decimal('9000.00'))

    def test_montant_restitue_jamais_negatif(self):
        # Retenue exactement égale au dépôt → restitution nulle, jamais négative.
        encaisser_depot(self.bail)
        restituer_depot(self.bail, montant_retenu=Decimal('6000.00'))
        self.assertEqual(montant_restitue_depot(self.bail), Decimal('0'))

    def test_api_restituer_depot_refuse_retenue_excessive(self):
        api = auth(self.admin_a)
        api.post(
            f'/api/django/immobilier/baux/{self.bail.id}/encaisser-depot/',
            {}, format='json')
        resp = api.post(
            f'/api/django/immobilier/baux/{self.bail.id}/restituer-depot/',
            {'montant_retenu': '9000.00'}, format='json')
        self.assertEqual(resp.status_code, 400)

"""NTPRO9 — Rentabilité par actif (loyers vs charges vs travaux).

Couvre : le calcul dégrade proprement si aucun chantier lié (marge = revenus
- charges), pas d'exposition de prix d'achat produit, et l'agrégation
site/bâtiment.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.immobilier.models import (
    Bail, Batiment, EcheanceLoyer, Local, Locataire, Niveau, Site,
)
from apps.immobilier.selectors import rentabilite_actif
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


class Ntpro9RentabiliteTests(TestCase):
    def setUp(self):
        self.co_a = make_company('immo-rent-a', 'Immo Rent A')
        self.admin_a = make_user(self.co_a, 'immo-rent-admin-a')
        self.site = Site.objects.create(company=self.co_a, nom='Résidence')
        self.batiment = Batiment.objects.create(
            company=self.co_a, site=self.site, nom='Bât A')
        niveau = Niveau.objects.create(
            company=self.co_a, batiment=self.batiment, numero='RDC')
        self.local_loue = Local.objects.create(
            company=self.co_a, niveau=niveau, reference='RDC-01')
        self.local_libre = Local.objects.create(
            company=self.co_a, niveau=niveau, reference='RDC-02')
        locataire = Locataire.objects.create(company=self.co_a, nom='Bennani')
        bail = creer_bail(
            company=self.co_a, local=self.local_loue, locataire=locataire,
            type_bail=Bail.TypeBail.HABITATION, date_debut=date(2026, 1, 1),
            duree_mois=1, loyer_mensuel_ht=Decimal('3000.00'))
        generer_echeancier(bail)
        echeance = EcheanceLoyer.objects.get(bail=bail)
        echeance.statut = EcheanceLoyer.Statut.EMISE
        echeance.facture_ventes_id = 555
        echeance.save(update_fields=['statut', 'facture_ventes_id'])

    def test_rentabilite_site_degrade_sans_chantier(self):
        data = rentabilite_actif(self.co_a, site_id=self.site.id)
        self.assertEqual(data['total_locaux'], 2)
        self.assertEqual(data['locaux_loues'], 1)
        self.assertEqual(data['taux_occupation'], Decimal('50'))
        self.assertEqual(data['revenus'], Decimal('3000.00'))
        self.assertEqual(data['charges'], Decimal('0'))
        self.assertEqual(data['travaux'], Decimal('0'))
        self.assertEqual(data['marge_nette'], Decimal('3000.00'))
        self.assertEqual(len(data['par_local']), 2)

    def test_rentabilite_batiment_meme_calcul(self):
        data = rentabilite_actif(self.co_a, batiment_id=self.batiment.id)
        self.assertEqual(data['revenus'], Decimal('3000.00'))
        self.assertEqual(data['marge_nette'], Decimal('3000.00'))

    def test_rentabilite_requiert_un_identifiant(self):
        with self.assertRaises(ValueError):
            rentabilite_actif(self.co_a)

    def test_rentabilite_ne_expose_aucun_prix_achat(self):
        data = rentabilite_actif(self.co_a, site_id=self.site.id)
        serialise = str(data)
        self.assertNotIn('prix_achat', serialise)

    def test_api_site_rentabilite(self):
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/immobilier/sites/{self.site.id}/rentabilite/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total_locaux'], 2)

    def test_api_batiment_rentabilite(self):
        api = auth(self.admin_a)
        resp = api.get(
            f'/api/django/immobilier/batiments/{self.batiment.id}/rentabilite/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['locaux_loues'], 1)

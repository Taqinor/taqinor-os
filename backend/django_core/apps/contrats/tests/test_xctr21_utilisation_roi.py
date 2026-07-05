"""Tests XCTR21 — Utilisation & ROI du parc de location.

Couvre : taux d'utilisation exact sur un jeu de test (bornage des périodes
chevauchantes), payback admin-only (403 pour les autres rôles), matériel
dormant identifié.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors, services
from apps.crm.models import Client
from apps.stock.models import Produit

User = get_user_model()

BASE = '/api/django/contrats/ordres-location/'


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


def make_produit(company, **kwargs):
    return Produit.objects.create(
        company=company, nom=kwargs.pop('nom', 'Nacelle'),
        prix_vente=Decimal('100'), louable=True,
        prix_achat=kwargs.pop('prix_achat', Decimal('10000')),
        tarif_location_jour=Decimal('100'), **kwargs)


def make_client(company, nom='Client X'):
    return Client.objects.create(company=company, nom=nom)


class UtilisationSelectorTests(TestCase):
    def setUp(self):
        self.company = make_company('xctr21-sel', 'Sel')
        self.client_obj = make_client(self.company)
        self.produit = make_produit(self.company)
        self.produit_dormant = make_produit(
            self.company, nom='Groupe dormant', prix_achat=Decimal('5000'))

    def test_taux_utilisation_borne_a_la_periode(self):
        # Location du 15 au 25 janvier — la période analysée est tout janvier
        # (31 jours) : 11 jours loués bornés dans la période.
        services.creer_ordre_location(
            self.company, client_id=self.client_obj.id, produit=self.produit,
            date_reservation=date(2026, 1, 10),
            date_enlevement_prevue=date(2026, 1, 15),
            date_retour_prevue=date(2026, 1, 25),
        )
        rows = selectors.utilisation_parc_location(
            self.company, periode_debut=date(2026, 1, 1),
            periode_fin=date(2026, 1, 31))
        row = next(r for r in rows if r['produit_id'] == self.produit.id)
        self.assertEqual(row['jours_disponibles'], 31)
        self.assertEqual(row['jours_loues'], 11)
        self.assertAlmostEqual(
            float(row['taux_utilisation']), 11 / 31, places=6)
        self.assertFalse(row['dormant'])

    def test_chevauchement_partiel_hors_periode_borne(self):
        # Location qui commence AVANT la période et finit APRÈS.
        services.creer_ordre_location(
            self.company, client_id=self.client_obj.id, produit=self.produit,
            date_reservation=date(2025, 12, 20),
            date_enlevement_prevue=date(2025, 12, 25),
            date_retour_prevue=date(2026, 1, 10),
        )
        rows = selectors.utilisation_parc_location(
            self.company, periode_debut=date(2026, 1, 1),
            periode_fin=date(2026, 1, 31))
        row = next(r for r in rows if r['produit_id'] == self.produit.id)
        # Seuls les 10 premiers jours de janvier comptent (1er -> 10 janvier).
        self.assertEqual(row['jours_loues'], 10)

    def test_materiel_dormant_sans_ordre_absent(self):
        rows = selectors.utilisation_parc_location(
            self.company, periode_debut=date(2026, 1, 1),
            periode_fin=date(2026, 1, 31))
        # Aucun ordre créé pour produit_dormant -> il n'apparaît pas (jamais
        # loué du tout, distinct d'un produit avec un ordre à 0 jour dans la
        # fenêtre analysée).
        ids = {r['produit_id'] for r in rows}
        self.assertNotIn(self.produit_dormant.id, ids)

    def test_ordre_annule_exclu(self):
        from apps.contrats.models import OrdreLocation

        ordre = services.creer_ordre_location(
            self.company, client_id=self.client_obj.id, produit=self.produit,
            date_reservation=date(2026, 1, 1),
            date_enlevement_prevue=date(2026, 1, 5),
            date_retour_prevue=date(2026, 1, 9),
        )
        services.changer_statut_ordre_location(
            ordre, OrdreLocation.Statut.ANNULEE)
        rows = selectors.utilisation_parc_location(
            self.company, periode_debut=date(2026, 1, 1),
            periode_fin=date(2026, 1, 31))
        ids = {r['produit_id'] for r in rows}
        self.assertNotIn(self.produit.id, ids)

    def test_payback_calcule_avec_admin_true(self):
        services.creer_ordre_location(
            self.company, client_id=self.client_obj.id, produit=self.produit,
            date_reservation=date(2026, 1, 1),
            date_enlevement_prevue=date(2026, 1, 1),
            date_retour_prevue=date(2026, 1, 10),
        )
        rows = selectors.utilisation_parc_location(
            self.company, periode_debut=date(2026, 1, 1),
            periode_fin=date(2026, 1, 31), admin=True)
        row = next(r for r in rows if r['produit_id'] == self.produit.id)
        self.assertIn('prix_achat', row)
        self.assertIn('payback', row)

    def test_payback_absent_sans_admin(self):
        services.creer_ordre_location(
            self.company, client_id=self.client_obj.id, produit=self.produit,
            date_reservation=date(2026, 1, 1),
            date_enlevement_prevue=date(2026, 1, 1),
            date_retour_prevue=date(2026, 1, 10),
        )
        rows = selectors.utilisation_parc_location(
            self.company, periode_debut=date(2026, 1, 1),
            periode_fin=date(2026, 1, 31), admin=False)
        row = next(r for r in rows if r['produit_id'] == self.produit.id)
        self.assertNotIn('prix_achat', row)
        self.assertNotIn('payback', row)


class UtilisationApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xctr21-api', 'Api')
        self.admin = make_user(self.company, 'xctr21-admin', role='admin')
        self.responsable = make_user(
            self.company, 'xctr21-resp', role='responsable')
        self.client_obj = make_client(self.company)
        self.produit = make_produit(self.company)
        services.creer_ordre_location(
            self.company, client_id=self.client_obj.id, produit=self.produit,
            date_reservation=date(2026, 2, 1),
            date_enlevement_prevue=date(2026, 2, 1),
            date_retour_prevue=date(2026, 2, 10),
        )

    def test_admin_voit_le_rapport(self):
        api = auth(self.admin)
        resp = api.get(f'{BASE}utilisation/?periode=2026-02')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(len(resp.data['results']) >= 1)
        self.assertIn('payback', resp.data['results'][0])

    def test_responsable_403(self):
        api = auth(self.responsable)
        resp = api.get(f'{BASE}utilisation/?periode=2026-02')
        self.assertEqual(resp.status_code, 403)

"""Tests XACC33 — "Immobiliser" une ligne de facture fournisseur (capitalisation).

Couvre : immobiliser une ligne crée l'actif au bon coût avec la pièce
référencée et son plan d'amortissement, re-cliquer -> 400 (anti-doublon),
ligne cross-company -> 404, tests.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import Immobilisation
from apps.stock.models import FactureFournisseur, Fournisseur

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


def make_facture_avec_ligne(company, *, montant_ht=Decimal('50000'),
                            taux_tva=Decimal('20'),
                            date_facture=date(2026, 6, 1)):
    fournisseur = Fournisseur.objects.create(
        company=company, nom='Fournisseur Capitalisation')
    facture = FactureFournisseur.objects.create(
        company=company, reference='FF-XACC33-1', fournisseur=fournisseur,
        date_facture=date_facture,
        montant_ht=montant_ht, montant_tva=montant_ht * taux_tva / 100,
        montant_ttc=montant_ht * (1 + taux_tva / 100))
    ligne = facture.lignes.create(
        designation='Groupe électrogène', quantite=1,
        prix_unitaire_ht=montant_ht, taux_tva=taux_tva)
    return facture, ligne


class CapitalisationServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc33-svc', 'XACC33 Svc')
        self.user = make_user(self.co, 'xacc33-svc-user')

    def test_capitalise_cree_immo_au_bon_cout_avec_plan(self):
        facture, ligne = make_facture_avec_ligne(
            self.co, montant_ht=Decimal('50000'))
        immo = services.capitaliser_ligne_facture_fournisseur(
            self.co, facture_id=facture.id, ligne_id=ligne.id,
            duree_annees=5, user=self.user)
        self.assertEqual(immo.cout, Decimal('50000.00'))
        self.assertEqual(immo.libelle, 'Groupe électrogène')
        self.assertEqual(
            immo.piece_origine_facture_fournisseur_id, facture.id)
        self.assertEqual(
            immo.piece_origine_ligne_facture_fournisseur_id, ligne.id)
        # Un plan d'amortissement existe pour cette immo (créé en un geste).
        from apps.compta.models import PlanAmortissement
        plan = PlanAmortissement.objects.filter(immobilisation=immo).first()
        self.assertIsNotNone(plan)
        self.assertEqual(plan.duree_annees, 5)

    def test_recapitaliser_meme_ligne_refuse(self):
        facture, ligne = make_facture_avec_ligne(self.co)
        services.capitaliser_ligne_facture_fournisseur(
            self.co, facture_id=facture.id, ligne_id=ligne.id, user=self.user)
        with self.assertRaises(Exception):
            services.capitaliser_ligne_facture_fournisseur(
                self.co, facture_id=facture.id, ligne_id=ligne.id,
                user=self.user)
        self.assertEqual(
            Immobilisation.objects.filter(
                piece_origine_ligne_facture_fournisseur_id=ligne.id).count(),
            1)

    def test_ligne_cross_company_leve_erreur(self):
        autre_co = make_company('xacc33-autre', 'XACC33 Autre')
        facture, ligne = make_facture_avec_ligne(autre_co)
        with self.assertRaises(Exception):
            services.capitaliser_ligne_facture_fournisseur(
                self.co, facture_id=facture.id, ligne_id=ligne.id,
                user=self.user)


class CapitalisationApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('xacc33-a', 'XACC33 A')
        self.co_b = make_company('xacc33-b', 'XACC33 B')
        self.user_a = make_user(self.co_a, 'xacc33-user-a')

    def test_endpoint_cree_immobilisation(self):
        facture, ligne = make_facture_avec_ligne(self.co_a)
        resp = auth(self.user_a).post(
            '/api/django/compta/immobilisations/depuis-facture-fournisseur/',
            {'facture_id': facture.id, 'ligne_id': ligne.id, 'duree': 5},
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Decimal(str(resp.data['cout'])), Decimal('50000.00'))

    def test_recliquer_400(self):
        facture, ligne = make_facture_avec_ligne(self.co_a)
        auth(self.user_a).post(
            '/api/django/compta/immobilisations/depuis-facture-fournisseur/',
            {'facture_id': facture.id, 'ligne_id': ligne.id}, format='json')
        resp = auth(self.user_a).post(
            '/api/django/compta/immobilisations/depuis-facture-fournisseur/',
            {'facture_id': facture.id, 'ligne_id': ligne.id}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_ligne_cross_company_404(self):
        facture, ligne = make_facture_avec_ligne(self.co_b)
        resp = auth(self.user_a).post(
            '/api/django/compta/immobilisations/depuis-facture-fournisseur/',
            {'facture_id': facture.id, 'ligne_id': ligne.id}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_champs_obligatoires_400(self):
        resp = auth(self.user_a).post(
            '/api/django/compta/immobilisations/depuis-facture-fournisseur/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400)

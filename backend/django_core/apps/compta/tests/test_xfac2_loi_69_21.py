"""Tests XFAC2 — Conformité loi 69-21 (délais de paiement légaux fournisseurs).

Couvre :
  * ``stock.selectors.exposition_69_21`` (calcul pur) et son wrapper
    ``compta.selectors.exposition_69_21`` (company-scopé) ;
  * limites 60/120 jours, délai fournisseur configuré (XPUR6) vs défaut légal ;
  * une facture payée (solde_du == 0) est exclue ;
  * l'endpoint ``etats/loi-69-21/`` (JSON + ``?export=csv``), scoping société.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import selectors as compta_selectors
from apps.stock import selectors as stock_selectors
from apps.stock.models import FactureFournisseur, Fournisseur

User = get_user_model()


def make_company(slug='xfac2-co', nom='XFAC2 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestExpositionSelector(TestCase):
    def setUp(self):
        self.company = make_company()
        self.today = timezone.localdate()

    def _facture(self, fournisseur, jours_avant, ttc='10000'):
        return FactureFournisseur.objects.create(
            company=self.company, reference=f'FF-{fournisseur.nom}',
            fournisseur=fournisseur,
            date_facture=self.today - timedelta(days=jours_avant),
            montant_ht=Decimal('8333.33'), montant_tva=Decimal('1666.67'),
            montant_ttc=Decimal(ttc))

    def test_facture_en_depassement_defaut_60j(self):
        f = Fournisseur.objects.create(company=self.company, nom='SansDelai')
        facture = self._facture(f, jours_avant=90)
        lignes = stock_selectors.exposition_69_21(self.company)
        self.assertEqual(len(lignes), 1)
        ligne = lignes[0]
        self.assertEqual(ligne['facture_id'], facture.id)
        self.assertEqual(ligne['delai_legal_jours'], 60)
        self.assertEqual(ligne['jours_depassement'], 30)
        self.assertGreater(ligne['amende_estimee'], Decimal('0'))

    def test_facture_dans_les_60_jours_absente(self):
        f = Fournisseur.objects.create(company=self.company, nom='SansDelai2')
        self._facture(f, jours_avant=30)
        lignes = stock_selectors.exposition_69_21(self.company)
        self.assertEqual(lignes, [])

    def test_delai_fournisseur_convenu_borne_a_120(self):
        f = Fournisseur.objects.create(
            company=self.company, nom='Convenu150', delai_paiement_jours=150)
        facture = self._facture(f, jours_avant=130)
        lignes = stock_selectors.exposition_69_21(self.company)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['delai_legal_jours'], 120)
        self.assertEqual(lignes[0]['facture_id'], facture.id)

    def test_facture_payee_exclue(self):
        f = Fournisseur.objects.create(company=self.company, nom='Payee')
        facture = self._facture(f, jours_avant=90)
        from apps.stock.models import PaiementFournisseur
        PaiementFournisseur.objects.create(
            company=self.company, facture=facture, montant=Decimal('10000'),
            date_paiement=self.today, mode='virement')
        lignes = stock_selectors.exposition_69_21(self.company)
        self.assertEqual(lignes, [])

    def test_periode_filtre_par_trimestre(self):
        f = Fournisseur.objects.create(company=self.company, nom='Q1')
        # Facture datée en janvier, très en retard (>60j) — dans le
        # trimestre 2026-01/02/03.
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-Q1', fournisseur=f,
            date_facture=date(2026, 1, 5),
            montant_ht=Decimal('8333.33'), montant_tva=Decimal('1666.67'),
            montant_ttc=Decimal('10000'))
        lignes = stock_selectors.exposition_69_21(
            self.company, periode='2026-02')
        ids = [ligne['facture_id'] for ligne in lignes]
        self.assertIn(facture.id, ids)
        lignes_hors_trimestre = stock_selectors.exposition_69_21(
            self.company, periode='2026-07')
        ids_hors = [ligne['facture_id'] for ligne in lignes_hors_trimestre]
        self.assertNotIn(facture.id, ids_hors)

    def test_wrapper_compta_total_amende(self):
        f = Fournisseur.objects.create(company=self.company, nom='Wrapper')
        self._facture(f, jours_avant=90)
        rapport = compta_selectors.exposition_69_21(self.company)
        self.assertEqual(len(rapport['lignes']), 1)
        self.assertEqual(
            rapport['total_amende_estimee'],
            rapport['lignes'][0]['amende_estimee'])

    def test_scoping_societe(self):
        autre = make_company('xfac2-autre', 'Autre Co')
        f_autre = Fournisseur.objects.create(company=autre, nom='AutreFourn')
        FactureFournisseur.objects.create(
            company=autre, reference='FF-AUTRE', fournisseur=f_autre,
            date_facture=self.today - timedelta(days=90),
            montant_ht=Decimal('8333.33'), montant_tva=Decimal('1666.67'),
            montant_ttc=Decimal('10000'))
        lignes = stock_selectors.exposition_69_21(self.company)
        self.assertEqual(lignes, [])


class TestEndpoint(TestCase):
    def setUp(self):
        self.company = make_company('xfac2-api-co', 'XFAC2 API Co')
        self.user = make_user(self.company, 'xfac2-admin', role='admin')
        self.api = auth(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='API Fourn')
        self.facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-API-0001',
            fournisseur=self.fournisseur,
            date_facture=timezone.localdate() - timedelta(days=90),
            montant_ht=Decimal('8333.33'), montant_tva=Decimal('1666.67'),
            montant_ttc=Decimal('10000'))

    def test_endpoint_json(self):
        resp = self.api.get('/api/django/compta/etats/loi-69-21/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['lignes']), 1)
        self.assertEqual(resp.data['lignes'][0]['facture_id'], self.facture.id)

    def test_endpoint_csv_export(self):
        resp = self.api.get('/api/django/compta/etats/loi-69-21/?export=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn(b'FF-API-0001', resp.content)

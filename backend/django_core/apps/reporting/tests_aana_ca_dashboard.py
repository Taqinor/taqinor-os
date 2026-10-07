"""AANA20 (C-AANA-020, D-AANA-6) — le CA du tableau de bord vient de
``Facture.total_ht`` et la créance de ``Facture.montant_du`` (TTC).

Scénario R2 : facture émise, une ligne 1×1000, ``remise_globale=50`` (%).
Avant le correctif : ``total_ht=500`` mais ``ca_attente=1000`` et créance
1000 (somme de lignes brute, remise ignorée, HT présenté comme dû).

Données RÉELLES en base, propriétés RÉELLES du modèle (aucun mock).
Rétablir l'ancien ``_ca_factures`` (somme de lignes) rougit ces tests.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.reporting.kpi_alertes import _resolve_representative_user
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, Paiement
from authentication.models import Company

User = get_user_model()

URL = '/api/django/reporting/dashboard/'


class TestCaDashboard(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aana20-co', defaults={'nom': 'AANA20 Co'})[0]
        self.user = User.objects.create_user(
            username='aana20_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cli R2')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit', sku='AANA20-P',
            prix_vente=Decimal('1000'), quantite_stock=0)

    def _facture(self, reference, statut, remise_globale=Decimal('0')):
        facture = Facture.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut=statut, remise_globale=remise_globale)
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Kit',
            quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'))
        return facture

    def test_remise_globale_appliquee(self):
        facture = self._facture('FAC-AANA20-1', Facture.Statut.EMISE,
                                remise_globale=Decimal('50'))
        self.assertEqual(facture.total_ht, Decimal('500.00'))

        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        # CA en attente = total_ht (remise globale honorée), pas 1000.
        self.assertEqual(resp.data['kpis']['ca_attente'], 500.0)
        # Créance = montant_du (TTC restant dû), pas une somme HT de lignes.
        self.assertEqual(len(resp.data['creances']), 1)
        self.assertEqual(resp.data['creances'][0]['montant_total'],
                         float(facture.montant_du))
        self.assertNotEqual(resp.data['creances'][0]['montant_total'], 1000.0)

    def test_creance_deduit_paiements(self):
        facture = self._facture('FAC-AANA20-2', Facture.Statut.EMISE)
        Paiement.objects.create(
            company=self.company, facture=facture, client=self.client_obj,
            montant=Decimal('200'), date_paiement=date.today(),
            mode=Paiement.Mode.VIREMENT)
        Facture.objects.filter(pk=facture.pk).update(
            statut=Facture.Statut.EMISE)
        facture.refresh_from_db()
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['creances'][0]['montant_total'],
                         float(facture.montant_du))
        self.assertEqual(float(facture.montant_du),
                         float(facture.total_ttc) - 200.0)

    def test_payee_avec_reliquat_pas_encaissee_pour_le_reliquat(self):
        facture = self._facture('FAC-AANA20-3', Facture.Statut.PAYEE)
        moitie = (Decimal(facture.total_ttc) / 2).quantize(Decimal('0.01'))
        Paiement.objects.create(
            company=self.company, facture=facture, client=self.client_obj,
            montant=moitie, date_paiement=date.today(),
            mode=Paiement.Mode.VIREMENT)
        # État testé : statut « payée » malgré un reliquat (saisie manuelle).
        Facture.objects.filter(pk=facture.pk).update(
            statut=Facture.Statut.PAYEE)
        facture.refresh_from_db()
        self.assertGreater(facture.montant_du, 0)

        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        kpis = resp.data['kpis']
        # Seule la moitié du HT est encaissée ; l'autre moitié reste en attente.
        self.assertAlmostEqual(kpis['ca_paye'], 500.0, places=1)
        self.assertAlmostEqual(kpis['ca_attente'], 500.0, places=1)
        self.assertAlmostEqual(kpis['ca_paye'] + kpis['ca_attente'],
                               float(facture.total_ht), places=2)
        # Le CA mensuel lit la même base (encaissé HT).
        self.assertAlmostEqual(resp.data['ca_mensuel'][-1]['ca'], 500.0,
                               places=1)


class TestUtilisateurDeCalculKpi(TestCase):
    """AANA20 — l'encours échu se calcule au nom d'un admin/responsable,
    jamais du premier utilisateur venu (portée « ses enregistrements »)."""

    def test_admin_prefere_au_premier_utilisateur(self):
        company = Company.objects.get_or_create(
            slug='aana20-kpi', defaults={'nom': 'AANA20 KPI'})[0]
        User.objects.create_user(
            username='aana20_normal', password='x', role_legacy='normal',
            company=company)
        admin = User.objects.create_user(
            username='aana20_admin', password='x', role_legacy='admin',
            company=company)
        self.assertEqual(_resolve_representative_user(company), admin)

    def test_aucun_admin_ni_responsable(self):
        company = Company.objects.get_or_create(
            slug='aana20-kpi2', defaults={'nom': 'AANA20 KPI 2'})[0]
        User.objects.create_user(
            username='aana20_normal2', password='x', role_legacy='normal',
            company=company)
        self.assertIsNone(_resolve_representative_user(company))

"""NTDATA1 — datasets BI ventes (devis / factures / paiements).

Couvre :
  * les trois datasets sont enregistrés (via `apps.py` ready()) ;
  * le queryset est scopé société (aucune fuite cross-tenant) ;
  * un group-by statut renvoie des lignes ;
  * `market_mode` / `canal` / `kwc` sont exploitables ;
  * `kwc` reste VIDE (jamais une erreur) sur un `etude_params` non numérique ;
  * `reste_du` d'une facture tient compte des paiements encaissés ;
  * aucune marge / aucun `prix_achat` dans la liste blanche.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.ventes.bi_datasets import (
    DEVIS_DATASET, DEVIS_FIELDS, FACTURES_DATASET, PAIEMENTS_DATASET,
)
from apps.ventes.models import Devis, Facture, Paiement
from authentication.models import Company
from core import data_explorer

User = get_user_model()


class VentesBiDatasetsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='ntdata1-co', defaults={'nom': 'NTDATA1 Co'})[0]
        self.autre = Company.objects.get_or_create(
            slug='ntdata1-autre', defaults={'nom': 'NTDATA1 Autre'})[0]
        self.user = User.objects.create_user(
            username='ntdata1_u', password='x', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='ClientNTDATA1')

    # ── enregistrement ─────────────────────────────────────────────────────
    def test_les_trois_datasets_sont_enregistres(self):
        noms = {d['name'] for d in data_explorer.list_datasets()}
        self.assertIn(DEVIS_DATASET, noms)
        self.assertIn(FACTURES_DATASET, noms)
        self.assertIn(PAIEMENTS_DATASET, noms)

    def test_aucun_champ_de_marge_ni_prix_achat(self):
        interdits = {'marge_snapshot', 'prix_achat', 'marge', 'cout_achat'}
        self.assertEqual(set(DEVIS_FIELDS) & interdits, set())

    # ── scoping société ────────────────────────────────────────────────────
    def test_devis_scope_societe(self):
        Devis.objects.create(
            company=self.company, reference='D-NTDATA1-1',
            client=self.client_obj)
        autre_client = Client.objects.create(
            company=self.autre, nom='AutreClientNTDATA1')
        Devis.objects.create(
            company=self.autre, reference='D-NTDATA1-X', client=autre_client)
        lignes = data_explorer.run_query(
            DEVIS_DATASET, self.company, self.user, {'select': ['id']})
        self.assertEqual(len(lignes), 1)

    # ── group-by statut (critère d'acceptation) ────────────────────────────
    def test_group_by_statut_renvoie_des_lignes(self):
        Devis.objects.create(
            company=self.company, reference='D-NTDATA1-2',
            client=self.client_obj, statut=Devis.Statut.BROUILLON)
        Devis.objects.create(
            company=self.company, reference='D-NTDATA1-3',
            client=self.client_obj, statut=Devis.Statut.ENVOYE)
        lignes = data_explorer.run_query(
            DEVIS_DATASET, self.company, self.user, {
                'group_by': ['statut'],
                'aggregates': [{'alias': 'n', 'fn': 'count', 'field': 'id'}],
            })
        self.assertEqual(sum(r['n'] for r in lignes), 2)
        self.assertEqual({r['statut'] for r in lignes},
                         {Devis.Statut.BROUILLON, Devis.Statut.ENVOYE})

    def test_market_mode_canal_et_kwc(self):
        lead = Lead.objects.create(
            company=self.company, nom='LeadNTDATA1', canal='meta')
        Devis.objects.create(
            company=self.company, reference='D-NTDATA1-4',
            client=self.client_obj, lead=lead,
            mode_installation=Devis.ModeInstallation.AGRICOLE,
            etude_params={'puissance_kwc': 12.5})
        lignes = data_explorer.run_query(
            DEVIS_DATASET, self.company, self.user,
            {'select': ['market_mode', 'canal', 'kwc']})
        ligne = lignes[0]
        self.assertEqual(ligne['market_mode'],
                         Devis.ModeInstallation.AGRICOLE)
        self.assertEqual(ligne['canal'], 'meta')
        self.assertAlmostEqual(ligne['kwc'], 12.5)

    def test_kwc_non_numerique_reste_vide_sans_erreur(self):
        Devis.objects.create(
            company=self.company, reference='D-NTDATA1-5',
            client=self.client_obj, etude_params={'puissance_kwc': 'inconnu'})
        lignes = data_explorer.run_query(
            DEVIS_DATASET, self.company, self.user, {'select': ['kwc']})
        self.assertIsNone(lignes[0]['kwc'])

    # ── factures ───────────────────────────────────────────────────────────
    def test_facture_reste_du_et_echue(self):
        facture = Facture.objects.create(
            company=self.company, reference='F-NTDATA1-1',
            client=self.client_obj, montant_ht=Decimal('1000.00'),
            montant_tva=Decimal('200.00'), montant_ttc=Decimal('1200.00'),
            statut=Facture.Statut.EMISE,
            date_echeance=date(2020, 1, 1))
        Paiement.objects.create(
            company=self.company, facture=facture, client=self.client_obj,
            montant=Decimal('500.00'), date_paiement=date(2020, 2, 1),
            mode=Paiement.Mode.VIREMENT)
        Paiement.objects.create(
            company=self.company, facture=facture, client=self.client_obj,
            montant=Decimal('100.00'), date_paiement=date(2020, 2, 2),
            mode=Paiement.Mode.ESPECES, statut=Paiement.Statut.REJETE)
        lignes = data_explorer.run_query(
            FACTURES_DATASET, self.company, self.user,
            {'select': ['id', 'montant_paye', 'reste_du', 'echue_bool']})
        ligne = next(r for r in lignes if r['id'] == facture.id)
        # Le paiement REJETÉ ne compte pas.
        self.assertEqual(ligne['montant_paye'], Decimal('500.00'))
        self.assertEqual(ligne['reste_du'], Decimal('700.00'))
        self.assertTrue(ligne['echue_bool'])

    def test_factures_group_by_statut_somme_ttc(self):
        Facture.objects.create(
            company=self.company, reference='F-NTDATA1-2',
            client=self.client_obj, montant_ht=Decimal('100.00'),
            montant_tva=Decimal('20.00'), montant_ttc=Decimal('120.00'),
            statut=Facture.Statut.EMISE)
        lignes = data_explorer.run_query(
            FACTURES_DATASET, self.company, self.user, {
                'group_by': ['statut'],
                'aggregates': [
                    {'alias': 'total', 'fn': 'sum', 'field': 'montant_ttc'}],
            })
        self.assertTrue(any(r['total'] for r in lignes))

    # ── paiements ──────────────────────────────────────────────────────────
    def test_paiements_group_by_mode(self):
        Paiement.objects.create(
            company=self.company, client=self.client_obj,
            montant=Decimal('250.00'), date_paiement=date(2026, 3, 4),
            mode=Paiement.Mode.CHEQUE)
        lignes = data_explorer.run_query(
            PAIEMENTS_DATASET, self.company, self.user, {
                'group_by': ['mode'],
                'aggregates': [
                    {'alias': 'total', 'fn': 'sum', 'field': 'montant'}],
            })
        total = {r['mode']: r['total'] for r in lignes}
        self.assertEqual(total[Paiement.Mode.CHEQUE], Decimal('250.00'))

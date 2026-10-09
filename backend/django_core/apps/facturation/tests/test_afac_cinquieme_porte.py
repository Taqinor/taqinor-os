"""AFAC66 (C-AFAC-057) — la cinquième porte de facturation d'un devis est
fermée : ``POST``/``PATCH /api/django/ventes/factures/`` portant le
``bon_commande`` d'un devis est refusé (400 nommé), la seule porte restant
``bons-commande/<id>/creer-facture/`` (copie fidèle du devis signé, ATOT2).

Rejoue les sondes FUI-6 / L2-C-AFAC-057 (chemin écran 201 puis
`total_ttc 18000.00`, `remise_globale 0.00`). APIClient, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_cinquieme_porte"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()
FACTURES = '/api/django/ventes/factures/'


class CinquiemePorteTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from apps.ventes.models import BonCommande, Devis, LigneDevis
        from authentication.models import Company
        self.company = Company.objects.create(nom='AFAC66', slug='afac66-co')
        self.resp = User.objects.create_user(
            username='afac66_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.resp)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='AFAC66',
            email='afac66@example.invalid')
        # Devis accepté remisé à 10 % : 10 000 HT − 10 % = 9 000 HT,
        # TTC signé 10 800.
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-AFAC66-1',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), remise_globale=Decimal('10'),
            mode_installation='residentiel')
        produit = Produit.objects.create(
            company=self.company, nom='Centrale', sku='AFAC66-P',
            prix_vente=Decimal('10000'))
        LigneDevis.objects.create(
            devis=self.devis, produit=produit, designation='Centrale',
            quantite=Decimal('1'),
            prix_unitaire=Decimal('10000'), remise=Decimal('0'),
            taux_tva=Decimal('20'))
        self.bc_devis = BonCommande.objects.create(
            company=self.company, reference='BC-AFAC66-1', devis=self.devis,
            client=self.client_obj, statut=BonCommande.Statut.CONFIRME)
        self.bc_libre = BonCommande.objects.create(
            company=self.company, reference='BC-AFAC66-2',
            client=self.client_obj, statut=BonCommande.Statut.CONFIRME)

    def test_post_facture_avec_bc_de_devis_refuse(self):
        from apps.ventes.models import Facture
        avant = Facture.objects.filter(company=self.company).count()
        r = self.api.post(FACTURES, {
            'client': self.client_obj.id, 'bon_commande': self.bc_devis.id,
            'taux_tva': '20.00'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('créez la facture depuis le bon de commande',
                      str(r.data['bon_commande']))
        self.assertEqual(
            Facture.objects.filter(company=self.company).count(), avant)

    def test_patch_bc_de_devis_refuse(self):
        from apps.ventes.models import Facture
        brouillon = Facture.objects.create(
            company=self.company, reference='FAC-AFAC66-B',
            client=self.client_obj, statut=Facture.Statut.BROUILLON,
            taux_tva=Decimal('20'))
        r = self.api.patch(f'{FACTURES}{brouillon.id}/', {
            'bon_commande': self.bc_devis.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        brouillon.refresh_from_db()
        self.assertIsNone(brouillon.bon_commande_id)

    def test_creer_facture_bc_reste_la_porte(self):
        from apps.ventes.models import Facture
        r = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc_devis.id}/'
            'creer-facture/', {}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        factures = Facture.objects.filter(bon_commande=self.bc_devis)
        self.assertEqual(factures.count(), 1)
        self.assertEqual(factures.get().total_ttc, Decimal('10800.00'))

    def test_bc_sans_devis_accepte(self):
        r = self.api.post(FACTURES, {
            'client': self.client_obj.id, 'bon_commande': self.bc_libre.id,
            'taux_tva': '20.00'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)

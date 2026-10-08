"""ERR-BC-LIVRER-PARTIEL-DOUBLE-SORTIE — « une vente = une sortie » pour la
livraison PARTIELLE d'un BC (XSAL12).

Devis de 10 panneaux accepté (chantier, réservation 10, stock 30). Livraison
partielle 4/10 puis « Installé » : la sortie des 4 livrés doit solder 4 de la
réservation, « Installé » ne sort que le reliquat 6 => Σ SORTIE = 10 (et non 14).
Aucun mock : services réels, endpoint réel.

Run :
    python manage.py test apps.ventes.tests.test_err_bc_livrer_partiel_double_sortie
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations.models import Installation, StockReservation
from apps.installations.services import (
    changer_statut_chantier, create_installation_from_devis,
)
from apps.stock.models import MouvementStock, Produit
from apps.stock.services import mouvement_type_sortie
from apps.ventes.models import BonCommande, Devis, LigneDevis

User = get_user_model()


class LivrerPartielSortieUniqueTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Co BCLP', slug='co-bclp')
        self.user = User.objects.create_user(
            username='resp-bclp', password='x', company=self.company,
            role_legacy='responsable')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau BCLP', sku='SKU-BCLP',
            prix_vente=Decimal('100'), quantite_stock=30,
            tva=Decimal('20.00'))
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email='bclp@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-BCLP', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'),
            taux_tva=Decimal('20.00'))
        self.inst, _ = create_installation_from_devis(
            self.devis, self.user, self.company)
        self.bc = BonCommande.objects.create(
            company=self.company, reference='BC-BCLP', devis=self.devis,
            client=client, statut=BonCommande.Statut.CONFIRME)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _livrer(self, quantite):
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/livrer-partiel/',
            {'lignes': [{'ligne_devis': self.ligne.id,
                         'quantite': str(quantite)}]}, format='json')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))

    def _installer(self):
        self.inst.refresh_from_db()
        changer_statut_chantier(
            self.inst, Installation.Statut.INSTALLE, self.user,
            verifier_gates=False)

    def _total_sorties(self):
        return MouvementStock.objects.filter(
            produit=self.panneau, type_mouvement=mouvement_type_sortie()
        ).aggregate(t=Sum('quantite'))['t'] or 0

    def test_livraison_partielle_puis_installe_dix_sorties(self):
        self._livrer(4)
        resa = StockReservation.objects.get(
            installation=self.inst, produit=self.panneau)
        self.assertEqual(resa.quantite, 6)
        self.assertFalse(resa.consomme)
        self._installer()
        self.assertEqual(self._total_sorties(), 10)
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)

    def test_deux_livraisons_partielles_puis_installe(self):
        self._livrer(4)
        self._livrer(6)  # solde le BC : chaque livraison solde sa part
        resa = StockReservation.objects.get(
            installation=self.inst, produit=self.panneau)
        self.assertEqual(resa.quantite, 0)
        self.assertTrue(resa.consomme)
        self._installer()
        self.assertEqual(self._total_sorties(), 10)
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)

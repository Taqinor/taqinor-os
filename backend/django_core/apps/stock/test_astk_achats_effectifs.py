"""ASTK189 (C-ASTK-043, volet FOUR-17) — UN sélecteur « achats effectifs
par fournisseur » (lignes de BCF ni brouillon ni annulés) nourrit l'export
conformité, le top fournisseurs du tableau de bord achats et la performance
fournisseur : les trois rendent le MÊME montant.

Sonde FOUR-17 d'origine : un BCF annulé de 10 × 1 000 → export conformité
montant_achete = 10 000,00 alors que la performance disait 0.

Aucun mock : vues, sélecteurs et services réels.

Run :
    python manage.py test apps.stock.test_astk_achats_effectifs -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur, Produit,
)
from apps.stock.selectors import achats_effectifs_fournisseur

User = get_user_model()

BASE = '/api/django/stock'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AchatsEffectifsTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='astk189', slug='astk189')
        self.admin = User.objects.create_user(
            username='astk189-admin', password='x', company=self.co,
            role_legacy='admin')
        self.api = _api(self.admin)
        self.fournisseur = Fournisseur.objects.create(
            company=self.co, nom='Fournisseur ASTK189')
        self.produit = Produit.objects.create(
            company=self.co, nom='Onduleur ASTK189', sku='ASTK189-1',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'))
        self._bcf('BCF-ANN', BonCommandeFournisseur.Statut.ANNULE, 10)
        self._bcf('BCF-BRO', BonCommandeFournisseur.Statut.BROUILLON, 1)

    def _bcf(self, reference, statut, quantite, prix='1000'):
        bc = BonCommandeFournisseur.objects.create(
            company=self.co, reference=reference,
            fournisseur=self.fournisseur, statut=statut)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=quantite,
            prix_achat_unitaire=Decimal(prix))
        return bc

    def _trois_montants(self):
        export = self.api.get(f'{BASE}/fournisseurs/export-conformite/')
        self.assertEqual(export.status_code, 200, export.content)
        ligne = next(r for r in export.json()
                     if r['fournisseur_id'] == self.fournisseur.id)
        tableau = self.api.get(f'{BASE}/tableau-bord-achats/')
        self.assertEqual(tableau.status_code, 200, tableau.content)
        top = next((r['volume'] for r in tableau.json()['top_fournisseurs']
                    if r['fournisseur_id'] == self.fournisseur.id), '0')
        perf = self.api.get(
            f'{BASE}/fournisseurs/{self.fournisseur.id}/performance/')
        self.assertEqual(perf.status_code, 200, perf.content)
        return (Decimal(str(ligne['montant_achete'])), Decimal(str(top)),
                Decimal(str(perf.json()['total_achats_ht'])))

    def test_annule_et_brouillon_exclus_partout(self):
        self.assertEqual(
            achats_effectifs_fournisseur(self.co, self.fournisseur.id),
            Decimal('0'))
        self.assertEqual(self._trois_montants(),
                         (Decimal('0'), Decimal('0'), Decimal('0')))

    def test_bcf_envoye_compte_pareil_partout(self):
        self._bcf('BCF-ENV', BonCommandeFournisseur.Statut.ENVOYE, 2, '500')
        self.assertEqual(
            achats_effectifs_fournisseur(self.co, self.fournisseur.id),
            Decimal('1000'))
        self.assertEqual(self._trois_montants(),
                         (Decimal('1000'), Decimal('1000'), Decimal('1000')))

    def test_trois_lectures_des_reglements_meme_regle(self):
        """ASTK241 — /paiements-fournisseur/, …/factures-fournisseur/<id>/paiements/
        et la clé imbriquée `paiements` du détail suivent UNE règle
        (PeutLirePaiementsFournisseur) : un rôle `achats_payer` sans
        `prix_achat_voir` lit les trois ; un rôle sans ces codes : 403, 403,
        clé absente."""
        import datetime
        from apps.roles.models import Role
        from apps.stock.models import FactureFournisseur, PaiementFournisseur
        facture = FactureFournisseur.objects.create(
            company=self.co, reference='FF-ASTK241', fournisseur=self.fournisseur,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        PaiementFournisseur.objects.create(
            company=self.co, facture=facture, montant=Decimal('400'),
            date_paiement=datetime.date(2026, 10, 1))
        for nom, codes, attendu in (('payeur', ['stock_voir', 'achats_payer'], 200),
                                    ('lecteur', ['stock_voir'], 403)):
            user = User.objects.create_user(
                username=f'astk241-{nom}', password='x', company=self.co,
                role=Role.objects.create(company=self.co, nom=nom, permissions=codes))
            api = _api(user)
            liste = api.get(f'{BASE}/paiements-fournisseur/')
            action = api.get(f'{BASE}/factures-fournisseur/{facture.id}/paiements/')
            detail = api.get(f'{BASE}/factures-fournisseur/{facture.id}/')
            self.assertEqual(
                (liste.status_code, action.status_code, detail.status_code),
                (attendu, attendu, 200), nom)
            self.assertEqual('paiements' in detail.data, attendu == 200, nom)
            if attendu == 200:
                self.assertEqual(len(action.data), 1)
                self.assertEqual(len(detail.data['paiements']), 1)

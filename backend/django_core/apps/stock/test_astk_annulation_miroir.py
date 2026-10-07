"""ASTK54 — annuler une réception confirmée défait CHAQUE effet de la
confirmation (ventilation d'emplacement, lot, ligne service) ; une réception
en livraison directe chantier est refusée (passer par un retour).

Constat C-ASTK-011 (sondes MVT-10, BCF-13) : après annulation d'une réception
vers la camionnette avec lot, la ventilation restait {principal 40,
camionnette 10} et le lot 10 ; l'annulation d'une livraison directe chantier
ressortait 5 unités du stock libre (5 → 0) qui ne les avait jamais reçues.

Run :
    python manage.py test apps.stock.test_astk_annulation_miroir -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models_installation import Installation
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, EmplacementStock, Fournisseur, LotEntrepot,
    Produit, ReceptionFournisseur, RetourFournisseur, StockEmplacement,
)
from apps.stock.services import (
    annuler_reception_confirmee, apply_retour_fournisseur,
    confirm_reception_fournisseur, ensure_emplacements, stock_breakdown,
)
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)


class AnnulationMiroirTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.n = n
        self.company = Company.objects.create(
            slug=f'astk54-co-{n}', nom=f'ASTK54 Co {n}')
        role = Role.objects.create(
            company=self.company, nom=f'r-astk54-{n}',
            permissions=['stock_modifier', 'stock_voir'])
        self.user = User.objects.create_user(
            username=f'astk54-{n}', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK54')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie ASTK54', sku=f'ASTK54-{n}',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'),
            quantite_stock=50)
        ensure_emplacements(self.company)
        # Camionnette créée par ensure_emplacements (non principale).
        self.camionnette = EmplacementStock.objects.get(
            company=self.company, nom='Camionnette')

    def _bcf(self, **extra):
        return BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ASTK54-{next(_seq)}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE, **extra)

    def _reception(self, bc, ligne_cmd, quantite, **extra):
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-ASTK54-{next(_seq)}',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.user)
        rec.lignes.create(
            ligne_commande=ligne_cmd, produit=ligne_cmd.produit,
            quantite=quantite, **extra)
        return rec

    def _ventilation(self):
        p = Produit.objects.get(pk=self.produit.pk)
        return {row['emplacement_nom']: row['quantite']
                for row in stock_breakdown(p)
                if row['is_principal'] or row['emplacement_id']
                == self.camionnette.id}

    def _principal_nom(self):
        return EmplacementStock.objects.get(
            company=self.company, is_principal=True).nom

    def _reception_camionnette_avec_lot(self):
        bc = self._bcf(emplacement_destination=self.camionnette)
        ligne_cmd = bc.lignes.create(
            produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('100'))
        rec = self._reception(bc, ligne_cmd, 10, numero_lot='LOT-X')
        confirm_reception_fournisseur(rec, self.user)
        return bc, rec

    def test_ventilation_restauree(self):
        avant = self._ventilation()
        _bc, rec = self._reception_camionnette_avec_lot()
        self.assertEqual(self._ventilation()['Camionnette'], 10)

        annuler_reception_confirmee(rec, self.user)

        self.assertEqual(self._ventilation(), avant)
        self.assertEqual(
            self._ventilation(),
            {self._principal_nom(): 50, 'Camionnette': 0})
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 50)

    def test_lot_restant_zero(self):
        _bc, rec = self._reception_camionnette_avec_lot()
        annuler_reception_confirmee(rec, self.user)
        lot = LotEntrepot.objects.get(
            company=self.company, produit=self.produit, numero_lot='LOT-X')
        self.assertEqual(lot.quantite_restante, 0)
        self.assertEqual(lot.quantite_recue, 0)

    def test_confirmer_puis_annuler_etat_identique(self):
        avant = (self._ventilation(),
                 Produit.objects.get(pk=self.produit.pk).quantite_stock)
        _bc, rec = self._reception_camionnette_avec_lot()
        annuler_reception_confirmee(rec, self.user)
        apres = (self._ventilation(),
                 Produit.objects.get(pk=self.produit.pk).quantite_stock)
        self.assertEqual(apres, avant)

    def test_livraison_directe_refusee(self):
        client = Client.objects.create(
            company=self.company, nom='Client ASTK54', prenom='Test')
        chantier = Installation.objects.create(
            company=self.company, reference=f'CH-ASTK54-{self.n}',
            client=client)
        Produit.objects.filter(pk=self.produit.pk).update(quantite_stock=5)
        bc = self._bcf(chantier_livraison=chantier)
        ligne_cmd = bc.lignes.create(
            produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('100'))
        rec = self._reception(bc, ligne_cmd, 5)
        confirm_reception_fournisseur(rec, self.user)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 5)

        resp = self.api.post(
            f'/api/django/stock/receptions-fournisseur/{rec.id}/annuler/')

        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('chantier', resp.data['detail'])
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 5)
        rec.refresh_from_db()
        self.assertEqual(rec.statut, ReceptionFournisseur.Statut.CONFIRME)

    def test_ligne_service_decrementee_et_bcf_rouvert(self):
        bc = self._bcf()
        ligne_cmd = bc.lignes.create(
            produit=None, designation='Transport', sans_stock=True,
            quantite=1, prix_achat_unitaire=Decimal('300'))
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-ASTK54-{next(_seq)}',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.user)
        rec.lignes.create(ligne_commande=ligne_cmd, produit=None, quantite=1)
        confirm_reception_fournisseur(rec, self.user)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.RECU)

        annuler_reception_confirmee(rec, self.user)

        ligne_cmd.refresh_from_db()
        bc.refresh_from_db()
        self.assertEqual(ligne_cmd.quantite_recue, 0)
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.ENVOYE)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 50)

    def test_retour_fournisseur_debite_l_emplacement(self):
        bc, _rec = self._reception_camionnette_avec_lot()
        retour = RetourFournisseur.objects.create(
            company=self.company, reference=f'RET-ASTK54-{self.n}',
            fournisseur=self.fournisseur, bon_commande=bc)
        retour.lignes.create(produit=self.produit, quantite=4)
        apply_retour_fournisseur(retour, self.user)
        se = StockEmplacement.objects.get(
            produit=self.produit, emplacement=self.camionnette)
        self.assertEqual(se.quantite, 6)

"""ASTK59 — la quantité RÉELLEMENT entrée par une réception
(`quantite_appliquee`) est persistée à la confirmation et relue par la
facturation et l'annulation ; la création est plafonnée au reste dû net des
réceptions brouillon ; une confirmation qui n'applique rien est refusée.

Constat C-ASTK-012 (sonde BCF-1) : deux réceptions brouillon de 10 sur une
ligne de 10 — la 2e se confirmait en n'appliquant rien (plafond à 0) mais
passait CONFIRMÉE, puis se facturait 1 000 HT une seconde fois ; l'annulation
relisait la quantité SAISIE et retirait du stock ce qui n'était jamais entré.

Run :
    python manage.py test apps.stock.test_astk_quantite_appliquee -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, FactureFournisseur, Fournisseur,
    MouvementStock, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    annuler_reception_confirmee, confirm_reception_fournisseur,
    facturer_reception,
)
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/stock/receptions-fournisseur'


class QuantiteAppliqueeTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'astk59-co-{n}', nom=f'ASTK59 Co {n}')
        role = Role.objects.create(
            company=self.company, nom=f'r-astk59-{n}',
            permissions=['stock_modifier', 'stock_voir'])
        self.user = User.objects.create_user(
            username=f'astk59-{n}', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK59')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ASTK59', sku=f'ASTK59-{n}',
            prix_vente=Decimal('200'), prix_achat=Decimal('100'),
            quantite_stock=0)

    def _bcf(self, quantite=10, pu='100'):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ASTK59-{next(_seq)}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = bc.lignes.create(
            produit=self.produit, quantite=quantite,
            prix_achat_unitaire=Decimal(pu))
        return bc, ligne

    def _creer_api(self, bc, ligne, qte):
        return self.api.post(
            f'{BASE}/', {'bon_commande': bc.id, 'lignes': [
                {'ligne_commande': ligne.id, 'quantite': qte}]},
            format='json')

    def _creer_orm(self, bc, ligne, qte):
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-ASTK59-{next(_seq)}',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.user)
        rec.lignes.create(ligne_commande=ligne, produit=self.produit,
                          quantite=qte)
        return rec

    def test_deuxieme_brouillon_refuse_a_la_creation(self):
        bc, ligne = self._bcf()
        r1 = self._creer_api(bc, ligne, 10)
        self.assertEqual(r1.status_code, 201, r1.content)
        r2 = self._creer_api(bc, ligne, 10)
        self.assertEqual(r2.status_code, 400, r2.content)
        self.assertIn('dépasse le reste dû', str(r2.data))
        self.assertEqual(ReceptionFournisseur.objects.filter(
            bon_commande=bc).count(), 1)

    def test_pas_de_double_facture(self):
        bc, ligne = self._bcf()
        r1 = self._creer_orm(bc, ligne, 10)
        r2 = self._creer_orm(bc, ligne, 10)  # brouillon déjà existant
        confirm_reception_fournisseur(r1, self.user)
        with self.assertRaisesMessage(ValueError, 'Rien à recevoir'):
            confirm_reception_fournisseur(
                ReceptionFournisseur.objects.get(pk=r2.pk), self.user)

        r2.refresh_from_db()
        self.assertEqual(r2.statut, ReceptionFournisseur.Statut.BROUILLON)
        f1 = facturer_reception(self.company, self.user, r1)
        self.assertEqual(f1.montant_ht, Decimal('1000.00'))
        with self.assertRaises(ValueError):
            facturer_reception(self.company, self.user, r2)
        self.assertEqual(FactureFournisseur.objects.filter(
            bon_commande=bc).count(), 1)
        self.produit.refresh_from_db()
        ligne.refresh_from_db()
        bc.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 10)
        self.assertEqual(ligne.quantite_recue, 10)
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.RECU)
        self.assertEqual(MouvementStock.objects.filter(
            produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE).count(), 1)

    def test_sur_livraison_plafonnee_et_persistee(self):
        bc, ligne = self._bcf(quantite=10, pu='60')
        resp = self._creer_api(bc, ligne, 12)
        self.assertEqual(resp.status_code, 201, resp.content)
        rec = ReceptionFournisseur.objects.get(pk=resp.data['id'])
        confirm_reception_fournisseur(rec, self.user)
        lr = rec.lignes.get()
        self.assertEqual(lr.quantite, 12)
        self.assertEqual(lr.quantite_appliquee, 10)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 10)
        rec.refresh_from_db()
        facture = facturer_reception(self.company, self.user, rec)
        self.assertEqual(facture.montant_ht, Decimal('600.00'))

    def test_annulation_relit_quantite_appliquee(self):
        Produit.objects.filter(pk=self.produit.pk).update(quantite_stock=5)
        bc, ligne = self._bcf(quantite=10)
        rec = self._creer_orm(bc, ligne, 12)
        confirm_reception_fournisseur(rec, self.user)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 15)
        annuler_reception_confirmee(
            ReceptionFournisseur.objects.get(pk=rec.pk), self.user)
        self.produit.refresh_from_db()
        # Avant ASTK59 : 3 (12 saisis retirés alors que 10 seulement entrés).
        self.assertEqual(self.produit.quantite_stock, 5)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite_recue, 0)

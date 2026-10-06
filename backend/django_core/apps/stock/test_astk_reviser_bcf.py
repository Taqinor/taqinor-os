"""ASTK63 — `reviser_bcf` refuse une quantité ≤ 0 ou sous le reçu et toute
modification du prix d'une quantité déjà reçue ; tout ou rien ; statut et PU
devise recalculés.

Constat C-ASTK-014 (sonde BCF-5) : {quantite:4, prix:'150'} sur un BCF reçu
10/10 @ 100 était accepté (quantite_recue 10 > quantite 4, statut reçu, coût
moyen 100 → 150) ; −3 et 0 acceptés ; une 2e ligne invalide levait APRÈS que
la ligne 1 eut été sauvegardée.

Run :
    python manage.py test apps.stock.test_astk_reviser_bcf -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur, Produit,
)
from apps.stock.services import average_cost_with_source, reviser_bcf
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)


class ReviserBcfTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'astk63-co-{n}', nom=f'ASTK63 Co {n}')
        self.user = User.objects.create_user(
            username=f'astk63-{n}', password='x', company=self.company,
            role_legacy='admin')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK63')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK63', sku=f'ASTK63-{n}',
            prix_vente=Decimal('300'), prix_achat=Decimal('100'),
            quantite_stock=10)

    def _bcf(self, statut, lignes, **extra):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ASTK63-{next(_seq)}',
            fournisseur=self.fournisseur, statut=statut, **extra)
        out = []
        for quantite, pu, recue in lignes:
            out.append(LigneBonCommandeFournisseur.objects.create(
                bon_commande=bc, produit=self.produit, quantite=quantite,
                prix_achat_unitaire=Decimal(pu), quantite_recue=recue))
        return bc, out

    def _recu(self):
        return self._bcf(BonCommandeFournisseur.Statut.RECU,
                         [(10, '100', 10)])

    def test_sous_le_recu_refuse(self):
        bc, (ligne,) = self._recu()
        with self.assertRaisesMessage(ValueError, 'déjà reçue'):
            reviser_bcf(self.company, self.user, bc,
                        lignes=[{'id': ligne.id, 'quantite': 4}])
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite, 10)

    def test_prix_d_une_ligne_recue_refuse(self):
        bc, (ligne,) = self._recu()
        cout_avant, _ = average_cost_with_source(self.produit)
        with self.assertRaisesMessage(ValueError, 'revalorisation'):
            reviser_bcf(self.company, self.user, bc, lignes=[
                {'id': ligne.id, 'quantite': 10, 'prix_achat_unitaire': '150'}])
        ligne.refresh_from_db()
        self.assertEqual(ligne.prix_achat_unitaire, Decimal('100'))
        cout_apres, _ = average_cost_with_source(
            Produit.objects.get(pk=self.produit.pk))
        self.assertEqual(cout_apres, cout_avant)

    def test_quantite_negative_ou_nulle_refusee(self):
        bc, (ligne, _l2) = self._bcf(
            BonCommandeFournisseur.Statut.ENVOYE,
            [(10, '100', 0), (5, '50', 0)])
        for valeur in (-3, 0):
            with self.assertRaisesMessage(ValueError, 'strictement positive'):
                reviser_bcf(self.company, self.user, bc,
                            lignes=[{'id': ligne.id, 'quantite': valeur}])
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite, 10)

    def test_tout_ou_rien(self):
        bc, (l1, l2) = self._bcf(
            BonCommandeFournisseur.Statut.ENVOYE,
            [(10, '100', 0), (5, '50', 0)])
        with self.assertRaises(ValueError):
            reviser_bcf(self.company, self.user, bc, lignes=[
                {'id': l1.id, 'quantite': 20},
                {'id': l2.id, 'quantite': -1}])
        l1.refresh_from_db()
        bc.refresh_from_db()
        self.assertEqual(l1.quantite, 10)
        self.assertEqual(bc.revision, 0)

    def test_hausse_sur_bcf_recu_repasse_envoye(self):
        bc, (ligne,) = self._recu()
        bc, _ = reviser_bcf(self.company, self.user, bc,
                            lignes=[{'id': ligne.id, 'quantite': 12}])
        bc.refresh_from_db()
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite, 12)
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.ENVOYE)
        self.assertEqual(bc.revision, 1)

    def test_pu_devise_recalcule(self):
        bc, (ligne,) = self._bcf(
            BonCommandeFournisseur.Statut.ENVOYE, [(10, '1080', 0)],
            devise='EUR', taux_change=Decimal('10.8'))
        reviser_bcf(self.company, self.user, bc, lignes=[
            {'id': ligne.id, 'prix_achat_unitaire': '2160'}])
        ligne.refresh_from_db()
        self.assertEqual(ligne.prix_achat_unitaire, Decimal('2160.00'))
        self.assertEqual(ligne.prix_achat_unitaire_devise, Decimal('200.00'))

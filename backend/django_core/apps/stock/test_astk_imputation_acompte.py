"""ASTK106 — un acompte fournisseur s'impute par MONTANT plafonné au solde de
la facture cible, sur la première facture du BCF à solde > 0 ; le reliquat
reste ouvert et s'impute sur la suivante ; le montant d'un acompte imputé
n'est plus modifiable.

Run:
    python manage.py test apps.stock.test_astk_imputation_acompte
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AcompteFournisseur, BonCommandeFournisseur, FactureFournisseur,
    Fournisseur, LigneBonCommandeFournisseur, LigneReceptionFournisseur,
    PaiementFournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.selectors import acomptes_fournisseur_ouverts
from apps.stock.services import (
    facturer_reception, recompute_facture_fournisseur_statut,
)

User = get_user_model()


class ImputationAcompteTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='astk106-co', slug='astk106-co')
        role = Role.objects.create(
            company=self.company, nom='r-astk106',
            permissions=['stock_voir', 'stock_modifier'])
        self.user = User.objects.create_user(
            username='astk106-user', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK106')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='PV-ASTK106',
            prix_vente=Decimal('200'), prix_achat=Decimal('100'),
            tva=Decimal('20'))
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK106-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.produit, quantite=100,
            prix_achat_unitaire=Decimal('100'))
        self.n = 0

    def _facturer(self, quantite):
        """Réception confirmée de `quantite` × 100 HT puis facture (TTC =
        quantite × 120)."""
        self.n += 1
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-ASTK106-{self.n}',
            bon_commande=self.bcf,
            statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=datetime.date(2026, 10, self.n))
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=self.ligne, produit=self.produit,
            quantite=quantite)
        facture = facturer_reception(self.company, self.user, rec)
        return FactureFournisseur.objects.get(pk=facture.pk)

    def _acompte(self, montant):
        return AcompteFournisseur.objects.create(
            company=self.company, bon_commande=self.bcf, montant=montant,
            date_versement=datetime.date(2026, 9, 1))

    def test_reliquat_reste_ouvert(self):
        acompte = self._acompte(Decimal('5000'))
        f1 = self._facturer(25)  # TTC 3 000
        self.assertEqual(f1.montant_ttc, Decimal('3000.00'))
        self.assertEqual(f1.total_acomptes_imputes, Decimal('3000.00'))
        self.assertEqual(f1.solde_du, Decimal('0.00'))
        self.assertEqual(f1.statut, FactureFournisseur.Statut.PAYEE)
        acompte.refresh_from_db()
        self.assertEqual(acompte.montant_consomme, Decimal('3000.00'))
        self.assertEqual(acompte.montant_non_consomme, Decimal('2000.00'))
        ouverts = acomptes_fournisseur_ouverts(self.company)
        self.assertEqual(len(ouverts), 1)
        self.assertEqual(ouverts[0]['id'], acompte.id)
        self.assertEqual(
            ouverts[0]['montant_non_consomme'], Decimal('2000.00'))
        # Facture suivante du BCF : le reliquat s'y impute.
        f2 = self._facturer(50)  # TTC 6 000
        self.assertEqual(f2.total_acomptes_imputes, Decimal('2000.00'))
        self.assertEqual(f2.solde_du, Decimal('4000.00'))
        acompte.refresh_from_db()
        self.assertEqual(acompte.montant_consomme, Decimal('5000.00'))
        self.assertEqual(acomptes_fournisseur_ouverts(self.company), [])
        # Relus : imputations persistées.
        self.assertEqual(
            sorted(acompte.imputations.values_list('facture_id', 'montant')),
            sorted([(f1.id, Decimal('3000.00')),
                    (f2.id, Decimal('2000.00'))]))

    def test_acompte_tardif_sur_facture_non_soldee(self):
        f1 = self._facturer(25)  # TTC 3 000, payée en entier
        PaiementFournisseur.objects.create(
            company=self.company, facture=f1, montant=Decimal('3000'),
            date_paiement=datetime.date(2026, 10, 2))
        recompute_facture_fournisseur_statut(f1)
        acompte = self._acompte(Decimal('3000'))
        f2 = self._facturer(50)  # TTC 6 000
        f1 = FactureFournisseur.objects.get(pk=f1.pk)
        self.assertEqual(f1.total_acomptes_imputes, Decimal('0'))
        self.assertEqual(f2.total_acomptes_imputes, Decimal('3000.00'))
        self.assertEqual(f2.solde_du, Decimal('3000.00'))
        acompte.refresh_from_db()
        self.assertEqual(acompte.facture_imputee_id, f2.id)

    def test_montant_verrouille_apres_imputation(self):
        acompte = self._acompte(Decimal('1200'))
        self._facturer(25)
        resp = self.api.patch(
            f'/api/django/stock/acomptes-fournisseur/{acompte.id}/',
            {'montant': '900'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        acompte.refresh_from_db()
        self.assertEqual(acompte.montant, Decimal('1200.00'))
        # Un acompte non imputé reste modifiable.
        libre = AcompteFournisseur.objects.create(
            company=self.company,
            bon_commande=BonCommandeFournisseur.objects.create(
                company=self.company, reference='BCF-ASTK106-2',
                fournisseur=self.fournisseur),
            montant=Decimal('500'))
        resp = self.api.patch(
            f'/api/django/stock/acomptes-fournisseur/{libre.id}/',
            {'montant': '600'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

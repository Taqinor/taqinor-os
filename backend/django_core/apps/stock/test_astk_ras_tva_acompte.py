"""ASTK175 — RAS-TVA par facture fournisseur, règle (a) tranchée par le
fondateur le 07/10/2026 (réponse à ASTK171, « Toute la TVA ») : la retenue
due = TVA × taux de la facture ENTIÈRE, ventilée sur ses règlements, le
DERNIER règlement portant le solde de retenue au centime. Un acompte imputé
ne porte pas de retenue propre (aucun champ RAS sur l'acompte) : sa part de
retenue est portée par les paiements suivants.

Run:
    python manage.py test apps.stock.test_astk_ras_tva_acompte
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
    AchatsParametres, AcompteFournisseur, BonCommandeFournisseur,
    FactureFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, PaiementFournisseur, Produit,
    ReceptionFournisseur,
)
from apps.stock.services import facturer_reception

User = get_user_model()


class RasTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='astk175-co', slug='astk175-co')
        role = Role.objects.create(
            company=self.company, nom='r-astk175',
            permissions=['stock_voir', 'stock_modifier'])
        self.user = User.objects.create_user(
            username='astk175-user', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        params = AchatsParametres.for_company(self.company)
        params.ras_tva_actif = True
        params.save()
        # Fournisseur SANS ARF : biens ⇒ retenue 100 %.
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK175')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-ASTK175',
            prix_vente=Decimal('200'), prix_achat=Decimal('100'),
            tva=Decimal('20'))

    def _facture_avec_acompte(self, acompte):
        """Facture de biens TTC 1 200 / TVA 200 avec un acompte imputé."""
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK175-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('100'))
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-ASTK175-1',
            bon_commande=bcf, statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=datetime.date(2026, 10, 1))
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=ligne, produit=self.produit,
            quantite=10)
        AcompteFournisseur.objects.create(
            company=self.company, bon_commande=bcf, montant=acompte)
        facture = facturer_reception(self.company, self.user, rec)
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        self.assertEqual(facture.type_achat, FactureFournisseur.TypeAchat.BIENS)
        self.assertEqual(facture.montant_ttc, Decimal('1200.00'))
        self.assertEqual(facture.montant_tva, Decimal('200.00'))
        self.assertEqual(facture.total_acomptes_imputes, acompte)
        return facture

    def _payer(self, facture, montant):
        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture.id, 'montant': montant,
            'date_paiement': '2026-10-05',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return PaiementFournisseur.objects.get(pk=resp.data['id'])

    def test_ras_totale_facture(self):
        """Sonde FACF-12 rejouée : 140,00 observé au prorata, 200,00 sous (a)."""
        facture = self._facture_avec_acompte(Decimal('360'))
        paiement = self._payer(facture, '840')
        self.assertEqual(paiement.montant_ras_tva, Decimal('200.00'))
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        total_ras = sum(
            (p.montant_ras_tva for p in facture.paiements.all()),
            Decimal('0'))
        self.assertEqual(total_ras, Decimal('200.00'))

    def test_ras_ventilee_dernier_reglement_porte_le_solde(self):
        facture = self._facture_avec_acompte(Decimal('360'))
        p1 = self._payer(facture, '400')
        # Part réglée après p1 = 360 + 400 = 760 / 1 200 ⇒ 126,67 dus.
        self.assertEqual(p1.montant_ras_tva, Decimal('126.67'))
        p2 = self._payer(facture, '440')
        self.assertEqual(p2.montant_ras_tva, Decimal('73.33'))
        self.assertEqual(
            p1.montant_ras_tva + p2.montant_ras_tva, Decimal('200.00'))

    def test_trois_reglements_somme_exacte_au_centime(self):
        facture = self._facture_avec_acompte(Decimal('100'))
        paiements = [self._payer(facture, m) for m in ('333', '333', '434')]
        self.assertEqual(
            sum((p.montant_ras_tva for p in paiements), Decimal('0')),
            Decimal('200.00'))

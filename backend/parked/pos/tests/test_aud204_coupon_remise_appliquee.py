"""AUD204 — Le coupon brûlait sa limite d'usage sans jamais appliquer sa remise.

Rouge avant correctif : l'action `coupon/` CONSOMMAIT le coupon
(`promotions/services.py:139-154`), `valider_vente` exigeait malgré tout le
total PLEIN (`pos/services.py:67-110`) et rien ne refermait la boucle
(`pos/views.py:188-199`). Un coupon de -50 MAD sur une vente de 500 MAD : le
client payait 500 MAD et perdait son coupon.

Vert : la remise est soustraite du total exigé ET du montant facturé (450 MAD),
et le coupon n'est consommé qu'à la validation, une seule fois, dans la même
transaction que la facture.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.pos import services as pos_services
from apps.pos.models import LigneVenteComptoir, VenteComptoir
from apps.promotions import services as promo_services
from apps.promotions.models import (
    CouponUnique, CouponUtilisation, ReglexPromotion,
)
from apps.stock.models import Categorie, Produit

User = get_user_model()


class Aud204CouponRemiseAppliqueeTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aud204', defaults={'nom': 'AUD204 Co'})
        self.user = User.objects.create_user(
            username='aud204-caissier', password='x', company=self.co,
            role_legacy='responsable')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.produit = Produit.objects.create(
            company=self.co, nom='Panneau', prix_vente=Decimal('500'),
            prix_achat=Decimal('200'), quantite_stock=10, categorie=categorie)
        self.regle = ReglexPromotion.objects.create(
            company=self.co, nom='Coupon -50', type_regle='remise_montant_panier',
            remise_montant=Decimal('50'))
        self.coupon = CouponUnique.objects.create(
            company=self.co, regle=self.regle)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _vente(self, reference='VC-AUD204', prix='500'):
        vente = VenteComptoir.objects.create(
            company=self.co, reference=reference, client=self.client_obj,
            taux_tva=Decimal('20'), created_by=self.user)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation=self.produit.nom,
            quantite=1, prix_unitaire_ttc=Decimal(prix))
        return vente

    # ── le scénario du constat ──────────────────────────────────────────────

    def test_coupon_50_sur_vente_500_le_client_paie_450(self):
        """ROUGE avant AUD204 : 450 MAD était refusé comme « insuffisant »."""
        vente = self._vente()
        pos_services.valider_vente(
            vente=vente,
            paiements=[{'mode': 'virement', 'montant': '450'}],
            user=self.user, coupon_code=self.coupon.code)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, VenteComptoir.Statut.VALIDEE)
        self.assertIsNotNone(vente.facture)
        self.assertEqual(
            Decimal(str(vente.facture.total_ttc)), Decimal('450.00'))
        # La remise ne déforme pas le taux de TVA : 450 TTC à 20 %.
        self.assertEqual(
            Decimal(str(vente.facture.montant_ht)), Decimal('375.00'))
        self.assertEqual(
            Decimal(str(vente.facture.montant_tva)), Decimal('75.00'))
        # Le coupon a été consommé EXACTEMENT une fois.
        self.assertEqual(
            CouponUtilisation.objects.filter(coupon=self.coupon).count(), 1)

    def test_apercu_coupon_ne_consomme_pas(self):
        """L'écran caisse peut afficher la remise sans brûler le coupon."""
        vente = self._vente()
        resp = self.api.post(
            f'/api/django/pos/ventes/{vente.id}/coupon/',
            {'code': self.coupon.code}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['montant_remise'], '50.00')
        self.assertEqual(
            CouponUtilisation.objects.filter(coupon=self.coupon).count(), 0)

    def test_apercu_puis_validation_ne_brule_le_coupon_quune_fois(self):
        vente = self._vente()
        self.api.post(
            f'/api/django/pos/ventes/{vente.id}/coupon/',
            {'code': self.coupon.code}, format='json')
        resp = self.api.post(
            f'/api/django/pos/ventes/{vente.id}/valider/',
            {'paiements': [{'mode': 'virement', 'montant': '450'}],
             'coupon': self.coupon.code}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            CouponUtilisation.objects.filter(coupon=self.coupon).count(), 1)
        vente.refresh_from_db()
        self.assertEqual(
            Decimal(str(vente.facture.total_ttc)), Decimal('450.00'))

    def test_vente_refusee_ne_brule_pas_le_coupon(self):
        """Règlement insuffisant même remise déduite : rien n'est écrit."""
        vente = self._vente()
        with self.assertRaises(pos_services.VenteComptoirError):
            pos_services.valider_vente(
                vente=vente,
                paiements=[{'mode': 'virement', 'montant': '100'}],
                user=self.user, coupon_code=self.coupon.code)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, VenteComptoir.Statut.BROUILLON)
        self.assertEqual(
            CouponUtilisation.objects.filter(coupon=self.coupon).count(), 0)

    def test_sans_coupon_le_total_reste_plein(self):
        vente = self._vente(reference='VC-AUD204-SANS')
        pos_services.valider_vente(
            vente=vente,
            paiements=[{'mode': 'virement', 'montant': '500'}],
            user=self.user)
        vente.refresh_from_db()
        self.assertEqual(
            Decimal(str(vente.facture.total_ttc)), Decimal('500.00'))

    def test_coupon_sans_remise_nest_pas_consomme(self):
        """Un coupon dont la règle n'ouvre AUCUNE remise sur ce panier ne
        brûle plus sa limite d'usage (le client le garde)."""
        regle_zero = ReglexPromotion.objects.create(
            company=self.co, nom='Coupon inopérant',
            type_regle='remise_montant_panier', remise_montant=Decimal('0'))
        coupon_zero = CouponUnique.objects.create(
            company=self.co, regle=regle_zero)
        vente = self._vente(reference='VC-AUD204-ZERO')
        with self.assertRaises(promo_services.CouponError):
            promo_services.consommer_coupon(
                self.co, coupon_zero.code, vente.lignes.all())
        self.assertEqual(
            CouponUtilisation.objects.filter(coupon=coupon_zero).count(), 0)

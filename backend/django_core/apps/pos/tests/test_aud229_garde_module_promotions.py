"""AUD229 — Le POS appelait le moteur promotions sans garde d'activation.

`DisabledModuleMiddleware` (core/permissions.py:103-117, :167-176) ne coupe
qu'au PRÉFIXE D'URL : il est aveugle aux appels function-local que
`pos/services.py:1032-1215` fait vers `apps.promotions.services`. Le
désactivateur par tenant (SOL8) était donc inopérant sur cette surface.

Rouge avant correctif : une société ayant désactivé le module « promotions »
voyait quand même le moteur s'exécuter depuis la caisse. Vert : no-op propre
(aucune promotion appliquée, aucun coupon consommé) ou refus explicite selon
la surface.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.pos import services as pos_services
from apps.pos.models import LigneVenteComptoir, VenteComptoir
from apps.promotions.models import (
    CouponUnique, CouponUtilisation, ReglexPromotion,
)
from apps.stock.models import Categorie, Produit
from core.models import ModuleToggle

User = get_user_model()


class Aud229GardeModulePromotionsTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aud229', defaults={'nom': 'AUD229 Co'})
        self.user = User.objects.create_user(
            username='aud229-caissier', password='x', company=self.co,
            role_legacy='responsable')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.produit = Produit.objects.create(
            company=self.co, nom='Panneau', prix_vente=Decimal('500'),
            prix_achat=Decimal('200'), quantite_stock=10, categorie=categorie)
        self.regle = ReglexPromotion.objects.create(
            company=self.co, nom='Coupon -50',
            type_regle='remise_montant_panier', remise_montant=Decimal('50'))
        self.coupon = CouponUnique.objects.create(
            company=self.co, regle=self.regle)

    def _desactiver_promotions(self):
        ModuleToggle.objects.update_or_create(
            company=self.co, module='promotions', defaults={'actif': False})

    def _vente(self, reference='VC-AUD229', prix='500'):
        vente = VenteComptoir.objects.create(
            company=self.co, reference=reference, client=self.client_obj,
            taux_tva=Decimal('20'), created_by=self.user)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation=self.produit.nom,
            quantite=1, prix_unitaire_ttc=Decimal(prix))
        return vente

    # ── le scénario du constat ──────────────────────────────────────────────

    def test_valider_vente_avec_coupon_module_off_est_un_no_op(self):
        """ROUGE avant AUD229 : le moteur promotions s'exécutait quand même."""
        self._desactiver_promotions()
        vente = self._vente()
        pos_services.valider_vente(
            vente=vente,
            paiements=[{'mode': 'virement', 'montant': '500'}],
            user=self.user, coupon_code=self.coupon.code)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, VenteComptoir.Statut.VALIDEE)
        # Aucune promotion appliquée : le total reste plein.
        self.assertEqual(
            Decimal(str(vente.facture.total_ttc)), Decimal('500.00'))
        # Aucun coupon consommé.
        self.assertEqual(
            CouponUtilisation.objects.filter(coupon=self.coupon).count(), 0)

    def test_module_actif_le_coupon_sapplique_toujours(self):
        """Le défaut « module actif » (aucun ModuleToggle) est inchangé."""
        vente = self._vente(reference='VC-AUD229-ON')
        pos_services.valider_vente(
            vente=vente,
            paiements=[{'mode': 'virement', 'montant': '450'}],
            user=self.user, coupon_code=self.coupon.code)
        vente.refresh_from_db()
        self.assertEqual(
            Decimal(str(vente.facture.total_ttc)), Decimal('450.00'))

    def test_promotions_applicables_module_off_renvoie_vide(self):
        self._desactiver_promotions()
        vente = self._vente(reference='VC-AUD229-PROMO')
        self.assertEqual(pos_services.promotions_applicables(vente), [])
        self.assertEqual(
            pos_services.total_remises_promotions(vente), Decimal('0'))

    def test_appliquer_coupon_module_off_refuse(self):
        self._desactiver_promotions()
        vente = self._vente(reference='VC-AUD229-CPN')
        with self.assertRaises(pos_services.CouponPosError):
            pos_services.appliquer_coupon(vente=vente, code=self.coupon.code)
        with self.assertRaises(pos_services.CouponPosError):
            pos_services.previsualiser_coupon(
                vente=vente, code=self.coupon.code)
        self.assertEqual(
            CouponUtilisation.objects.filter(coupon=self.coupon).count(), 0)

    def test_emettre_carte_cadeau_module_off_refuse(self):
        self._desactiver_promotions()
        with self.assertRaises(pos_services.CarteCadeauPosError):
            pos_services.emettre_carte_cadeau_comptoir(
                company=self.co, montant=Decimal('500'),
                paiement={'mode': 'especes', 'montant': '500'},
                user=self.user, client=self.client_obj)

    def test_reglement_carte_cadeau_module_off_refuse_avant_ecriture(self):
        from apps.promotions import services as promo_services
        carte = promo_services.emettre_carte_cadeau(self.co, Decimal('500'))
        self._desactiver_promotions()
        vente = self._vente(reference='VC-AUD229-CC')
        with self.assertRaises(pos_services.VenteComptoirError):
            pos_services.valider_vente(
                vente=vente,
                paiements=[{'mode': 'carte_cadeau', 'montant': '500',
                            'carte_code': carte.code}],
                user=self.user)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, VenteComptoir.Statut.BROUILLON)
        carte.refresh_from_db()
        self.assertEqual(carte.solde, Decimal('500.00'))

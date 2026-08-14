"""NTRET13 — Coupons à code unique (distinct de compta.CodePromotion).

Couvre : un coupon consommé refuse toute réutilisation au-delà de sa limite
(1×/client ET N× global), un code expiré est refusé, la remise calculée
correspond à la règle liée, et l'intégration caisse (apps.pos.services)
consomme réellement le coupon (utilise_par/utilise_le posés une seule fois).
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.pos import services as pos_services
from apps.pos.models import LigneVenteComptoir, VenteComptoir
from apps.promotions import services as promo_services
from apps.promotions.models import CouponUnique, CouponUtilisation, ReglexPromotion
from apps.stock.models import Categorie, Produit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy='responsable')


class CouponServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret13', 'NTRET13 Co')
        self.user = make_user(self.co, 'ntret13-user')
        self.client_a = Client.objects.create(company=self.co, nom='Client A')
        self.client_b = Client.objects.create(company=self.co, nom='Client B')
        self.regle = ReglexPromotion.objects.create(
            company=self.co, nom='Remise coupon', type_regle='remise_montant_panier',
            remise_montant=Decimal('50'))

    def _lignes(self, prix='200'):
        categorie = Categorie.objects.create(company=self.co, nom=f'Cat-{prix}')
        produit = Produit.objects.create(
            company=self.co, nom=f'Produit-{prix}', prix_vente=Decimal(prix),
            prix_achat=Decimal('10'), quantite_stock=10, categorie=categorie)
        vente = VenteComptoir.objects.create(
            company=self.co, reference=f'VC-CPN-{prix}', created_by=self.user)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=produit, designation=produit.nom,
            quantite=1, prix_unitaire_ttc=Decimal(prix))
        return vente

    def test_valider_coupon_unknown_code_refused(self):
        with self.assertRaises(promo_services.CouponError):
            promo_services.valider_coupon(self.co, 'INTROUVABLE')

    def test_valider_coupon_expired_refused(self):
        coupon = CouponUnique.objects.create(
            company=self.co, regle=self.regle,
            date_expiration=datetime.date(2020, 1, 1))
        with self.assertRaises(promo_services.CouponError):
            promo_services.valider_coupon(self.co, coupon.code)

    def test_valider_coupon_inactif_refused(self):
        coupon = CouponUnique.objects.create(
            company=self.co, regle=self.regle, actif=False)
        with self.assertRaises(promo_services.CouponError):
            promo_services.valider_coupon(self.co, coupon.code)

    def test_consommer_coupon_computes_correct_discount(self):
        coupon = CouponUnique.objects.create(company=self.co, regle=self.regle)
        vente = self._lignes(prix='200')
        consumed, montant = promo_services.consommer_coupon(
            self.co, coupon.code, vente.lignes.all())
        self.assertEqual(montant, Decimal('50.00'))
        self.assertEqual(consumed.id, coupon.id)

    def test_consommer_coupon_sets_utilise_par_le_once(self):
        coupon = CouponUnique.objects.create(company=self.co, regle=self.regle)
        vente = self._lignes()
        promo_services.consommer_coupon(
            self.co, coupon.code, vente.lignes.all(), client=self.client_a)
        coupon.refresh_from_db()
        premiere_date = coupon.utilise_le
        self.assertEqual(coupon.utilise_par_id, self.client_a.id)
        self.assertIsNotNone(premiere_date)

        # Réutilisation par un AUTRE client (mode global, limite par défaut
        # 1 — donc refusée ici) : utilise_par/utilise_le NE bougent PAS.
        coupon.limite_usage = 5
        coupon.save(update_fields=['limite_usage'])
        vente2 = self._lignes(prix='150')
        promo_services.consommer_coupon(
            self.co, coupon.code, vente2.lignes.all(), client=self.client_b)
        coupon.refresh_from_db()
        self.assertEqual(coupon.utilise_par_id, self.client_a.id)  # inchangé
        self.assertEqual(coupon.utilise_le, premiere_date)  # inchangé

    def test_global_mode_refuses_beyond_limit(self):
        coupon = CouponUnique.objects.create(
            company=self.co, regle=self.regle,
            mode_limite=CouponUnique.ModeLimite.GLOBAL, limite_usage=2)
        vente1 = self._lignes(prix='100')
        vente2 = self._lignes(prix='110')
        vente3 = self._lignes(prix='120')
        promo_services.consommer_coupon(self.co, coupon.code, vente1.lignes.all())
        promo_services.consommer_coupon(self.co, coupon.code, vente2.lignes.all())
        with self.assertRaises(promo_services.CouponError):
            promo_services.consommer_coupon(self.co, coupon.code, vente3.lignes.all())
        self.assertEqual(CouponUtilisation.objects.filter(coupon=coupon).count(), 2)

    def test_unique_par_client_mode_refuses_same_client_twice(self):
        coupon = CouponUnique.objects.create(
            company=self.co, regle=self.regle,
            mode_limite=CouponUnique.ModeLimite.UNIQUE_PAR_CLIENT)
        vente1 = self._lignes(prix='100')
        vente2 = self._lignes(prix='90')
        promo_services.consommer_coupon(
            self.co, coupon.code, vente1.lignes.all(), client=self.client_a)
        with self.assertRaises(promo_services.CouponError):
            promo_services.consommer_coupon(
                self.co, coupon.code, vente2.lignes.all(), client=self.client_a)

    def test_unique_par_client_mode_allows_different_clients(self):
        coupon = CouponUnique.objects.create(
            company=self.co, regle=self.regle,
            mode_limite=CouponUnique.ModeLimite.UNIQUE_PAR_CLIENT)
        vente1 = self._lignes(prix='100')
        vente2 = self._lignes(prix='90')
        promo_services.consommer_coupon(
            self.co, coupon.code, vente1.lignes.all(), client=self.client_a)
        # Un AUTRE client peut utiliser le même coupon (pas de limite globale
        # en mode unique_par_client, seulement 1×/client).
        promo_services.consommer_coupon(
            self.co, coupon.code, vente2.lignes.all(), client=self.client_b)
        self.assertEqual(CouponUtilisation.objects.filter(coupon=coupon).count(), 2)

    def test_unique_par_client_requires_client(self):
        coupon = CouponUnique.objects.create(
            company=self.co, regle=self.regle,
            mode_limite=CouponUnique.ModeLimite.UNIQUE_PAR_CLIENT)
        with self.assertRaises(promo_services.CouponError):
            promo_services.valider_coupon(self.co, coupon.code, client=None)

    def test_code_generated_automatically_and_alphanumeric(self):
        coupon = CouponUnique.objects.create(company=self.co, regle=self.regle)
        self.assertEqual(len(coupon.code), 8)
        self.assertTrue(coupon.code.isalnum())

    def test_code_lookup_case_insensitive(self):
        coupon = CouponUnique.objects.create(company=self.co, regle=self.regle)
        found = promo_services.valider_coupon(self.co, coupon.code.lower())
        self.assertEqual(found.id, coupon.id)

    def test_isolation_multi_tenant(self):
        co_b = make_company('ntret13-b', 'B')
        coupon = CouponUnique.objects.create(company=self.co, regle=self.regle)
        with self.assertRaises(promo_services.CouponError):
            promo_services.valider_coupon(co_b, coupon.code)


class CouponPosIntegrationTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret13-pos', 'NTRET13 POS Co')
        self.user = make_user(self.co, 'ntret13-pos-user')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        self.categorie = Categorie.objects.create(company=self.co, nom='Divers')
        self.produit = Produit.objects.create(
            company=self.co, nom='Accessoire', prix_vente=Decimal('300'),
            prix_achat=Decimal('150'), quantite_stock=20, categorie=self.categorie)
        self.regle = ReglexPromotion.objects.create(
            company=self.co, nom='Remise caisse', type_regle='remise_montant_panier',
            remise_montant=Decimal('40'))

    def _vente(self):
        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-CPN-POS', client=self.client_obj,
            created_by=self.user)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation=self.produit.nom,
            quantite=1, prix_unitaire_ttc=Decimal('300'))
        return vente

    def test_appliquer_coupon_from_caisse_consumes_and_returns_discount(self):
        coupon = CouponUnique.objects.create(company=self.co, regle=self.regle)
        vente = self._vente()
        consumed, montant = pos_services.appliquer_coupon(
            vente=vente, code=coupon.code, user=self.user)
        self.assertEqual(montant, Decimal('40.00'))
        coupon.refresh_from_db()
        self.assertEqual(coupon.utilise_par_id, self.client_obj.id)

    def test_appliquer_coupon_invalid_code_raises_pos_error(self):
        vente = self._vente()
        with self.assertRaises(pos_services.CouponPosError):
            pos_services.appliquer_coupon(vente=vente, code='INVALIDE', user=self.user)

    def test_appliquer_coupon_reused_beyond_limit_raises(self):
        coupon = CouponUnique.objects.create(company=self.co, regle=self.regle)
        vente1 = self._vente()
        pos_services.appliquer_coupon(vente=vente1, code=coupon.code, user=self.user)
        vente2 = self._vente()
        with self.assertRaises(pos_services.CouponPosError):
            pos_services.appliquer_coupon(vente=vente2, code=coupon.code, user=self.user)

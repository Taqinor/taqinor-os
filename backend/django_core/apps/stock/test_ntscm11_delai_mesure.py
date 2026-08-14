"""NTSCM11 — délai fournisseur MESURÉ vs ANNONCÉ (par produit).

Critère d'acceptation testé : si le délai réel mesuré dépasse le délai annoncé
de PLUS DE 20 %, le point de commande recalculé (NTSCM6) utilise le délai
RÉEL — vérifié en comparant les DEUX scénarios (sous le seuil / au-dessus).

Toutes les dates sont FIXES et injectées.

Run :
    python manage.py test apps.stock.test_ntscm11_delai_mesure -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    PrixFournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.selectors import (
    delai_mesure_vs_annonce, point_de_commande_avec_delai_reel,
)

User = get_user_model()

AUJOURDHUI = datetime.date(2026, 6, 30)
COMMANDE_LE = datetime.date(2026, 6, 1)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntscm11Base(TestCase):
    def setUp(self):
        self.company = make_company('ntscm11-co', 'NTSCM11 Co')
        self.autre = make_company('ntscm11-autre', 'NTSCM11 Autre')
        self.admin = User.objects.create_user(
            username='ntscm11_admin', password='x', role_legacy='admin',
            company=self.company)
        self.normal = User.objects.create_user(
            username='ntscm11_normal', password='x', role_legacy='normal',
            company=self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTSCM11')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 5 kW', sku='OND5-NTSCM11',
            fournisseur=self.fournisseur, prix_achat=Decimal('7000'),
            prix_vente=Decimal('9000'), quantite_stock=100)
        # Délai ANNONCÉ au catalogue : 10 jours.
        self.tarif = PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('7000'),
            delai_livraison_jours=10)
        self._seq = 0

    def _livraison(self, jours_reels):
        self._seq += 1
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-NTSCM11-{self._seq:04d}',
            fournisseur=self.fournisseur, date_commande=COMMANDE_LE)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=5,
            quantite_recue=5, prix_achat_unitaire=Decimal('7000'))
        ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-NTSCM11-{self._seq:04d}',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=COMMANDE_LE + datetime.timedelta(days=jours_reels))
        return bc


class Ntscm11DelaiTests(Ntscm11Base):
    def test_ecart_sous_le_seuil_garde_le_delai_annonce(self):
        # Réel 11 j vs annoncé 10 j = +10 % (< 20 %).
        self._livraison(11)

        res = delai_mesure_vs_annonce(
            self.company, self.fournisseur, self.produit,
            aujourdhui=AUJOURDHUI)

        self.assertEqual(res['delai_annonce_jours'], 10)
        self.assertEqual(res['delai_mesure_jours'], 11)
        self.assertEqual(res['ecart_pct'], '10')
        self.assertFalse(res['utiliser_delai_reel'])
        self.assertEqual(res['delai_retenu_jours'], 10)

    def test_ecart_au_dessus_du_seuil_impose_le_delai_reel(self):
        # Réel 18 j vs annoncé 10 j = +80 % (> 20 %).
        self._livraison(18)

        res = delai_mesure_vs_annonce(
            self.company, self.fournisseur, self.produit,
            aujourdhui=AUJOURDHUI)

        self.assertEqual(res['ecart_pct'], '80')
        self.assertTrue(res['utiliser_delai_reel'])
        self.assertEqual(res['delai_retenu_jours'], 18)

    def test_lecart_type_est_calcule_des_deux_mesures(self):
        self._livraison(10)
        self._livraison(20)
        res = delai_mesure_vs_annonce(
            self.company, self.fournisseur, self.produit,
            aujourdhui=AUJOURDHUI)
        self.assertEqual(res['nb_mesures'], 2)
        self.assertEqual(res['delai_mesure_jours'], 15)
        self.assertEqual(res['ecart_type_jours'], 5.0)

    def test_sans_mesure_on_retombe_sur_le_delai_annonce(self):
        res = delai_mesure_vs_annonce(
            self.company, self.fournisseur, self.produit,
            aujourdhui=AUJOURDHUI)
        self.assertEqual(res['nb_mesures'], 0)
        self.assertIsNone(res['delai_mesure_jours'])
        self.assertFalse(res['utiliser_delai_reel'])
        self.assertEqual(res['delai_retenu_jours'], 10)

    def test_le_seuil_est_configurable(self):
        self._livraison(11)  # +10 %
        res = delai_mesure_vs_annonce(
            self.company, self.fournisseur, self.produit,
            aujourdhui=AUJOURDHUI, seuil_ecart_pct='5')
        self.assertTrue(res['utiliser_delai_reel'])

    def test_aucune_mesure_dune_autre_societe(self):
        self._livraison(18)
        autre_fournisseur = Fournisseur.objects.create(
            company=self.autre, nom='Voisin NTSCM11')
        res = delai_mesure_vs_annonce(
            self.autre, autre_fournisseur, aujourdhui=AUJOURDHUI)
        self.assertEqual(res['nb_mesures'], 0)


class Ntscm11PointDeCommandeTests(Ntscm11Base):
    def test_les_deux_scenarios_donnent_deux_points_de_commande(self):
        # Scénario 1 — écart sous le seuil : délai annoncé (10 j).
        self._livraison(11)
        sous_seuil = point_de_commande_avec_delai_reel(
            self.company, self.produit, avg_daily_consumption=2,
            aujourdhui=AUJOURDHUI)
        self.assertEqual(sous_seuil['lead_time_days'], 10)

        # Scénario 2 — une livraison très en retard fait basculer la moyenne.
        self._livraison(25)
        au_dessus = point_de_commande_avec_delai_reel(
            self.company, self.produit, avg_daily_consumption=2,
            aujourdhui=AUJOURDHUI)

        self.assertTrue(au_dessus['delai']['utiliser_delai_reel'])
        self.assertEqual(au_dessus['lead_time_days'], 18)
        self.assertGreater(au_dessus['reorder_point'],
                           sous_seuil['reorder_point'])

    def test_un_produit_sans_fournisseur_retombe_a_zero(self):
        orphelin = Produit.objects.create(
            company=self.company, nom='Sans fournisseur', sku='ORPH-NTSCM11',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=5)
        res = point_de_commande_avec_delai_reel(
            self.company, orphelin, avg_daily_consumption=1,
            aujourdhui=AUJOURDHUI)
        self.assertEqual(res['lead_time_days'], 0)
        self.assertIsNone(res['delai'])


class Ntscm11ApiTests(Ntscm11Base):
    def _url(self):
        return (f'/api/django/stock/fournisseurs/{self.fournisseur.id}/'
                'delai-mesure/')

    def test_endpoint_expose_lecart(self):
        self._livraison(18)
        res = auth(self.admin).get(self._url(), {'produit': self.produit.id})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['utiliser_delai_reel'])

    def test_endpoint_refuse_un_role_normal(self):
        self.assertEqual(auth(self.normal).get(self._url()).status_code, 403)

    def test_endpoint_refuse_lanonyme(self):
        self.assertEqual(APIClient().get(self._url()).status_code, 401)

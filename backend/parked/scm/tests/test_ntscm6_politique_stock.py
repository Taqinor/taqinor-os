"""NTSCM6 — Politique de stock par classe (min/max, ROP, SS).

Critère d'acceptation : un produit classé A avec forte variabilité obtient un
ROP strictement supérieur à un produit classé C à consommation identique
mais stable, vérifié par test.

``Produit``/``MouvementStock`` créés directement via ``apps.stock.models``
UNIQUEMENT pour construire la fixture de test (même justification que les
tests NTSCM2/3/5)."""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.scm.models import ClassificationABC, PolitiqueStock
from apps.scm.services import recalculer_politiques_stock
from apps.stock.models import MouvementStock, Produit

from .helpers import make_company

# Même moyenne mensuelle (300 -> 10/jour) pour les deux produits : seule la
# VARIABILITÉ et la CLASSE ABC diffèrent.
STABLE_SERIES = [300, 300, 300, 300, 300, 300]
VOLATILE_SERIES = [50, 600, 80, 500, 60, 510]


class RecalculerPolitiquesStockTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-pol', 'Supply Politiques')
        self.produit_a = Produit.objects.create(
            company=self.company, nom='Onduleur (classe A, volatil)',
            prix_vente=8000, quantite_stock=500)
        self.produit_c = Produit.objects.create(
            company=self.company, nom='Vis inox (classe C, stable)',
            prix_vente=2, quantite_stock=5000)
        ClassificationABC.objects.create(
            company=self.company, produit=self.produit_a, classe='A',
            valeur_cumulee_ht=Decimal('0'), rang=1)
        ClassificationABC.objects.create(
            company=self.company, produit=self.produit_c, classe='C',
            valeur_cumulee_ht=Decimal('0'), rang=2)
        self._seed_mois(self.produit_a, VOLATILE_SERIES)
        self._seed_mois(self.produit_c, STABLE_SERIES)

    def _seed_mois(self, produit, quantites):
        today = timezone.localdate()
        idx_dernier = today.year * 12 + (today.month - 1) - 1
        qty_restante = 100000
        for offset, qte in zip(range(len(quantites) - 1, -1, -1), quantites):
            idx = idx_dernier - offset
            y, m0 = divmod(idx, 12)
            mvt = MouvementStock.objects.create(
                company=self.company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                quantite=qte, quantite_avant=qty_restante,
                quantite_apres=qty_restante - qte)
            qty_restante -= qte
            mvt.date = timezone.make_aware(timezone.datetime(y, m0 + 1, 15))
            mvt.save(update_fields=['date'])

    def test_class_a_volatile_gets_strictly_higher_rop_than_class_c_stable(self):
        politiques = recalculer_politiques_stock(self.company)
        self.assertEqual(len(politiques), 2)

        pol_a = PolitiqueStock.objects.get(company=self.company, produit=self.produit_a)
        pol_c = PolitiqueStock.objects.get(company=self.company, produit=self.produit_c)

        self.assertEqual(pol_a.classe_abc, 'A')
        self.assertEqual(pol_c.classe_abc, 'C')
        self.assertEqual(pol_a.service_level_pct, Decimal('95'))
        self.assertEqual(pol_c.service_level_pct, Decimal('85'))
        self.assertGreater(pol_a.stock_securite_calcule, pol_c.stock_securite_calcule)
        self.assertGreater(pol_a.point_commande, pol_c.point_commande)

    def test_manual_override_takes_precedence_over_calculated(self):
        recalculer_politiques_stock(self.company)
        pol_a = PolitiqueStock.objects.get(company=self.company, produit=self.produit_a)
        pol_a.stock_securite_manuel = Decimal('999')
        pol_a.save(update_fields=['stock_securite_manuel'])

        recalculer_politiques_stock(self.company)
        pol_a.refresh_from_db()
        # 15 (délai défaut) x 10 (conso/j) + 999 (override) = 1149.00
        self.assertEqual(pol_a.point_commande, Decimal('1149.00'))

    def test_personalized_service_level_survives_recalcul(self):
        recalculer_politiques_stock(self.company)
        pol_c = PolitiqueStock.objects.get(company=self.company, produit=self.produit_c)
        pol_c.service_level_pct = Decimal('99')
        pol_c.save(update_fields=['service_level_pct'])

        recalculer_politiques_stock(self.company)
        pol_c.refresh_from_db()
        self.assertEqual(pol_c.service_level_pct, Decimal('99'))

    def test_recalculer_endpoint(self):
        from .helpers import auth, make_user

        admin = make_user(self.company, 'scm-pol-admin', 'admin')
        resp = auth(admin).post(
            '/api/django/scm/politiques-stock/recalculer/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_politiques'], 2)

"""NTSCM5 — Stock de sécurité calculé au niveau de service.

Critère d'acceptation : pour une demande stable (σ≈0), le stock de sécurité
calculé tend vers le stock de sécurité minimal (borne basse configurable) ;
pour une demande volatile, il croît avec le niveau de service demandé —
vérifié par 3 tests paramétrés.

``core.safety_stock`` est une fonction PURE (``SimpleTestCase``, comme
``core/tests/test_stock_reorder.py``) ; ``appliquer_politique_stock``
(``apps.scm.services``) est testée séparément avec DB (historique de
sorties)."""
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.scm.services import appliquer_politique_stock
from apps.stock.models import MouvementStock, Produit
from core.safety_stock import Z_TABLE, compute_safety_stock, z_for_service_level

from .helpers import make_company


class ZForServiceLevelTests(SimpleTestCase):
    def test_standard_table_values(self):
        self.assertEqual(z_for_service_level(90), Z_TABLE[90.0])
        self.assertEqual(z_for_service_level(95), Z_TABLE[95.0])
        self.assertEqual(z_for_service_level(97.5), Z_TABLE[97.5])
        self.assertEqual(z_for_service_level(99), Z_TABLE[99.0])

    def test_unknown_level_falls_back_to_nearest(self):
        self.assertEqual(z_for_service_level(96), Z_TABLE[95.0])
        self.assertEqual(z_for_service_level(None), Z_TABLE[95.0])


class ComputeSafetyStockParametrizedTests(SimpleTestCase):
    def test_stable_demand_tends_to_the_minimal_floor(self):
        """σ≈0 : le stock de sécurité tend vers la borne basse, QUEL QUE
        SOIT le niveau de service demandé (aucun terme statistique à
        amplifier)."""
        floor = 3.0 * 20.0  # min_coverage_days=3 (défaut) x avg_demand=20
        ss_90 = compute_safety_stock(20.0, 0.0, lead_time_days=10, service_level_pct=90)
        ss_99 = compute_safety_stock(20.0, 0.0, lead_time_days=10, service_level_pct=99)
        self.assertEqual(ss_90, floor)
        self.assertEqual(ss_99, floor)

    def test_volatile_demand_grows_with_service_level(self):
        """σ>0 (assez grand pour dominer la borne basse) : un niveau de
        service plus élevé (z plus grand) produit un stock de sécurité
        strictement plus grand."""
        ss_90 = compute_safety_stock(10.0, 15.0, lead_time_days=10, service_level_pct=90)
        ss_95 = compute_safety_stock(10.0, 15.0, lead_time_days=10, service_level_pct=95)
        ss_99 = compute_safety_stock(10.0, 15.0, lead_time_days=10, service_level_pct=99)
        self.assertLess(ss_90, ss_95)
        self.assertLess(ss_95, ss_99)

    def test_high_service_level_beats_the_minimal_floor_when_volatile(self):
        """Le terme statistique (z × σ × √délai) dépasse la borne basse dès
        que la variabilité est significative — le stock de sécurité n'est
        alors plus juste "quelques jours de couverture"."""
        floor = 3.0 * 20.0
        ss_99 = compute_safety_stock(20.0, 15.0, lead_time_days=15, service_level_pct=99)
        self.assertGreater(ss_99, floor)


class AppliquerPolitiqueStockServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-safety', 'Supply Safety')
        self.produit = Produit.objects.create(
            company=self.company, nom='Câble solaire 6mm2', prix_vente=15,
            quantite_stock=1000)

    @staticmethod
    def _seed_mois(company, produit, quantites):
        today = timezone.localdate()
        idx_dernier = today.year * 12 + (today.month - 1) - 1
        qty_restante = 100000
        for offset, qte in zip(range(len(quantites) - 1, -1, -1), quantites):
            idx = idx_dernier - offset
            y, m0 = divmod(idx, 12)
            mvt = MouvementStock.objects.create(
                company=company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                quantite=qte, quantite_avant=qty_restante,
                quantite_apres=qty_restante - qte)
            qty_restante -= qte
            mvt.date = timezone.make_aware(timezone.datetime(y, m0 + 1, 15))
            mvt.save(update_fields=['date'])

    def test_stable_history_yields_low_safety_stock(self):
        self._seed_mois(self.company, self.produit, [300, 300, 300, 300, 300, 300])
        resultat = appliquer_politique_stock(
            self.produit, 95, self.company, lead_time_days=10, fenetre_mois=12)
        self.assertEqual(resultat['std_dev_daily'], 0.0)
        self.assertGreater(resultat['stock_securite'], 0)

    def test_volatile_history_yields_higher_safety_stock_than_stable(self):
        self._seed_mois(self.company, self.produit, [300, 300, 300, 300, 300, 300])
        stable = appliquer_politique_stock(
            self.produit, 95, self.company, lead_time_days=10, fenetre_mois=12)

        volatile_company = make_company('scm-safety-v', 'Supply Safety Volatile')
        volatile_produit = Produit.objects.create(
            company=volatile_company, nom='Câble solaire 6mm2 (volatil)',
            prix_vente=15, quantite_stock=1000)
        self._seed_mois(
            volatile_company, volatile_produit, [50, 600, 80, 500, 60, 550])
        volatile = appliquer_politique_stock(
            volatile_produit, 95, volatile_company, lead_time_days=10, fenetre_mois=12)

        self.assertGreater(volatile['std_dev_daily'], 0)
        self.assertGreater(volatile['stock_securite'], stable['stock_securite'])

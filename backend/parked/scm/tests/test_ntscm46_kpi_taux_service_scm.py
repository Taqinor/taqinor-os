"""NTSCM46 — KPI SCM dans le module reporting central.

Le KPI « taux de service SCM » (``apps.scm.selectors.tableau_bord_executif``,
NTSCM28) devient un membre de premier ordre du catalogue fermé
``reporting.KpiAlerte.Kpi`` — même mécanisme d'évaluation/notification
générique que les KPI existants (DSO, encours échu, valeur de stock…), même
patron que NTLOG51 (délai moyen de dédouanement).

Critère d'acceptation : le KPI apparaît dans la liste des KPI disponibles à
l'ajout d'un tableau de bord personnalisé et respecte un seuil d'alerte
configuré."""
from decimal import Decimal

from django.test import TestCase

from apps.scm.models import PolitiqueStock
from apps.stock.models import MouvementStock, Produit

from .helpers import auth, make_company, make_user


class KpiTauxServiceScmCatalogueTests(TestCase):
    """Le KPI est un membre du catalogue fermé et branché sur le registre des
    calculateurs — le MÊME mécanisme générique que les autres KPI."""

    def test_membre_du_catalogue_kpialerte(self):
        from apps.reporting.models import KpiAlerte
        self.assertIn('taux_service_scm', KpiAlerte.Kpi.values)

    def test_branche_sur_le_registre_des_calculateurs(self):
        from apps.reporting.kpi_alertes import _KPI_COMPUTERS
        from apps.reporting.models import KpiAlerte
        self.assertIn(KpiAlerte.Kpi.TAUX_SERVICE_SCM, _KPI_COMPUTERS)

    def test_disponible_a_lajout_dune_kpi_alerte(self):
        """« Apparaît dans la liste des KPI disponibles à l'ajout » — le
        serializer expose `kpi_label` pour CE code, exactement comme les
        autres membres du catalogue."""
        from apps.reporting.kpi_alertes import KpiAlerteSerializer
        from apps.reporting.models import KpiAlerte
        company = make_company('scm-kpi-catalogue', 'Supply KPI Catalogue')
        alerte = KpiAlerte.objects.create(
            company=company, kpi=KpiAlerte.Kpi.TAUX_SERVICE_SCM,
            operateur=KpiAlerte.Operateur.INF, seuil=Decimal('90'))
        data = KpiAlerteSerializer(alerte).data
        self.assertEqual(data['kpi'], 'taux_service_scm')
        self.assertEqual(data['kpi_label'], 'Supply chain — taux de service (%)')


class EvaluateKpiTauxServiceScmTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-kpi-eval', 'Supply KPI Éval')
        self.admin = make_user(self.company, 'scm-kpi-eval-admin', 'admin')
        self.produit_ok = Produit.objects.create(
            company=self.company, nom='Kit solaire 3kWc', prix_vente=20000,
            quantite_stock=100)
        self.produit_rupture = Produit.objects.create(
            company=self.company, nom='Batterie 5kWh', prix_vente=15000,
            quantite_stock=0)

    def test_seuil_dalerte_respecte(self):
        from apps.reporting.kpi_alertes import evaluate_kpi_alerte
        from apps.reporting.models import KpiAlerte

        # Politique confortable (jamais de réappro) -> statut 'ok'.
        PolitiqueStock.objects.create(
            company=self.company, produit=self.produit_ok, classe_abc='A',
            service_level_pct=Decimal('95'), point_commande=Decimal('1'),
            stock_securite_calcule=Decimal('1'))
        # Consommation soutenue + stock à 0 -> `predict_reorder` calcule une
        # VRAIE date de rupture (jamais `reorder_now=False` par garde-fou
        # division par zéro, voir `core.stock_reorder.predict_reorder`) ->
        # statut rupture_imminente/à_commander.
        for _i in range(6):
            MouvementStock.objects.create(
                company=self.company, produit=self.produit_rupture,
                type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                quantite=20, quantite_avant=100, quantite_apres=80)
        PolitiqueStock.objects.create(
            company=self.company, produit=self.produit_rupture, classe_abc='A',
            service_level_pct=Decimal('95'), point_commande=Decimal('50'),
            stock_securite_calcule=Decimal('20'))

        alerte = KpiAlerte.objects.create(
            company=self.company, kpi=KpiAlerte.Kpi.TAUX_SERVICE_SCM,
            operateur=KpiAlerte.Operateur.INF, seuil=Decimal('90'))

        valeur, franchi, _notifie = evaluate_kpi_alerte(alerte)
        self.assertIsNotNone(valeur)
        # 1 produit OK / 2 politiques = 50% < seuil 90% -> alerte franchie.
        self.assertEqual(valeur, Decimal('50'))
        self.assertTrue(franchi)

    def test_aucune_politique_de_stock_valeur_none(self):
        from apps.reporting.kpi_alertes import evaluate_kpi_alerte
        from apps.reporting.models import KpiAlerte

        alerte = KpiAlerte.objects.create(
            company=self.company, kpi=KpiAlerte.Kpi.TAUX_SERVICE_SCM,
            operateur=KpiAlerte.Operateur.INF, seuil=Decimal('90'))
        valeur, franchi, _notifie = evaluate_kpi_alerte(alerte)
        self.assertIsNone(valeur)
        self.assertFalse(franchi)

    def test_endpoint_kpi_alerte_creation_admin(self):
        resp = auth(self.admin).post('/api/django/reporting/kpi-alertes/', {
            'kpi': 'taux_service_scm', 'operateur': 'inf', 'seuil': '90',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

"""NTMFG40 — KPI Production dans `reporting.Kpi`/Dashboard consolidé de
l'entreprise.

Critère : les 3 KPI apparaissent dans le catalogue de KPI disponibles pour
composer un dashboard (ARC40, `GET /reporting/reports/kpi-federes/`), valeurs
identiques à l'écran dédié NTMFG22 sur le même jeu de données, isolation
tenant."""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import OrdreFabrication
from apps.mrp.selectors import kpi_production, tableau_bord_production
from apps.stock.models import Produit
from core import platform as core_platform

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


class KpiProductionProviderTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ntmfg40-1', 'MRP NTMFG40 1')

    def test_provider_declare_dans_le_registre_plateforme(self):
        self.assertIn(
            'apps.mrp.selectors.kpi_production',
            core_platform.kpi_providers(self.company))

    def test_3_tuiles_avec_ids_stables(self):
        tuiles = kpi_production(self.company)
        ids = {t['id'] for t in tuiles}
        self.assertEqual(
            ids, {'mrp_taux_charge_atelier', 'mrp_trs_moyen', 'mrp_of_en_retard'})
        for tuile in tuiles:
            self.assertIn('label', tuile)
            self.assertIn('valeur', tuile)

    def test_valeurs_identiques_au_tableau_de_bord_ntmfg22(self):
        produit = make_produit(self.company)
        OrdreFabrication.objects.create(
            company=self.company, produit=produit, quantite=1,
            statut=OrdreFabrication.Statut.PLANIFIE)

        donnees = tableau_bord_production(self.company)
        tuiles = {t['id']: t['valeur'] for t in kpi_production(self.company)}

        self.assertEqual(
            tuiles['mrp_taux_charge_atelier'], donnees['charge_moyenne_pct'])
        self.assertEqual(tuiles['mrp_trs_moyen'], donnees['trs_moyen_pct'])
        self.assertEqual(tuiles['mrp_of_en_retard'], donnees['of_en_retard'])

    def test_isolation_tenant(self):
        from django.utils import timezone

        autre_company = make_company('mrp-ntmfg40-2', 'MRP NTMFG40 2')
        autre_produit = make_produit(autre_company, 'Autre produit')
        OrdreFabrication.objects.create(
            company=autre_company, produit=autre_produit, quantite=1,
            statut=OrdreFabrication.Statut.PLANIFIE,
            date_fin_planifiee=timezone.now() - timezone.timedelta(days=1))
        # L'OF en retard appartient à `autre_company` : le KPI de `self.company`
        # (aucun OF) reste à 0, jamais gonflé par une autre société.
        tuiles_moi = {t['id']: t['valeur'] for t in kpi_production(self.company)}
        self.assertEqual(tuiles_moi['mrp_of_en_retard'], 0)


class KpiFederesEndpointTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ntmfg40-api-1', 'MRP NTMFG40 API 1')
        self.responsable = make_user(
            self.company, 'mrp-ntmfg40-resp', role='responsable')

    def test_tuiles_mrp_visibles_dans_le_hub_kpi_federe(self):
        resp = auth(self.responsable).get('/api/django/reporting/reports/kpi-federes/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {t['id'] for t in resp.data['tuiles']}
        self.assertTrue({'mrp_taux_charge_atelier', 'mrp_trs_moyen', 'mrp_of_en_retard'}.issubset(ids))

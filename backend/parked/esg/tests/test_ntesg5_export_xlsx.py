"""NTESG5 — Export xlsx ESG multi-feuilles.

Critère d'acceptation : le classeur s'ouvre avec 4 feuilles cohérentes au
centime avec le PDF NTESG4 pour la même période (même source de données,
``selectors.donnees_effectives_periode``) ; les lignes sans donnée ne sont
jamais ajoutées.
"""
from datetime import date

from django.test import TestCase

from testkit.factories import CompanyFactory

from apps.esg.esg_export import build_esg_workbook
from apps.esg.models import PeriodeReportingESG


def _make_periode(company):
    return PeriodeReportingESG.objects.create(
        company=company, libelle='T1 2026',
        date_debut=date(2026, 1, 1), date_fin=date(2026, 3, 31))


class EsgExportXlsxTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def test_workbook_has_four_sheets(self):
        periode = _make_periode(self.company)
        wb = build_esg_workbook(periode)
        self.assertEqual(
            wb.sheetnames,
            ['Environnement', 'Social', 'Gouvernance', 'Méthodologie'])

    def test_empty_company_has_no_data_rows_only_headers(self):
        periode = _make_periode(self.company)
        wb = build_esg_workbook(periode)
        env_ws = wb['Environnement']
        # Une seule ligne : l'en-tête (aucune ligne à valeur vide ajoutée).
        self.assertEqual(env_ws.max_row, 1)

    def test_carburant_flotte_row_present_when_available(self):
        from apps.flotte.models import PleinCarburant, Vehicule

        vehicule = Vehicule.objects.create(
            company=self.company, immatriculation='1234-A-12',
            energie=Vehicule.Energie.DIESEL)
        PleinCarburant.objects.create(
            company=self.company, vehicule=vehicule,
            date_plein=date(2026, 2, 1), kilometrage=1000,
            quantite=50, unite=PleinCarburant.Unite.LITRE)
        periode = _make_periode(self.company)
        wb = build_esg_workbook(periode)
        env_ws = wb['Environnement']
        libelles = [row[0].value for row in env_ws.iter_rows(min_row=2)]
        self.assertTrue(
            any('gasoil' in (lbl or '').lower() for lbl in libelles))

    def test_methodologie_sheet_documents_unavailable_sources(self):
        periode = _make_periode(self.company)
        wb = build_esg_workbook(periode)
        meth_ws = wb['Méthodologie']
        cles = [row[0].value for row in meth_ws.iter_rows(min_row=2)]
        self.assertTrue(any('bilan_carbone' in (c or '') for c in cles))

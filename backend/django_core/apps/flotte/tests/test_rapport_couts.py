"""Tests XFLT7 — Rapport d'analyse des coûts (pivot + benchmark).

Couvre :
- Selector ``analyse_couts_report(company, group_by=...)`` :
  - pivot correct sur données multi-véhicules (group_by vehicule/categorie) ;
  - coût/km par véhicule ;
  - benchmark : outlier de consommation (>20% au-dessus de la médiane du
    modèle) signalé, véhicule seul de son modèle jamais outlier.
- Endpoint ``GET /flotte/rapports/couts/`` :
  - pivot JSON par défaut (lecture tout rôle) ;
  - export XLSX via ``?export=xlsx`` (JAMAIS ``?format=``).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import ActifFlotte, CoutVehicule, Vehicule
from apps.flotte.selectors import analyse_couts_report

User = get_user_model()

URL = "/api/django/flotte/rapports/couts/"


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


class AnalyseCoutsReportSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("rap-couts", "Rap Couts")
        self.veh1 = Vehicule.objects.create(
            company=self.co, immatriculation="RC1", energie="diesel",
            kilometrage=10000)
        self.actif1 = ActifFlotte.objects.create(
            company=self.co, vehicule=self.veh1)
        self.veh2 = Vehicule.objects.create(
            company=self.co, immatriculation="RC2", energie="diesel",
            kilometrage=5000)
        self.actif2 = ActifFlotte.objects.create(
            company=self.co, vehicule=self.veh2)

        CoutVehicule.objects.create(
            company=self.co, actif_flotte=self.actif1, categorie="peage",
            date=datetime.date(2026, 6, 1), montant=100)
        CoutVehicule.objects.create(
            company=self.co, actif_flotte=self.actif2, categorie="lavage",
            date=datetime.date(2026, 6, 15), montant=50)

    def test_pivot_par_vehicule(self):
        result = analyse_couts_report(self.co, group_by='vehicule')
        totaux = {p['cle']: p['total'] for p in result['pivot']}
        self.assertEqual(totaux[self.veh1.id], 100.0)
        self.assertEqual(totaux[self.veh2.id], 50.0)

    def test_pivot_par_categorie(self):
        result = analyse_couts_report(self.co, group_by='categorie')
        totaux = {p['cle']: p['total'] for p in result['pivot']}
        self.assertEqual(totaux['peage'], 100.0)
        self.assertEqual(totaux['lavage'], 50.0)

    def test_cout_par_km(self):
        result = analyse_couts_report(self.co, group_by='vehicule')
        par_veh = {p['vehicule_id']: p for p in result['par_vehicule']}
        self.assertEqual(
            par_veh[self.veh1.id]['cout_par_km'], round(100 / 10000, 3))

    def test_cout_par_km_none_si_distance_nulle(self):
        veh3 = Vehicule.objects.create(
            company=self.co, immatriculation="RC3", energie="diesel",
            kilometrage=0)
        result = analyse_couts_report(self.co, group_by='vehicule')
        par_veh = {p['vehicule_id']: p for p in result['par_vehicule']}
        self.assertIsNone(par_veh[veh3.id]['cout_par_km'])

    def test_outlier_signale(self):
        from apps.flotte.models import PleinCarburant

        # Trois véhicules du même modèle : 2 consomment ~7L/100km, un ~10L/100km.
        veh_a = Vehicule.objects.create(
            company=self.co, immatriculation="OUT-A", energie="diesel",
            marque="Renault", modele="Kangoo")
        veh_b = Vehicule.objects.create(
            company=self.co, immatriculation="OUT-B", energie="diesel",
            marque="Renault", modele="Kangoo")
        veh_c = Vehicule.objects.create(
            company=self.co, immatriculation="OUT-C", energie="diesel",
            marque="Renault", modele="Kangoo")

        for veh, conso in ((veh_a, 7.0), (veh_b, 7.2), (veh_c, 10.0)):
            PleinCarburant.objects.create(
                company=self.co, vehicule=veh,
                date_plein=datetime.date(2026, 5, 1), kilometrage=0,
                quantite=0, prix_total=0)
            PleinCarburant.objects.create(
                company=self.co, vehicule=veh,
                date_plein=datetime.date(2026, 5, 2), kilometrage=1000,
                quantite=conso * 10, prix_total=1000)

        result = analyse_couts_report(self.co, group_by='vehicule')
        outlier_ids = {o['vehicule_id'] for o in result['outliers']}
        self.assertIn(veh_c.id, outlier_ids)
        self.assertNotIn(veh_a.id, outlier_ids)

    def test_seul_de_son_modele_jamais_outlier(self):
        from apps.flotte.models import PleinCarburant

        veh_unique = Vehicule.objects.create(
            company=self.co, immatriculation="UNIQ", energie="diesel",
            marque="Iveco", modele="Daily")
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh_unique,
            date_plein=datetime.date(2026, 5, 1), kilometrage=0,
            quantite=0, prix_total=0)
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh_unique,
            date_plein=datetime.date(2026, 5, 2), kilometrage=1000,
            quantite=500, prix_total=1000)
        result = analyse_couts_report(self.co, group_by='vehicule')
        outlier_ids = {o['vehicule_id'] for o in result['outliers']}
        self.assertNotIn(veh_unique.id, outlier_ids)


class RapportCoutsApiTests(TestCase):
    def setUp(self):
        self.co = make_company("rap-api", "Rap Api")
        self.admin = make_user(self.co, "rap-admin", "admin")
        self.user_normal = make_user(self.co, "rap-user", "normal")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="RAPAPI", energie="diesel",
            kilometrage=1000)
        self.actif = ActifFlotte.objects.create(
            company=self.co, vehicule=self.veh)
        CoutVehicule.objects.create(
            company=self.co, actif_flotte=self.actif, categorie="peage",
            date=datetime.date(2026, 6, 1), montant=75)

    def test_read_any_role(self):
        resp = auth(self.user_normal).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('pivot', resp.data)

    def test_export_xlsx(self):
        resp = auth(self.admin).get(f"{URL}?export=xlsx")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            'spreadsheetml',
            resp['Content-Type'])

    def test_group_by_invalide_retombe_vehicule(self):
        resp = auth(self.admin).get(f"{URL}?group_by=n_importe_quoi")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['group_by'], 'vehicule')

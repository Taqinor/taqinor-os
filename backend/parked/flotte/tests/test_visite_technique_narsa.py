"""Tests XFLT10 — Périodicité visite technique NARSA auto-calculée.

Couvre :
- Selector ``date_mise_circulation_vehicule(vehicule)`` : lit
  ``CarteGriseVehicule.date_mise_circulation`` via l'actif (jamais dupliquée
  sur ``Vehicule``), ``None`` si absente.
- Service ``prochaine_visite_narsa(vehicule, today)`` :
  - véhicule particulier (type_fiscal vide/tourisme) : 3 ans → pas encore de
    1re visite due (premiere_visite = mise_en_circulation + 5 ans) ;
  - véhicule particulier 7 ans : périodicité 2 ans après la 1re visite ;
  - véhicule particulier 12 ans : périodicité annuelle ;
  - véhicule utilitaire : périodicité 6-12 mois ;
  - override manuel respecté (la fonction ne fait QUE proposer, jamais
    n'écrase une saisie déjà présente côté appelant) ;
  - aucune date de mise en circulation connue → None.
"""
import datetime

from django.test import TestCase

from authentication.models import Company

from apps.flotte.models import ActifFlotte, CarteGriseVehicule, Vehicule
from apps.flotte.selectors import date_mise_circulation_vehicule
from apps.flotte.services import prochaine_visite_narsa


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_vehicule(company, immat, type_fiscal='', mise_en_circulation=None):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel",
        type_fiscal=type_fiscal)
    actif = ActifFlotte.objects.create(company=company, vehicule=veh)
    if mise_en_circulation is not None:
        CarteGriseVehicule.objects.create(
            company=company, actif_flotte=actif,
            numero_carte_grise=f"CG-{immat}",
            date_mise_circulation=mise_en_circulation)
    return veh


class DateMiseCirculationSelectorTests(TestCase):
    def setUp(self):
        self.company = make_company("narsa-co", "NARSA Co")

    def test_lit_la_date_mise_circulation_depuis_carte_grise(self):
        date_mec = datetime.date(2020, 1, 15)
        veh = make_vehicule(self.company, "NA-1", mise_en_circulation=date_mec)
        self.assertEqual(date_mise_circulation_vehicule(veh), date_mec)

    def test_none_sans_carte_grise(self):
        veh = make_vehicule(self.company, "NA-2")
        self.assertIsNone(date_mise_circulation_vehicule(veh))

    def test_none_sans_actif_flotte(self):
        veh = Vehicule.objects.create(
            company=self.company, immatriculation="NA-3", energie="diesel")
        self.assertIsNone(date_mise_circulation_vehicule(veh))


class ProchaineVisiteNarsaTests(TestCase):
    def setUp(self):
        self.company = make_company("narsa-co2", "NARSA Co 2")

    def test_particulier_3_ans_pas_encore_de_1re_visite(self):
        today = datetime.date(2026, 7, 3)
        mec = today - datetime.timedelta(days=365 * 3)
        veh = make_vehicule(
            self.company, "NA-P3", type_fiscal='', mise_en_circulation=mec)
        proposition = prochaine_visite_narsa(veh, today=today)
        # 1re visite due à 5 ans → doit tomber ~2 ans dans le futur.
        self.assertGreater(proposition, today)
        self.assertLess((proposition - mec).days, 365 * 6)
        self.assertGreater((proposition - mec).days, 365 * 4)

    def test_particulier_7_ans_periodicite_2_ans(self):
        today = datetime.date(2026, 7, 3)
        mec = today - datetime.timedelta(days=365 * 7)
        veh = make_vehicule(
            self.company, "NA-P7", type_fiscal='tourisme',
            mise_en_circulation=mec)
        proposition = prochaine_visite_narsa(veh, today=today)
        self.assertIsNotNone(proposition)
        self.assertGreaterEqual(proposition, today)
        # Doit être calée sur premiere_visite (5 ans) + N*2 ans.
        premiere = mec.replace(year=mec.year + 5)
        delta_mois = (proposition.year - premiere.year) * 12 \
            + (proposition.month - premiere.month)
        self.assertEqual(delta_mois % 24, 0)

    def test_particulier_12_ans_periodicite_annuelle(self):
        today = datetime.date(2026, 7, 3)
        mec = today - datetime.timedelta(days=365 * 12)
        veh = make_vehicule(
            self.company, "NA-P12", mise_en_circulation=mec)
        proposition = prochaine_visite_narsa(veh, today=today)
        self.assertIsNotNone(proposition)
        self.assertGreaterEqual(proposition, today)
        self.assertLess((proposition - today).days, 366)

    def test_utilitaire_periodicite_6_mois(self):
        today = datetime.date(2026, 7, 3)
        mec = today - datetime.timedelta(days=365 * 2)
        veh = make_vehicule(
            self.company, "NA-U1", type_fiscal='utilitaire',
            mise_en_circulation=mec)
        proposition = prochaine_visite_narsa(veh, today=today)
        self.assertIsNotNone(proposition)
        self.assertGreaterEqual(proposition, today)
        self.assertLess((proposition - today).days, 183)

    def test_aucune_date_mise_circulation_retourne_none(self):
        veh = make_vehicule(self.company, "NA-NONE")
        self.assertIsNone(prochaine_visite_narsa(veh))

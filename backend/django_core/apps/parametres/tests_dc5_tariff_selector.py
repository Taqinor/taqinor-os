"""DC5 — CompanyProfile est la SOURCE UNIQUE des repères ROI/tarifaires.

Le tarif ONEE et le productible étaient dupliqués (CompanyProfile vs
TariffSettings). DÉCISION : CompanyProfile est canonique (déjà consommé par le
moteur de devis via DC2). Tout lecteur passe par un accesseur UNIQUE,
``parametres.selectors.tariff_for``, qui lit CompanyProfile — et NON
TariffSettings — pour ces repères. Ces tests verrouillent ce choix.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.parametres.models import CompanyProfile
from apps.parametres.models_tariff import TariffSettings
from apps.parametres.selectors import tariff_for


def _company():
    c, _ = Company.objects.get_or_create(
        slug='dc5-co', defaults={'nom': 'DC5 Co'})
    return c


class TestDC5TariffSelector(TestCase):
    def test_tariff_for_reads_company_profile(self):
        company = _company()
        p = CompanyProfile.get(company=company)
        p.onee_tarif_kwh = Decimal('2.10')
        p.productible_kwh_kwc = Decimal('1750.0')
        p.rendement_global = Decimal('0.85')
        p.save()
        t = tariff_for(company)
        self.assertAlmostEqual(t['onee_tarif_kwh'], 2.10, places=3)
        self.assertAlmostEqual(t['productible_kwh_kwc'], 1750.0, places=1)
        self.assertAlmostEqual(t['rendement_global'], 0.85, places=3)

    def test_tariff_for_defaults_when_no_profile_fields(self):
        # profil vierge (défauts du modèle : 1.75 / 1600 / 0.8)
        t = tariff_for(_company())
        self.assertAlmostEqual(t['onee_tarif_kwh'], 1.75, places=3)
        self.assertAlmostEqual(t['productible_kwh_kwc'], 1600.0, places=1)
        self.assertAlmostEqual(t['rendement_global'], 0.8, places=3)

    def test_tariff_settings_edit_does_not_leak_into_tariff_for(self):
        # Le champ TariffSettings.productible_manuel n'est PAS la source du
        # repère ROI du devis : seul CompanyProfile l'est (source unique).
        company = _company()
        ts = TariffSettings.get(company=company)
        ts.productible_manuel_kwh_kwc = Decimal('1234.0')
        ts.save()
        t = tariff_for(company)
        self.assertNotAlmostEqual(t['productible_kwh_kwc'], 1234.0, places=1)
        self.assertAlmostEqual(t['productible_kwh_kwc'], 1600.0, places=1)

"""APDF39 (C-APDF-013) — le rapport de production énergétique lit le rendement
et le tarif de `parametres.selectors.tariff_for(company)` quand l'URL ne les
surcharge pas (repères du devis de la même société).

Rejoue PCHT-2 : « 1 600 kWh/kWc/an », « 1,40 MAD/kWh », « 8 800 kWh/an ».

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_apdf_rapport_energie"
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.installations.energy_report import render_energy_report_pdf
from apps.installations.models import Installation
from apps.parametres.models import CompanyProfile
from apps.crm.models import Client


def _texte(pdf):
    import fitz
    doc = fitz.open(stream=pdf, filetype='pdf')
    brut = ''.join(p.get_text() for p in doc)
    return ' '.join(brut.replace('\xa0', ' ').replace(' ', ' ').split())


class RapportEnergieReperesTests(TestCase):
    def _chantier(self, slug, tarif, productible):
        company = Company.objects.create(nom=slug, slug=slug)
        profil = CompanyProfile.get(company=company)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            onee_tarif_kwh=Decimal(tarif),
            productible_kwh_kwc=Decimal(productible))
        client = Client.objects.create(
            company=company, nom='Site', prenom=slug,
            email=f'{slug}@example.invalid')
        return Installation.objects.create(
            company=company, reference=f'CH-{slug}', client=client,
            puissance_installee_kwc=Decimal('5.50'))

    def test_reperes_societe(self):
        inst = self._chantier('apdf39-a', '2.10', '1500')
        texte = _texte(render_energy_report_pdf(inst, {}))
        self.assertIn('1 500 kWh/kWc/an', texte)
        self.assertIn('8 250 kWh/an', texte)
        self.assertIn('2,10 MAD/kWh', texte)

    def test_surcharge_url(self):
        inst = self._chantier('apdf39-b', '2.10', '1500')
        texte = _texte(render_energy_report_pdf(
            inst, {'tarif_mad_par_kwh': Decimal('1.9')}))
        self.assertIn('1,90 MAD/kWh', texte)
        self.assertIn('1 500 kWh/kWc/an', texte)

    def test_deux_societes(self):
        a = self._chantier('apdf39-c', '2.10', '1500')
        b = self._chantier('apdf39-d', '1.20', '1700')
        self.assertNotEqual(_texte(render_energy_report_pdf(a, {})),
                            _texte(render_energy_report_pdf(b, {})))

"""QJR662 (décision fondateur 01/10/2026, amende CAD166) — pour un lead
INDUSTRIEL ou COMMERCIAL sans conso saisie, le moteur se replie sur le kWh
mensuel déclaré sur le site (``bill_kwh``), en lecture seule. La conso saisie
prime toujours ; le résidentiel (et l'agricole) ne se replient jamais.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.crm.tests_conso_pro_repli"
"""
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.crm.selectors import conso_mensuelle_kwh_pour_devis
from apps.ventes.models import Devis
from authentication.models import Company


class ConsoProRepliTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR662 Co', slug='qjr662-co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR662',
            email='qjr662@example.test')
        self.n = 0

    def _devis(self, *, type_installation, bill_kwh=None, conso=None):
        self.n += 1
        lead = Lead.objects.create(
            company=self.company, nom=f'Lead {self.n}',
            telephone=f'+21260066200{self.n}', client=self.client_obj,
            type_installation=type_installation, bill_kwh=bill_kwh,
            conso_mensuelle_kwh=conso)
        return Devis.objects.create(
            company=self.company, reference=f'DEV-QJR662-{self.n}',
            client=self.client_obj, lead=lead, taux_tva=Decimal('20'))

    def test_industriel_sans_conso_lit_le_kwh_du_site(self):
        devis = self._devis(type_installation='industriel',
                            bill_kwh=Decimal('30000'))
        self.assertEqual(conso_mensuelle_kwh_pour_devis(devis), 30000.0)

    def test_commercial_sans_conso_lit_le_kwh_du_site(self):
        devis = self._devis(type_installation='commercial',
                            bill_kwh=Decimal('4500'))
        self.assertEqual(conso_mensuelle_kwh_pour_devis(devis), 4500.0)

    def test_residentiel_ne_se_replie_jamais(self):
        devis = self._devis(type_installation='residentiel',
                            bill_kwh=Decimal('30000'))
        self.assertIsNone(conso_mensuelle_kwh_pour_devis(devis))

    def test_agricole_ni_segment_vide_ne_se_replient(self):
        for segment in ('agricole', None):
            devis = self._devis(type_installation=segment,
                                bill_kwh=Decimal('30000'))
            self.assertIsNone(conso_mensuelle_kwh_pour_devis(devis), segment)

    def test_la_conso_saisie_prime_toujours(self):
        devis = self._devis(type_installation='industriel',
                            bill_kwh=Decimal('30000'), conso=Decimal('12000'))
        self.assertEqual(conso_mensuelle_kwh_pour_devis(devis), 12000.0)

    def test_repli_en_lecture_seule(self):
        devis = self._devis(type_installation='industriel',
                            bill_kwh=Decimal('30000'))
        conso_mensuelle_kwh_pour_devis(devis)
        devis.lead.refresh_from_db()
        self.assertIsNone(devis.lead.conso_mensuelle_kwh)
        self.assertEqual(devis.lead.bill_kwh, Decimal('30000'))

    def test_kwh_du_site_nul_vaut_absence(self):
        devis = self._devis(type_installation='industriel',
                            bill_kwh=Decimal('0'))
        self.assertIsNone(conso_mensuelle_kwh_pour_devis(devis))

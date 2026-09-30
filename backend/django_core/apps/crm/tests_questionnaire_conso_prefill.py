"""QJR592 — le pré-remplissage « énergie » reprend le kWh mensuel déjà saisi
sur le site pour un lead PRO (industriel / commercial), jamais en résidentiel.

Les colonnes `bill_kwh` et `conso_mensuelle_kwh` ne fusionnent pas (CAD166) :
aucune écriture serveur, uniquement une valeur proposée à confirmer.
"""
from django.test import TestCase

from authentication.models import Company

from apps.crm import questionnaire as quest
from apps.crm.models import Lead


class ConsoPrefillTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Soc QJR592')

    def _lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Pro', prenom='Client', **extra)

    def test_industriel_bill_kwh_reprend_la_conso(self):
        lead = self._lead(
            type_installation=Lead.TypeInstallation.INDUSTRIEL,
            bill_kwh=30000)
        out = quest.prefill(lead, ['energie'])
        self.assertEqual(out['conso_mensuelle_kwh'], 30000)

    def test_commercial_bill_kwh_reprend_la_conso(self):
        lead = self._lead(
            type_installation=Lead.TypeInstallation.COMMERCIAL,
            bill_kwh=1200)
        self.assertEqual(
            quest.prefill(lead, ['energie'])['conso_mensuelle_kwh'], 1200)

    def test_residentiel_reste_vide(self):
        lead = self._lead(
            type_installation=Lead.TypeInstallation.RESIDENTIEL,
            bill_kwh=30000)
        self.assertIsNone(
            quest.prefill(lead, ['energie'])['conso_mensuelle_kwh'])

    def test_conso_renseignee_gagne(self):
        lead = self._lead(
            type_installation=Lead.TypeInstallation.INDUSTRIEL,
            bill_kwh=30000, conso_mensuelle_kwh=25000)
        self.assertEqual(
            quest.prefill(lead, ['energie'])['conso_mensuelle_kwh'], 25000)

    def test_aucune_ecriture_serveur(self):
        lead = self._lead(
            type_installation=Lead.TypeInstallation.INDUSTRIEL,
            bill_kwh=30000)
        quest.prefill(lead, ['energie'])
        lead.refresh_from_db()
        self.assertIsNone(lead.conso_mensuelle_kwh)

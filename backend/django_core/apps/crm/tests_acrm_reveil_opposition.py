"""ACRM16 — le réveil saisonnier (`reveil_b`) respecte l'opposition : un lead
Froid ``ne_plus_contacter`` ne reçoit aucune touche, motif « opposition (ne
plus contacter) » ; un lead Froid non opposé la reçoit comme avant — rejoue
la sonde LSVC4-3.

Test-du-test : retirer le refus ⇒ test_oppose_refuse échoue.
"""
import datetime

from django.test import TestCase

from authentication.models import Company
from apps.crm import horaires, stages
from apps.crm.cadence_reveil_saison import (
    REVEIL_SAISON_CLE, motif_de_refus, poser_reveil_saisonnier,
    poser_reveils_saisonniers,
)
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile

EN_SAISON = datetime.datetime(2026, 7, 15, 10, 0, tzinfo=horaires.CASABLANCA)


class ReveilOppositionTests(TestCase):

    def setUp(self):
        from testkit.time import frozen
        gel = frozen(EN_SAISON)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='ACRM16 Solaire', slug='acrm16-reveil')
        CompanyProfile.objects.create(company=self.company)

    def _froid(self, nom, **kw):
        return Lead.objects.create(company=self.company, nom=nom,
                                   stage=stages.COLD, **kw)

    def _touches(self, lead):
        return RelanceEtape.objects.filter(
            lead=lead, template_cle=REVEIL_SAISON_CLE).count()

    def test_oppose_refuse(self):
        lead = self._froid('Opposé', ne_plus_contacter=True)
        motif = motif_de_refus(lead, maintenant=EN_SAISON)
        self.assertIsNotNone(motif)
        self.assertIn('opposition (ne plus contacter)', motif.lower())
        self.assertIsNone(poser_reveil_saisonnier(lead, maintenant=EN_SAISON))
        poser_reveils_saisonniers(self.company, maintenant=EN_SAISON)
        self.assertEqual(self._touches(lead), 0)

    def test_non_oppose_inchange(self):
        lead = self._froid('Dormant')
        self.assertIsNone(motif_de_refus(lead, maintenant=EN_SAISON))
        poser_reveils_saisonniers(self.company, maintenant=EN_SAISON)
        self.assertEqual(self._touches(lead), 1)

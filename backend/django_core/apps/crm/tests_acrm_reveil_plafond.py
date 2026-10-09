"""ACRM18 — ``poser_reveils_saisonniers`` sert CHAQUE dormant éligible une
fois par saison : les refus durables (déjà servi cette année, touche
ouverte, opposé) sont filtrés DANS la requête avant la troncature — 205
dormants sont servis en deux passages (200 puis 5 puis 0) — rejoue la sonde
LSVC4-2.

Test-du-test : remettre la troncature avant le filtre ⇒ 200 / 0 / 0.
"""
import datetime

from django.test import TestCase

from authentication.models import Company
from apps.crm import horaires, stages
from apps.crm.cadence_reveil_saison import (
    REVEIL_SAISON_CLE, poser_reveils_saisonniers,
)
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile

EN_SAISON = datetime.datetime(2026, 7, 15, 10, 0, tzinfo=horaires.CASABLANCA)


class ReveilPlafondTests(TestCase):

    def setUp(self):
        from testkit.time import frozen
        gel = frozen(EN_SAISON)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='ACRM18 Solaire', slug='acrm18-plafond')
        CompanyProfile.objects.create(company=self.company)
        Lead.objects.bulk_create([
            Lead(company=self.company, nom=f'Dormant {i}', stage=stages.COLD)
            for i in range(205)])

    def test_population_superieure_au_plafond(self):
        servis = [len(poser_reveils_saisonniers(
            self.company, maintenant=EN_SAISON, limite=200))
            for _ in range(3)]
        self.assertEqual(servis, [200, 5, 0])
        sans_touche = (Lead.objects.filter(company=self.company,
                                           stage=stages.COLD)
                       .exclude(relance_etapes__template_cle=REVEIL_SAISON_CLE)
                       .count())
        self.assertEqual(sans_touche, 0)
        self.assertEqual(RelanceEtape.objects.filter(
            company=self.company, template_cle=REVEIL_SAISON_CLE).count(),
            205)

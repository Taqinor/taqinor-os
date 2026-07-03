"""Tests XFSM14 — Thermographie IR : points chauds classés + baseline/suivi.

Couvre :

* le classement automatique de sévérité par seuil (observation / à surveiller
  / intervention requise) ;
* la NCR auto-créée sur sévérité maximale ;
* la comparaison recette (baseline) vs dernier suivi.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.qhse.models import NonConformite, ReleveThermographie
from apps.qhse.services import (
    comparer_campagnes_thermographie, enregistrer_releve_thermographie,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ClassementSeveriteTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xfsm14-classe', 'CoXfsm14Classe')

    def test_observation_sous_seuil(self):
        releve = ReleveThermographie.objects.create(
            company=self.company, equipement_ref='ONDULEUR-1', delta_t=2)
        self.assertEqual(
            releve.classe_severite, ReleveThermographie.Severite.OBSERVATION)

    def test_a_surveiller_entre_seuils(self):
        releve = ReleveThermographie.objects.create(
            company=self.company, equipement_ref='ONDULEUR-1', delta_t=8)
        self.assertEqual(
            releve.classe_severite, ReleveThermographie.Severite.A_SURVEILLER)

    def test_intervention_requise_au_dessus_seuil(self):
        releve = ReleveThermographie.objects.create(
            company=self.company, equipement_ref='ONDULEUR-1', delta_t=20)
        self.assertEqual(
            releve.classe_severite,
            ReleveThermographie.Severite.INTERVENTION_REQUISE)

    def test_seuils_parametrables(self):
        releve = ReleveThermographie.objects.create(
            company=self.company, equipement_ref='ONDULEUR-1', delta_t=4,
            seuil_a_surveiller=3, seuil_intervention=10)
        self.assertEqual(
            releve.classe_severite, ReleveThermographie.Severite.A_SURVEILLER)


class EnregistrerReleveThermographieTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xfsm14-ncr', 'CoXfsm14Ncr')

    def test_intervention_requise_leve_ncr(self):
        releve = enregistrer_releve_thermographie(
            company=self.company, equipement_ref='STRING-3', delta_t=25)
        self.assertIsNotNone(releve.ncr_id)
        ncr = NonConformite.objects.get(pk=releve.ncr_id)
        self.assertEqual(ncr.gravite, NonConformite.Gravite.MAJEURE)
        self.assertEqual(ncr.company, self.company)

    def test_observation_ne_leve_pas_ncr(self):
        releve = enregistrer_releve_thermographie(
            company=self.company, equipement_ref='STRING-4', delta_t=1)
        self.assertIsNone(releve.ncr_id)

    def test_a_surveiller_ne_leve_pas_ncr(self):
        releve = enregistrer_releve_thermographie(
            company=self.company, equipement_ref='STRING-5', delta_t=8)
        self.assertIsNone(releve.ncr_id)


class CompararCampagnesTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xfsm14-comp', 'CoXfsm14Comp')

    def test_compare_recette_et_suivi(self):
        ReleveThermographie.objects.create(
            company=self.company, equipement_ref='ONDULEUR-2', delta_t=3,
            campagne=ReleveThermographie.Campagne.RECETTE,
            date_releve=date(2026, 1, 1))
        ReleveThermographie.objects.create(
            company=self.company, equipement_ref='ONDULEUR-2', delta_t=9,
            campagne=ReleveThermographie.Campagne.SUIVI,
            date_releve=date(2026, 6, 1))
        result = comparer_campagnes_thermographie(self.company, 'ONDULEUR-2')
        self.assertIsNotNone(result['recette'])
        self.assertIsNotNone(result['suivi'])
        self.assertEqual(result['delta'], 6)

    def test_sans_recette_delta_none(self):
        ReleveThermographie.objects.create(
            company=self.company, equipement_ref='ONDULEUR-3', delta_t=4,
            campagne=ReleveThermographie.Campagne.SUIVI)
        result = comparer_campagnes_thermographie(self.company, 'ONDULEUR-3')
        self.assertIsNone(result['recette'])
        self.assertIsNone(result['delta'])

    def test_isolation_societe(self):
        autre = make_company('co-xfsm14-comp-autre', 'CoXfsm14CompAutre')
        ReleveThermographie.objects.create(
            company=self.company, equipement_ref='ONDULEUR-4', delta_t=3,
            campagne=ReleveThermographie.Campagne.RECETTE)
        result = comparer_campagnes_thermographie(autre, 'ONDULEUR-4')
        self.assertIsNone(result['recette'])

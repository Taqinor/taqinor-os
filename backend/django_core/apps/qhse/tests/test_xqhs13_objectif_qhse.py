"""Tests XQHS13 — Objectifs & cibles QHSE/ESG avec revues périodiques.

Couvre :

* le calcul automatique d'atteinte (sens hausse/baisse) ;
* la trajectoire baseline→cible vs réel ;
* la détection des objectifs dont la revue est due ;
* le scoping société.
"""
from datetime import date, timedelta

from django.test import TestCase

from authentication.models import Company

from apps.qhse.models import ObjectifQhse, RevueObjectif
from apps.qhse.selectors import objectifs_revue_due, trajectoire_objectif


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class CalculerAtteintTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs13-atteint', 'CoXqhs13Atteint')

    def test_sens_hausse_atteint(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='Satisfaction client',
            valeur_cible=90, sens_amelioration=ObjectifQhse.SensAmelioration.HAUSSE)
        revue = RevueObjectif.objects.create(
            company=self.company, objectif=objectif, valeur_constatee=95)
        self.assertTrue(revue.atteint)

    def test_sens_hausse_non_atteint(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='Satisfaction client',
            valeur_cible=90, sens_amelioration=ObjectifQhse.SensAmelioration.HAUSSE)
        revue = RevueObjectif.objects.create(
            company=self.company, objectif=objectif, valeur_constatee=70)
        self.assertFalse(revue.atteint)

    def test_sens_baisse_atteint(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='Taux accidents',
            valeur_cible=2, sens_amelioration=ObjectifQhse.SensAmelioration.BAISSE)
        revue = RevueObjectif.objects.create(
            company=self.company, objectif=objectif, valeur_constatee=1)
        self.assertTrue(revue.atteint)

    def test_sans_cible_ni_valeur_none(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='Sans cible')
        revue = RevueObjectif.objects.create(
            company=self.company, objectif=objectif)
        self.assertIsNone(revue.atteint)


class TrajectoireObjectifTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs13-traj', 'CoXqhs13Traj')

    def test_points_ordonnes_chronologiquement(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='CO2', valeur_baseline=100,
            valeur_cible=50, annee_baseline=2025)
        RevueObjectif.objects.create(
            company=self.company, objectif=objectif, periode='T2',
            date_revue=date(2026, 6, 1), valeur_constatee=70)
        RevueObjectif.objects.create(
            company=self.company, objectif=objectif, periode='T1',
            date_revue=date(2026, 3, 1), valeur_constatee=85)
        result = trajectoire_objectif(objectif)
        self.assertEqual(result['baseline'], 100)
        self.assertEqual(result['cible'], 50)
        self.assertEqual(len(result['points']), 2)
        self.assertEqual(result['points'][0]['periode'], 'T1')
        self.assertEqual(result['points'][1]['periode'], 'T2')


class ObjectifsRevueDueTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs13-due', 'CoXqhs13Due')

    def test_due_sans_revue_anterieure(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='Nouveau')
        dus = objectifs_revue_due(self.company)
        self.assertIn(objectif, dus)

    def test_pas_due_apres_revue_recente(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='Récent',
            frequence_revue=ObjectifQhse.Frequence.TRIMESTRIELLE)
        RevueObjectif.objects.create(
            company=self.company, objectif=objectif,
            date_revue=date.today() - timedelta(days=10))
        dus = objectifs_revue_due(self.company)
        self.assertNotIn(objectif, dus)

    def test_due_apres_cadence_depassee(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='En retard',
            frequence_revue=ObjectifQhse.Frequence.TRIMESTRIELLE)
        RevueObjectif.objects.create(
            company=self.company, objectif=objectif,
            date_revue=date.today() - timedelta(days=100))
        dus = objectifs_revue_due(self.company)
        self.assertIn(objectif, dus)

    def test_isolation_societe(self):
        autre = make_company('co-xqhs13-due-autre', 'CoXqhs13DueAutre')
        ObjectifQhse.objects.create(company=self.company, intitule='X')
        dus = objectifs_revue_due(autre)
        self.assertEqual(dus, [])

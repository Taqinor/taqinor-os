"""Tests ZRH5 — Clôture automatique des pointages oubliés.

``services.clore_pointages_ouverts`` clôture les pointages ARRIVÉE sans
DÉPART au-delà du seuil société, une fois, avec un ``IncidentPresence``
« départ automatique ». Un pointage déjà fermé est intouché ; seuil désactivé
= no-op ; isolation multi-société.
"""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.rh import services
from apps.rh.models import DossierEmploye, IncidentPresence, Pointage, \
    ReglageRH


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='N', prenom='P')


def make_pointage_ouvert(company, employe, heures_ecoulees):
    return Pointage.objects.create(
        company=company, employe=employe,
        type_pointage=Pointage.TypePointage.ARRIVEE,
        heure_arrivee=timezone.now() - timedelta(hours=heures_ecoulees))


class ClotureAutoServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('zrh5-a', 'A')
        self.employe = make_employe(self.company, 'ZRH5-1')

    def test_seuil_desactive_noop(self):
        make_pointage_ouvert(self.company, self.employe, 100)
        traites = services.clore_pointages_ouverts(self.company, apply=True)
        self.assertEqual(traites, [])

    def test_pointage_au_dela_du_seuil_cloture(self):
        ReglageRH.objects.create(
            company=self.company, pointage_auto_depart_apres_h=10)
        pointage = make_pointage_ouvert(self.company, self.employe, 12)
        traites = services.clore_pointages_ouverts(self.company, apply=True)
        self.assertEqual(len(traites), 1)
        pointage.refresh_from_db()
        self.assertTrue(pointage.depart_auto)
        self.assertIsNotNone(pointage.heure_depart)
        self.assertTrue(
            IncidentPresence.objects.filter(
                company=self.company, employe=self.employe).exists())

    def test_pointage_sous_le_seuil_intouche(self):
        ReglageRH.objects.create(
            company=self.company, pointage_auto_depart_apres_h=10)
        pointage = make_pointage_ouvert(self.company, self.employe, 3)
        traites = services.clore_pointages_ouverts(self.company, apply=True)
        self.assertEqual(traites, [])
        pointage.refresh_from_db()
        self.assertFalse(pointage.depart_auto)
        self.assertIsNone(pointage.heure_depart)

    def test_idempotence_deja_ferme_intouche(self):
        ReglageRH.objects.create(
            company=self.company, pointage_auto_depart_apres_h=10)
        pointage = make_pointage_ouvert(self.company, self.employe, 12)
        services.clore_pointages_ouverts(self.company, apply=True)
        pointage.refresh_from_db()
        heure_depart_1 = pointage.heure_depart

        # 2e exécution : le pointage est désormais FERMÉ, ne doit plus être
        # sélectionné (filtre heure_depart__isnull=True).
        traites2 = services.clore_pointages_ouverts(self.company, apply=True)
        self.assertEqual(traites2, [])
        pointage.refresh_from_db()
        self.assertEqual(pointage.heure_depart, heure_depart_1)

    def test_dry_run_ne_modifie_rien(self):
        ReglageRH.objects.create(
            company=self.company, pointage_auto_depart_apres_h=10)
        pointage = make_pointage_ouvert(self.company, self.employe, 12)
        traites = services.clore_pointages_ouverts(self.company, apply=False)
        self.assertEqual(len(traites), 1)
        pointage.refresh_from_db()
        self.assertFalse(pointage.depart_auto)
        self.assertIsNone(pointage.heure_depart)
        self.assertFalse(IncidentPresence.objects.exists())

    def test_isolation_societe(self):
        autre = make_company('zrh5-b', 'B')
        ReglageRH.objects.create(
            company=autre, pointage_auto_depart_apres_h=1)
        emp_autre = make_employe(autre, 'ZRH5-AUTRE')
        make_pointage_ouvert(autre, emp_autre, 12)
        # self.company n'a pas de réglage -> seuil désactivé.
        traites = services.clore_pointages_ouverts(self.company, apply=True)
        self.assertEqual(traites, [])


class ClorePointagesCommandTests(TestCase):
    def test_commande_dry_run_par_defaut(self):
        company = make_company('zrh5-c', 'C')
        ReglageRH.objects.create(
            company=company, pointage_auto_depart_apres_h=1)
        employe = make_employe(company, 'ZRH5-CMD')
        make_pointage_ouvert(company, employe, 5)
        out = StringIO()
        call_command('clore_pointages_ouverts', stdout=out)
        self.assertIn('DRY-RUN', out.getvalue())
        self.assertFalse(Pointage.objects.get(employe=employe).depart_auto)

    def test_commande_apply(self):
        company = make_company('zrh5-d', 'D')
        ReglageRH.objects.create(
            company=company, pointage_auto_depart_apres_h=1)
        employe = make_employe(company, 'ZRH5-CMD2')
        make_pointage_ouvert(company, employe, 5)
        out = StringIO()
        call_command('clore_pointages_ouverts', '--apply', stdout=out)
        self.assertIn('APPLIQUÉ', out.getvalue())
        self.assertTrue(Pointage.objects.get(employe=employe).depart_auto)

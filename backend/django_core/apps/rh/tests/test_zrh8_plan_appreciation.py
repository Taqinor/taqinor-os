"""Tests ZRH8 — Plans d'appréciation automatiques.

Couvre :
- ``manage.py planifier_appreciations`` (dry-run par défaut, ``--apply`` pour
  committer) : un employé dont l'ancienneté franchit PILE un jalon obtient
  une évaluation planifiée UNE SEULE FOIS ; un re-run n'en crée jamais un
  doublon (idempotence) ; un employé sous le jalon ne génère rien ; isolation
  multi-tenant.
- ``services.planifier_appreciations_pour_societe`` (dry-run / apply).
- ``services.campagne_annuelle_par_defaut`` : idempotente (une seule campagne
  par société/année).
"""
import datetime
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    CampagneEvaluation, DossierEmploye, EvaluationEmploye, PlanAppreciation,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_employe(company, matricule, date_embauche, **kwargs):
    defaults = dict(
        nom='N', prenom='P', statut=DossierEmploye.Statut.ACTIF,
        date_embauche=date_embauche)
    defaults.update(kwargs)
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, **defaults)


def make_plan(company, jalons, campagne_cible=None):
    return PlanAppreciation.objects.create(
        company=company, libelle='Plan standard',
        mois_apres_embauche=jalons, campagne_cible=campagne_cible)


class CampagneAnnuelleParDefautTests(TestCase):
    def setUp(self):
        self.co = make_company('zrh8-camp', 'ZRH8 Camp')

    def test_creation_et_idempotence(self):
        c1 = services.campagne_annuelle_par_defaut(self.co, 2026)
        c2 = services.campagne_annuelle_par_defaut(self.co, 2026)
        self.assertEqual(c1.id, c2.id)
        self.assertEqual(
            CampagneEvaluation.objects.filter(company=self.co, annee=2026).count(),
            1)


class PlanifierAppreciationsServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('zrh8-svc', 'ZRH8 Svc')
        self.today = datetime.date(2026, 7, 5)

    def test_jalon_pile_franchi_planifie_une_evaluation(self):
        """Un employé embauché il y a EXACTEMENT 12 mois franchit le jalon."""
        embauche = datetime.date(2025, 7, 5)
        employe = make_employe(self.co, 'M1', embauche)
        make_plan(self.co, [3, 12, 24])

        resultat = services.planifier_appreciations_pour_societe(
            self.co, aujourd_hui=self.today, apply=True)

        self.assertEqual(resultat['nb_a_creer'], 1)
        self.assertTrue(
            EvaluationEmploye.objects.filter(employe=employe).exists())
        evaluation = EvaluationEmploye.objects.get(employe=employe)
        self.assertEqual(
            evaluation.statut, EvaluationEmploye.Statut.PLANIFIE)
        self.assertIn('[ZRH8:jalon=12]', evaluation.synthese)

    def test_employe_sous_le_jalon_rien_genere(self):
        """Embauché il y a 2 mois : le premier jalon (3 mois) n'est pas
        encore franchi."""
        embauche = datetime.date(2026, 5, 5)
        make_employe(self.co, 'M2', embauche)
        make_plan(self.co, [3, 12, 24])

        resultat = services.planifier_appreciations_pour_societe(
            self.co, aujourd_hui=self.today, apply=True)

        self.assertEqual(resultat['nb_a_creer'], 0)
        self.assertEqual(EvaluationEmploye.objects.count(), 0)

    def test_rerun_idempotent_zero_doublon(self):
        embauche = datetime.date(2025, 7, 5)
        make_employe(self.co, 'M3', embauche)
        make_plan(self.co, [12])

        services.planifier_appreciations_pour_societe(
            self.co, aujourd_hui=self.today, apply=True)
        premier_total = EvaluationEmploye.objects.count()

        resultat_2 = services.planifier_appreciations_pour_societe(
            self.co, aujourd_hui=self.today, apply=True)

        self.assertEqual(resultat_2['nb_a_creer'], 0)
        self.assertEqual(resultat_2['nb_deja'], 1)
        self.assertEqual(EvaluationEmploye.objects.count(), premier_total)

    def test_deux_jalons_franchis_meme_campagne_pas_de_doublon_ligne(self):
        """Un employé qui franchit DEUX jalons dans la même campagne obtient
        une seule ligne EvaluationEmploye (contrainte unique campagne+employe),
        les deux marques de jalon coexistent dans synthese."""
        embauche = datetime.date(2024, 1, 5)  # ~30 mois d'ancienneté.
        employe = make_employe(self.co, 'M4', embauche)
        make_plan(self.co, [12, 24])

        services.planifier_appreciations_pour_societe(
            self.co, aujourd_hui=self.today, apply=True)

        self.assertEqual(
            EvaluationEmploye.objects.filter(employe=employe).count(), 1)
        evaluation = EvaluationEmploye.objects.get(employe=employe)
        self.assertIn('[ZRH8:jalon=12]', evaluation.synthese)
        self.assertIn('[ZRH8:jalon=24]', evaluation.synthese)

    def test_dry_run_par_defaut_ne_cree_rien(self):
        embauche = datetime.date(2025, 7, 5)
        make_employe(self.co, 'M5', embauche)
        make_plan(self.co, [12])

        resultat = services.planifier_appreciations_pour_societe(
            self.co, aujourd_hui=self.today)  # apply=False par défaut.

        self.assertEqual(resultat['nb_a_creer'], 1)
        self.assertEqual(EvaluationEmploye.objects.count(), 0)

    def test_evaluateur_manager_pose_si_identifiable(self):
        """L'évaluateur posé = le dernier évaluateur connu de l'employé
        (proxy manager), sinon None."""
        embauche = datetime.date(2024, 7, 5)
        manager = make_employe(self.co, 'MGR', embauche)
        employe = make_employe(self.co, 'M6', embauche)
        campagne_passee = CampagneEvaluation.objects.create(
            company=self.co, intitule='Campagne passée', annee=2025)
        EvaluationEmploye.objects.create(
            company=self.co, campagne=campagne_passee, employe=employe,
            evaluateur=manager, statut=EvaluationEmploye.Statut.VALIDE)

        make_plan(self.co, [24])
        services.planifier_appreciations_pour_societe(
            self.co, aujourd_hui=self.today, apply=True)

        nouvelle_campagne = services.campagne_annuelle_par_defaut(
            self.co, self.today.year)
        evaluation = EvaluationEmploye.objects.get(
            employe=employe, campagne=nouvelle_campagne)
        self.assertEqual(evaluation.evaluateur_id, manager.id)

    def test_isolation_multi_tenant(self):
        co_b = make_company('zrh8-svc-b', 'ZRH8 Svc B')
        embauche = datetime.date(2025, 7, 5)
        make_employe(self.co, 'M7', embauche)
        make_employe(co_b, 'M8', embauche)
        make_plan(self.co, [12])
        make_plan(co_b, [12])

        resultat_a = services.planifier_appreciations_pour_societe(
            self.co, aujourd_hui=self.today, apply=True)
        self.assertEqual(resultat_a['nb_a_creer'], 1)
        self.assertEqual(
            EvaluationEmploye.objects.filter(company=self.co).count(), 1)
        self.assertEqual(
            EvaluationEmploye.objects.filter(company=co_b).count(), 0)

    def test_aucun_plan_actif_rien_genere(self):
        make_employe(self.co, 'M9', datetime.date(2025, 7, 5))
        resultat = services.planifier_appreciations_pour_societe(
            self.co, aujourd_hui=self.today, apply=True)
        self.assertEqual(resultat['nb_a_creer'], 0)

    def test_plan_inactif_ignore(self):
        make_employe(self.co, 'M10', datetime.date(2025, 7, 5))
        plan = make_plan(self.co, [12])
        plan.actif = False
        plan.save()
        resultat = services.planifier_appreciations_pour_societe(
            self.co, aujourd_hui=self.today, apply=True)
        self.assertEqual(resultat['nb_a_creer'], 0)


class PlanifierAppreciationsCommandTests(TestCase):
    def setUp(self):
        self.co = make_company('zrh8-cmd', 'ZRH8 Cmd')
        self.today_str_embauche = datetime.date(2025, 7, 5)

    def run_cmd(self, **kwargs):
        out = StringIO()
        call_command('planifier_appreciations', stdout=out, **kwargs)
        return out.getvalue()

    def test_dry_run_par_defaut(self):
        make_employe(self.co, 'CMD1', self.today_str_embauche)
        make_plan(self.co, [12])
        output = self.run_cmd(company='zrh8-cmd')
        self.assertIn('DRY-RUN', output)
        self.assertEqual(EvaluationEmploye.objects.count(), 0)

    def test_apply_committe(self):
        make_employe(self.co, 'CMD2', self.today_str_embauche)
        make_plan(self.co, [12])
        output = self.run_cmd(company='zrh8-cmd', apply=True)
        self.assertIn('APPLIQUÉ', output)

    def test_company_slug_inconnu_leve(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            self.run_cmd(company='inexistant')

"""NTSCM22 — Ouverture automatique du cycle S&OP mensuel (opt-in par
société).

Critère d'acceptation : avec ``sop_actif=False`` (défaut), aucun cycle n'est
créé automatiquement ; activé, le cycle du mois M+1 apparaît le 20 du mois M.

ADAPTATION DE PÉRIMÈTRE (voir ``apps.scm.models.ParametresSCM``) :
``sop_actif``/``animateur_sop`` vivent dans ``apps.scm.models.ParametresSCM``
(pas ``apps.parametres.CompanyProfile``, hors périmètre de cette lane)."""
from datetime import date

from django.test import TestCase

from apps.scm.models import CyclePlanificationSOP, ParametresSCM
from apps.scm.services import parametres_scm
from apps.scm.tasks import ouvrir_cycle_sop_mensuel_task

from .helpers import auth, make_company, make_user


class OuvrirCycleSopMensuelTaskTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-tache-sop', 'Supply Tâche SOP')
        self.admin = make_user(self.company, 'scm-tache-sop-admin', 'admin')

    def test_aucun_cycle_cree_par_defaut(self):
        self.assertFalse(
            ParametresSCM.objects.filter(company=self.company).exists())
        crees = ouvrir_cycle_sop_mensuel_task(today=date(2026, 8, 20))
        self.assertEqual(crees, [])
        self.assertFalse(
            CyclePlanificationSOP.objects.filter(company=self.company).exists())

    def test_cycle_du_mois_suivant_cree_quand_actif(self):
        parametres = parametres_scm(self.company)
        parametres.sop_actif = True
        parametres.animateur_sop = self.admin
        parametres.save(update_fields=['sop_actif', 'animateur_sop'])

        crees = ouvrir_cycle_sop_mensuel_task(today=date(2026, 8, 20))
        self.assertEqual(len(crees), 1)
        cycle = CyclePlanificationSOP.objects.get(company=self.company)
        self.assertEqual(cycle.periode, '2026-09')
        self.assertEqual(cycle.statut, CyclePlanificationSOP.Statut.BROUILLON)
        self.assertEqual(cycle.anime_par_id, self.admin.id)

    def test_idempotent_pas_de_doublon(self):
        parametres = parametres_scm(self.company)
        parametres.sop_actif = True
        parametres.save(update_fields=['sop_actif'])

        ouvrir_cycle_sop_mensuel_task(today=date(2026, 8, 20))
        crees_2 = ouvrir_cycle_sop_mensuel_task(today=date(2026, 8, 21))
        self.assertEqual(crees_2, [])
        self.assertEqual(
            CyclePlanificationSOP.objects.filter(company=self.company).count(), 1)

    def test_tache_apparait_dans_core_jobs(self):
        resp = auth(self.admin).get('/api/django/core/jobs/')
        self.assertEqual(resp.status_code, 200, resp.data)
        taches = resp.data if isinstance(resp.data, list) else resp.data.get('results', [])
        self.assertTrue(any(
            job.get('task') == 'scm.ouvrir_cycle_sop_mensuel' for job in taches))


class ParametresSopViewTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-parametres-sop', 'Supply Paramètres SOP')
        self.admin = make_user(self.company, 'scm-parametres-sop-admin', 'admin')

    def test_get_defaut_puis_patch_active(self):
        resp = auth(self.admin).get('/api/django/scm/parametres-sop/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['sop_actif'])

        resp2 = auth(self.admin).patch(
            '/api/django/scm/parametres-sop/', {'sop_actif': True}, format='json')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertTrue(resp2.data['sop_actif'])
        self.assertTrue(
            ParametresSCM.objects.get(company=self.company).sop_actif)

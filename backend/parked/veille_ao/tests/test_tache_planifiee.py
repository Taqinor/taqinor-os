"""VAO22 — la tâche planifiée existe, est JOIGNABLE, et est DÉSARMÉE.

Les trois preuves que le « Done = » demande :
  * l'entrée ``beat_schedule`` est présente (sinon la tâche ne tournerait
    jamais — le mode de défaillance dominant du dépôt) et à 06:00 ;
  * drapeau à ``0`` (le DÉFAUT) → la tâche sort SANS aucun appel réseau et
    sans toucher la base ;
  * la tâche apparaît dans l'écran « Tâches planifiées » (``core.jobs.list_jobs``
    la lit gratuitement).

Aucune exécution réelle n'est possible avant VAO4 : c'est le sens du drapeau.
"""
from django.test import SimpleTestCase, TestCase, override_settings

from authentication.models import Company
from apps.veille_ao.models import (
    MotCleVeille, NiveauMotCle, SourceVeille, TypeSource,
)
from apps.veille_ao.tasks import (
    MOTIF_DESARME, collecte_active, collecte_quotidienne,
)

NOM_TACHE = 'veille_ao.collecte_quotidienne'


class BeatTests(SimpleTestCase):
    def test_la_tache_est_planifiee_a_06h00(self):
        from erp_agentique.celery import app

        entrees = [e for e in app.conf.beat_schedule.values()
                   if e.get('task') == NOM_TACHE]
        self.assertEqual(len(entrees), 1, 'la tâche doit être au beat, une fois')
        schedule = entrees[0]['schedule']
        self.assertEqual(str(schedule._orig_hour), '6')
        self.assertEqual(str(schedule._orig_minute), '0')

    def test_le_fuseau_du_beat_est_casablanca(self):
        """06:00 n'a de sens que dans le fuseau des remises de plis."""
        from erp_agentique.celery import app

        self.assertEqual(app.conf.timezone, 'Africa/Casablanca')

    def test_la_tache_est_visible_dans_l_ecran_taches_planifiees(self):
        from core.jobs import list_jobs

        self.assertIn(NOM_TACHE, {j['task'] for j in list_jobs()})


class DesarmementTests(TestCase):
    """Le drapeau à 0 rend le collecteur INERTE — pas « discret », inerte."""

    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor Désarmé')
        self.source = SourceVeille.objects.create(
            company=self.company, code='pmmp', libelle='Portail',
            type_source=TypeSource.PORTAIL_OFFICIEL,
            url_base='https://exemple.test/', actif=True)
        MotCleVeille.objects.create(
            company=self.company, libelle='solaire',
            niveau=NiveauMotCle.NOYAU, poids=10, actif=True)

    def test_le_defaut_du_depot_est_DESARME(self):
        """Sans réglage explicite, la collecte n'est PAS armée."""
        self.assertFalse(collecte_active())

    @override_settings(VEILLE_AO_COLLECTE_ACTIVE=False)
    def test_desarmee_la_tache_sort_sans_rien_collecter(self):
        resultat = collecte_quotidienne()

        self.assertFalse(resultat['arme'])
        self.assertEqual(resultat['executions'], [])
        self.assertEqual(resultat['motif'], MOTIF_DESARME)
        self.source.refresh_from_db()
        self.assertIsNone(self.source.derniere_collecte_reussie)

    @override_settings(VEILLE_AO_COLLECTE_ACTIVE=False)
    def test_le_motif_NOMME_la_tache_d_armement(self):
        """Un « désactivé » nu envoie l'utilisateur chercher pourquoi."""
        self.assertIn('VAO4', MOTIF_DESARME)
        self.assertIn('VEILLE_AO_COLLECTE_ACTIVE', MOTIF_DESARME)

    @override_settings(VEILLE_AO_COLLECTE_ACTIVE=True)
    def test_armee_sans_collecteur_branche_la_tache_echoue_franchement(self):
        """Armer NE fabrique pas un collecteur : VAO15-VAO20 restent gatées.

        La collecte part, ne trouve aucun lecteur branché et le DIT — elle ne
        rend pas « 0 résultat » en silence.
        """
        resultat = collecte_quotidienne(company_id=self.company.pk)

        self.assertTrue(resultat['arme'])
        self.assertEqual(len(resultat['executions']), 1)
        self.assertEqual(resultat['executions'][0]['verdict'], 'echec')

    @override_settings(VEILLE_AO_COLLECTE_ACTIVE=False)
    def test_le_job_de_fond_est_marque_termine_meme_desarme(self):
        """Un job qui reste « en cours » sans raison fait perdre confiance."""
        from core.models import BackgroundJob
        from authentication.models import CustomUser

        user = CustomUser.objects.create_user(
            username='dir', password='x', company=self.company)
        job = BackgroundJob.objects.create(
            company=self.company, user=user, kind='veille_ao_collecte')

        collecte_quotidienne(job_id=job.pk, company_id=self.company.pk)

        job.refresh_from_db()
        self.assertEqual(job.statut, BackgroundJob.STATUT_DONE)

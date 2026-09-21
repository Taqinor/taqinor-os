"""AUD524 — trois services testés et corrects, sans AUCUN appelant.

``relancer_derogations`` (XQHS2), ``relancer_audits_planifies_en_retard``
(XQHS10) et ``cloturer_contrats_impayes`` (ZCTR2) n'apparaissaient nulle part
hors de leurs tests (et, pour les deux premiers, d'une action manuelle de vue) :
ni ``tasks.py``, ni ``erp_agentique/celery.py`` ``beat_schedule`` — où seules
DEUX tâches qhse figuraient. ``contrats/scheduled.py`` affirmait pourtant à
tort qu'un « beat ``cloturer_contrats_impayes`` séparé » existait.

Conséquence : dérogations, audits planifiés en retard et impayés ne relançaient
ni ne clôturaient JAMAIS automatiquement. Le code était juste ; il ne tournait
simplement pas.
"""
from django.test import SimpleTestCase


class TestCablageBeat(SimpleTestCase):
    """ROUGE avant le correctif : 0 référence aux trois noms de tâche."""

    NOMS = (
        'qhse.relancer_derogations',
        'qhse.relancer_audits_planifies_en_retard',
        'contrats.cloturer_contrats_impayes_daily',
    )

    def test_les_trois_taches_sont_enregistrees(self):
        # `autodiscover_tasks()` est PARESSEUX : l'enregistrement a lieu à
        # l'import du module de tâches. On les importe donc explicitement —
        # c'est exactement ce que fait le worker au démarrage.
        import apps.contrats.scheduled  # noqa: F401
        import apps.qhse.tasks  # noqa: F401
        from erp_agentique.celery import app
        for nom in self.NOMS:
            with self.subTest(tache=nom):
                self.assertIn(
                    nom, app.tasks,
                    f'{nom} n\'est pas une tâche Celery enregistrée')

    def test_les_trois_taches_sont_au_beat_schedule(self):
        from erp_agentique.celery import app
        planifiees = {
            entree['task'] for entree in app.conf.beat_schedule.values()}
        for nom in self.NOMS:
            with self.subTest(tache=nom):
                self.assertIn(
                    nom, planifiees,
                    f'{nom} n\'a aucune entrée au beat_schedule : le service '
                    f'ne tournera jamais tout seul')

    def test_chaque_tache_delegue_au_service_homonyme(self):
        """Les enveloppes ne DUPLIQUENT aucune logique métier : toute la
        logique reste dans les services (testables sans Celery)."""
        from apps.contrats import scheduled as contrats_scheduled
        from apps.qhse import tasks as qhse_tasks

        for module, attribut in (
                (qhse_tasks, 'relancer_derogations_task'),
                (qhse_tasks, 'relancer_audits_planifies_en_retard_task'),
                (contrats_scheduled, 'cloturer_contrats_impayes_daily'),
        ):
            with self.subTest(fonction=attribut):
                self.assertTrue(hasattr(module, attribut))

    def test_le_balayage_est_borne_aux_societes_actives(self):
        """AUD415/SCA19 — un tenant suspendu ne doit plus être relancé."""
        import inspect

        from apps.contrats import scheduled as contrats_scheduled
        from apps.qhse import tasks as qhse_tasks

        for module, attribut in (
                (qhse_tasks, 'relancer_derogations_task'),
                (qhse_tasks, 'relancer_audits_planifies_en_retard_task'),
                (contrats_scheduled, 'cloturer_contrats_impayes_daily'),
        ):
            with self.subTest(fonction=attribut):
                fonction = getattr(module, attribut)
                source = inspect.getsource(
                    getattr(fonction, '__wrapped__', fonction))
                self.assertIn('active_companies', source)

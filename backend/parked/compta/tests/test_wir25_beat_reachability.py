"""Tests WIR25 — les deux commandes comptables/fiscales orphelines sont
désormais PLANIFIÉES au Celery beat (elles ne tournaient qu'à la main) :

  * ``compta.generer_ecritures_recurrentes`` (XACC8 — écritures récurrentes) ;
  * ``fiscal.rappels_fiscaux`` (NTMAR15 — échéances CNSS/taxe pro/TVA/IS).

Couvre : présence dans ``beat_schedule`` (le mode de défaillance dominant du
dépôt — une tâche bâtie mais hors beat ne tourne jamais, cf. QX11), routage
vers la file ``scheduled``, joignabilité + idempotence des enveloppes (no-op
sans donnée = 0, aucun double envoi).
"""
from django.test import TestCase

from authentication.models import Company
from apps.compta.scheduled import generer_ecritures_recurrentes_dues
from apps.fiscal.tasks import rappels_fiscaux_task


class Wir25BeatReachabilityTests(TestCase):
    def _beat(self):
        from erp_agentique.celery import app
        return {v['task'] for v in app.conf.beat_schedule.values()}

    def test_les_deux_taches_sont_planifiees(self):
        planifiees = self._beat()
        self.assertIn('compta.generer_ecritures_recurrentes', planifiees)
        self.assertIn('fiscal.rappels_fiscaux', planifiees)

    def test_routees_vers_la_file_scheduled(self):
        from django.conf import settings
        routes = settings.CELERY_TASK_ROUTES
        self.assertEqual(
            routes['compta.generer_ecritures_recurrentes']['queue'],
            'scheduled')
        self.assertEqual(
            routes['fiscal.rappels_fiscaux']['queue'], 'scheduled')

    def test_enveloppes_enregistrees_avec_le_bon_nom(self):
        self.assertEqual(
            generer_ecritures_recurrentes_dues.name,
            'compta.generer_ecritures_recurrentes')
        self.assertEqual(
            rappels_fiscaux_task.name, 'fiscal.rappels_fiscaux')

    def test_enveloppes_joignables_no_op_sans_donnee(self):
        # Aucune société / aucune échéance : les tâches tournent sans erreur et
        # ne produisent rien (idempotent, pas de double envoi).
        self.assertEqual(rappels_fiscaux_task(), 0)
        Company.objects.get_or_create(slug='wir25-co', defaults={'nom': 'WIR25'})
        self.assertEqual(generer_ecritures_recurrentes_dues(), 0)
        # Re-run le même jour : toujours 0 (idempotent).
        self.assertEqual(generer_ecritures_recurrentes_dues(), 0)
        self.assertEqual(rappels_fiscaux_task(), 0)

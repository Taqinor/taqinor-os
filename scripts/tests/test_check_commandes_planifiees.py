"""Tests AUD231 — scripts/check_commandes_planifiees.py.

Le garde lui-même doit être prouvé : la tâche AUD231 exige qu'il ÉCHOUE sur un
cas négatif CONSTRUIT (une commande qui se dit « Celery beat » sans entrée de
beat) et PASSE sur un cas positif (la même commande, planifiée).

Pur stdlib (unittest + ast), sans Django ni base. Run :
    python -m unittest scripts.tests.test_check_commandes_planifiees -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_commandes_planifiees as gard  # noqa: E402


COMMANDE_BEAT = '''\
"""NTWMS99 — balaye les machins dus.

IDEMPOTENTE : rejouée le même jour elle ne recrée rien. Plannifiable par Celery
beat comme les autres jobs du module.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Balaye les machins dus (idempotent)."

    def handle(self, *args, **options):
        pass
'''

COMMANDE_CRON_DANS_LE_HELP = '''\
"""Balaye les trucs."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("Balaye les trucs — pensé pour un planificateur (cron / Celery "
            "beat).")

    def handle(self, *args, **options):
        pass
'''

COMMANDE_MANUELLE = '''\
"""Outil d'administration ponctuel : recalcule un agrégat à la demande.

    python manage.py recalculer_agregat --company 3
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Recalcule l'agrégat d'une société (outil manuel)."

    def handle(self, *args, **options):
        pass
'''

BEAT_AVEC = """\
app.conf.beat_schedule = {
    'stock-balayer-machins': {
        'task': 'stock.balayer_machins',
        'schedule': crontab(hour=5, minute=15),
    },
}
"""

BEAT_SANS = """\
app.conf.beat_schedule = {
    'ventes-check-overdue-factures': {
        'task': 'ventes.check_overdue_factures',
        'schedule': crontab(hour=0, minute=30),
    },
}
"""


class DetectionTests(unittest.TestCase):
    def test_docstring_celery_beat_est_detectee(self):
        self.assertTrue(gard.se_declare_planifiable(COMMANDE_BEAT))

    def test_mention_cron_dans_le_help_est_detectee(self):
        """Le `help` compte autant que la docstring : plusieurs commandes du
        dépôt ne portent la mention que là."""
        self.assertTrue(
            gard.se_declare_planifiable(COMMANDE_CRON_DANS_LE_HELP))

    def test_commande_manuelle_nest_jamais_examinee(self):
        # Anti-faux-positif : un outil manuel n'a rien à faire dans le beat.
        self.assertFalse(gard.se_declare_planifiable(COMMANDE_MANUELLE))

    def test_source_illisible_ne_leve_jamais(self):
        self.assertFalse(gard.se_declare_planifiable("def ("))


class BeatTests(unittest.TestCase):
    def test_les_noms_de_taches_sont_lus_du_beat(self):
        self.assertEqual(gard.taches_planifiees(BEAT_AVEC),
                         {'stock.balayer_machins'})

    def test_cas_negatif_construit_la_commande_nest_pas_planifiee(self):
        """Le cas que la garde existe pour attraper."""
        planifiees = gard.taches_planifiees(BEAT_SANS)
        self.assertNotIn('stock.balayer_machins', planifiees)

    def test_cas_positif_construit_la_commande_est_planifiee(self):
        planifiees = gard.taches_planifiees(BEAT_AVEC)
        self.assertIn('stock.balayer_machins', planifiees)


class DepotReelTests(unittest.TestCase):
    """Le garde tourne sur le VRAI dépôt : il doit être vert (toute commande
    « cron/beat » non planifiée est soit planifiée, soit dans la base de
    référence) — et les huit balayages d'AUD231 doivent être planifiés."""

    HUIT_AUD231 = (
        'stock.generer_comptages_tournants',
        'stock.liberer_vagues_planifiees',
        'pos.liberer_reservations_expirees',
        'installations.generer_interventions_recurrentes',
        'gestion_projet.generer_taches_recurrentes',
        'gestion_projet.alertes_retards_projets',
        'gestion_projet.rappels_timesheets',
        'btp_chantier.alertes_rfi_retard',
    )

    def test_le_garde_est_vert_sur_le_depot(self):
        self.assertEqual(gard.main([]), 0)

    def test_les_huit_balayages_aud231_sont_planifies(self):
        planifiees = gard.taches_planifiees()
        for nom in self.HUIT_AUD231:
            self.assertIn(nom, planifiees, f'{nom} absent du beat_schedule')

    def test_aucun_des_huit_ne_reste_en_base_de_reference(self):
        baseline = gard._lire_baseline()
        for nom in self.HUIT_AUD231:
            self.assertNotIn(nom, baseline)

    def test_la_base_de_reference_ne_contient_que_du_reel(self):
        """Une entrée périmée (commande disparue ou désormais planifiée) doit
        faire échouer le garde — donc n'existe pas ici."""
        manquantes = {
            cle for cle, _ in gard.collecter_manquantes(
                gard.taches_planifiees())
        }
        self.assertEqual(gard._lire_baseline() - manquantes, set())


if __name__ == '__main__':
    unittest.main()

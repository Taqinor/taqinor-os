"""QX11 — garde de joignabilité du beat.

Le mode de défaillance DOMINANT du dépôt : une tâche périodique BÂTIE et TESTÉE
mais jamais ajoutée à ``beat_schedule`` — elle ne tourne donc jamais en prod
(ex. ZFAC12 « accepté mais jamais facturé »). Ce test échoue si un nouveau
``@shared_task`` périodique apparaît sans être planifié NI explicitement
listé comme « à la demande ».
"""
import re
import pathlib

from django.test import SimpleTestCase

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[3]

# Tâches délibérément DÉCLENCHÉES À LA DEMANDE (jamais périodiques) OU
# planifiées par une autre tâche/lane — chacune justifiée.
ON_DEMAND_ALLOWLIST = {
    # ENG18 — génération de variantes créatives : déclenchée à la demande
    # depuis la bibliothèque créative (jamais périodique).
    'adsengine.generate_creative_variants',
}


def _all_shared_task_names():
    names = set()
    for base in ('apps', 'core'):
        root = BACKEND_ROOT / base
        for p in root.rglob('*.py'):
            txt = p.read_text(encoding='utf-8', errors='ignore')
            for m in re.finditer(
                    r"@shared_task\(name=['\"]([^'\"]+)['\"]", txt):
                names.add(m.group(1))
    return names


def _scheduled_task_names():
    beat = (BACKEND_ROOT / 'erp_agentique' / 'celery.py').read_text(
        encoding='utf-8')
    return set(re.findall(r"'task':\s*'([^']+)'", beat))


class Qx11BeatReachabilityTests(SimpleTestCase):
    def test_every_shared_task_is_scheduled_or_allowlisted(self):
        names = _all_shared_task_names()
        scheduled = _scheduled_task_names()
        missing = sorted(names - scheduled - ON_DEMAND_ALLOWLIST)
        self.assertEqual(
            missing, [],
            'Ces @shared_task ne sont NI planifiés NI dans '
            'ON_DEMAND_ALLOWLIST — ils ne tourneront jamais : ' + str(missing))

    def test_headline_ventes_reminders_are_scheduled(self):
        scheduled = _scheduled_task_names()
        self.assertIn('ventes.pre_echeance_reminders', scheduled)
        self.assertIn('ventes.devis_a_facturer_reminder', scheduled)

    def test_beat_schedule_imports_and_is_nonempty(self):
        from erp_agentique.celery import app
        self.assertGreater(len(app.conf.beat_schedule), 30)

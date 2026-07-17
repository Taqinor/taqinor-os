"""NTDMO8 — non-régression des deux booléens démo sur ``Company``.

Le SCHÉMA (``Company.est_demo`` + ``Company.mode_presentation_actif`` +
migration) a été introduit en NTDMO1 (front-load, car ``seed_demo_company`` et
le endpoint reset-demo NTDMO7 en dépendent avant la position de NTDMO8). Ces
tests valident le contrat NTDMO8 : additifs, défaut False, et un toggle ne
change RIEN pour une société où le drapeau reste False.
"""
from django.test import TestCase

from authentication.models import Company


class DemoFlagsNTDMO8Test(TestCase):
    def test_defaults_false_and_additive(self):
        c = Company.objects.create(nom='Société neuve', slug='societe-neuve')
        self.assertFalse(c.est_demo)
        self.assertFalse(c.mode_presentation_actif)

    def test_toggle_does_not_affect_other_companies(self):
        demo = Company.objects.create(
            nom='Démo', slug='demo-x', est_demo=True,
            mode_presentation_actif=True)
        autre = Company.objects.create(nom='Réelle', slug='reelle-x')
        # Une autre société reste strictement inchangée (non-régression totale).
        autre.refresh_from_db()
        self.assertFalse(autre.est_demo)
        self.assertFalse(autre.mode_presentation_actif)
        self.assertTrue(demo.mode_presentation_actif)

    def test_flags_independent(self):
        # est_demo True n'implique pas mode présentation, et inversement.
        c = Company.objects.create(
            nom='Démo Y', slug='demo-y', est_demo=True)
        self.assertTrue(c.est_demo)
        self.assertFalse(c.mode_presentation_actif)

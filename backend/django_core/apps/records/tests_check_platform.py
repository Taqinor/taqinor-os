"""ARC8 — unit test du garde-fou ``check_platform`` (convergence du chatter).

Le garde-fou rejette toute NOUVELLE classe modèle ``*Activity`` hors de
``apps/records`` (le chatter doit converger sur ``records.Activity``). On teste
la logique PURE (``apps.records.platform_guards``) — pas d'accès disque — que le
script ``scripts/check_platform.py`` réutilise comme source unique de vérité.
"""
from django.test import SimpleTestCase

from apps.records.platform_guards import (
    GRANDFATHERED_ACTIVITY_CLASSES,
    scan_activity_classes,
)

# Une NOUVELLE classe *Activity fictive dans une app métier (ex. flotte).
FICTIVE_NEW_ACTIVITY = (
    "class SinistreActivity(models.Model):\n"
    "    company = models.ForeignKey('authentication.Company', on_delete=1)\n"
)

# Une classe *Activity déjà grand-fatherée (existe à l'heure d'ARC8).
GRANDFATHERED_SOURCE = (
    "class LeadActivity(models.Model):\n"
    "    pass\n"
)


class TestActivityGuard(SimpleTestCase):
    def test_new_activity_class_is_red(self):
        """Une nouvelle classe *Activity fictive hors records = violation."""
        found = scan_activity_classes("flotte", FICTIVE_NEW_ACTIVITY)
        self.assertIn("flotte.SinistreActivity", found)

    def test_grandfathered_class_is_green(self):
        """Une des 13 classes héritées ne déclenche jamais le garde-fou."""
        found = scan_activity_classes("crm", GRANDFATHERED_SOURCE)
        self.assertEqual(found, [])

    def test_records_app_is_exempt(self):
        """records POSSÈDE l'Activity générique : jamais signalé, même une
        classe nommée *Activity."""
        found = scan_activity_classes(
            "records", "class WeirdActivity(models.Model):\n    pass\n")
        self.assertEqual(found, [])

    def test_non_model_class_ignored(self):
        """Une classe *Activity qui n'est PAS un modèle Django (pas de base
        ``Model``) est ignorée (ex. un helper, une TextChoices n'est pas au
        niveau module)."""
        found = scan_activity_classes(
            "flotte", "class HelperActivity(object):\n    pass\n")
        self.assertEqual(found, [])

    def test_grandfathered_set_covers_real_tree(self):
        """Garde-fou du garde-fou : les 13 classes héritées réelles sont bien
        gelées (sinon le scan du dépôt serait rouge dès l'introduction du
        script). On vérifie la présence des pilotes ARC8."""
        self.assertIn("contrats.ContratActivity", GRANDFATHERED_ACTIVITY_CLASSES)
        self.assertIn("flotte.ActiviteFlotte", GRANDFATHERED_ACTIVITY_CLASSES)

"""ARC8/ARC26 — unit tests des garde-fous ``check_platform``.

ARC8 : rejeter toute NOUVELLE classe modèle ``*Activity`` hors de
``apps/records`` (le chatter doit converger sur ``records.Activity``).
ARC26 : rejeter tout NOUVEAU ``FileField``/``ImageField`` hors de la liste
gelée (toute nouvelle pièce jointe passe par ``records.Attachment`` ou
``ged.Document``). On teste la logique PURE (``apps.records.platform_guards``)
— pas d'accès disque — que le script ``scripts/check_platform.py`` réutilise
comme source unique de vérité.
"""
from django.test import SimpleTestCase

from apps.records.platform_guards import (
    GRANDFATHERED_ACTIVITY_CLASSES,
    GRANDFATHERED_FILEFIELDS,
    scan_activity_classes,
    scan_filefields,
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


class TestFileFieldGuard(SimpleTestCase):
    """ARC26 — « plus de FileField sauvage »."""

    def test_new_filefield_in_new_file_is_red(self):
        """Un FileField fictif dans un fichier non gelé = violation."""
        src = "    piece = models.FileField(upload_to='x/')\n"
        found = scan_filefields("apps/sav/models.py", src)
        self.assertEqual(found, ["apps/sav/models.py:piece"])

    def test_imagefield_is_red_too(self):
        src = "    photo_avant = models.ImageField(upload_to='x/')\n"
        found = scan_filefields("apps/qhse/models.py", src)
        self.assertEqual(found, ["apps/qhse/models.py:photo_avant"])

    def test_grandfathered_exact_count_is_green(self):
        """Les deux ``fichier`` gelés de compta ne déclenchent rien."""
        src = (
            "    fichier = models.FileField(upload_to='a/')\n"
            "    fichier = models.FileField(upload_to='b/')\n"
        )
        found = scan_filefields("apps/compta/models.py", src)
        self.assertEqual(found, [])

    def test_count_overflow_is_red(self):
        """Un 3ᵉ ``fichier`` dans compta (compte gelé = 2) = violation."""
        src = (
            "    fichier = models.FileField(upload_to='a/')\n"
            "    fichier = models.FileField(upload_to='b/')\n"
            "    fichier = models.FileField(upload_to='c/')\n"
        )
        found = scan_filefields("apps/compta/models.py", src)
        self.assertEqual(found, ["apps/compta/models.py:fichier"])

    def test_frozen_list_shape(self):
        """La liste gelée committée couvre bien les 7 fichiers / 17 champs de
        l'inventaire ARC26 (grep du 2026-07-10)."""
        self.assertEqual(len(GRANDFATHERED_FILEFIELDS), 7)
        total = sum(sum(v.values()) for v in GRANDFATHERED_FILEFIELDS.values())
        self.assertEqual(total, 17)

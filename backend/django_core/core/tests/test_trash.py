"""Tests FG388 — corbeille / restauration (soft-delete + undo).

Couvre :
  * mixin ``SoftDeleteModel`` : manager masque les supprimés, ``all_objects``
    les voit, ``soft_delete`` journalise, ``restore`` ferme l'entrée ;
  * services ``core.trash`` : corbeille scopée société, fenêtre d'undo,
    restauration dynamique via contenttypes ;
  * découplage : un modèle de test concret est créé via ``isolate_apps`` +
    schema_editor — aucun import d'app domaine.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection, models
from django.test import TestCase
from django.test.utils import isolate_apps
from django.utils import timezone

from authentication.models import Company
from core import trash
from core.models import DeletionRecord, SoftDeleteModel

User = get_user_model()


@isolate_apps('core')
class SoftDeleteMixinTests(TestCase):
    """Exerce le mixin via un modèle concret éphémère (table créée à la volée)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        class Widget(SoftDeleteModel):
            company = models.ForeignKey(
                'authentication.Company', on_delete=models.CASCADE)
            nom = models.CharField(max_length=50)

            class Meta:
                app_label = 'core'

        cls.Widget = Widget
        with connection.schema_editor() as editor:
            editor.create_model(Widget)

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as editor:
            editor.delete_model(cls.Widget)
        super().tearDownClass()

    def setUp(self):
        self.company = Company.objects.create(nom='ACME')
        self.user = User.objects.create_user(
            username='u1', password='x', company=self.company)

    def test_soft_delete_hides_and_journals(self):
        w = self.Widget.objects.create(company=self.company, nom='W')
        w.soft_delete(user=self.user)
        # Manager par défaut le masque ; all_objects le voit.
        self.assertFalse(self.Widget.objects.filter(pk=w.pk).exists())
        self.assertTrue(self.Widget.all_objects.filter(pk=w.pk).exists())
        # Une entrée de corbeille a été créée pour la société.
        rec = DeletionRecord.objects.get(object_id=w.pk)
        self.assertEqual(rec.company, self.company)
        self.assertIsNone(rec.restored_at)

    def test_restore_reactivates_and_closes_record(self):
        w = self.Widget.objects.create(company=self.company, nom='W')
        w.soft_delete(user=self.user)
        rec = DeletionRecord.objects.get(object_id=w.pk)
        restored = trash.restaurer(rec)
        self.assertIsNotNone(restored)
        self.assertTrue(self.Widget.objects.filter(pk=w.pk).exists())
        rec.refresh_from_db()
        self.assertIsNotNone(rec.restored_at)


class TrashServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other = Company.objects.create(nom='Autre')

    def _make_record(self, company, minutes_ago=0):
        from django.contrib.contenttypes.models import ContentType
        rec = DeletionRecord.objects.create(
            company=company,
            content_type=ContentType.objects.get_for_model(Company),
            object_id=999, label='x')
        if minutes_ago:
            DeletionRecord.objects.filter(pk=rec.pk).update(
                created_at=timezone.now() - timedelta(minutes=minutes_ago))
        return rec

    def test_corbeille_scoped_to_company(self):
        self._make_record(self.company)
        self._make_record(self.other)
        self.assertEqual(trash.corbeille(self.company).count(), 1)

    def test_undo_window_excludes_old(self):
        self._make_record(self.company, minutes_ago=0)
        self._make_record(self.company, minutes_ago=120)  # hors fenêtre
        self.assertEqual(
            trash.dans_fenetre_undo(self.company, minutes=30).count(), 1)

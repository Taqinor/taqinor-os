"""Tests FG388 — corbeille / restauration (soft-delete + undo).

Couvre :
  * mixin ``SoftDeleteModel`` : structure (champs ``is_deleted`` /
    ``deleted_at`` / ``deleted_by`` + managers ``objects`` / ``all_objects``) ;
  * services ``core.trash`` : corbeille scopée société, fenêtre d'undo,
    restauration dynamique via contenttypes (chemin générique : cible sans
    ``restore`` → l'entrée est fermée proprement) ;
  * découplage : aucun import d'app domaine, AUCUNE table éphémère (pas de
    ``schema_editor`` qui forcerait un rebuild complet du schéma de test).
"""
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from core import trash
from core.models import DeletionRecord, SoftDeleteManager, SoftDeleteModel


class SoftDeleteMixinStructureTests(TestCase):
    """Vérifie la structure du mixin sans créer de table éphémère."""

    def test_softdelete_fields_present(self):
        names = {f.name for f in SoftDeleteModel._meta.get_fields()}
        self.assertIn('is_deleted', names)
        self.assertIn('deleted_at', names)
        self.assertIn('deleted_by', names)

    def test_softdelete_managers(self):
        # Modèle abstrait : on inspecte les managers déclarés sans déclencher
        # le garde-fou « Manager isn't available; abstract ».
        managers = {m.name: m for m in SoftDeleteModel._meta.managers}
        self.assertIn('objects', managers)
        self.assertIn('all_objects', managers)
        self.assertIsInstance(managers['objects'], SoftDeleteManager)

    def test_softdelete_methods_present(self):
        self.assertTrue(callable(getattr(SoftDeleteModel, 'soft_delete', None)))
        self.assertTrue(callable(getattr(SoftDeleteModel, 'restore', None)))


class TrashServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other = Company.objects.create(nom='Autre')

    def _make_record(self, company, minutes_ago=0, object_id=999,
                     model=Company):
        rec = DeletionRecord.objects.create(
            company=company,
            content_type=ContentType.objects.get_for_model(model),
            object_id=object_id, label='x')
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

    def test_restaurer_missing_target_closes_record(self):
        # Cible inexistante (object_id qui n'existe pas) → l'entrée est fermée
        # proprement, jamais d'exception.
        rec = self._make_record(self.company, object_id=10_000_000)
        obj = trash.restaurer(rec)
        rec.refresh_from_db()
        self.assertIsNone(obj)
        self.assertIsNotNone(rec.restored_at)

    def test_restaurer_target_without_restore_closes_record(self):
        # Cible existante mais SANS méthode ``restore`` (Company n'est pas
        # SoftDelete) → chemin générique : l'entrée est fermée, l'objet reste.
        rec = self._make_record(self.company, object_id=self.other.pk)
        trash.restaurer(rec)
        rec.refresh_from_db()
        self.assertIsNotNone(rec.restored_at)
        self.assertTrue(Company.objects.filter(pk=self.other.pk).exists())

    def test_restaurer_already_restored_is_noop(self):
        rec = self._make_record(self.company)
        DeletionRecord.objects.filter(pk=rec.pk).update(
            restored_at=timezone.now())
        rec.refresh_from_db()
        self.assertIsNone(trash.restaurer(rec))

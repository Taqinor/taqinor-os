"""GED25 — Purge automatique de la corbeille échue (DRY-RUN d'abord).

Couvre :
  * DRY-RUN par défaut : aucun document effacé, seulement compté ;
  * `apply=True` efface réellement les documents en corbeille échue ;
  * le délai de grâce : un document en corbeille trop récent n'est pas éligible ;
  * un document VIVANT (hors corbeille) n'est jamais purgé ;
  * gardes légales : un document archivé (GED23) ou sous legal hold (GED24)
    en corbeille échue est EXCLU (protégé), jamais effacé ni 500 ;
  * isolation par société (la purge de A ne touche pas B) ;
  * la tâche Celery `ged.purge_corbeille_echue` reste dry-run sans opt-in.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, Folder

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class PurgeBase(TestCase):
    def setUp(self):
        self.co_a = make_company('ged25-a', 'Ged25 A')
        self.co_b = make_company('ged25-b', 'Ged25 B')
        self.admin_a = make_user(self.co_a, 'ged25-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'ged25-admin-b', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.cab_b = Cabinet.objects.create(company=self.co_b, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Dossier B')

    def _doc(self, company, folder, nom):
        return Document.objects.create(company=company, folder=folder, nom=nom)

    def _en_corbeille_depuis(self, document, jours):
        """Met le document en corbeille avec une date `supprime_le` reculée."""
        document.supprime_le = timezone.now() - datetime.timedelta(days=jours)
        document.supprime_par = self.admin_a
        document.save(update_fields=['supprime_le', 'supprime_par'])
        return document


class PurgeServiceTests(PurgeBase):
    def test_dry_run_compte_sans_effacer(self):
        doc = self._doc(self.co_a, self.folder_a, 'vieux corbeille')
        self._en_corbeille_depuis(doc, 40)
        res = services.purger_corbeille_echue(self.co_a, apply=False)
        self.assertTrue(res['dry_run'])
        self.assertEqual(res['eligibles'], 1)
        self.assertEqual(res['purges'], 1)
        # Rien n'est réellement effacé en dry-run.
        self.assertTrue(Document.objects.filter(pk=doc.pk).exists())

    def test_apply_efface_reellement(self):
        doc = self._doc(self.co_a, self.folder_a, 'a purger')
        self._en_corbeille_depuis(doc, 40)
        res = services.purger_corbeille_echue(self.co_a, apply=True)
        self.assertFalse(res['dry_run'])
        self.assertEqual(res['purges'], 1)
        self.assertFalse(Document.objects.filter(pk=doc.pk).exists())

    def test_delai_de_grace_protege_recent(self):
        doc = self._doc(self.co_a, self.folder_a, 'recent corbeille')
        self._en_corbeille_depuis(doc, 5)  # < 30 j de grâce
        res = services.purger_corbeille_echue(self.co_a, apply=True)
        self.assertEqual(res['eligibles'], 0)
        self.assertTrue(Document.objects.filter(pk=doc.pk).exists())

    def test_document_vivant_jamais_purge(self):
        doc = self._doc(self.co_a, self.folder_a, 'vivant')
        res = services.purger_corbeille_echue(self.co_a, apply=True)
        self.assertEqual(res['eligibles'], 0)
        self.assertTrue(Document.objects.filter(pk=doc.pk).exists())

    def test_archive_legalement_exclu(self):
        doc = self._doc(self.co_a, self.folder_a, 'archive en corbeille')
        services.add_version(
            doc, file_key='k/archive.pdf', company=self.co_a, filename='a.pdf')
        self._en_corbeille_depuis(doc, 40)
        services.archiver_legalement(doc, user=self.admin_a, motif='preuve')
        res = services.purger_corbeille_echue(self.co_a, apply=True)
        self.assertEqual(res['proteges'], 1)
        self.assertEqual(res['purges'], 0)
        self.assertTrue(Document.objects.filter(pk=doc.pk).exists())

    def test_legal_hold_exclu(self):
        doc = self._doc(self.co_a, self.folder_a, 'hold en corbeille')
        self._en_corbeille_depuis(doc, 40)
        services.placer_legal_hold(doc, user=self.admin_a, motif='litige')
        res = services.purger_corbeille_echue(self.co_a, apply=True)
        self.assertEqual(res['proteges'], 1)
        self.assertEqual(res['purges'], 0)
        self.assertTrue(Document.objects.filter(pk=doc.pk).exists())

    def test_isolation_societe(self):
        doc_a = self._doc(self.co_a, self.folder_a, 'a')
        doc_b = self._doc(self.co_b, self.folder_b, 'b')
        self._en_corbeille_depuis(doc_a, 40)
        doc_b.supprime_le = timezone.now() - datetime.timedelta(days=40)
        doc_b.supprime_par = self.admin_b
        doc_b.save(update_fields=['supprime_le', 'supprime_par'])
        services.purger_corbeille_echue(self.co_a, apply=True)
        # B intact (purge bornée à A).
        self.assertTrue(Document.objects.filter(pk=doc_b.pk).exists())
        self.assertFalse(Document.objects.filter(pk=doc_a.pk).exists())

    def test_toutes_societes_agrege(self):
        doc_a = self._doc(self.co_a, self.folder_a, 'a')
        doc_b = self._doc(self.co_b, self.folder_b, 'b')
        self._en_corbeille_depuis(doc_a, 40)
        doc_b.supprime_le = timezone.now() - datetime.timedelta(days=40)
        doc_b.save(update_fields=['supprime_le'])
        res = services.purger_corbeille_toutes_societes(apply=False)
        self.assertTrue(res['dry_run'])
        self.assertGreaterEqual(res['eligibles'], 2)

    def test_grace_days_surchargeable(self):
        doc = self._doc(self.co_a, self.folder_a, 'recent')
        self._en_corbeille_depuis(doc, 5)
        # Avec un délai de grâce de 1 jour, 5 j en corbeille devient éligible.
        res = services.purger_corbeille_echue(
            self.co_a, grace_days=1, apply=False)
        self.assertEqual(res['eligibles'], 1)


class PurgeTaskTests(PurgeBase):
    @override_settings(GED_PURGE_AUTO_APPLY=False)
    def test_task_dry_run_par_defaut(self):
        from apps.ged.tasks import purge_corbeille_echue
        doc = self._doc(self.co_a, self.folder_a, 'task dry')
        self._en_corbeille_depuis(doc, 40)
        result = purge_corbeille_echue()
        self.assertTrue(result['dry_run'])
        self.assertTrue(Document.objects.filter(pk=doc.pk).exists())

    @override_settings(GED_PURGE_AUTO_APPLY=True)
    def test_task_apply_opt_in(self):
        from apps.ged.tasks import purge_corbeille_echue
        doc = self._doc(self.co_a, self.folder_a, 'task apply')
        self._en_corbeille_depuis(doc, 40)
        result = purge_corbeille_echue()
        self.assertFalse(result['dry_run'])
        self.assertFalse(Document.objects.filter(pk=doc.pk).exists())

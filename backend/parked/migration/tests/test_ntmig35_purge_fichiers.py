"""NTMIG35 — purge sécurisée des fichiers source après migration."""
from django.test import TestCase
from django.utils import timezone

from apps.migration import services
from apps.migration.models import (
    LotMigration, ProjetMigration, RapportReconciliation)

from ._base import make_company
from ._stockage_factice import patcher_stockage

CSV = b'Nom,Email\nClient A,a@exemple.ma\n'


class PurgeFichiersSourceTests(TestCase):

    def setUp(self):
        self.stockage = patcher_stockage(self)
        self.company = make_company('ntmig35', 'NTMIG35')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Bascule', source='excel')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

    def _memoriser(self):
        services.memoriser_fichier_source(self.lot, CSV, 'clients.csv')
        self.lot.save(update_fields=[
            'fichier_source_cle', 'fichier_source_nom', 'updated_at'])

    def test_fichier_memorise_puis_relu(self):
        self._memoriser()
        self.lot.refresh_from_db()
        contenu, nom = services.fichier_source_de(self.lot)
        self.assertEqual(contenu, CSV)
        self.assertEqual(nom, 'clients.csv')

    def test_projet_termine_depuis_plus_de_30j_est_purge(self):
        self._memoriser()
        RapportReconciliation.objects.create(
            company=self.company, lot=self.lot, nb_source=1,
            nb_cible_crees=1, conforme=True)
        self.projet.statut = ProjetMigration.Statut.TERMINE
        self.projet.date_fin = timezone.now() - timezone.timedelta(days=31)
        self.projet.save(update_fields=['statut', 'date_fin'])

        resultat = services.purger_fichiers_expires()

        self.assertEqual(resultat['projets'], 1)
        self.assertEqual(resultat['fichiers'], 1)
        self.lot.refresh_from_db()
        self.projet.refresh_from_db()
        self.assertFalse(bool(self.lot.fichier_source_cle))
        self.assertTrue(self.projet.fichiers_purges)
        self.assertIsNone(services.fichier_source_de(self.lot))
        # Les rapports (agrégats non-PII) sont CONSERVÉS.
        self.assertEqual(self.lot.rapports.count(), 1)
        self.assertTrue(self.lot.rapports.first().conforme)

    def test_projet_termine_recemment_n_est_pas_purge(self):
        self._memoriser()
        self.projet.statut = ProjetMigration.Statut.TERMINE
        self.projet.date_fin = timezone.now() - timezone.timedelta(days=5)
        self.projet.save(update_fields=['statut', 'date_fin'])

        services.purger_fichiers_expires()

        self.lot.refresh_from_db()
        self.assertTrue(bool(self.lot.fichier_source_cle))

    def test_projet_en_cours_n_est_jamais_purge(self):
        self._memoriser()
        self.projet.date_fin = timezone.now() - timezone.timedelta(days=90)
        self.projet.save(update_fields=['date_fin'])

        services.purger_fichiers_expires()

        self.lot.refresh_from_db()
        self.assertTrue(bool(self.lot.fichier_source_cle))
        self.projet.refresh_from_db()
        self.assertFalse(self.projet.fichiers_purges)

    def test_purge_idempotente(self):
        self._memoriser()
        self.projet.statut = ProjetMigration.Statut.TERMINE
        self.projet.date_fin = timezone.now() - timezone.timedelta(days=45)
        self.projet.save(update_fields=['statut', 'date_fin'])

        services.purger_fichiers_expires()
        second = services.purger_fichiers_expires()

        self.assertEqual(second, {'projets': 0, 'fichiers': 0})

    def test_tache_beat_appelle_le_service(self):
        from apps.migration.tasks import purger_fichiers_migration

        self.assertEqual(
            purger_fichiers_migration(), {'projets': 0, 'fichiers': 0})

    def test_memorisation_remplace_le_fichier_precedent(self):
        """Une nouvelle analyse ne laisse pas traîner l'ancien fichier PII."""
        self._memoriser()
        ancien = self.lot.fichier_source_cle
        services.memoriser_fichier_source(
            self.lot, b'Nom,Email\nClient B,b@exemple.ma\n', 'clients2.csv')
        self.lot.save(update_fields=[
            'fichier_source_cle', 'fichier_source_nom', 'updated_at'])
        self.assertNotIn(ancien, self.stockage.objets)
        self.assertIn(self.lot.fichier_source_cle, self.stockage.objets)
        self.assertEqual(self.lot.fichier_source_nom, 'clients2.csv')

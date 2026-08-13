"""NTMIG38 — reprise sur incident : un lot partiellement chargé repart après
sa dernière ligne commitée, sans dupliquer ce qui est déjà passé."""
import tempfile

from django.test import TestCase, override_settings

from apps.crm.models import Client
from apps.dataimport.models import ImportJob, ImportJobRow
from apps.migration import services
from apps.migration.models import LotMigration, ProjetMigration

from ._base import auth, make_admin, make_company

_MEDIA = tempfile.mkdtemp(prefix='ntmig38-')


def _csv(debut, fin):
    lignes = ['Nom,Email']
    for i in range(debut, fin + 1):
        lignes.append(f'Client {i:04d},client{i:04d}@exemple.ma')
    return ('\n'.join(lignes) + '\n').encode('utf-8')


@override_settings(MEDIA_ROOT=_MEDIA)
class RepriseLotTests(TestCase):

    def setUp(self):
        self.company = make_company('ntmig38', 'NTMIG38')
        self.admin = make_admin(self.company, 'ntmig38-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Reprise', source='excel')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

    def _simuler_chargement_interrompu(self, jusqu_a, total):
        """Charge les `jusqu_a` premières lignes, comme une passe coupée."""
        services.charger_lot(
            self.lot, _csv(1, jusqu_a), 'clients.csv', user=self.admin)
        self.lot.refresh_from_db()
        # Le fichier D'ORIGINE (total lignes) est celui du projet : c'est lui
        # qu'on mémorise, la passe n'en a traité qu'un début.
        services.memoriser_fichier_source(
            self.lot, _csv(1, total), 'clients.csv')
        self.lot.save(update_fields=[
            'fichier_source', 'fichier_source_nom', 'updated_at'])

    def test_reprise_apres_la_derniere_ligne_commitee(self):
        self._simuler_chargement_interrompu(jusqu_a=60, total=100)
        self.assertEqual(Client.objects.filter(
            company=self.company).count(), 60)

        rapport = services.reprendre_lot(self.lot, user=self.admin)

        self.assertEqual(rapport['reprise_depuis_ligne'], 61)
        self.assertEqual(rapport['lignes_rejouees'], 40)
        self.assertEqual(rapport['total_source'], 100)
        # 100 clients au total, aucun doublon des 60 premiers.
        self.assertEqual(Client.objects.filter(
            company=self.company).count(), 100)
        self.assertEqual(Client.objects.filter(
            company=self.company, nom='Client 0001').count(), 1)

    def test_compteurs_cumules_apres_reprise(self):
        self._simuler_chargement_interrompu(jusqu_a=60, total=100)
        services.reprendre_lot(self.lot, user=self.admin)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.source_lignes, 100)
        self.assertEqual(self.lot.crees + self.lot.maj, 100)

    def test_reconciliation_conforme_apres_reprise(self):
        self._simuler_chargement_interrompu(jusqu_a=60, total=100)
        services.reprendre_lot(self.lot, user=self.admin)
        self.lot.refresh_from_db()
        rapport = services.reconcilier_lot(self.lot)
        self.assertTrue(rapport.conforme, rapport.ecarts)
        self.assertEqual(rapport.nb_source, 100)

    def test_seconde_reprise_repart_du_bon_endroit(self):
        """Le décalage est mémorisé : la 2ᵉ reprise ne rejoue pas la 1ʳᵉ."""
        self._simuler_chargement_interrompu(jusqu_a=40, total=100)
        # 1ʳᵉ reprise sur un fichier volontairement tronqué à 70 lignes
        # (comme si l'incident s'était reproduit à la 70ᵉ).
        services.reprendre_lot(
            self.lot, _csv(1, 70), 'clients.csv', user=self.admin)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.fichier_offset_lignes, 40)

        rapport = services.reprendre_lot(
            self.lot, _csv(1, 100), 'clients.csv', user=self.admin)

        self.assertEqual(rapport['reprise_depuis_ligne'], 71)
        self.assertEqual(Client.objects.filter(
            company=self.company).count(), 100)

    def test_le_fichier_original_reste_memorise(self):
        self._simuler_chargement_interrompu(jusqu_a=60, total=100)
        services.reprendre_lot(self.lot, user=self.admin)
        self.lot.refresh_from_db()
        contenu, _ = services.fichier_source_de(self.lot)
        self.assertIn(b'Client 0001', contenu)
        self.assertIn(b'Client 0100', contenu)

    def test_rien_a_reprendre(self):
        services.charger_lot(
            self.lot, _csv(1, 10), 'clients.csv', user=self.admin)
        self.lot.refresh_from_db()
        with self.assertRaises(services.RepriseImpossible):
            services.reprendre_lot(self.lot, user=self.admin)

    def test_sans_fichier_memorise_la_reprise_est_refusee(self):
        job = ImportJob.objects.create(
            company=self.company, target='clients', total_lignes=10)
        ImportJobRow.objects.create(
            job=job, ligne=5, statut=ImportJobRow.Statut.OK)
        self.lot.import_job = job
        self.lot.save(update_fields=['import_job'])
        with self.assertRaises(services.RepriseImpossible):
            services.reprendre_lot(self.lot, user=self.admin)

    def test_lot_reconcilie_ne_se_reprend_pas(self):
        self._simuler_chargement_interrompu(jusqu_a=60, total=100)
        self.lot.statut = LotMigration.Statut.RECONCILIE
        self.lot.save(update_fields=['statut'])
        with self.assertRaises(services.LotFige):
            services.reprendre_lot(self.lot, user=self.admin)

    def test_endpoint_reprendre(self):
        self._simuler_chargement_interrompu(jusqu_a=60, total=100)
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/migration/lots-migration/{self.lot.pk}/reprendre/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['reprise']['reprise_depuis_ligne'], 61)

    def test_endpoint_reprendre_sans_rien_a_reprendre_renvoie_400(self):
        services.charger_lot(
            self.lot, _csv(1, 10), 'clients.csv', user=self.admin)
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/migration/lots-migration/{self.lot.pk}/reprendre/')
        self.assertEqual(resp.status_code, 400)

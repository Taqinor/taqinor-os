"""NTMIG15 — étalonnage tenant : external_system stable ``migration:<source>``.

Rejouer deux fois le même fichier sur un projet ne crée les enregistrements
qu'une fois (2ᵉ passe = 0 création, N mises à jour) grâce aux ``ExternalRef``
posés avec un système externe stable — qui permet aussi à un rollback de lot
de cibler précisément ce que CE projet a créé.

Couvre aussi la garantie de non-destruction : le chargement est en
REMPLISSAGE SEUL, donc une colonne vide (ou absente) du fichier source ne
remplace jamais une valeur déjà saisie dans l'ERP.
"""
from django.test import TestCase

from apps.crm.models import Client
from apps.dataimport.models import ExternalRef
from apps.migration import services
from apps.migration.models import LotMigration, ProjetMigration

from ._base import auth, make_admin, make_company

CSV = (
    b'nom,email,telephone,external_id\n'
    b'Alpha SARL,alpha@ex.ma,0600000001,ODOO-1\n'
    b'Beta SA,beta@ex.ma,0600000002,ODOO-2\n'
)

# Même fichier, mais téléphone PRÉSENT-MAIS-VIDE et email absent : le piège
# classique qui a déjà effacé des données ailleurs dans ce dépôt.
CSV_CELLULES_VIDES = (
    b'nom,email,telephone,external_id\n'
    b'Alpha SARL,,,ODOO-1\n'
    b'Beta SA,,,ODOO-2\n'
)


class ExternalSystemTests(TestCase):
    def setUp(self):
        self.company = make_company('mig-g15-co', 'Migr G15')
        self.user = make_admin(self.company, 'mig-g15-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Client D', source='odoo')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

    def test_external_system_derive_de_la_source(self):
        self.assertEqual(
            services.external_system_pour(self.projet), 'migration:odoo')
        sage = ProjetMigration.objects.create(
            company=self.company, nom='Autre', source='sage')
        self.assertEqual(
            services.external_system_pour(sage), 'migration:sage')

    def test_rejeu_ne_duplique_pas(self):
        r1 = services.charger_lot(
            self.lot, CSV, 'clients.csv', mode='upsert', user=self.user)
        self.assertEqual(r1['created'], 2)

        # 2ᵉ passe du MÊME fichier : 0 création, N mises à jour.
        r2 = services.charger_lot(
            self.lot, CSV, 'clients.csv', mode='upsert', user=self.user)
        self.assertEqual(r2['created'], 0)
        self.assertEqual(r2['updated'], 2)
        self.assertEqual(
            Client.objects.filter(company=self.company).count(), 2)

        # Les ExternalRef portent bien le système stable migration:<source>.
        refs = ExternalRef.objects.filter(
            company=self.company, external_system='migration:odoo')
        self.assertEqual(refs.count(), 2)

        # Compteurs miroir du lot = la DERNIÈRE passe (0 créés, 2 màj).
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.crees, 0)
        self.assertEqual(self.lot.maj, 2)
        self.assertEqual(self.lot.statut, LotMigration.Statut.CHARGE)
        self.assertIsNotNone(self.lot.import_job_id)

    def test_cellule_vide_neffacer_jamais_une_valeur_saisie(self):
        """Le cas qui a déjà détruit des données : cellule présente-mais-vide.

        Elle doit valoir « aucune valeur fournie », jamais « mettre à vide ».
        """
        services.charger_lot(
            self.lot, CSV, 'clients.csv', mode='upsert', user=self.user)
        alpha = Client.objects.get(company=self.company, nom='Alpha SARL')
        # Correction humaine après import.
        Client.objects.filter(pk=alpha.pk).update(
            telephone='0611223344', email='corrige@ex.ma')

        services.charger_lot(
            self.lot, CSV_CELLULES_VIDES, 'clients.csv', mode='upsert',
            user=self.user)

        alpha.refresh_from_db()
        self.assertEqual(alpha.telephone, '0611223344')
        self.assertEqual(alpha.email, 'corrige@ex.ma')

    def test_valeur_saisie_non_ecrasee_par_la_source(self):
        """Remplissage seul : la source ne remplace pas une valeur remplie."""
        services.charger_lot(
            self.lot, CSV, 'clients.csv', mode='upsert', user=self.user)
        alpha = Client.objects.get(company=self.company, nom='Alpha SARL')
        Client.objects.filter(pk=alpha.pk).update(telephone='0699999999')

        result = services.charger_lot(
            self.lot, CSV, 'clients.csv', mode='upsert', user=self.user)

        alpha.refresh_from_db()
        self.assertEqual(alpha.telephone, '0699999999')
        # Le moteur remonte ce qu'il a REFUSÉ d'écraser (audit, pas silence).
        self.assertEqual(result['ecrasements'], 0)
        self.assertTrue(result['refuses'])

    def test_lot_reconcilie_refuse_un_rechargement(self):
        """Recharger un lot déjà réconcilié rendrait son PV mensonger."""
        services.charger_lot(
            self.lot, CSV, 'clients.csv', mode='upsert', user=self.user)
        services.reconcilier_lot(self.lot)
        services.marquer_lot_termine(self.lot)
        self.lot.refresh_from_db()
        with self.assertRaises(services.LotFige):
            services.charger_lot(
                self.lot, CSV, 'clients.csv', mode='upsert', user=self.user)
        with self.assertRaises(services.LotFige):
            services.analyser_lot(self.lot, CSV, 'clients.csv')

    def test_reconcilier_apres_chargement_propre_est_conforme(self):
        services.analyser_lot(self.lot, CSV, 'clients.csv')
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.source_lignes, 2)
        services.charger_lot(
            self.lot, CSV, 'clients.csv', mode='upsert', user=self.user)
        rapport = services.reconcilier_lot(self.lot)
        self.assertTrue(rapport.conforme, rapport.ecarts)
        self.assertEqual(rapport.nb_source, 2)


class AnalyseNecritRienTests(TestCase):
    def setUp(self):
        self.company = make_company('mig-g15dry-co', 'Migr G15 dry')
        self.admin = make_admin(self.company, 'mig-g15dry-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Client DR', source='odoo')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

    def test_analyser_endpoint_ncree_aucun_client(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fichier = SimpleUploadedFile('clients.csv', CSV, content_type='text/csv')
        resp = auth(self.admin).post(
            f'/api/django/migration/lots-migration/{self.lot.pk}/analyser/',
            {'fichier': fichier}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total_lignes'], 2)
        self.assertEqual(
            Client.objects.filter(company=self.company).count(), 0)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.statut, LotMigration.Statut.ANALYSE)

    def test_charger_endpoint_nexpose_pas_dinterrupteur_decrasement(self):
        """Même si le client envoie ``ecraser``, le serveur reste en
        remplissage seul (le paramètre n'est jamais relayé au moteur)."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        api = auth(self.admin)
        fichier = SimpleUploadedFile('clients.csv', CSV, content_type='text/csv')
        api.post(
            f'/api/django/migration/lots-migration/{self.lot.pk}/charger/',
            {'fichier': fichier}, format='multipart')
        alpha = Client.objects.get(company=self.company, nom='Alpha SARL')
        Client.objects.filter(pk=alpha.pk).update(telephone='0655555555')

        fichier2 = SimpleUploadedFile('clients.csv', CSV, content_type='text/csv')
        resp = api.post(
            f'/api/django/migration/lots-migration/{self.lot.pk}/charger/',
            {'fichier': fichier2, 'ecraser': 'true'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['resultat']['ecraser'])
        alpha.refresh_from_db()
        self.assertEqual(alpha.telephone, '0655555555')

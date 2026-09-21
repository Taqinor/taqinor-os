"""NTMIG — régressions d'INTÉGRITÉ trouvées en revue adversariale.

Chaque test ci-dessous correspond à un chemin par lequel le groupe pouvait
soit détruire/corrompre des données, soit — plus insidieux — CERTIFIER
« conforme » une migration qui ne l'était pas. Un PV de migration qui ment est
aussi grave qu'une donnée perdue : c'est la pièce sur laquelle le client signe.
"""
from django.test import TestCase

from apps.crm.models import Client
from apps.migration import services
from apps.migration.models import (
    LotMigration, ProjetMigration, RapportReconciliation)

from ._base import auth, make_admin, make_company

CSV_A = (
    b'nom,email,external_id\n'
    b'Alpha SARL,alpha@ex.ma,ODOO-1\n'
    b'Beta SA,beta@ex.ma,ODOO-2\n'
)
CSV_B = (
    b'nom,email,external_id\n'
    b'Gamma SARL,gamma@ex.ma,ODOO-3\n'
)
# Deux lignes source qui pointent vers le MÊME client (même e-mail).
CSV_FUSION = (
    b'nom,email,external_id\n'
    b'Delta SARL,delta@ex.ma,ODOO-10\n'
    b'Delta SARL (bis),delta@ex.ma,ODOO-11\n'
)


class AnalyseNeLaissePasDeCompteursPerimesTests(TestCase):
    """Analyser un NOUVEAU fichier doit invalider les compteurs de l'ANCIEN
    chargement — sinon on réconcilie le comptage du nouveau fichier contre les
    résultats de l'ancien et on certifie « conforme » un fichier jamais
    importé."""

    def setUp(self):
        self.company = make_company('mig-int1-co', 'Migr int1')
        self.user = make_admin(self.company, 'mig-int1-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='P', source='odoo')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

    def test_analyse_remet_a_zero_les_compteurs_cible(self):
        services.charger_lot(
            self.lot, CSV_A, 'a.csv', user=self.user)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.crees, 2)
        self.assertIsNotNone(self.lot.import_job_id)

        services.analyser_lot(self.lot, CSV_B, 'b.csv')
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.crees, 0)
        self.assertEqual(self.lot.maj, 0)
        self.assertEqual(self.lot.erreurs, 0)
        self.assertIsNone(self.lot.import_job_id)

    def test_reconcilier_apres_une_analyse_seule_nest_jamais_conforme(self):
        """Le scénario complet : charger A, analyser B, réconcilier."""
        services.charger_lot(self.lot, CSV_A, 'a.csv', user=self.user)
        services.analyser_lot(self.lot, CSV_A, 'a.csv')  # même comptage !
        rapport = services.reconcilier_lot(self.lot)
        self.assertFalse(rapport.conforme)
        types = {e['type'] for e in rapport.ecarts}
        self.assertIn('comptage', types)


class DerogationNeSurvitPasAUnRechargementTests(TestCase):
    """Une dérogation porte sur les chiffres du chargement qu'elle couvre.
    La laisser en place après un rechargement clôturerait le NOUVEAU
    chargement sur un motif périmé — et imprimerait ce motif sur le PV."""

    def setUp(self):
        self.company = make_company('mig-int2-co', 'Migr int2')
        self.user = make_admin(self.company, 'mig-int2-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='P', source='odoo')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

    def test_le_rechargement_leve_la_derogation(self):
        services.charger_lot(self.lot, CSV_A, 'a.csv', user=self.user)
        services.deroger_reconcile(self.lot, 'écarts acceptés', self.user)
        self.lot.refresh_from_db()
        self.assertTrue(self.lot.derogation_reconcile)

        services.charger_lot(self.lot, CSV_A, 'a.csv', user=self.user)
        self.lot.refresh_from_db()
        self.assertFalse(self.lot.derogation_reconcile)
        self.assertEqual(self.lot.derogation_motif, '')
        self.assertIsNone(self.lot.derogation_par)
        self.assertIsNone(self.lot.derogation_at)
        # Et la clôture redevient bloquée tant qu'on n'a pas réconcilié.
        with self.assertRaises(services.ReconcileBloque):
            services.marquer_lot_termine(self.lot)


class ModeDeChargementFiltreTests(TestCase):
    """``creer`` ne rapproche rien : accepté depuis une requête HTTP, il
    supprimerait l'idempotence de tout le groupe (doublons à chaque passe)."""

    def setUp(self):
        self.company = make_company('mig-int3-co', 'Migr int3')
        self.user = make_admin(self.company, 'mig-int3-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='P', source='odoo')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

    def test_mode_creer_demande_est_ignore(self):
        r1 = services.charger_lot(
            self.lot, CSV_A, 'a.csv', mode='creer', user=self.user)
        self.assertEqual(r1['mode'], 'upsert')
        r2 = services.charger_lot(
            self.lot, CSV_A, 'a.csv', mode='creer', user=self.user)
        self.assertEqual(r2['created'], 0)
        self.assertEqual(
            Client.objects.filter(company=self.company).count(), 2)

    def test_endpoint_ignore_un_mode_creer_du_corps_de_requete(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        api = auth(self.user)
        url = f'/api/django/migration/lots-migration/{self.lot.pk}/charger/'
        for _ in range(2):
            fichier = SimpleUploadedFile(
                'a.csv', CSV_A, content_type='text/csv')
            resp = api.post(
                url, {'fichier': fichier, 'mode': 'creer'}, format='multipart')
            self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            Client.objects.filter(company=self.company).count(), 2)

    def test_cible_sans_upsert_retombe_sur_creer_sans_lever(self):
        lot_produits = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='products')
        apercu = services.analyser_lot(
            lot_produits, b'nom,prix\nPanneau,100\n', 'p.csv')
        self.assertEqual(apercu['total_lignes'], 1)
        self.assertEqual(apercu['mode'], 'creer')


class ReconcileNeCriePasAuLoupTests(TestCase):
    """Un chargement correct — y compris un ré-import identique — doit rester
    « conforme ». Un faux écart pousserait l'intégrateur à déroger par réflexe
    et viderait la garde NTMIG5 de son sens."""

    def setUp(self):
        self.company = make_company('mig-int4-co', 'Migr int4')
        self.user = make_admin(self.company, 'mig-int4-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='P', source='odoo')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

    def test_chargement_propre_est_conforme(self):
        services.charger_lot(self.lot, CSV_A, 'a.csv', user=self.user)
        self.lot.refresh_from_db()
        rapport = services.reconcilier_lot(self.lot)
        self.assertTrue(rapport.conforme, rapport.ecarts)

    def test_reimport_identique_reste_conforme(self):
        services.charger_lot(self.lot, CSV_A, 'a.csv', user=self.user)
        services.charger_lot(self.lot, CSV_A, 'a.csv', user=self.user)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.crees, 0)
        self.assertEqual(self.lot.maj, 2)
        rapport = services.reconcilier_lot(self.lot)
        self.assertTrue(rapport.conforme, rapport.ecarts)

    def test_deux_lignes_sur_un_seul_client_limite_connue(self):
        """LIMITE DOCUMENTÉE (pas une régression) : le moteur compte une màj
        par LIGNE, donc deux lignes fusionnées passent le comptage. La
        détection exige le nombre d'enregistrements distincts touchés, que
        ``dataimport.commit`` ne renvoie pas — c'est à cette app-là de
        l'ajouter, pas à une heuristique locale."""
        services.charger_lot(self.lot, CSV_FUSION, 'f.csv', user=self.user)
        self.lot.refresh_from_db()
        self.assertEqual(
            Client.objects.filter(company=self.company).count(), 1)
        self.assertEqual(self.lot.crees + self.lot.maj, 2)


class ReconcileFinancierTests(TestCase):
    def setUp(self):
        self.company = make_company('mig-int5-co', 'Migr int5')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='P', source='odoo')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients',
            source_lignes=2, crees=2, source_montant='1000.00')

    def test_ecart_financier_rend_non_conforme(self):
        rapport = services.reconcilier_lot(
            self.lot, total_financier_cible='940.00')
        self.assertFalse(rapport.conforme)
        self.assertIn('financier', {e['type'] for e in rapport.ecarts})
        self.assertEqual(str(rapport.ecart_financier), '-60.00')

    def test_totaux_egaux_restent_conformes(self):
        rapport = services.reconcilier_lot(
            self.lot, total_financier_cible='1000.00')
        self.assertTrue(rapport.conforme, rapport.ecarts)

    def test_sans_total_cible_le_rapport_ne_pretend_rien(self):
        """Le PV ne doit pas laisser croire à un contrôle financier fait."""
        rapport = services.reconcilier_lot(self.lot)
        self.assertIsNone(rapport.total_financier_cible)
        self.assertIsNone(rapport.ecart_financier)
        self.assertNotIn('financier', {e['type'] for e in rapport.ecarts})


class ChampsFigesApresCreationTests(TestCase):
    LOTS = '/api/django/migration/lots-migration/'
    PROJETS = '/api/django/migration/projets-migration/'

    def setUp(self):
        self.company = make_company('mig-int6-co', 'Migr int6')
        self.admin = make_admin(self.company, 'mig-int6-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='P', source='odoo')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

    def test_un_lot_ne_peut_pas_etre_deplace_vers_un_projet_dune_autre_societe(self):
        """Le déplacement ferait apparaître ce lot dans le PV de l'autre
        société ET permettrait à celle-ci d'écrire son statut."""
        autre_co = make_company('mig-int6-autre', 'Autre')
        autre_projet = ProjetMigration.objects.create(
            company=autre_co, nom='Autre P', source='odoo')
        resp = auth(self.admin).patch(
            f'{self.LOTS}{self.lot.pk}/', {'projet': autre_projet.pk})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.projet_id, self.projet.pk)

    def test_lentite_dun_lot_est_figee_apres_creation(self):
        resp = auth(self.admin).patch(
            f'{self.LOTS}{self.lot.pk}/', {'entite': 'products'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.entite, 'clients')

    def test_la_source_dun_projet_est_figee_apres_creation(self):
        """Changer la source déplacerait l'espace de noms ExternalRef : les
        réimports se remettraient à créer des doublons."""
        resp = auth(self.admin).patch(
            f'{self.PROJETS}{self.projet.pk}/', {'source': 'sage'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.source, 'odoo')

    def test_une_entite_inconnue_est_refusee_a_la_creation(self):
        resp = auth(self.admin).post(
            self.LOTS, {'projet': self.projet.pk, 'entite': 'nimportequoi'})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('entite', resp.data)

    def test_une_entite_connue_est_acceptee(self):
        resp = auth(self.admin).post(
            self.LOTS, {'projet': self.projet.pk, 'entite': 'fournisseurs'})
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_le_nom_reste_modifiable(self):
        resp = auth(self.admin).patch(
            f'{self.PROJETS}{self.projet.pk}/', {'nom': 'Nouveau nom'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.nom, 'Nouveau nom')


class SuppressionGardeeTests(TestCase):
    LOTS = '/api/django/migration/lots-migration/'
    PROJETS = '/api/django/migration/projets-migration/'

    def setUp(self):
        self.company = make_company('mig-int7-co', 'Migr int7')
        self.admin = make_admin(self.company, 'mig-int7-admin')
        self.user = self.admin
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='P', source='odoo')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

    def test_un_projet_cloture_nest_pas_supprimable(self):
        services.charger_lot(self.lot, CSV_A, 'a.csv', user=self.user)
        self.lot.refresh_from_db()
        services.reconcilier_lot(self.lot)
        services.terminer_projet(self.projet)

        resp = auth(self.admin).delete(f'{self.PROJETS}{self.projet.pk}/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertTrue(
            ProjetMigration.objects.filter(pk=self.projet.pk).exists())
        # Et les rapports sont toujours là.
        self.assertTrue(RapportReconciliation.objects.filter(
            lot=self.lot).exists())

    def test_un_lot_ayant_charge_nest_pas_supprimable(self):
        services.charger_lot(self.lot, CSV_A, 'a.csv', user=self.user)
        resp = auth(self.admin).delete(f'{self.LOTS}{self.lot.pk}/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertTrue(LotMigration.objects.filter(pk=self.lot.pk).exists())

    def test_un_lot_vide_reste_supprimable(self):
        resp = auth(self.admin).delete(f'{self.LOTS}{self.lot.pk}/')
        self.assertEqual(resp.status_code, 204, resp.data)
        self.assertFalse(LotMigration.objects.filter(pk=self.lot.pk).exists())

    def test_un_projet_en_cours_reste_supprimable(self):
        vide = ProjetMigration.objects.create(
            company=self.company, nom='Vide', source='excel')
        resp = auth(self.admin).delete(f'{self.PROJETS}{vide.pk}/')
        self.assertEqual(resp.status_code, 204, resp.data)


class ComptePortailRefuseTests(TestCase):
    """Un compte de PORTAIL externe n'a rien à faire dans une migration, quel
    que soit le rôle qu'on lui a attribué."""

    def test_portail_client_refuse_meme_avec_role_admin(self):
        from django.contrib.auth import get_user_model
        company = make_company('mig-int8-co', 'Migr int8')
        User = get_user_model()
        portail = User.objects.create_user(
            username='mig-int8-portail', password='x', company=company,
            role_legacy='admin', portee='portail_client')
        resp = auth(portail).get('/api/django/migration/projets-migration/')
        self.assertEqual(resp.status_code, 403)

"""NTMIG5 — garde « pas de succès sans reconcile ».

Un lot/projet ne se clôture jamais tant que son rapport n'est pas conforme,
sauf dérogation explicite motivée et attribuée (bool + motif + qui + quand).
C'est la garde qui empêche d'annoncer « migration réussie » à un grand compte
sur des données silencieusement incomplètes.
"""
from django.test import TestCase

from apps.migration import services
from apps.migration.models import (
    LotMigration, ProjetMigration, RapportReconciliation)

from ._base import auth, make_admin, make_company, make_user


class GardeReconcileServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('mig-g5-co', 'Migr G5')
        self.user = make_admin(self.company, 'mig-g5-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Client A', source='odoo',
            statut=ProjetMigration.Statut.CHARGEMENT)
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients',
            statut=LotMigration.Statut.CHARGE, source_lignes=100,
            crees=97, maj=0, erreurs=3)

    def _rapport(self, conforme, ecarts):
        return RapportReconciliation.objects.create(
            company=self.company, lot=self.lot, nb_source=100,
            nb_cible_crees=97, nb_erreurs=3, ecarts=ecarts,
            conforme=conforme)

    def test_refuse_sans_aucun_rapport(self):
        """Aucun rapport du tout = l'écart le plus grave : jamais clôturable."""
        with self.assertRaises(services.ReconcileBloque) as ctx:
            services.marquer_lot_termine(self.lot)
        self.assertEqual(ctx.exception.ecarts[0]['type'], 'sans_rapport')
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.statut, LotMigration.Statut.CHARGE)

    def test_refuse_rapport_non_conforme(self):
        self._rapport(False, [{'type': 'comptage', 'source': 100,
                               'cible': 97}])
        with self.assertRaises(services.ReconcileBloque) as ctx:
            services.marquer_lot_termine(self.lot)
        self.assertTrue(ctx.exception.ecarts)
        self.lot.refresh_from_db()
        # Le lot reste « chargé », jamais « réconcilié ».
        self.assertEqual(self.lot.statut, LotMigration.Statut.CHARGE)

    def test_accepte_rapport_conforme(self):
        self._rapport(True, [])
        services.marquer_lot_termine(self.lot)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.statut, LotMigration.Statut.RECONCILIE)

    def test_seul_le_dernier_rapport_fait_foi(self):
        """Un vieux rapport conforme ne blanchit pas une reprise en écart."""
        self._rapport(True, [])
        self._rapport(False, [{'type': 'comptage', 'detail': 'régression'}])
        with self.assertRaises(services.ReconcileBloque):
            services.marquer_lot_termine(self.lot)

    def test_derogation_journalisee_debloque(self):
        self._rapport(False, [{'type': 'comptage'}])
        services.deroger_reconcile(self.lot, 'Doublons source acceptés',
                                   self.user)
        self.lot.refresh_from_db()
        self.assertTrue(self.lot.derogation_reconcile)
        self.assertEqual(self.lot.derogation_par, self.user)
        self.assertEqual(self.lot.derogation_motif, 'Doublons source acceptés')
        self.assertIsNotNone(self.lot.derogation_at)
        services.marquer_lot_termine(self.lot)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.statut, LotMigration.Statut.RECONCILIE)

    def test_derogation_exige_un_motif(self):
        for motif in ('', '   ', None):
            with self.assertRaises(ValueError):
                services.deroger_reconcile(self.lot, motif, self.user)
        self.lot.refresh_from_db()
        self.assertFalse(self.lot.derogation_reconcile)

    def test_deroger_necrase_aucun_autre_champ(self):
        """La dérogation n'écrit QUE ses propres champs."""
        self._rapport(False, [{'type': 'comptage'}])
        LotMigration.objects.filter(pk=self.lot.pk).update(crees=42)
        services.deroger_reconcile(self.lot, 'motif', self.user)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.crees, 42)


class TerminerProjetServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('mig-g5p-co', 'Migr G5 Projet')
        self.user = make_admin(self.company, 'mig-g5p-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Client P', source='excel',
            statut=ProjetMigration.Statut.CHARGEMENT)
        self.lot_ok = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients',
            statut=LotMigration.Statut.CHARGE)
        RapportReconciliation.objects.create(
            company=self.company, lot=self.lot_ok, conforme=True)
        self.lot_ko = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='products',
            statut=LotMigration.Statut.CHARGE)
        RapportReconciliation.objects.create(
            company=self.company, lot=self.lot_ko, conforme=False,
            ecarts=[{'type': 'comptage', 'detail': '2 produits manquants'}])

    def test_un_lot_en_ecart_bloque_tout_le_projet(self):
        with self.assertRaises(services.ReconcileBloque) as ctx:
            services.terminer_projet(self.projet, user=self.user)
        entites = [b['entite'] for b in ctx.exception.ecarts]
        self.assertEqual(entites, ['products'])

    def test_cloture_refusee_ne_cloture_aucun_lot(self):
        """Refus = rien de partiel : le lot conforme reste « chargé »."""
        with self.assertRaises(services.ReconcileBloque):
            services.terminer_projet(self.projet, user=self.user)
        self.lot_ok.refresh_from_db()
        self.projet.refresh_from_db()
        self.assertEqual(self.lot_ok.statut, LotMigration.Statut.CHARGE)
        self.assertNotEqual(
            self.projet.statut, ProjetMigration.Statut.TERMINE)

    def test_cloture_ok_apres_derogation_du_lot_en_ecart(self):
        services.deroger_reconcile(self.lot_ko, 'écarts acceptés', self.user)
        services.terminer_projet(self.projet, user=self.user)
        self.projet.refresh_from_db()
        self.lot_ok.refresh_from_db()
        self.lot_ko.refresh_from_db()
        self.assertEqual(self.projet.statut, ProjetMigration.Statut.TERMINE)
        self.assertIsNotNone(self.projet.date_fin)
        self.assertEqual(self.lot_ok.statut, LotMigration.Statut.RECONCILIE)
        self.assertEqual(self.lot_ko.statut, LotMigration.Statut.RECONCILIE)


class MigrationApiTests(TestCase):
    BASE = '/api/django/migration/projets-migration/'
    LOTS = '/api/django/migration/lots-migration/'

    def setUp(self):
        self.company = make_company('mig-g5api-co', 'Migr G5 API')
        self.admin = make_admin(self.company, 'mig-g5api-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Client B', source='sage',
            statut=ProjetMigration.Statut.CHARGEMENT)
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients',
            statut=LotMigration.Statut.CHARGE, source_lignes=100,
            crees=97, erreurs=3)
        RapportReconciliation.objects.create(
            company=self.company, lot=self.lot, nb_source=100,
            nb_cible_crees=97, nb_erreurs=3,
            ecarts=[{'type': 'erreurs', 'nb': 3}], conforme=False)

    def test_terminer_bloque_400_avec_ecarts(self):
        resp = auth(self.admin).post(f'{self.BASE}{self.projet.pk}/terminer/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertTrue(resp.data['ecarts'])
        self.projet.refresh_from_db()
        self.assertNotEqual(
            self.projet.statut, ProjetMigration.Statut.TERMINE)

    def test_terminer_ok_apres_derogation(self):
        api = auth(self.admin)
        derog = api.post(f'{self.LOTS}{self.lot.pk}/deroger/',
                         {'motif': 'écarts acceptés'})
        self.assertEqual(derog.status_code, 200, derog.data)
        resp = api.post(f'{self.BASE}{self.projet.pk}/terminer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.statut, ProjetMigration.Statut.TERMINE)
        self.assertIsNotNone(self.projet.date_fin)

    def test_deroger_sans_motif_refuse_400(self):
        resp = auth(self.admin).post(f'{self.LOTS}{self.lot.pk}/deroger/', {})
        self.assertEqual(resp.status_code, 400)
        self.lot.refresh_from_db()
        self.assertFalse(self.lot.derogation_reconcile)

    def test_creation_force_company_et_cree_par(self):
        resp = auth(self.admin).post(
            self.BASE, {'nom': 'Nouveau', 'source': 'odoo',
                        'company': 999999, 'statut': 'termine'})
        self.assertEqual(resp.status_code, 201, resp.data)
        projet = ProjetMigration.objects.get(pk=resp.data['id'])
        self.assertEqual(projet.company_id, self.company.pk)
        self.assertEqual(projet.cree_par, self.admin)
        # ``statut`` est en lecture seule : jamais « terminé » à la création.
        self.assertEqual(projet.statut, ProjetMigration.Statut.BROUILLON)

    def test_non_admin_refuse(self):
        simple = make_user(self.company, 'mig-g5-simple')
        resp = auth(simple).post(f'{self.BASE}{self.projet.pk}/terminer/')
        self.assertEqual(resp.status_code, 403)

    def test_anonyme_refuse(self):
        from rest_framework.test import APIClient
        resp = APIClient().get(self.BASE)
        self.assertIn(resp.status_code, (401, 403))

    def test_isolation_societe(self):
        autre_co = make_company('mig-g5api-autre', 'Autre société')
        autre_admin = make_admin(autre_co, 'mig-g5api-autre-admin')
        resp = auth(autre_admin).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        ids = [p['id'] for p in resp.data.get('results', resp.data)]
        self.assertNotIn(self.projet.pk, ids)
        # Et pas de clôture croisée non plus.
        bloque = auth(autre_admin).post(
            f'{self.BASE}{self.projet.pk}/terminer/')
        self.assertEqual(bloque.status_code, 404)

    def test_lot_ne_peut_pas_se_greffer_sur_un_projet_dune_autre_societe(self):
        autre_co = make_company('mig-g5api-autre2', 'Autre société 2')
        autre_admin = make_admin(autre_co, 'mig-g5api-autre2-admin')
        resp = auth(autre_admin).post(
            self.LOTS, {'projet': self.projet.pk, 'entite': 'clients'})
        self.assertEqual(resp.status_code, 400, resp.data)

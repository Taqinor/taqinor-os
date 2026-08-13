"""NTMIG34 — estimation d'effort de migration (indicative, reproductible)."""
from decimal import Decimal

from django.test import TestCase

from apps.migration import services
from apps.migration.models import LotMigration, ProjetMigration

from ._base import auth, make_admin, make_company


class EstimationEffortTests(TestCase):

    def setUp(self):
        self.company = make_company('ntmig34', 'NTMIG34')
        self.admin = make_admin(self.company, 'ntmig34-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Bascule Odoo', source='odoo')
        for ordre, entite in enumerate(
                ('clients', 'products', 'fournisseurs', 'leads',
                 'equipements'), start=1):
            LotMigration.objects.create(
                company=self.company, projet=self.projet, entite=entite,
                ordre=ordre, source_lignes=2000)

    def test_projet_odoo_5_entites_10000_lignes(self):
        estimation = services.estimer_effort(self.projet)
        self.assertEqual(estimation['nb_lots'], 5)
        self.assertEqual(estimation['lignes_source_total'], 10000)
        jours = Decimal(estimation['jours_homme'])
        # Socle + 5 lots volumés : une estimation strictement positive et
        # bornée au bon sens (pas 0 jour, pas 100 jours).
        self.assertGreater(jours, Decimal('1'))
        self.assertLess(jours, Decimal('30'))
        self.assertEqual(len(estimation['detail_par_lot']), 5)

    def test_reproductible(self):
        premier = services.estimer_effort(self.projet)
        second = services.estimer_effort(self.projet)
        self.assertEqual(premier, second)

    def test_croissante_avec_le_volume(self):
        avant = Decimal(services.estimer_effort(self.projet)['jours_homme'])
        self.projet.lots.update(source_lignes=50000)
        apres = Decimal(services.estimer_effort(self.projet)['jours_homme'])
        self.assertGreater(apres, avant)

    def test_points_attention_signalent_les_lots_non_analyses(self):
        LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='vehicules',
            ordre=6, source_lignes=0)
        points = services.estimer_effort(self.projet)['points_attention']
        self.assertTrue(any('vehicules' in p and 'analysés' in p
                            for p in points))

    def test_maitre_detail_coute_plus_cher(self):
        simple = Decimal(services.estimer_effort(self.projet)['jours_homme'])
        LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='factures',
            ordre=7, source_lignes=2000)
        avec_documents = Decimal(
            services.estimer_effort(self.projet)['jours_homme'])
        self.assertGreater(avec_documents - simple, Decimal('1'))

    def test_n_ecrit_rien(self):
        services.estimer_effort(self.projet)
        self.projet.refresh_from_db()
        self.assertEqual(
            self.projet.statut, ProjetMigration.Statut.BROUILLON)

    def test_endpoint_estimation(self):
        api = auth(self.admin)
        resp = api.get(
            f'/api/django/migration/projets-migration/{self.projet.pk}/'
            'estimation/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['nb_lots'], 5)

    def test_estimation_scopee_societe(self):
        autre = make_company('ntmig34-autre', 'NTMIG34 autre')
        intrus = make_admin(autre, 'ntmig34-intrus')
        resp = auth(intrus).get(
            f'/api/django/migration/projets-migration/{self.projet.pk}/'
            'estimation/')
        self.assertEqual(resp.status_code, 404)

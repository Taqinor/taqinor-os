"""NTMIG37 — réconciliation croisée des soldes (contrôle comptable).

Pour les clients migrés par un projet, compare le solde SOURCE (balance âgée
fournie par l'intégrateur) au solde OUVERT recalculé côté TAQINOR
(``ventes.selectors.encours_ouvert_par_tiers``) — garantit qu'aucun encours
n'est perdu à la migration, client par client (au-delà des comptages
globaux du reconcile NTMIG4).
"""
from decimal import Decimal

from django.test import TestCase

from apps.migration import services
from apps.migration.models import LotMigration, ProjetMigration

from ._base import auth, make_admin, make_company
from ._stockage_factice import patcher_stockage

CSV_CLIENTS = (
    b'nom,email,external_id\n'
    b'Client A,a@ex.ma,ODOO-C1\n'
    b'Client B,b@ex.ma,ODOO-C2\n'
)


def _facture_ouverte(company, client, montant_ttc):
    from apps.ventes.models import Facture

    return Facture.objects.create(
        company=company, client=client,
        type_facture=Facture.TypeFacture.COMPLETE,
        statut=Facture.Statut.EMISE,
        montant_ht=montant_ttc, montant_tva=Decimal('0'),
        montant_ttc=montant_ttc,
        reference=f'FAC-TEST-{client.pk}')


class ReconcilierSoldesTests(TestCase):

    def setUp(self):
        self.stockage = patcher_stockage(self)
        self.company = make_company('ntmig37', 'NTMIG37')
        self.admin = make_admin(self.company, 'ntmig37-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Bascule', source='odoo')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')
        services.charger_lot(
            self.lot, CSV_CLIENTS, 'clients.csv', user=self.admin)

    def _client(self, email):
        from apps.crm.models import Client
        return Client.objects.get(company=self.company, email=email)

    def test_soldes_concordants_aucune_divergence(self):
        client_a = self._client('a@ex.ma')
        _facture_ouverte(self.company, client_a, Decimal('12000'))

        divergences = services.reconcilier_soldes(
            self.projet, {'ODOO-C1': '12000'})

        self.assertEqual(divergences, [])

    def test_encours_source_perdu_signale(self):
        """Un client dont l'encours source (12 000 MAD) ne matche pas
        l'encours migré (9 000 MAD) est listé AVANT clôture."""
        client_a = self._client('a@ex.ma')
        _facture_ouverte(self.company, client_a, Decimal('9000'))

        divergences = services.reconcilier_soldes(
            self.projet, {'ODOO-C1': '12000'})

        self.assertEqual(len(divergences), 1)
        self.assertEqual(divergences[0]['solde_source'], '12000')
        self.assertEqual(divergences[0]['solde_migre'], '9000')
        self.assertEqual(divergences[0]['ecart'], '-3000')

    def test_client_absent_de_la_migration_signale(self):
        divergences = services.reconcilier_soldes(
            self.projet, {'ODOO-INCONNU': '5000'})

        self.assertEqual(len(divergences), 1)
        self.assertIsNone(divergences[0]['client_id'])
        self.assertIn('introuvable', divergences[0]['motif'])

    def test_client_sans_encours_ouvert_compte_comme_zero(self):
        divergences = services.reconcilier_soldes(
            self.projet, {'ODOO-C2': '0'})
        self.assertEqual(divergences, [])

    def test_ne_touche_ni_projet_ni_client(self):
        client_a = self._client('a@ex.ma')
        services.reconcilier_soldes(self.projet, {'ODOO-C1': '999999'})
        self.projet.refresh_from_db()
        client_a.refresh_from_db()
        self.assertEqual(self.projet.statut, ProjetMigration.Statut.BROUILLON)

    def test_endpoint_reconcilier_soldes(self):
        client_a = self._client('a@ex.ma')
        _facture_ouverte(self.company, client_a, Decimal('12000'))
        api = auth(self.admin)

        resp = api.post(
            f'/api/django/migration/projets-migration/{self.projet.pk}/'
            'reconcilier-soldes/',
            {'balance': {'ODOO-C1': 12000}}, format='json')

        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['nb_divergences'], 0)

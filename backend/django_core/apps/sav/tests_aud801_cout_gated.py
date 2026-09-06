"""AUD801 — le dataset RÉEL ``sav_tickets`` : le coût interne d'un ticket
(``cout``) ne sort plus sans ``prix_achat_voir``.

``apps/sav/bi_datasets.py`` déléguait explicitement le masquage de ``cout`` à
« l'appelant » — et aucun des huit consommateurs de
``core.data_explorer.run_query`` ne le faisait. Le scénario du constat : un
employé sans ``can_view_buy_prices`` POST
``/core/saved-queries/run/ {"dataset":"sav_tickets","spec":{"select":["id",
"cout"]}}`` et reçoit les coûts internes bruts en JSON.

Le masquage vit désormais dans le MOTEUR (``gated_fields``) ; ce module vérifie
qu'il est bien DÉCLARÉ sur le dataset de production et qu'il mord de bout en
bout (le moteur lui-même est couvert par
``core/tests/test_aud801_gated_fields.py``).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.crm.models import Client
from apps.roles.models import Role
from apps.sav.bi_datasets import DATASET_NAME, GATED_FIELDS
from apps.sav.models import Ticket
from authentication.models import Company
from core import data_explorer
from core.views import SavedQueryViewSet

User = get_user_model()


class Aud801CoutGatedTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aud801-sav-co', defaults={'nom': 'AUD801 SAV Co'})[0]
        self.role_sans = Role.objects.create(
            company=self.company, nom='AUD801 sans prix achat',
            permissions=['tickets_gerer'])
        self.role_avec = Role.objects.create(
            company=self.company, nom='AUD801 avec prix achat',
            permissions=['tickets_gerer', 'prix_achat_voir'])
        self.sans_droit = User.objects.create_user(
            username='aud801_sav_sans', password='x', company=self.company,
            role=self.role_sans)
        self.avec_droit = User.objects.create_user(
            username='aud801_sav_avec', password='x', company=self.company,
            role=self.role_avec)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client AUD801')
        Ticket.objects.create(
            company=self.company, reference='AUD801-1',
            client=self.client_obj, cout=Decimal('150.00'))
        Ticket.objects.create(
            company=self.company, reference='AUD801-2',
            client=self.client_obj, cout=Decimal('850.00'))
        self.factory = APIRequestFactory()

    def test_le_dataset_declare_le_champ_gated(self):
        self.assertEqual(GATED_FIELDS, {'cout': 'can_view_buy_prices'})
        spec = data_explorer.get_dataset(DATASET_NAME)
        self.assertEqual(spec.get('gated_fields'),
                         {'cout': 'can_view_buy_prices'})

    def test_scenario_du_constat_le_post_ne_rend_plus_les_couts(self):
        req = self.factory.post('/saved-queries/run/', {
            'dataset': DATASET_NAME, 'spec': {'select': ['id', 'cout']},
        }, format='json')
        force_authenticate(req, user=self.sans_droit)
        resp = SavedQueryViewSet.as_view({'post': 'run_adhoc'})(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['rows']), 2)
        for row in resp.data['rows']:
            self.assertNotIn('cout', row)

    def test_le_lecteur_autorise_voit_toujours_les_couts(self):
        rows = data_explorer.run_query(
            DATASET_NAME, self.company, self.avec_droit,
            {'select': ['id', 'cout']})
        self.assertEqual(
            sorted(r['cout'] for r in rows),
            [Decimal('150.00'), Decimal('850.00')])

    def test_somme_des_couts_ecartee_sans_permission(self):
        rows = data_explorer.run_query(
            DATASET_NAME, self.company, self.sans_droit,
            {'aggregates': [
                {'alias': 'total_cout', 'fn': 'sum', 'field': 'cout'},
                {'alias': 'n', 'fn': 'count', 'field': 'id'}]})
        self.assertNotIn('total_cout', rows[0])
        self.assertEqual(rows[0]['n'], 2)

    def test_extrait_planifie_user_none_n_exporte_pas_les_couts(self):
        """``core.scheduled_export.rendre_extrait_detaille`` appelle le moteur
        avec ``user=None`` littéral (CSV/parquet vers SFTP/S3 externe)."""
        rows = data_explorer.run_query(
            DATASET_NAME, self.company, None, {})
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertNotIn('cout', row)
            self.assertIn('statut', row)

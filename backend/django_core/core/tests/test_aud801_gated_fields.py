"""AUD801 — le moteur ``core.data_explorer`` n'avait AUCUNE notion de champ
sous permission : un champ « interne » fuyait par ses huit consommateurs.

Constat d'origine : ``register_dataset``/``run_query`` ignoraient tout du
masquage, et le seul dataset de production (``sav_tickets``) déléguait
explicitement le masquage de ``cout`` « à l'appelant » — qu'AUCUN des huit
consommateurs ne faisait (``SavedQueryViewSet.run_adhoc`` en
``IsAuthenticated`` seul avec un corps libre, le drill, les formules, les
widgets de tableau de bord, le cache BI, le classeur, les rapports, et
l'extrait planifié vers SFTP/S3 qui appelle ``run_query`` avec ``user=None``
littéral). N'importe quel rôle interne récupérait les coûts bruts en JSON.

Ce module teste le MOTEUR (couche fondation) sur un dataset de test bâti sur un
modèle de ``core`` — ``core`` n'importe jamais une app métier. Le dataset RÉEL
``sav_tickets`` est couvert par ``apps/sav/tests_aud801_cout_gated.py``.

Les CINQ positions de la spec comptent, pas seulement ``select`` : un filtre
(``{"montant__gt": X}`` + comptage = dichotomie), un ``group_by`` (la valeur
devient une clé de ligne), un ``order_by`` (l'ordre relatif) et un agrégat
(``{"fn":"sum"}`` rend le total) fuient tout autant. Plus la projection PAR
DÉFAUT : une spec SANS ``select`` projetait tous les champs.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.roles.models import Role
from authentication.models import Company
from core import bi_cache, data_explorer
from core.models import PaymentTransaction
from core.views import SavedQueryViewSet

User = get_user_model()

DATASET = 'aud801.transactions'
CHAMPS = ['id', 'provider', 'statut', 'montant']


def _transactions_queryset(company, user):
    return PaymentTransaction.objects.filter(company=company)


class Aud801GatedFieldsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='AUD801 SARL')
        # Rôle SANS ``prix_achat_voir`` → ``can_view_buy_prices`` faux.
        cls.role_sans = Role.objects.create(
            company=cls.company, nom='AUD801 sans prix',
            permissions=['tickets_gerer'])
        cls.role_avec = Role.objects.create(
            company=cls.company, nom='AUD801 avec prix',
            permissions=['tickets_gerer', 'prix_achat_voir'])
        cls.sans_droit = User.objects.create_user(
            username='aud801_sans', password='x', company=cls.company,
            role=cls.role_sans)
        cls.avec_droit = User.objects.create_user(
            username='aud801_avec', password='x', company=cls.company,
            role=cls.role_avec)
        cls.factory = APIRequestFactory()

    def setUp(self):
        data_explorer.register_dataset(
            DATASET, 'Transactions AUD801', CHAMPS, _transactions_queryset,
            gated_fields={'montant': 'can_view_buy_prices'})
        for montant in (Decimal('100.00'), Decimal('900.00')):
            PaymentTransaction.objects.create(
                company=self.company, provider='cmi', montant=montant,
                statut=PaymentTransaction.STATUT_PAYE)

    def _run(self, user, spec):
        return data_explorer.run_query(DATASET, self.company, user, spec)

    # ── 1. select ─────────────────────────────────────────────────────────
    def test_select_du_champ_gated_est_ecarte(self):
        rows = self._run(self.sans_droit, {'select': ['id', 'montant']})
        self.assertTrue(rows)
        for row in rows:
            self.assertNotIn('montant', row)
            self.assertIn('id', row)

    def test_select_du_champ_gated_reste_visible_avec_la_permission(self):
        rows = self._run(self.avec_droit, {'select': ['id', 'montant']})
        self.assertTrue(rows)
        self.assertIn('montant', rows[0])

    # ── 2. filters (inférence par dichotomie) ─────────────────────────────
    def test_filtre_sur_le_champ_gated_est_ecarte(self):
        """Sans cette garde, ``{"montant__gt": X}`` + comptage retrouve la
        valeur par dichotomie sans jamais l'afficher."""
        toutes = self._run(self.sans_droit, {'select': ['id']})
        filtrees = self._run(
            self.sans_droit,
            {'select': ['id'], 'filters': {'montant__gt': Decimal('500')}})
        self.assertEqual(len(filtrees), len(toutes))
        # Le lecteur autorisé, lui, filtre réellement.
        filtrees_ok = self._run(
            self.avec_droit,
            {'select': ['id'], 'filters': {'montant__gt': Decimal('500')}})
        self.assertEqual(len(filtrees_ok), 1)

    # ── 3. group_by ───────────────────────────────────────────────────────
    def test_group_by_sur_le_champ_gated_est_ecarte(self):
        rows = self._run(self.sans_droit, {
            'group_by': ['montant'],
            'aggregates': [{'alias': 'n', 'fn': 'count', 'field': 'id'}],
        })
        for row in rows:
            self.assertNotIn('montant', row)

    # ── 4. order_by ───────────────────────────────────────────────────────
    def test_order_by_sur_le_champ_gated_est_ecarte(self):
        rows = self._run(self.sans_droit,
                         {'select': ['id'], 'order_by': ['-montant']})
        self.assertTrue(rows)
        for row in rows:
            self.assertNotIn('montant', row)

    # ── 5. aggregates ─────────────────────────────────────────────────────
    def test_agregat_sur_le_champ_gated_est_ecarte(self):
        rows = self._run(self.sans_droit, {
            'aggregates': [
                {'alias': 'total', 'fn': 'sum', 'field': 'montant'},
                {'alias': 'n', 'fn': 'count', 'field': 'id'},
            ],
        })
        self.assertEqual(len(rows), 1)
        self.assertNotIn('total', rows[0])
        self.assertEqual(rows[0]['n'], 2)

    def test_agregat_visible_avec_la_permission(self):
        rows = self._run(self.avec_droit, {
            'aggregates': [
                {'alias': 'total', 'fn': 'sum', 'field': 'montant'}],
        })
        self.assertEqual(rows[0]['total'], Decimal('1000.00'))

    # ── 6. projection par DÉFAUT (spec sans select) ───────────────────────
    def test_spec_sans_select_ne_projette_pas_le_champ_gated(self):
        rows = self._run(self.sans_droit, {})
        self.assertTrue(rows)
        for row in rows:
            self.assertNotIn('montant', row)
            self.assertIn('provider', row)

    # ── 7. user=None (extrait planifié vers SFTP/S3) ──────────────────────
    def test_user_none_n_obtient_jamais_le_champ_gated(self):
        rows = self._run(None, {'select': ['id', 'montant']})
        self.assertTrue(rows)
        for row in rows:
            self.assertNotIn('montant', row)

    def test_user_none_sans_select_non_plus(self):
        rows = self._run(None, {})
        self.assertTrue(rows)
        for row in rows:
            self.assertNotIn('montant', row)

    # ── 8. l'endpoint ad-hoc (le scénario du constat) ─────────────────────
    def test_endpoint_run_adhoc_ne_rend_plus_le_champ_gated(self):
        req = self.factory.post('/saved-queries/run/', {
            'dataset': DATASET, 'spec': {'select': ['id', 'montant']},
        }, format='json')
        force_authenticate(req, user=self.sans_droit)
        resp = SavedQueryViewSet.as_view({'post': 'run_adhoc'})(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['rows'])
        for row in resp.data['rows']:
            self.assertNotIn('montant', row)

    # ── 9. un champ INCONNU reste une erreur (pas un silence) ─────────────
    def test_champ_inconnu_leve_toujours(self):
        with self.assertRaises(data_explorer.ChampNonAutorise):
            self._run(self.avec_droit, {'select': ['secret_inexistant']})

    # ── 10. cache : un dataset gated ne partage jamais son entrée ─────────
    def test_cache_partage_refuse_avec_des_champs_gated(self):
        with self.assertRaises(ValueError):
            data_explorer.register_dataset(
                'aud801.interdit', 'X', CHAMPS, _transactions_queryset,
                cache_partage=True,
                gated_fields={'montant': 'can_view_buy_prices'})

    def test_bi_cache_ne_partage_pas_un_dataset_gated(self):
        self.assertFalse(bi_cache._partage(DATASET))

    def test_cle_cache_reste_par_utilisateur(self):
        cle_a = bi_cache.cle_cache(
            DATASET, {'select': ['id']}, self.sans_droit,
            partage=bi_cache._partage(DATASET))
        cle_b = bi_cache.cle_cache(
            DATASET, {'select': ['id']}, self.avec_droit,
            partage=bi_cache._partage(DATASET))
        self.assertNotEqual(cle_a, cle_b)

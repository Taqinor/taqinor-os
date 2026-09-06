"""AUDV27 (YHARD2) — ``POST /api/django/agent/logs/confirmer/``.

`log_confirmed_action` existait déjà, testée, mais AUCUN endpoint ne
l'invoquait après une exécution réelle : le journal restait vide en
production. Ce fichier couvre le câblage HTTP self-service (n'importe quel
utilisateur authentifié journalise SA PROPRE confirmation — la lecture/
l'annulation du journal restent admin/Directeur, non touchées ici) + le fix
de `AgentActionLog.is_undoable` (reflète désormais un handler RÉELLEMENT
enregistré).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.agent import services
from apps.agent.models import AgentActionLog
from apps.crm.models import Client

User = get_user_model()

URL = '/api/django/agent/logs/confirmer/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AgentActionConfirmerViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='AUDV27 Co')
        cls.user = User.objects.create_user(
            username='audv27_user', password='x', role_legacy='normal',
            company=cls.company)

    def test_journalise_apres_confirmation_self_service(self):
        """N'importe quel utilisateur authentifié — pas seulement admin —
        peut journaliser SA propre action confirmée."""
        resp = _api(self.user).post(URL, {
            'action_key': 'devis.envoyer',
            'risk_level': 'outward',
            'inputs': {'devis_id': 7},
            'proposal_hash': 'abc123',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        log = AgentActionLog.objects.get(pk=resp.data['id'])
        self.assertEqual(log.company_id, self.company.id)
        self.assertEqual(log.user_id, self.user.id)
        self.assertEqual(log.action_key, 'devis.envoyer')
        self.assertEqual(log.risk_level, 'outward')
        self.assertIsNotNone(log.executed_at)

    def test_resout_le_client_cree_pour_l_action_pilote(self):
        client_obj = Client.objects.create(
            company=self.company, nom='Client Confirmé')
        resp = _api(self.user).post(URL, {
            'action_key': 'crm.client.create',
            'risk_level': 'outward',
            'inputs': {'nom': 'Client Confirmé'},
            'object_id': client_obj.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        log = AgentActionLog.objects.get(pk=resp.data['id'])
        self.assertIsNotNone(log.content_type)
        self.assertEqual(log.object_id, str(client_obj.id))
        self.assertEqual(log.object_repr, str(client_obj))

    def test_object_id_d_une_autre_societe_ne_resout_rien(self):
        autre = Company.objects.create(nom='AUDV27 Autre')
        client_autre = Client.objects.create(company=autre, nom='X')
        resp = _api(self.user).post(URL, {
            'action_key': 'crm.client.create',
            'risk_level': 'outward',
            'object_id': client_autre.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        log = AgentActionLog.objects.get(pk=resp.data['id'])
        self.assertIsNone(log.content_type)
        self.assertEqual(log.object_id, '')

    def test_action_key_manquant_est_un_400(self):
        resp = _api(self.user).post(
            URL, {'risk_level': 'outward'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(AgentActionLog.objects.count(), 0)

    def test_risk_level_invalide_est_un_400(self):
        resp = _api(self.user).post(URL, {
            'action_key': 'x', 'risk_level': 'n-importe-quoi',
        }, format='json')
        self.assertEqual(resp.status_code, 400)


class IsUndoableReflectsHandlerTests(TestCase):
    """AUDV27 — `is_undoable` ne dit plus « annulable » pour une action
    réversible SANS handler réellement enregistré."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='AUDV27 Undo Co')
        cls.user = User.objects.create_user(
            username='audv27_undo', password='x', company=cls.company)

    def test_sans_handler_jamais_undoable_meme_reversible(self):
        log = services.log_confirmed_action(
            company=self.company, user=self.user,
            action_key='audv27.sans_handler.unique',
            risk_level=AgentActionLog.RiskLevel.OUTWARD)
        self.assertFalse(services.has_undo_handler(log.action_key))
        self.assertFalse(log.is_undoable)

    def test_avec_handler_devient_undoable(self):
        services.register_undo_handler(
            'audv27.avec_handler.unique', lambda log: 'ok')
        log = services.log_confirmed_action(
            company=self.company, user=self.user,
            action_key='audv27.avec_handler.unique',
            risk_level=AgentActionLog.RiskLevel.OUTWARD)
        self.assertTrue(log.is_undoable)

    def test_irreversible_jamais_undoable_meme_avec_handler(self):
        services.register_undo_handler(
            'audv27.irreversible.unique', lambda log: 'ok')
        log = services.log_confirmed_action(
            company=self.company, user=self.user,
            action_key='audv27.irreversible.unique',
            risk_level=AgentActionLog.RiskLevel.IRREVERSIBLE)
        self.assertFalse(log.is_undoable)

    def test_deja_annulee_jamais_undoable(self):
        services.register_undo_handler(
            'audv27.deja_annulee.unique', lambda log: 'ok')
        log = services.log_confirmed_action(
            company=self.company, user=self.user,
            action_key='audv27.deja_annulee.unique',
            risk_level=AgentActionLog.RiskLevel.OUTWARD)
        services.annuler_action(log)
        self.assertFalse(log.is_undoable)


class CrmClientCreateUndoHandlerTests(TestCase):
    """AUDV27 — l'action PILOTE : le handler de rollback réel de
    `crm.client.create`, enregistré depuis `apps.crm.agent_actions` via
    `CrmConfig.ready()` (déjà actif — aucune inscription manuelle ici)."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='AUDV27 Crm Co')
        cls.user = User.objects.create_user(
            username='audv27_crm', password='x', company=cls.company)

    def test_handler_est_enregistre_au_demarrage(self):
        self.assertTrue(services.has_undo_handler('crm.client.create'))

    def test_annulation_supprime_le_client_cree(self):
        client_obj = Client.objects.create(
            company=self.company, nom='À annuler')
        log = services.log_confirmed_action(
            company=self.company, user=self.user,
            action_key='crm.client.create',
            risk_level=AgentActionLog.RiskLevel.OUTWARD,
            resulted_object=client_obj)
        self.assertTrue(log.is_undoable)

        result = services.annuler_action(log)
        self.assertIsNotNone(result.undone_at)
        self.assertIn('supprimé', result.undo_detail)
        self.assertFalse(Client.objects.filter(pk=client_obj.pk).exists())

    def test_client_deja_reference_par_un_devis_nest_pas_supprime(self):
        from decimal import Decimal

        from apps.ventes.models import Devis

        client_obj = Client.objects.create(
            company=self.company, nom='Référencé')
        Devis.objects.create(
            company=self.company, client=client_obj, reference='DEV-AUDV27',
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'))
        log = services.log_confirmed_action(
            company=self.company, user=self.user,
            action_key='crm.client.create',
            risk_level=AgentActionLog.RiskLevel.OUTWARD,
            resulted_object=client_obj)

        result = services.annuler_action(log)
        self.assertIsNotNone(result.undone_at)
        self.assertIn('NON supprimé', result.undo_detail)
        # Le client survit : l'annulation dégrade proprement, jamais un 500.
        self.assertTrue(Client.objects.filter(pk=client_obj.pk).exists())

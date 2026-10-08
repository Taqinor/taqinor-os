"""AACQ76 — Une action n'est appliquée que dans la version EXACTE approuvée.

Empreinte (kind + payload) posée à chaque passage en ``approuvee`` (humain ou
création directe auto) ; ``apply_action`` / ``apply_batch`` refusent un
contenu modifié depuis : retour ``proposee`` sans aucun appel Meta. Paramétré
sur TOUS les ``EngineAction.Kind`` (un kind nouveau est couvert d'office).
"""
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import services
from apps.adsengine.meta_client import MetaClient
from apps.adsengine.models import EngineAction

User = get_user_model()
MESSAGE = "Contenu modifié depuis l'approbation : nouvelle approbation requise."


class ApprobationVersionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Ver', slug='aacq76-ver')
        role = Role.objects.create(
            company=self.company, nom='aacq76-appr',
            permissions=['adsengine_view', 'adsengine_approve'])
        self.approbateur = User.objects.create_user(
            username='aacq76-appr', password='x', company=self.company,
            role_legacy='normal', role=role)

    def _approuvee(self, kind, payload):
        action = EngineAction.objects.create(
            company=self.company, kind=kind, reason_fr='Raison.',
            payload=payload)
        services.approve_action(action, user=self.approbateur)
        action.refresh_from_db()
        self.assertTrue(action.approved_fingerprint)
        return action

    def _assert_refus(self, action, client):
        with self.assertRaises(services.ActionNotApproved) as ctx:
            services.apply_action(action, client=client)
        self.assertEqual(str(ctx.exception), MESSAGE)
        self.assertEqual(client.method_calls, [])
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertIsNone(action.approved_by_id)
        self.assertEqual(action.error, MESSAGE)
        self.assertIsNone(action.applied_at)
        return action

    def test_payload_modifie_apres_approbation_refuse_pour_chaque_kind(self):
        for kind in EngineAction.Kind.values:
            with self.subTest(kind=kind):
                action = self._approuvee(
                    kind, {'object_id': '120999', 'name': 'Nom approuvé'})
                EngineAction.objects.filter(pk=action.pk).update(
                    payload={'object_id': '120999',
                             'name': 'NOM JAMAIS APPROUVE'})
                action.refresh_from_db()
                action = self._assert_refus(action, Mock(spec=MetaClient))
                # Le payload modifié reste intact (rien n'est écrasé).
                self.assertEqual(action.payload['name'], 'NOM JAMAIS APPROUVE')

    def test_kind_modifie_refuse(self):
        action = self._approuvee(
            EngineAction.Kind.RENAME, {'object_id': '1', 'name': 'N'})
        EngineAction.objects.filter(pk=action.pk).update(
            kind=EngineAction.Kind.EDIT_COPY)
        action.refresh_from_db()
        self._assert_refus(action, Mock(spec=MetaClient))

    def test_objet_en_memoire_perime_n_envoie_que_l_approuve(self):
        # Le contenu en base est la version approuvée ; un objet en mémoire
        # modifié (non sauvé) ne fait jamais partir son contenu.
        action = self._approuvee(
            EngineAction.Kind.RENAME, {'object_id': '120999', 'name': 'OK'})
        action.payload = {'object_id': '120999', 'name': 'PAS APPROUVE'}
        client = Mock(spec=MetaClient)
        client.rename_object.return_value = {'success': True}
        services.apply_action(action, client=client)
        self.assertEqual(client.rename_object.call_args.kwargs['name'], 'OK')

    def test_auto_approuvee_porte_empreinte(self):
        action = EngineAction.objects.create(
            company=self.company, kind=EngineAction.Kind.ROTATE_CREATIVE,
            reason_fr='Auto.', payload={'adset_id': 'as-1'},
            status=EngineAction.Statut.APPROUVEE, auto=True)
        self.assertEqual(
            action.approved_fingerprint,
            EngineAction.fingerprint_of(action.kind, action.payload))

    def test_contenu_inchange_applique(self):
        action = self._approuvee(
            EngineAction.Kind.RENAME, {'object_id': '120999', 'name': 'OK'})
        client = Mock(spec=MetaClient)
        client.rename_object.return_value = {'success': True}
        services.apply_action(action, client=client)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        client.rename_object.assert_called_once()

    def test_lot_refuse_un_contenu_modifie(self):
        action = self._approuvee(
            EngineAction.Kind.RENAME, {'object_id': '1', 'name': 'N'})
        EngineAction.objects.filter(pk=action.pk).update(
            payload={'object_id': '1', 'name': 'AUTRE'})
        action.refresh_from_db()
        client = Mock(spec=MetaClient)
        with self.assertRaises(services.ActionNotApproved):
            services.apply_batch([action], client=client)
        self.assertEqual(client.method_calls, [])
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)

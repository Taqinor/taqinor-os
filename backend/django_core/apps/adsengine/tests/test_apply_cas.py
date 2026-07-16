"""ENGFIX3 — Réclamation atomique (compare-and-swap) contre le double-apply.

Avant ce fix, ``apply_action`` faisait un ``if action.status != APPROUVEE`` EN
MÉMOIRE puis dispatchait, n'écrivant ``appliquee`` qu'APRÈS : deux appels
concurrents (deux instances chargées ``approuvee``) dispatchaient tous les deux
→ objets Meta en double. On prouve ici que le compare-and-swap ne laisse qu'UN
seul appel réclamer la ligne, que le second est refusé sans rappeler le client,
et qu'un échec de dispatch repasse l'action ``echouee``.

``transaction.atomic`` / la réclamation ``UPDATE`` touchent la vraie base →
``TestCase`` (pas ``SimpleTestCase``).
"""
from unittest.mock import Mock

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import services
from apps.adsengine.models import EngineAction


class ApplyCasTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CAS Co', slug='cas-co')

    def _approved(self):
        return EngineAction.objects.create(
            company=self.company, kind=EngineAction.Kind.CREATE_CAMPAIGN,
            reason_fr="Lancer une campagne leads à Casablanca.",
            payload={'name': 'Solaire', 'objective': 'OUTCOME_LEADS'},
            status=EngineAction.Statut.APPROUVEE)

    def test_cas_lets_only_one_apply_win(self):
        action = self._approved()
        # Deux instances EN MÉMOIRE de la MÊME action, toutes deux « approuvee » :
        # simule deux workers ayant lu la ligne avant toute réclamation. La garde
        # rapide en mémoire passe pour LES DEUX → seul le compare-and-swap tranche.
        a1 = EngineAction.objects.get(pk=action.pk)
        a2 = EngineAction.objects.get(pk=action.pk)
        self.assertEqual(a2.status, EngineAction.Statut.APPROUVEE)

        client1 = Mock()
        client1.create_campaign.return_value = {'id': 'meta-1'}
        client2 = Mock()

        services.apply_action(a1, client=client1)  # réclame et dispatche
        with self.assertRaises(services.ActionNotApproved):
            services.apply_action(a2, client=client2)  # CAS échoue → refus

        client1.create_campaign.assert_called_once()
        client2.create_campaign.assert_not_called()
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        self.assertEqual(action.result, {'id': 'meta-1'})

    def test_sequential_second_apply_is_blocked(self):
        # Une réapplication (même instance déjà appliquée) est refusée d'emblée.
        action = self._approved()
        client = Mock()
        client.create_campaign.return_value = {'id': 'x'}
        services.apply_action(action, client=client)
        client.create_campaign.reset_mock()
        with self.assertRaises(services.ActionNotApproved):
            services.apply_action(action, client=client)
        client.create_campaign.assert_not_called()

    def test_dispatch_failure_reverts_to_echouee(self):
        # Un échec de dispatch APRÈS réclamation ne laisse jamais l'action
        # faussement « appliquee » : elle repasse « echouee ».
        action = self._approved()
        client = Mock()
        client.create_campaign.side_effect = RuntimeError('Token expiré')
        with self.assertRaises(RuntimeError):
            services.apply_action(action, client=client)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.ECHOUEE)
        self.assertIn('Token expiré', action.error)

    def test_approve_reject_race_last_writer_guarded(self):
        # Approuver puis rejeter : la seconde décision voit une action qui n'est
        # plus « proposee » sous le verrou → refus (jamais deux gagnants).
        action = EngineAction.objects.create(
            company=self.company, kind=EngineAction.Kind.CREATE_CAMPAIGN,
            reason_fr="Décision concurrente à arbitrer.",
            payload={}, status=EngineAction.Statut.PROPOSEE)
        user = None
        services.approve_action(action, user=user)
        stale = EngineAction.objects.get(pk=action.pk)
        stale.status = EngineAction.Statut.PROPOSEE  # instance périmée
        with self.assertRaises(ValueError):
            services.reject_action(stale, user=user, commentaire='trop tard')
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPROUVEE)

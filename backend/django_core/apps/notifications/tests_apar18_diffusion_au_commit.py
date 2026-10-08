"""APAR18 — la diffusion hors-app de ``notify()`` part AU COMMIT.

Constat C-APAR-024 : ``notify()`` diffusait e-mail / WhatsApp / push
immédiatement, dans la transaction de l'émetteur : un devis accepté puis
annulé (rollback) avait déjà poussé « Devis accepté », une facture soldée dans
une transaction annulée avait déjà envoyé « Facture intégralement réglée ».
La ligne in-app reste transactionnelle ; la diffusion part en
``transaction.on_commit``.

``TransactionTestCase`` OBLIGATOIRE : sous ``TestCase`` tout tourne dans une
transaction jamais validée (``on_commit`` n'y tire pas).

Test-du-test : rappeler ``_diffuser_hors_app`` en direct dans ``notify()`` ⇒
``test_rollback_aucune_diffusion`` rouge.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TransactionTestCase

from apps.notifications import services
from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType
from authentication.models import Company
from core.test_utils import WideTeardownTimeoutMixin


class _Annule(Exception):
    pass


class DiffusionAuCommitTests(WideTeardownTimeoutMixin, TransactionTestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='APAR18', slug='apar18-co')
        self.user = get_user_model().objects.create_user(
            username='apar18-u', password='x', company=self.co,
            email='apar18@example.invalid')

    def _notifier(self):
        return services.notify(
            self.user, EventType.DEVIS_ACCEPTED, 'Devis accepté',
            body='DEV-APAR18', company=self.co, respect_quiet_hours=False)

    def test_rollback_aucune_diffusion(self):
        with mock.patch.object(services, '_diffuser_hors_app') as espion:
            with self.assertRaises(_Annule):
                with transaction.atomic():
                    self._notifier()
                    espion.assert_not_called()  # rien avant le commit
                    raise _Annule()
        espion.assert_not_called()
        self.assertEqual(Notification.objects.filter(
            recipient=self.user).count(), 0)

    def test_commit_une_ligne_une_diffusion(self):
        with mock.patch.object(services, '_diffuser_hors_app') as espion:
            with transaction.atomic():
                self._notifier()
                espion.assert_not_called()
            espion.assert_called_once()
        self.assertEqual(Notification.objects.filter(
            recipient=self.user).count(), 1)

    def test_hors_transaction_diffusion_immediate(self):
        with mock.patch.object(services, '_diffuser_hors_app') as espion:
            self._notifier()
            espion.assert_called_once()

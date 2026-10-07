"""AANA31 — les webhooks ne partent qu'AU COMMIT de la transaction métier.

Constat C-AANA-024 : ``delivery.dispatch_event`` mettait la livraison en file
(``deliver_webhook.delay``) PENDANT la transaction : un passage de devis à
« accepté » suivi d'une erreur (rollback) livrait quand même ``devis.accepted``
— un évènement fantôme chez l'intégrateur. Désormais la mise en file passe
par ``transaction.on_commit`` (patron de ``core.events.emit_reliable``) et le
journal du flux d'évènements suit la même transaction.

Chaîne réelle : vrai ``Devis`` enregistré, vrais signaux ``publicapi``, vrai
``dispatch_event`` ; seule la frontière Celery (``delay``) est espionnée.

Run :
    python manage.py test apps.publicapi.tests_aana_webhook_commit -v2
"""
from unittest import mock

from django.db import transaction
from django.test import TestCase

from apps.crm.models import Client
from apps.ventes.models import Devis
from authentication.models import Company

from . import tasks
from .constants import EVENT_DEVIS_ACCEPTED
from .models import ApiEvent, Webhook


class WebhookAuCommitTest(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aana31-co', defaults={'nom': 'AANA31'})
        client = Client.objects.create(company=self.co, nom='Client AANA31')
        self.devis = Devis.objects.create(
            company=self.co, reference='DV-AANA31', client=client,
            statut=Devis.Statut.ENVOYE)
        self.webhook = Webhook.objects.create(
            company=self.co, label='integrateur',
            target_url='https://integrateur.example.test/hook',
            secret=Webhook.generate_secret(),
            events=[EVENT_DEVIS_ACCEPTED], enabled=True)

    def _accepter(self):
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save()

    def test_pas_de_webhook_si_rollback(self):
        with mock.patch.object(tasks.deliver_webhook, 'delay') as envoi, \
                self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    self._accepter()
                    raise RuntimeError('erreur après le passage à accepté')
        envoi.assert_not_called()
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)
        # Le journal du flux suit la MÊME transaction : annulé avec elle.
        self.assertFalse(ApiEvent.objects.filter(
            company=self.co, type=EVENT_DEVIS_ACCEPTED).exists())

    def test_un_seul_webhook_au_commit(self):
        with mock.patch.object(tasks.deliver_webhook, 'delay') as envoi, \
                self.captureOnCommitCallbacks(execute=False) as rappels:
            self._accepter()
            # Rien n'est mis en file tant que la transaction n'a pas commité.
            envoi.assert_not_called()
        self.assertTrue(rappels)
        with mock.patch.object(tasks.deliver_webhook, 'delay') as envoi:
            for rappel in rappels:
                rappel()
        envoi.assert_called_once()
        args, _kwargs = envoi.call_args
        self.assertEqual(args[0], self.webhook.id)
        self.assertEqual(args[1], EVENT_DEVIS_ACCEPTED)
        self.assertEqual(args[2]['id'], self.devis.pk)

    def test_commit_reel_livre_une_fois(self):
        with mock.patch.object(tasks.deliver_webhook, 'delay') as envoi, \
                self.captureOnCommitCallbacks(execute=True):
            self._accepter()
        envoi.assert_called_once()
        self.assertTrue(ApiEvent.objects.filter(
            company=self.co, type=EVENT_DEVIS_ACCEPTED).exists())

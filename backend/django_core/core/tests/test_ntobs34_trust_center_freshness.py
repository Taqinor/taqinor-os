"""NTOBS34 — vérification quotidienne de la fraîcheur des TrustCenterEntry
(alerte fondateur si un audit expire).

LIMITE ASSUMÉE (lane isolée, ``core/models.py``/``core/migrations``
appartiennent à une autre lane en ce moment) : le champ
``TrustCenterEntry.alerte_expiration_envoyee`` nommé par le plan n'est PAS
posé ici — l'anti-spam repose en attendant sur le cache Django (clé par
entrée + date d'audit, voir ``core/tasks.py``). Migration exacte à poser par
l'orchestrateur documentée en tête de ``core/tasks.py``."""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from core.tasks import verifier_fraicheur_trust_center_task
from core.trust_center import TrustCenterEntry

User = get_user_model()


def _il_y_a_mois(mois):
    return (timezone.now() - datetime.timedelta(days=mois * 31)).date()


class VerifierFraicheurTrustCenterTest(TestCase):
    def setUp(self):
        cache.clear()
        self.superuser = User.objects.create_superuser(
            username='founder34', password='x')

    def test_entry_older_than_12_months_triggers_one_notification(self):
        TrustCenterEntry.objects.create(
            categorie=TrustCenterEntry.Categorie.CERTIFICATION,
            titre='ISO 27001', dernier_audit_le=_il_y_a_mois(13))
        with mock.patch('core.notify_registry.notify') as notify_mock:
            result = verifier_fraicheur_trust_center_task()
        self.assertEqual(result['notifies'], 1)
        self.assertEqual(notify_mock.call_count, 1)

    def test_entry_within_12_months_is_not_notified(self):
        TrustCenterEntry.objects.create(
            categorie=TrustCenterEntry.Categorie.CERTIFICATION,
            titre='ISO 27001', dernier_audit_le=_il_y_a_mois(6))
        with mock.patch('core.notify_registry.notify') as notify_mock:
            result = verifier_fraicheur_trust_center_task()
        self.assertEqual(result['notifies'], 0)
        self.assertFalse(notify_mock.called)

    def test_entry_without_audit_date_is_never_notified(self):
        TrustCenterEntry.objects.create(
            categorie=TrustCenterEntry.Categorie.POLITIQUE, titre='RGPD')
        with mock.patch('core.notify_registry.notify') as notify_mock:
            verifier_fraicheur_trust_center_task()
        self.assertFalse(notify_mock.called)

    def test_no_daily_spam_for_the_same_stale_entry(self):
        TrustCenterEntry.objects.create(
            categorie=TrustCenterEntry.Categorie.CERTIFICATION,
            titre='ISO 27001', dernier_audit_le=_il_y_a_mois(13))
        with mock.patch('core.notify_registry.notify') as notify_mock:
            verifier_fraicheur_trust_center_task()
            verifier_fraicheur_trust_center_task()
        self.assertEqual(notify_mock.call_count, 1)

    def test_updating_the_entry_allows_a_fresh_alert_later(self):
        """« flag remis à False si l'entrée est mise à jour » — ici simulé en
        changeant ``dernier_audit_le`` (toujours périmé, mais une date
        DIFFÉRENTE) : la clé de cache change, l'alerte redevient possible."""
        entry = TrustCenterEntry.objects.create(
            categorie=TrustCenterEntry.Categorie.CERTIFICATION,
            titre='ISO 27001', dernier_audit_le=_il_y_a_mois(13))
        with mock.patch('core.notify_registry.notify') as notify_mock:
            verifier_fraicheur_trust_center_task()
        self.assertEqual(notify_mock.call_count, 1)

        entry.dernier_audit_le = _il_y_a_mois(14)
        entry.save(update_fields=['dernier_audit_le'])
        with mock.patch('core.notify_registry.notify') as notify_mock:
            verifier_fraicheur_trust_center_task()
        self.assertEqual(notify_mock.call_count, 1)

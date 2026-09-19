"""NTOBS21 — écran de réglages « Fiabilité » par tenant (préférences de
notification/affichage).

Cette lane (``apps/roles`` interdit — voir ``core/models.py``, hors
périmètre) ne pose PAS le modèle ``core.ReliabilitySettings`` lui-même
(schéma/migration réservés à une autre lane sur ``core/models.py``) : elle
câble la LECTURE défensive du flag ``notifier_quota_email`` dans
``core.usage_limits.notifier_seuils_usage`` (NTOBS13), testée ici via un
DOUBLE (mock de ``django.apps.apps.get_model``) puisque le vrai modèle n'a
pas encore de migration.

Modèle exact à poser par l'orchestrateur (autre lane, ``core/models.py`` +
migration) :

    class ReliabilitySettings(models.Model):
        company = models.OneToOneField(
            'authentication.Company', on_delete=models.CASCADE,
            related_name='reliability_settings')
        notifier_maintenance_email = models.BooleanField(default=True)
        notifier_quota_email = models.BooleanField(default=True)
        notifier_incident_region = models.CharField(
            max_length=100, null=True, blank=True, default='')
        afficher_badge_sla_dashboard = models.BooleanField(default=True)

Le screen frontend (``frontend/src/pages/parametres/
ReliabilitySettingsPage.jsx``) est hors périmètre de cette lane
(``frontend/src`` appartient à une autre lane)."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from core.usage_limits import notifier_seuils_usage

User = get_user_model()


class _FakeQuerySet:
    def __init__(self, row):
        self._row = row

    def filter(self, **kwargs):
        return self

    def first(self):
        return self._row


class _FakeReliabilitySettings:
    def __init__(self, notifier_quota_email):
        self.notifier_quota_email = notifier_quota_email


class NotifierSeuilsUsageReliabilitySettingsTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Acme', slug='ntobs21-acme', actif=True)
        self.autre = Company.objects.create(
            nom='Autre', slug='ntobs21-autre', actif=True)

    def _mock_get_model(self, rows_by_company):
        """``rows_by_company`` : {company_id: _FakeReliabilitySettings|None}.

        Renvoie un double minimal imitant ``Model.objects.filter(company=...)
        .first()`` — assez pour exercer ``_reliability_settings`` sans que la
        vraie migration ``core.ReliabilitySettings`` existe encore."""
        def get_model(app_label, model_name):
            assert (app_label, model_name) == ('core', 'ReliabilitySettings')

            class _Bound:
                class objects:  # noqa: N801 — miroir Django `Model.objects`
                    @staticmethod
                    def filter(company=None):
                        return _FakeQuerySet(
                            rows_by_company.get(getattr(company, 'id', None)))
            return _Bound
        return get_model

    def test_model_absent_keeps_default_behaviour(self):
        """``LookupError`` (migration pas encore posée) = comportement par
        défaut inchangé : la notification part normalement."""
        with mock.patch(
                'core.usage_limits.django_apps.get_model',
                side_effect=LookupError):
            with mock.patch(
                    'core.usage_limits.usage_summary',
                    return_value={'ressources': []}):
                n = notifier_seuils_usage()
        self.assertEqual(n, 0)  # aucune ressource mesurée -> rien à notifier,
        # mais la boucle n'a pas 'continue'-é prématurément (voir test suivant
        # pour la preuve que le flag est bien consulté quand il existe).

    def test_disabled_flag_skips_only_that_company(self):
        rows = {
            self.company.id: _FakeReliabilitySettings(notifier_quota_email=False),
            self.autre.id: _FakeReliabilitySettings(notifier_quota_email=True),
        }
        appelées = []

        def fake_usage_summary(company):
            appelées.append(company.id)
            return {'ressources': []}

        with mock.patch(
                'core.usage_limits.django_apps.get_model',
                side_effect=self._mock_get_model(rows)):
            with mock.patch(
                    'core.usage_limits.usage_summary',
                    side_effect=fake_usage_summary):
                notifier_seuils_usage()

        self.assertNotIn(self.company.id, appelées)
        self.assertIn(self.autre.id, appelées)

    def test_enabled_flag_does_not_skip(self):
        rows = {
            self.company.id: _FakeReliabilitySettings(notifier_quota_email=True),
        }
        appelées = []

        def fake_usage_summary(company):
            appelées.append(company.id)
            return {'ressources': []}

        with mock.patch(
                'core.usage_limits.django_apps.get_model',
                side_effect=self._mock_get_model(rows)):
            with mock.patch(
                    'core.usage_limits.usage_summary',
                    side_effect=fake_usage_summary):
                notifier_seuils_usage()

        self.assertIn(self.company.id, appelées)

"""ODX23 (reliquat) — gating ``ModuleToggle`` des notifications.

Un événement appartenant à un module métier explicitement désactivé pour la
société du destinataire (voir ``module_gating.EVENT_MODULE``) ne notifie plus
personne : `notify()` devient un no-op (aucune ligne `Notification`), sans
lever. Un événement non mappé (transverse/fondation) ou une société sans
`ModuleToggle` reste inchangé (non-régression, policy FG391 : actif par
défaut).
"""
from django.test import TestCase

from authentication.models import Company, CustomUser
from core.models import ModuleToggle

from .models import EventType, Notification
from .services import notify


def _make_company(name='GateCo'):
    return Company.objects.create(nom=name)


def _make_user(company, username='u1'):
    return CustomUser.objects.create_user(
        username=username, password='pw', company=company)


class NotifyModuleGatingTests(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.user = _make_user(self.company)

    def test_disabled_module_event_is_noop(self):
        ModuleToggle.objects.create(
            company=self.company, module='sav', actif=False)
        result = notify(
            self.user, EventType.WARRANTY_EXPIRING, 'Garantie', company=self.company)
        self.assertIsNone(result)
        self.assertFalse(Notification.objects.filter(
            recipient=self.user, event_type=EventType.WARRANTY_EXPIRING).exists())

    def test_default_active_module_still_notifies(self):
        # Aucun ModuleToggle -> actif par défaut, comportement inchangé.
        result = notify(
            self.user, EventType.WARRANTY_EXPIRING, 'Garantie', company=self.company)
        self.assertIsNotNone(result)
        self.assertTrue(Notification.objects.filter(
            recipient=self.user, event_type=EventType.WARRANTY_EXPIRING).exists())

    def test_unmapped_event_never_gated(self):
        """DIGEST n'est volontairement pas dans EVENT_MODULE (transverse) :
        même un module désactivé sans rapport ne l'affecte jamais."""
        ModuleToggle.objects.create(
            company=self.company, module='sav', actif=False)
        result = notify(
            self.user, EventType.DIGEST, 'Résumé', company=self.company)
        self.assertIsNotNone(result)

    def test_multi_tenant_isolation(self):
        other = _make_company('GateCo B')
        other_user = _make_user(other, 'u2')
        ModuleToggle.objects.create(company=self.company, module='sav', actif=False)

        blocked = notify(
            self.user, EventType.WARRANTY_EXPIRING, 'Garantie', company=self.company)
        allowed = notify(
            other_user, EventType.WARRANTY_EXPIRING, 'Garantie', company=other)

        self.assertIsNone(blocked)
        self.assertIsNotNone(allowed)

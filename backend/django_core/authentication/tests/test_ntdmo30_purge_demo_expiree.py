"""NTDMO30 — purge hebdomadaire des sociétés démo TAQINOR expirées (staging/
marketing uniquement, jamais une société réelle). Désactivée par défaut :
``DEMO_AUTO_PURGE_ENABLED`` (env, défaut 0) doit être explicitement activé.
"""
from datetime import date, timedelta

from django.test import TestCase, override_settings

from apps.audit.models import AuditLog
from apps.parametres.models_company import CompanyProfile
from authentication.models import Company, CustomUser
from authentication.tasks import purger_societes_demo_expirees_task

EXPIRED_91J = date.today() - timedelta(days=91)
EXPIRED_10J = date.today() - timedelta(days=10)


def _demo_company(slug, essai_expire_le=None):
    company = Company.objects.create(nom=slug, slug=slug, est_demo=True)
    if essai_expire_le is not None:
        profile = CompanyProfile.get(company)
        profile.essai_expire_le = essai_expire_le
        profile.save(update_fields=['essai_expire_le'])
    return company


class PurgeDemoExpireeGateTest(TestCase):
    """Le flag DÉSACTIVÉ (comportement par défaut, TOUTE installation
    existante) ne supprime JAMAIS aucune société, même expirée depuis
    longtemps."""

    @override_settings(DEMO_AUTO_PURGE_ENABLED=False)
    def test_disabled_by_default_never_purges(self):
        company = _demo_company('demo-expiree-off', EXPIRED_91J)
        result = purger_societes_demo_expirees_task()
        self.assertEqual(result, {'purged': 0, 'enabled': False})
        self.assertTrue(Company.objects.filter(pk=company.pk).exists())


class PurgeDemoExpireeEnabledTest(TestCase):
    @override_settings(DEMO_AUTO_PURGE_ENABLED=True)
    def test_purges_demo_company_expired_over_90_days(self):
        company = _demo_company('demo-expiree-on', EXPIRED_91J)
        result = purger_societes_demo_expirees_task()
        self.assertEqual(result['purged'], 1)
        self.assertIn('demo-expiree-on', result['slugs'])
        self.assertFalse(Company.objects.filter(pk=company.pk).exists())

    @override_settings(DEMO_AUTO_PURGE_ENABLED=True)
    def test_never_touches_a_non_demo_company_even_with_expired_profile(self):
        real = Company.objects.create(nom='Réelle', slug='reelle-purge')
        profile = CompanyProfile.get(real)
        profile.essai_expire_le = EXPIRED_91J
        profile.save(update_fields=['essai_expire_le'])
        result = purger_societes_demo_expirees_task()
        self.assertEqual(result['purged'], 0)
        self.assertTrue(Company.objects.filter(pk=real.pk).exists())

    @override_settings(DEMO_AUTO_PURGE_ENABLED=True)
    def test_never_purges_a_demo_company_not_yet_past_90_days(self):
        company = _demo_company('demo-recente', EXPIRED_10J)
        result = purger_societes_demo_expirees_task()
        self.assertEqual(result['purged'], 0)
        self.assertTrue(Company.objects.filter(pk=company.pk).exists())

    @override_settings(DEMO_AUTO_PURGE_ENABLED=True)
    def test_never_purges_a_demo_company_without_essai_expire_le(self):
        company = _demo_company('demo-sans-date')
        result = purger_societes_demo_expirees_task()
        self.assertEqual(result['purged'], 0)
        self.assertTrue(Company.objects.filter(pk=company.pk).exists())

    @override_settings(DEMO_AUTO_PURGE_ENABLED=True)
    def test_deletes_users_of_the_purged_company_too(self):
        company = _demo_company('demo-avec-users', EXPIRED_91J)
        CustomUser.objects.create(
            username='u-demo-purge', email='u@demo.local', company=company)
        purger_societes_demo_expirees_task()
        self.assertFalse(
            CustomUser.objects.filter(username='u-demo-purge').exists())

    @override_settings(DEMO_AUTO_PURGE_ENABLED=True)
    def test_writes_an_audit_log_before_deletion_that_survives_it(self):
        before = AuditLog.objects.filter(action='demo_company_purge').count()
        _demo_company('demo-audit-purge', EXPIRED_91J)
        purger_societes_demo_expirees_task()
        logs = AuditLog.objects.filter(action='demo_company_purge')
        self.assertEqual(logs.count(), before + 1)
        entry = logs.latest('id')
        # Survit à la suppression de la société (AuditLog.company=SET_NULL) :
        # le texte (`detail`) reste la preuve, même FK à None.
        self.assertIn('demo-audit-purge', entry.detail)
        self.assertIsNone(entry.company_id)

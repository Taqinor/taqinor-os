"""NTADM7 — has_feature() (paliers de licence), extension de FG391.

Politique NON-RESTRICTIVE PAR DÉFAUT : une société sans plan garde l'accès
complet (zéro régression). Une société avec un plan ne voit ``has_feature``
renvoyer False que pour un module explicitement ABSENT de
``modules_inclus``."""
from django.test import TestCase

from authentication.models import Company

from .feature_flags import has_feature
from .models import CompanyProfile


def _company(slug='ntadm7-co', nom='NTADM7 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class HasFeatureTests(TestCase):
    def test_sans_plan_accede_a_tout(self):
        """NULL (comportement de toute société existante) = accès complet."""
        company = _company()
        self.assertTrue(has_feature(company, 'crm'))
        self.assertTrue(has_feature(company, 'nimporte_quoi'))

    def test_sans_company_accede_a_tout(self):
        self.assertTrue(has_feature(None, 'crm'))

    def test_plan_starter_restreint_aux_modules_inclus(self):
        from apps.adminops.models import PlanLicence
        company = _company(slug='ntadm7-co-2', nom='NTADM7 Co 2')
        plan = PlanLicence.objects.create(
            code='starter', nom='Starter', modules_inclus=['crm', 'ventes'])
        profile = CompanyProfile.get(company=company)
        profile.plan = plan
        profile.save(update_fields=['plan'])

        self.assertTrue(has_feature(company, 'crm'))
        self.assertTrue(has_feature(company, 'ventes'))
        self.assertFalse(has_feature(company, 'paie'))

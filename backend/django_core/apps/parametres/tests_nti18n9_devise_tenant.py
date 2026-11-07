"""NTI18N9 — CompanyProfile.devise_tenant (devise d'affichage société).

Nouveau fichier car : la tâche est un champ de schéma isolé, sans module de
test parametres thématique existant (cf. tests_nti18n34/35 pour le même motif).
"""
from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company
from apps.parametres.models_company import CompanyProfile
from apps.parametres.serializers_company import CompanyProfileSerializer


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


class DeviseTenantTests(TestCase):
    def test_default_mad_and_independent_of_devise_defaut(self):
        p = CompanyProfile.get(_company('nti18n9-a'))
        self.assertEqual(p.devise_tenant, 'MAD')
        self.assertEqual(p.devise_defaut, 'MAD')

    def test_xof_company_does_not_touch_other_company_or_document_currency(self):
        xof = CompanyProfile.get(_company('nti18n9-xof'))
        xof.devise_tenant = 'XOF'
        xof.save(update_fields=['devise_tenant'])
        autre = CompanyProfile.get(_company('nti18n9-mad'))
        xof.refresh_from_db()
        self.assertEqual(xof.devise_tenant, 'XOF')
        self.assertEqual(xof.devise_defaut, 'MAD')  # devise document (FG52) intacte
        self.assertEqual(autre.devise_tenant, 'MAD')

    def test_exposed_by_serializer(self):
        p = CompanyProfile.get(_company('nti18n9-ser'))
        p.devise_tenant = 'XOF'
        p.save(update_fields=['devise_tenant'])
        self.assertEqual(CompanyProfileSerializer(p).data['devise_tenant'], 'XOF')

    def test_invalid_code_rejected(self):
        p = CompanyProfile.get(_company('nti18n9-bad'))
        p.devise_tenant = 'xof'
        with self.assertRaises(ValidationError):
            p.full_clean()

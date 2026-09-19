"""NTI18N35 — réglage "forcer la langue d'interface" par société (verrouillage).

Le 403 réel sur `PATCH /auth/me/langue/`
(`authentication.views.LangueInterfaceView`) est HORS périmètre de cette
lane (apps/parametres uniquement — authentication est une autre app) : ce
fichier couvre le champ modèle et les sélecteurs cross-app prêts à être
consommés par cette vue, jamais l'endpoint lui-même.
"""
from django.test import TestCase

from authentication.models import Company
from apps.parametres.models_company import CompanyProfile
from apps.parametres.selectors import (
    langue_interface_verrouillee,
    langue_par_defaut_effective,
)


def _company(slug='nti18n35-co', nom='NTI18N35 Co'):
    return Company.objects.create(nom=nom, slug=slug)


class CompanyProfileVerrouillageFieldTests(TestCase):
    def test_default_is_false_for_existing_companies(self):
        profile = CompanyProfile.get(_company())
        self.assertFalse(profile.langue_interface_verrouillee)


class LangueInterfaceVerrouilleeSelectorTests(TestCase):
    def test_false_by_default(self):
        company = _company('nti18n35-co-2', 'NTI18N35 Co 2')
        self.assertFalse(langue_interface_verrouillee(company))

    def test_true_when_activated(self):
        company = _company('nti18n35-co-3', 'NTI18N35 Co 3')
        profile = CompanyProfile.get(company)
        profile.langue_interface_verrouillee = True
        profile.save(update_fields=['langue_interface_verrouillee'])
        self.assertTrue(langue_interface_verrouillee(company))

    def test_no_company_never_locked(self):
        self.assertFalse(langue_interface_verrouillee(None))


class LangueParDefautEffectiveTests(TestCase):
    def test_none_when_not_locked(self):
        company = _company('nti18n35-co-4', 'NTI18N35 Co 4')
        self.assertIsNone(langue_par_defaut_effective(company))

    def test_returns_langue_repli_when_locked(self):
        company = _company('nti18n35-co-5', 'NTI18N35 Co 5')
        profile = CompanyProfile.get(company)
        profile.langue_interface_verrouillee = True
        profile.langue_repli = 'ar'
        profile.save(
            update_fields=['langue_interface_verrouillee', 'langue_repli'])
        self.assertEqual(langue_par_defaut_effective(company), 'ar')

    def test_unlocking_restores_individual_choice(self):
        # Non-régression : déverrouiller redonne immédiatement la main à
        # l'utilisateur (plus aucune langue imposée).
        company = _company('nti18n35-co-6', 'NTI18N35 Co 6')
        profile = CompanyProfile.get(company)
        profile.langue_interface_verrouillee = True
        profile.langue_repli = 'en'
        profile.save(
            update_fields=['langue_interface_verrouillee', 'langue_repli'])
        self.assertEqual(langue_par_defaut_effective(company), 'en')
        profile.langue_interface_verrouillee = False
        profile.save(update_fields=['langue_interface_verrouillee'])
        self.assertIsNone(langue_par_defaut_effective(company))

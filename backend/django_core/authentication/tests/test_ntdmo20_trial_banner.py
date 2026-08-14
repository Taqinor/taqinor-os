"""NTDMO20 — bannière d'expiration d'essai (fondation).

``CompanyProfile.essai_expire_le`` est additive, vide par défaut : une
société sans date renseignée n'est jamais affectée (comportement actuel
byte-identique). ``UserSerializer.company_essai_expire`` est le SEUL calcul
consommé par le frontend (banner non-bloquante)."""
from datetime import date, timedelta

from django.test import TestCase

from authentication.models import Company, CustomUser
from authentication.serializers import UserSerializer
from apps.parametres.models_company import CompanyProfile


class TrialBannerNTDMO20Test(TestCase):
    def _make_user(self, company):
        return CustomUser.objects.create(
            username=f'u-{company.slug}', email=f'{company.slug}@demo.local',
            company=company)

    def test_no_date_never_flags_expired(self):
        company = Company.objects.create(nom='Sans essai', slug='sans-essai')
        user = self._make_user(company)
        data = UserSerializer(user).data
        self.assertFalse(data['company_essai_expire'])

    def test_future_date_not_expired(self):
        company = Company.objects.create(nom='Essai futur', slug='essai-futur')
        profile = CompanyProfile.get(company)
        profile.essai_expire_le = date.today() + timedelta(days=10)
        profile.save(update_fields=['essai_expire_le'])
        user = self._make_user(company)
        data = UserSerializer(user).data
        self.assertFalse(data['company_essai_expire'])

    def test_past_date_flags_expired(self):
        company = Company.objects.create(nom='Essai expiré', slug='essai-expire')
        profile = CompanyProfile.get(company)
        profile.essai_expire_le = date.today() - timedelta(days=1)
        profile.save(update_fields=['essai_expire_le'])
        user = self._make_user(company)
        data = UserSerializer(user).data
        self.assertTrue(data['company_essai_expire'])

    def test_essai_expire_le_read_only_in_profile_serializer(self):
        from apps.parametres.serializers_company import CompanyProfileSerializer
        self.assertIn(
            'essai_expire_le',
            CompanyProfileSerializer.Meta.read_only_fields)

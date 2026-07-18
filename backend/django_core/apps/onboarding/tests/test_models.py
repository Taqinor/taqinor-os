"""NTDMO11 — modèles + catalogue onboarding + résolution par rôle."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.onboarding.models import OnboardingChecklistItem, OnboardingProgress
from apps.onboarding.selectors import checklist_pour_utilisateur
from apps.onboarding.services import seed_default_items

User = get_user_model()


class OnboardingModelsTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Co', slug='co-ob')

    def test_default_catalogue_seeded_by_migration(self):
        # Le seed (migration de données) crée le catalogue global.
        self.assertGreaterEqual(OnboardingChecklistItem.objects.count(), 5)
        self.assertTrue(OnboardingChecklistItem.objects.filter(
            key='premier_devis', company__isnull=True).exists())

    def test_seed_is_idempotent(self):
        n = OnboardingChecklistItem.objects.count()
        seed_default_items()
        self.assertEqual(OnboardingChecklistItem.objects.count(), n)

    def test_progress_unique_per_user_item(self):
        item = OnboardingChecklistItem.objects.first()
        u = User.objects.create_user('u1', password='x', company=self.company)
        OnboardingProgress.objects.create(
            company=self.company, user=u, item=item)
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OnboardingProgress.objects.create(
                    company=self.company, user=u, item=item)

    def test_role_targeting_differs_between_users(self):
        commercial = User.objects.create_user(
            'com', password='x', company=self.company,
            role_legacy='commercial')
        technicien = User.objects.create_user(
            'tech', password='x', company=self.company,
            role_legacy='technicien')
        # Rôle legacy ne matche pas les noms de Role fins ; on force via Role.
        from apps.roles.models import Role
        rc = Role.objects.create(company=self.company, nom='Commercial')
        rt = Role.objects.create(company=self.company, nom='Technicien')
        commercial.role = rc
        commercial.save()
        technicien.role = rt
        technicien.save()
        keys_com = {i['key'] for i in
                    checklist_pour_utilisateur(self.company, commercial)}
        keys_tech = {i['key'] for i in
                     checklist_pour_utilisateur(self.company, technicien)}
        # « premier_devis » cible Commercial, pas Technicien.
        self.assertIn('premier_devis', keys_com)
        self.assertNotIn('premier_devis', keys_tech)
        # Les listes diffèrent, toujours company-scopées.
        self.assertNotEqual(keys_com, keys_tech)

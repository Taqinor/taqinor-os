"""ASEC7 — la primitive ``core.entite_scoping`` refuse toute entité d'une
autre société, MÊME quand le rôle n'a aucun périmètre d'entités.

Modèles lus par ``apps.get_model`` : ``core`` (et ses tests) n'importe
aucune app (contrat import-linter ``core-foundation-is-a-base-layer``).
"""
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from authentication.models import Company
from core.entite_scoping import assert_entite_assignable

User = get_user_model()


class EntiteScopingTests(TestCase):
    def setUp(self):
        Entite = django_apps.get_model('entites', 'Entite')
        Role = django_apps.get_model('roles', 'Role')
        self.co_a = Company.objects.create(nom='ASEC7 A', slug='asec7-a')
        self.co_b = Company.objects.create(nom='ASEC7 B', slug='asec7-b')
        self.e_a1 = Entite.objects.create(company=self.co_a, nom='A1', code='A1')
        self.e_a2 = Entite.objects.create(company=self.co_a, nom='A2', code='A2')
        self.e_b = Entite.objects.create(company=self.co_b, nom='B1', code='B1')
        self.role_libre = Role.objects.create(
            company=self.co_a, nom='Sans périmètre', permissions=['crm_voir'])
        self.role_restreint = Role.objects.create(
            company=self.co_a, nom='Restreint A1', permissions=['crm_voir'])
        self.role_restreint.entites_visibles.add(self.e_a1)
        self.libre = User.objects.create_user(
            username='asec7_libre', password='x', company=self.co_a,
            role=self.role_libre)
        self.restreint = User.objects.create_user(
            username='asec7_restreint', password='x', company=self.co_a,
            role=self.role_restreint)

    def test_sans_perimetre_entite_etrangere_refusee(self):
        with self.assertRaises(ValidationError) as ctx:
            assert_entite_assignable(self.libre, self.e_b.id)
        self.assertIn('entite', ctx.exception.detail)
        # Id inexistant : même réponse (aucun oracle d'existence).
        with self.assertRaises(ValidationError):
            assert_entite_assignable(self.libre, 999999999)

    def test_perimetre_restreint_inchange(self):
        with self.assertRaises(PermissionDenied):
            assert_entite_assignable(self.restreint, self.e_a2.id)
        assert_entite_assignable(self.restreint, self.e_a1.id)
        with self.assertRaises(ValidationError):
            assert_entite_assignable(self.restreint, self.e_b.id)

    def test_sans_perimetre_entite_societe_acceptee(self):
        assert_entite_assignable(self.libre, self.e_a1.id)
        assert_entite_assignable(self.libre, self.e_a2.id)
        assert_entite_assignable(self.libre, None)
        assert_entite_assignable(self.libre, '')

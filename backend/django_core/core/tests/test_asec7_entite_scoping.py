"""ASEC7 — la primitive ``core.entite_scoping`` refuse toute entité d'une
autre société, MÊME quand le rôle n'a aucun périmètre d'entités.

Modèles lus par ``apps.get_model`` : ``core`` (et ses tests) n'importe
aucune app (contrat import-linter ``core-foundation-is-a-base-layer``).
"""
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

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
        # ENF17 — la réponse du champ borné (ACAL298) : « objet inexistant ».
        self.assertEqual(ctx.exception.detail['entite'][0].code,
                         'does_not_exist')
        # Id inexistant : même réponse (aucun oracle d'existence).
        with self.assertRaises(ValidationError) as absent:
            assert_entite_assignable(self.libre, 999999999)
        self.assertEqual(absent.exception.detail['entite'][0].code,
                         'does_not_exist')

    def test_saveur_404_meme_corps(self):
        """CI #1029 — ``inconnu_404`` : 404 au lieu de 400, corps identique
        (champ ``entite``, code ``does_not_exist``), étrangère ou inexistante."""
        for entite_id in (self.e_b.id, 999999999):
            with self.assertRaises(NotFound) as ctx:
                assert_entite_assignable(self.libre, entite_id, inconnu_404=True)
            self.assertEqual(ctx.exception.detail['entite'][0].code,
                             'does_not_exist')
        with self.assertRaises(ValidationError):
            assert_entite_assignable(self.libre, self.e_b.id)

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

    def test_methode_non_portee_par_la_route_reste_405(self):
        """CI #997 api-fuzz : ``PUT /devis/atomic/`` (route POST seule) avec une
        entité inconnue répondait 400 depuis ``initial`` ; la méthode refusée
        passe avant le contrôle d'entité (405)."""
        from rest_framework.test import APIClient
        admin = User.objects.create_user(
            username='asec7_admin', password='x', company=self.co_a,
            role_legacy='admin')
        api = APIClient()
        api.force_authenticate(admin)
        url = '/api/django/ventes/devis/atomic/'
        corps = {'entite': 999999999, 'lignes': [{}]}
        self.assertEqual(api.put(url, corps, format='json').status_code, 405)
        self.assertEqual(api.patch(url, corps, format='json').status_code, 405)

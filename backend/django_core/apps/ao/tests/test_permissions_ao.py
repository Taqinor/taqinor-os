"""AOF2 — permissions dédiées ``ao_voir`` / ``ao_gerer`` /
``ao_rentabilite_voir``.

Correction d'une régression de confidentialité EXISTANTE : avant AOF2 il
n'existait AUCUNE permission ``ao_*`` et les ViewSets AO étaient gardés par le
grossier ``IsResponsableOrAdmin`` — tout le palier Responsable voyait
l'intégralité d'un dossier d'appel d'offres.

Invariants verrouillés ici :
  1. les 3 codes existent au catalogue ``roles.ALL_PERMISSIONS`` ;
  2. ``ao_rentabilite_voir`` est ÉLEVÉE (octroi réservé à l'administrateur) ;
  3. aucun des 3 codes n'est mappé sur un rôle Responsable / Commercial /
     Technicien / Utilisateur — seuls Directeur et Administrateur les portent ;
  4. ``CanViewAoRentabilite`` refuse tout le monde sauf le porteur explicite
     (et le superuser), SANS repli légacy ;
  5. le serializer ``roles`` refuse l'octroi de ``ao_rentabilite_voir`` par un
     non-administrateur.

Run :
    python manage.py test apps.ao.tests.test_permissions_ao -v2
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory

from apps.ao.permissions import (
    AO_GERER, AO_RENTABILITE_VOIR, AO_VOIR, CanViewAoRentabilite,
)
from apps.roles import models as roles_models
from apps.roles.models import (
    ADMIN_PERMISSIONS, ALL_PERMISSIONS, COMMERCIAL_PERMISSIONS,
    COMMERCIAL_RESP_PERMISSIONS, DIRECTEUR_PERMISSIONS, ELEVATED_PERMISSIONS,
    RESPONSABLE_PERMISSIONS, Role, TECHNICIEN_PERMISSIONS,
    TECHNICIEN_RESP_PERMISSIONS, UTILISATEUR_PERMISSIONS,
)
from apps.roles.serializers import RoleSerializer
from authentication.models import Company

User = get_user_model()

CODES_AO = [AO_VOIR, AO_GERER, AO_RENTABILITE_VOIR]

LISTES_NON_DIRECTION = {
    'RESPONSABLE_PERMISSIONS': RESPONSABLE_PERMISSIONS,
    'COMMERCIAL_RESP_PERMISSIONS': COMMERCIAL_RESP_PERMISSIONS,
    'COMMERCIAL_PERMISSIONS': COMMERCIAL_PERMISSIONS,
    'TECHNICIEN_RESP_PERMISSIONS': TECHNICIEN_RESP_PERMISSIONS,
    'TECHNICIEN_PERMISSIONS': TECHNICIEN_PERMISSIONS,
    'UTILISATEUR_PERMISSIONS': UTILISATEUR_PERMISSIONS,
}


class TestCatalogueAO(SimpleTestCase):
    def test_les_trois_codes_sont_au_catalogue(self):
        for code in CODES_AO:
            self.assertIn(code, ALL_PERMISSIONS, code)

    def test_rentabilite_est_elevee(self):
        self.assertIn(AO_RENTABILITE_VOIR, ELEVATED_PERMISSIONS)

    def test_lecture_et_gestion_ne_sont_pas_elevees(self):
        """Élever ``ao_voir``/``ao_gerer`` empêcherait un admin de déléguer."""
        self.assertNotIn(AO_VOIR, ELEVATED_PERMISSIONS)
        self.assertNotIn(AO_GERER, ELEVATED_PERMISSIONS)

    def test_aucun_role_non_direction_ne_porte_les_codes_ao(self):
        for nom, liste in LISTES_NON_DIRECTION.items():
            for code in CODES_AO:
                self.assertNotIn(code, liste, f'{code} ne doit PAS être dans {nom}')

    def test_directeur_et_admin_les_portent_par_heritage(self):
        for code in CODES_AO:
            self.assertIn(code, DIRECTEUR_PERMISSIONS, code)
            self.assertIn(code, ADMIN_PERMISSIONS, code)

    def test_aucun_acces_elargi_pour_directeur_admin(self):
        """Directeur/Admin gagnent EXACTEMENT les 3 codes AO, rien d'autre."""
        attendu = set(ALL_PERMISSIONS) - {
            roles_models.SCOPE_TEAM, roles_models.SCOPE_SUBTREE}
        self.assertEqual(set(DIRECTEUR_PERMISSIONS), attendu)
        self.assertEqual(
            set(ADMIN_PERMISSIONS),
            attendu - {'journal_activite_voir', 'stock_creer'})


class TestCanViewAoRentabilite(TestCase):
    """La garde des endpoints d'économie AO — sans repli légacy."""

    def setUp(self):
        self.company = Company.objects.create(nom='AOF2 Co', slug='aof2-co')
        self.factory = APIRequestFactory()

    def _autorise(self, user):
        request = self.factory.get('/api/django/ao/economies/')
        request.user = user
        return CanViewAoRentabilite().has_permission(request, view=None)

    def _user(self, username, permissions=None, **kwargs):
        role = None
        if permissions is not None:
            role = Role.objects.create(
                company=self.company, nom=f'Role {username}',
                permissions=list(permissions))
        return User.objects.create_user(
            username=username, password='x', company=self.company, role=role,
            **kwargs)

    def test_directeur_autorise(self):
        self.assertTrue(self._autorise(
            self._user('aof2_dir', DIRECTEUR_PERMISSIONS)))

    def test_commercial_refuse(self):
        self.assertFalse(self._autorise(
            self._user('aof2_com', COMMERCIAL_PERMISSIONS)))

    def test_technicien_refuse(self):
        self.assertFalse(self._autorise(
            self._user('aof2_tech', TECHNICIEN_PERMISSIONS)))

    def test_responsable_refuse(self):
        self.assertFalse(self._autorise(
            self._user('aof2_resp', RESPONSABLE_PERMISSIONS)))

    def test_compte_legacy_sans_role_fin_refuse(self):
        """PAS de repli historique : le repli rouvrirait la fuite de marge."""
        legacy = self._user('aof2_legacy', None, role_legacy='responsable')
        self.assertIsNone(legacy.role_id)
        self.assertFalse(self._autorise(legacy))

    def test_superuser_autorise(self):
        su = User.objects.create_superuser(
            username='aof2_su', password='x', email='su@example.test')
        self.assertTrue(self._autorise(su))

    def test_anonyme_refuse(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertFalse(self._autorise(AnonymousUser()))


class TestOctroiRentabiliteReserveAdmin(TestCase):
    """Le serializer roles refuse l'octroi de ``ao_rentabilite_voir``."""

    def setUp(self):
        self.company = Company.objects.create(nom='AOF2 Roles', slug='aof2-rol')
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
        self.admin = User.objects.create_user(
            username='aof2_admin', password='x', company=self.company,
            role=self.admin_role, role_legacy='admin')
        self.resp_role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=list(RESPONSABLE_PERMISSIONS))
        self.responsable = User.objects.create_user(
            username='aof2_resp_role', password='x', company=self.company,
            role=self.resp_role)

    def _serializer(self, user, instance, permissions):
        class _Req:
            pass
        req = _Req()
        req.user = user
        return RoleSerializer(
            instance=instance, data={'permissions': permissions},
            partial=True, context={'request': req})

    def test_non_admin_ne_peut_pas_octroyer_la_rentabilite(self):
        cible = Role.objects.create(
            company=self.company, nom='Cible', permissions=[AO_VOIR])
        ser = self._serializer(
            self.responsable, cible, [AO_VOIR, AO_RENTABILITE_VOIR])
        self.assertFalse(ser.is_valid())
        self.assertIn('permissions', ser.errors)

    def test_non_admin_peut_octroyer_lecture_et_gestion(self):
        cible = Role.objects.create(
            company=self.company, nom='Cible2', permissions=[])
        ser = self._serializer(self.responsable, cible, [AO_VOIR, AO_GERER])
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_admin_peut_octroyer_la_rentabilite(self):
        cible = Role.objects.create(
            company=self.company, nom='Cible3', permissions=[])
        ser = self._serializer(self.admin, cible, [AO_RENTABILITE_VOIR])
        self.assertTrue(ser.is_valid(), ser.errors)

"""AOF3 — ``AoBaseViewSet`` : socle conforme + rebasement des 8 ViewSets.

Avant AOF3, les 8 ViewSets AO héritaient de ``_ComptaBaseViewSet``
(``TenantMixin`` + ``ModelViewSet`` + ``IsResponsableOrAdmin``) : d'une part
``scripts/check_platform.py`` (SCA4) refuse tout NOUVEAU ``ModelViewSet`` non
basé sur ``CompanyScopedModelViewSet``, d'autre part TOUT le palier Responsable
voyait l'intégralité d'un dossier d'appel d'offres.

Invariants verrouillés ici :
  1. les 8 ViewSets héritent d'``AoBaseViewSet`` → ``CompanyScopedModelViewSet``
     (donc ``TenantMixin`` : découverte AUTOMATIQUE par le sweep d'isolation
     multi-tenant) ;
  2. le socle porte ``read_permission='ao_voir'`` / ``write_permission=
     'ao_gerer'`` ;
  3. la garde du domaine (``ScopedPermission``) s'applique AUSSI aux actions de
     chatter héritées de ``records`` — jamais substituée par leur ``IsAnyRole`` ;
  4. matrice d'accès : resserrée pour les rôles non-direction, INCHANGÉE pour
     Directeur/Administrateur et pour les comptes légacy sans rôle fin ;
  5. le scan SCA4 de ``check_platform.py`` ne voit plus aucun ViewSet AO non
     basé sur le socle.

Run :
    python manage.py test apps.ao.tests.test_socle_viewset -v2
"""
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import views as ao_views
from apps.ao.permissions import AO_GERER, AO_VOIR
from apps.ao.viewsets import AoBaseViewSet
from apps.roles.models import (
    COMMERCIAL_PERMISSIONS, DIRECTEUR_PERMISSIONS, RESPONSABLE_PERMISSIONS,
    Role, TECHNICIEN_PERMISSIONS,
)
from authentication.models import Company
from core.viewsets import CompanyScopedModelViewSet

User = get_user_model()

VIEWSET_NAMES = [
    'AppelOffreViewSet',
    'BordereauPrixViewSet',
    'LigneBordereauViewSet',
    'CautionSoumissionViewSet',
    'DossierSoumissionViewSet',
    'PieceSoumissionViewSet',
    'EcheanceAOViewSet',
    'ResultatAOViewSet',
]

AO_DIR = Path(__file__).resolve().parent.parent


class TestSocleAoBaseViewSet(SimpleTestCase):
    def test_les_huit_viewsets_sont_au_socle(self):
        for name in VIEWSET_NAMES:
            cls = getattr(ao_views, name)
            self.assertTrue(issubclass(cls, AoBaseViewSet), name)
            self.assertTrue(issubclass(cls, CompanyScopedModelViewSet), name)

    def test_socle_detecte_par_le_sweep_isolation(self):
        """Le sweep YRBAC12 repère un ``TenantMixin`` NOMMÉ dans le MRO."""
        for name in VIEWSET_NAMES:
            cls = getattr(ao_views, name)
            self.assertIn(
                'TenantMixin', {base.__name__ for base in cls.__mro__}, name)

    def test_permissions_fines_portees_par_le_socle(self):
        self.assertEqual(AoBaseViewSet.read_permission, AO_VOIR)
        self.assertEqual(AoBaseViewSet.write_permission, AO_GERER)
        for name in VIEWSET_NAMES:
            cls = getattr(ao_views, name)
            self.assertEqual(cls.read_permission, AO_VOIR, name)
            self.assertEqual(cls.write_permission, AO_GERER, name)

    def test_chatter_generique_branche(self):
        """Chatter = ``records`` (ARC8), jamais une classe ``*Activity``."""
        for name in VIEWSET_NAMES:
            cls = getattr(ao_views, name)
            self.assertTrue(hasattr(cls, 'chatter_historique'), name)
            self.assertTrue(hasattr(cls, 'chatter_noter'), name)

    def test_scan_sca4_vert_sur_le_module_ao(self):
        from apps.records.platform_guards import (
            new_unscoped_viewsets, scan_unscoped_viewsets,
        )
        for fichier in ('views.py', 'viewsets.py'):
            texte = (AO_DIR / fichier).read_text(encoding='utf-8')
            trouve = scan_unscoped_viewsets('ao', texte)
            self.assertEqual(new_unscoped_viewsets(trouve), [], fichier)


class TestMatriceAccesAO(TestCase):
    """Matrice 403/200 sur ``/api/django/ao/appels-offres/``."""

    URL = '/api/django/ao/appels-offres/'

    def setUp(self):
        self.company = Company.objects.create(nom='AOF3 Co', slug='aof3-co')

    def _api(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _user_avec_role(self, username, permissions):
        role = Role.objects.create(
            company=self.company, nom=f'Role {username}',
            permissions=list(permissions))
        return User.objects.create_user(
            username=username, password='x', company=self.company, role=role)

    def test_commercial_refuse_en_lecture(self):
        user = self._user_avec_role('aof3_com', COMMERCIAL_PERMISSIONS)
        self.assertEqual(self._api(user).get(self.URL).status_code, 403)

    def test_technicien_refuse_en_lecture(self):
        user = self._user_avec_role('aof3_tech', TECHNICIEN_PERMISSIONS)
        self.assertEqual(self._api(user).get(self.URL).status_code, 403)

    def test_responsable_refuse_en_lecture(self):
        user = self._user_avec_role('aof3_resp', RESPONSABLE_PERMISSIONS)
        self.assertEqual(self._api(user).get(self.URL).status_code, 403)

    def test_directeur_autorise_en_lecture_et_ecriture(self):
        user = self._user_avec_role('aof3_dir', DIRECTEUR_PERMISSIONS)
        api = self._api(user)
        self.assertEqual(api.get(self.URL).status_code, 200)
        r = api.post(self.URL, {
            'reference': 'AO-AOF3-01', 'objet': 'Centrale PV',
            'type_marche': 'public',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_role_lecture_seule_ao_voir_ne_peut_pas_ecrire(self):
        user = self._user_avec_role('aof3_lecteur', [AO_VOIR])
        api = self._api(user)
        self.assertEqual(api.get(self.URL).status_code, 200)
        r = api.post(self.URL, {
            'reference': 'AO-AOF3-02', 'objet': 'Refusé',
            'type_marche': 'public',
        }, format='json')
        self.assertEqual(r.status_code, 403)

    def test_compte_legacy_sans_role_fin_inchange(self):
        """Repli historique : aucun accès retiré aux comptes hérités."""
        legacy = User.objects.create_user(
            username='aof3_legacy', password='x', company=self.company,
            role_legacy='responsable')
        self.assertEqual(self._api(legacy).get(self.URL).status_code, 200)

    def test_chatter_reste_garde_par_le_domaine(self):
        """Un Commercial ne lit PAS la timeline d'un AO qu'il ne voit pas."""
        from apps.ao.models import AppelOffre
        ao = AppelOffre.objects.create(
            company=self.company, reference='AO-AOF3-03', objet='Chatter')
        commercial = self._user_avec_role('aof3_com2', COMMERCIAL_PERMISSIONS)
        url = f'{self.URL}{ao.id}/chatter/historique/'
        self.assertEqual(self._api(commercial).get(url).status_code, 403)
        directeur = self._user_avec_role('aof3_dir2', DIRECTEUR_PERMISSIONS)
        self.assertEqual(self._api(directeur).get(url).status_code, 200)

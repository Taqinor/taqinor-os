"""NTI18N40 — permission fine ``localisation_gerer``.

Ce qui est vérifié : le code existe au catalogue (sans quoi Directeur/Admin,
qui en DÉRIVENT, ne le porteraient pas et les écrans répondraient 403 à tout
le monde — le défaut WIR169), aucun accès existant n'est retiré, et un rôle
personnalisé qui garde ``parametres_modifier`` mais PERD
``localisation_gerer`` reçoit bien 403 sur les endpoints de localisation et de
traduction.

Run :
    python manage.py test \
        apps.parametres.tests_nti18n40_permission_localisation -v 2
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres.localisation import (
    PERMISSION_LOCALISATION_GERER,
    peut_gerer_localisation,
)
from apps.roles.models import (
    ADMIN_PERMISSIONS,
    ALL_PERMISSIONS,
    DIRECTEUR_PERMISSIONS,
    RESPONSABLE_PERMISSIONS,
    Role,
)
from authentication.models import Company

User = get_user_model()

TRADUCTIONS = '/api/django/parametres/traductions/'
ONBOARDING = '/api/django/parametres/onboarding-localisation/'
FETES = '/api/django/parametres/fetes-mobiles/'
FETES_ENREGISTRER = '/api/django/parametres/fetes-mobiles/enregistrer/'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CatalogueTests(SimpleTestCase):
    def test_le_code_est_au_catalogue(self):
        self.assertIn(PERMISSION_LOCALISATION_GERER, ALL_PERMISSIONS)

    def test_forme_underscore_jamais_pointee(self):
        """Un code pointé ne matche jamais ``Role.permissions`` : la garde
        serait silencieusement inerte (défaut mesuré par WIR11)."""
        self.assertNotIn('.', PERMISSION_LOCALISATION_GERER)
        self.assertTrue(PERMISSION_LOCALISATION_GERER.endswith('_gerer'))

    def test_distinct_de_parametres_modifier(self):
        self.assertNotEqual(PERMISSION_LOCALISATION_GERER,
                            'parametres_modifier')
        self.assertIn('parametres_modifier', ALL_PERMISSIONS)

    def test_direction_et_responsable_le_portent(self):
        """Aucun accès existant retiré : les trois paliers qui écrivaient déjà
        ces écrans portent le code."""
        for jeu in (DIRECTEUR_PERMISSIONS, ADMIN_PERMISSIONS,
                    RESPONSABLE_PERMISSIONS):
            self.assertIn(PERMISSION_LOCALISATION_GERER, jeu)

    def test_catalogue_sans_doublon(self):
        self.assertEqual(len(ALL_PERMISSIONS), len(set(ALL_PERMISSIONS)))


class HelperTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='NTI18N40 Co', slug='nti18n40-co')

    def test_compte_herite_sans_role_fin_garde_son_comportement(self):
        herite = User.objects.create_user(
            username='nti18n40-herite', password='x', role_legacy='admin',
            company=self.company)
        self.assertTrue(peut_gerer_localisation(herite))

    def test_role_fin_sans_le_code_refuse(self):
        role = Role.objects.create(
            company=self.company, nom='Relecture compta',
            permissions=['parametres_voir', 'parametres_modifier'])
        user = User.objects.create_user(
            username='nti18n40-sans', password='x', role_legacy='admin',
            company=self.company, role=role)
        self.assertFalse(peut_gerer_localisation(user))

    def test_role_fin_avec_le_code_accepte(self):
        role = Role.objects.create(
            company=self.company, nom='Relecture linguistique',
            permissions=['parametres_voir', PERMISSION_LOCALISATION_GERER])
        user = User.objects.create_user(
            username='nti18n40-avec', password='x', role_legacy='admin',
            company=self.company, role=role)
        self.assertTrue(peut_gerer_localisation(user))

    def test_utilisateur_absent_refuse(self):
        self.assertFalse(peut_gerer_localisation(None))


class EndpointsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='NTI18N40 Endpoints', slug='nti18n40-endpoints')
        # Rôle qui garde TOUS les paramètres SAUF la localisation : le cas que
        # la tâche veut rendre possible. Base = ``DIRECTEUR_PERMISSIONS`` (donc
        # sans les marqueurs de portée d'enregistrements, hors sujet ici) : le
        # palier de menu reste 'admin' et la SEULE différence entre les deux
        # rôles est le code de localisation.
        self.role_sans = Role.objects.create(
            company=self.company, nom='Paramètres sans localisation',
            permissions=[c for c in DIRECTEUR_PERMISSIONS
                         if c != PERMISSION_LOCALISATION_GERER])
        self.sans = User.objects.create_user(
            username='nti18n40-ep-sans', password='x', role_legacy='admin',
            company=self.company, role=self.role_sans)
        self.role_avec = Role.objects.create(
            company=self.company, nom='Paramètres avec localisation',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.avec = User.objects.create_user(
            username='nti18n40-ep-avec', password='x', role_legacy='admin',
            company=self.company, role=self.role_avec)

    def test_ecriture_traduction_refusee_sans_le_code(self):
        resp = _auth(self.sans).post(
            TRADUCTIONS, {'locale': 'ar', 'key': 'nav.stock',
                          'value': 'مخزون'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_ecriture_traduction_autorisee_avec_le_code(self):
        resp = _auth(self.avec).post(
            TRADUCTIONS, {'locale': 'ar', 'key': 'nav.stock',
                          'value': 'مخزون'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_lecture_traduction_reste_ouverte_sans_le_code(self):
        """``list`` est chargée AU LOGIN par tous les rôles pour fusionner les
        surcharges : la borner afficherait une interface non traduite."""
        resp = _auth(self.sans).get(TRADUCTIONS)
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_onboarding_localisation_refuse_sans_le_code(self):
        resp = _auth(self.sans).post(ONBOARDING, {}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_fetes_mobiles_ecriture_refusee_sans_le_code(self):
        # L'écriture vit sur fetes-mobiles/enregistrer/ (POST) ; fetes-mobiles/
        # ne route que le GET (fetes_mobiles_etat) — y POSTer répond 405, pas
        # 403, et ne prouve rien sur la garde de permission.
        resp = _auth(self.sans).post(
            FETES_ENREGISTRER, {'annee': 2030, 'dates': {}}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_fetes_mobiles_lecture_reste_ouverte_sans_le_code(self):
        resp = _auth(self.sans).get(FETES, {'annee': 2030})
        self.assertEqual(resp.status_code, 200, resp.content)

"""NTEXT9 — permissions de champ par rôle (visible/éditable).

``FieldRolePermission`` (company, field_def, role_tier, niveau) : un champ
``masque`` pour un palier n'apparaît JAMAIS dans le formulaire de ce palier
(mais reste visible pour les autres) ; un champ ``lecture`` reste présent
mais marqué lecture-seule. Sans ligne pour un couple (champ, palier), le
comportement reste inchangé (tout visible/éditable).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.customfields.models import (
    CustomFieldDef, CustomObjectDef, FieldRolePermission,
)
from apps.customfields.services import niveau_pour_role

User = get_user_model()

DEFINITIONS = '/api/django/custom-fields/definitions/'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NiveauPourRoleTests(TestCase):
    """La fonction pure : défaut EDITION sans ligne, sinon la ligne fait foi."""

    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT9 Co')
        self.champ = CustomFieldDef.objects.create(
            company=self.company, module='lead', code='budget',
            libelle='Budget', type='number')

    def test_sans_ligne_edition_par_defaut(self):
        self.assertEqual(
            niveau_pour_role(self.champ, 'normal'),
            FieldRolePermission.Niveau.EDITION)

    def test_sans_role_tier_edition(self):
        self.assertEqual(
            niveau_pour_role(self.champ, ''),
            FieldRolePermission.Niveau.EDITION)

    def test_ligne_masque_fait_foi(self):
        FieldRolePermission.objects.create(
            company=self.company, field_def=self.champ, role_tier='normal',
            niveau=FieldRolePermission.Niveau.MASQUE)
        self.assertEqual(
            niveau_pour_role(self.champ, 'normal'),
            FieldRolePermission.Niveau.MASQUE)
        # Un AUTRE palier n'est pas affecté par la ligne.
        self.assertEqual(
            niveau_pour_role(self.champ, 'admin'),
            FieldRolePermission.Niveau.EDITION)


class ListeDefinitionsMasqueeTests(TestCase):
    """Bout en bout : un champ masqué pour Commercial (palier 'normal')
    n'apparaît pas dans la liste des définitions pour lui, mais reste visible
    pour Directeur (palier 'admin')."""

    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT9 Liste Co')
        self.commercial = User.objects.create_user(
            username='ntext9_commercial', password='x',
            role_legacy='normal', company=self.company)
        self.directeur = User.objects.create_user(
            username='ntext9_directeur', password='x',
            role_legacy='admin', company=self.company)
        self.champ_sensible = CustomFieldDef.objects.create(
            company=self.company, module='lead', code='marge_cible',
            libelle='Marge cible', type='number')
        self.champ_normal = CustomFieldDef.objects.create(
            company=self.company, module='lead', code='origine',
            libelle='Origine', type='text')
        FieldRolePermission.objects.create(
            company=self.company, field_def=self.champ_sensible,
            role_tier='normal', niveau=FieldRolePermission.Niveau.MASQUE)

    def test_champ_masque_absent_pour_le_palier_normal(self):
        api = _auth(self.commercial)
        res = api.get(f'{DEFINITIONS}?module=lead')
        self.assertEqual(res.status_code, 200, res.data)
        codes = [c['code'] for c in res.data['results']] \
            if isinstance(res.data, dict) and 'results' in res.data \
            else [c['code'] for c in res.data]
        self.assertNotIn('marge_cible', codes)
        self.assertIn('origine', codes)

    def test_champ_masque_reste_visible_pour_le_palier_admin(self):
        api = _auth(self.directeur)
        res = api.get(f'{DEFINITIONS}?module=lead')
        self.assertEqual(res.status_code, 200, res.data)
        codes = [c['code'] for c in res.data['results']] \
            if isinstance(res.data, dict) and 'results' in res.data \
            else [c['code'] for c in res.data]
        self.assertIn('marge_cible', codes)

    def test_champ_non_masque_porte_niveau_role_edition(self):
        api = _auth(self.commercial)
        res = api.get(f'{DEFINITIONS}?module=lead')
        origine = next(c for c in (
            res.data['results'] if isinstance(res.data, dict)
            else res.data) if c['code'] == 'origine')
        self.assertEqual(origine['niveau_role'], 'edition')


class VueFormulaireObjetCustomTests(TestCase):
    """Même règle pour un OBJET personnalisé (NTEXT3's vue-formulaire)."""

    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT9 Objet Co')
        self.commercial = User.objects.create_user(
            username='ntext9obj_commercial', password='x',
            role_legacy='normal', company=self.company)
        self.objet = CustomObjectDef.objects.create(
            company=self.company, code='intervention', libelle='Intervention')
        self.champ_lecture = CustomFieldDef.objects.create(
            company=self.company, module=self.objet.field_module,
            code='cout_interne', libelle='Coût interne', type='number')
        FieldRolePermission.objects.create(
            company=self.company, field_def=self.champ_lecture,
            role_tier='normal', niveau=FieldRolePermission.Niveau.LECTURE)

    def test_champ_lecture_reste_present_marque_lecture_seule(self):
        api = _auth(self.commercial)
        res = api.get(
            '/api/django/custom-fields/custom-objects/intervention/'
            'vue-formulaire/')
        self.assertEqual(res.status_code, 200, res.data)
        champ = next(c for c in res.data['champs']
                     if c['code'] == 'cout_interne')
        self.assertTrue(champ['lecture_seule_role'])

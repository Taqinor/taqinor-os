"""ASEC31 — toute écriture des réglages de la société exige
``parametres_modifier`` (D-ASEC-4, D-ASEC-5).

Constat C-ASEC-015 : Admin RH et Technicien responsable (palier
« responsable ») modifiaient le RIB/ICE, le logo, les tarifs et les modèles
de documents, alors que le registre des droits dit que les réglages de la
société restent hors de leur portée. Attendu : seuls les rôles portant
``parametres_modifier`` écrivent (200) ; les autres → 403 sans écriture ; la
lecture reste ouverte.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres.models_company import CompanyProfile
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    ADMIN_PERMISSIONS, ADMIN_RH_PERMISSIONS, COMMERCIAL_RESP_PERMISSIONS,
    DIRECTEUR_PERMISSIONS, TECHNICIEN_RESP_PERMISSIONS,
)
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/parametres/'
ROLES = {
    'Directeur': DIRECTEUR_PERMISSIONS,
    'Administrateur': ADMIN_PERMISSIONS,
    'Admin RH': ADMIN_RH_PERMISSIONS,
    'Technicien responsable': TECHNICIEN_RESP_PERMISSIONS,
    'Commercial responsable': COMMERCIAL_RESP_PERMISSIONS,
}
AUTORISES = {'Directeur', 'Administrateur'}
RIB_INITIAL = '011780000012345678901234'


class ParametresModifierTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASEC31 Co', slug='asec31-co')
        self.users = {}
        for i, (nom, perms) in enumerate(ROLES.items()):
            role = Role.objects.create(
                company=self.company, nom=nom, permissions=list(perms),
                est_systeme=True)
            self.users[nom] = User.objects.create_user(
                username=f'asec31_u{i}', password='x', role=role,
                company=self.company)
        self.profile = CompanyProfile.get(company=self.company)
        self.profile.rib = RIB_INITIAL
        self.profile.save()

    def _api(self, nom):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(
            self.users[nom]))
        return api

    def test_registre_directeur_admin_portent_le_code(self):
        self.assertIn('parametres_modifier', DIRECTEUR_PERMISSIONS)
        self.assertIn('parametres_modifier', ADMIN_PERMISSIONS)
        for nom in set(ROLES) - AUTORISES:
            self.assertNotIn('parametres_modifier', ROLES[nom], nom)

    def test_profil_rib_ice(self):
        for nom in ROLES:
            r = self._api(nom).patch(
                f'{BASE}update/', {'rib': '999', 'ice': '000000000000001'},
                format='json')
            self.profile.refresh_from_db()
            if nom in AUTORISES:
                self.assertEqual(r.status_code, 200, (nom, r.data))
                self.profile.rib = RIB_INITIAL
                self.profile.save()
            else:
                self.assertEqual(r.status_code, 403, (nom, r.data))
                self.assertEqual(self.profile.rib, RIB_INITIAL, nom)

    def test_televersement_logo_refuse(self):
        for nom in set(ROLES) - AUTORISES:
            fichier = SimpleUploadedFile(
                'logo.png', b'\x89PNG\r\n\x1a\n' + b'0' * 32,
                content_type='image/png')
            r = self._api(nom).post(f'{BASE}upload-logo/', {'file': fichier},
                                    format='multipart')
            self.assertEqual(r.status_code, 403, nom)
            r2 = self._api(nom).delete(f'{BASE}delete-logo/')
            self.assertEqual(r2.status_code, 403, nom)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.logo_key)

    def test_tarifs_et_modeles(self):
        for nom in ROLES:
            api = self._api(nom)
            r_tarif = api.patch(f'{BASE}tarification/update/', {},
                                format='json')
            r_doc = api.patch(f'{BASE}document-templates/update/', {},
                              format='json')
            attendu = 200 if nom in AUTORISES else 403
            self.assertEqual(r_tarif.status_code, attendu, (nom, r_tarif.data))
            self.assertEqual(r_doc.status_code, attendu, (nom, r_doc.data))

    def test_lecture_inchangee(self):
        for nom in ROLES:
            api = self._api(nom)
            self.assertEqual(api.get(BASE).status_code, 200, nom)
            self.assertEqual(api.get(f'{BASE}tarification/').status_code,
                             200, nom)

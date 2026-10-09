"""ACHT55 (C-ACHT-054) — fini les gardes inline `request.user.is_responsable`
(vrai dès qu'UN code d'écriture existe dans n'importe quel module) : les POST
`recette-pompage`, `recette`, `reserves`, `pack-remise` passent par
`get_permissions` (lecture IsAnyRole, écriture IsResponsableOrAdmin résolu au
module installations) et le palier « responsable » de l'approbation BCF exige
`achats_commander`.

Rejoue CTEN-6 : Admin RH -> RESERVES 201, RECETTE 201, PACK 201, APPROUVER BCF
200.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht55_gardes_inline"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    ApprobationBCF, HandoverPack, Installation, Reserve, SeuilApprobationBCF,
)
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    ADMIN_RH_PERMISSIONS, COMMERCIAL_TERRAIN_PERMISSIONS,
    RESPONSABLE_PERMISSIONS,
)
from apps.stock.models import BonCommandeFournisseur, Fournisseur

User = get_user_model()
BASE = '/api/django/installations'


class GardesInlineTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACHT55', slug='acht55-co')

        def _user(nom, perms):
            role = Role.objects.create(
                company=self.company, nom=nom, permissions=list(perms))
            return User.objects.create_user(
                username=f'{nom.lower().replace(" ", "-")}-acht55',
                password='x', company=self.company, role=role)

        self.rh = _user('Admin RH', ADMIN_RH_PERMISSIONS)
        self.terrain = _user('Commercial terrain',
                             COMMERCIAL_TERRAIN_PERMISSIONS)
        self.resp = _user('Responsable', RESPONSABLE_PERMISSIONS)
        self.chantier = Installation.objects.create(
            company=self.company, reference='CH-ACHT55')
        self.agricole = Installation.objects.create(
            company=self.company, reference='CH-ACHT55-AGR',
            type_installation=Installation.TypeInstallation.AGRICOLE)
        SeuilApprobationBCF.objects.create(
            company=self.company, seuil_responsable=Decimal('1000000000'),
            actif=True)
        four = Fournisseur.objects.create(company=self.company, nom='Four')
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ACHT55', fournisseur=four)

    def _api(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_roles_sans_droit_installations_refuses(self):
        for user in (self.rh, self.terrain):
            api = self._api(user)
            for url, corps in (
                    (f'{BASE}/chantiers/{self.chantier.id}/reserves/',
                     {'description': 'Fissure', 'bloquante': True}),
                    (f'{BASE}/chantiers/{self.chantier.id}/recette/', {}),
                    (f'{BASE}/chantiers/{self.chantier.id}/pack-remise/', {}),
                    (f'{BASE}/chantiers/{self.agricole.id}/recette-pompage/',
                     {})):
                r = api.post(url, corps, format='json')
                self.assertEqual(r.status_code, 403, (user.username, url))
        self.assertEqual(Reserve.objects.filter(
            company=self.company).count(), 0)
        self.assertEqual(HandoverPack.objects.filter(
            company=self.company).count(), 0)

    def test_approbation_bcf_palier_responsable_refuse(self):
        r = self._api(self.rh).post(
            f'{BASE}/approbations-bcf/approuver/', {'bcf': self.bcf.id},
            format='json')
        self.assertEqual(r.status_code, 403, r.data)
        self.assertEqual(ApprobationBCF.objects.filter(
            company=self.company).count(), 0)

    def test_responsable_chantier_inchange(self):
        api = self._api(self.resp)
        r = api.post(f'{BASE}/chantiers/{self.chantier.id}/reserves/',
                     {'description': 'Fissure', 'bloquante': True},
                     format='json')
        self.assertEqual(r.status_code, 201, r.data)
        r = api.get(f'{BASE}/chantiers/{self.chantier.id}/reserves/')
        self.assertEqual(r.status_code, 200)
        r = api.get(f'{BASE}/chantiers/{self.chantier.id}/pack-remise/')
        self.assertEqual(r.status_code, 200)

"""NTLOG43 — permissions par rôle, module douane (volet EXPORT seulement ;
le volet import/BaremeDouanier suivra NTLOG10, BLOCKED — voir
``apps/douane/apps.py``).

Couvre le critère d'acceptation adapté à ce qui existe réellement dans cette
app : un utilisateur du rôle ``comptabilite`` reçoit 403 sur
``PATCH /dossiers-export/{id}/`` mais 200 sur ``GET /dossiers-export/``. Un
utilisateur ``douane_responsable`` (ou le repli legacy superuser/palier
historique) garde l'écriture.

Run :
    python manage.py test apps.douane.tests.test_ntlog43_permissions -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.douane.models import DossierExport
from apps.douane.permissions import DOUANE_COMPTABILITE_VOIR, DOUANE_RESPONSABLE

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/douane'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntlog43-co-{n}', defaults={'nom': f'NTLOG43 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_role_user(company, permissions, role_legacy='normal'):
    """Utilisateur porteur d'un ``Role`` FIN avec exactement ces permissions
    (jamais le repli legacy : ``role_legacy='normal'`` par défaut, pour
    isoler strictement l'effet du code de permission testé)."""
    from apps.roles.models import Role
    role = Role.objects.create(
        company=company, nom=f'role-{next(_seq)}', permissions=permissions)
    return User.objects.create_user(
        username=f'ntlog43-{next(_seq)}', password='x',
        role_legacy=role_legacy, company=company, role=role)


def make_legacy_user(company, role_legacy):
    return User.objects.create_user(
        username=f'ntlog43-legacy-{next(_seq)}', password='x',
        role_legacy=role_legacy, company=company)


class TestPermissionsResponsableDouane(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_douane_responsable_ecrit(self):
        user = make_role_user(self.company, [DOUANE_RESPONSABLE])
        api = auth(user)
        r = api.post(f'{BASE}/dossiers-export/', {'incoterm': 'fob'})
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)

        dossier_id = r.data['id']
        r2 = api.patch(f'{BASE}/dossiers-export/{dossier_id}/', {'note': 'maj'})
        self.assertEqual(r2.status_code, status.HTTP_200_OK, r2.data)

    def test_legacy_responsable_garde_ecriture_repli(self):
        # Compte hérité SANS rôle fin, palier historique Responsable — la
        # docstring de core.permissions._user_has_or_legacy garantit qu'on ne
        # retire jamais cet accès existant.
        user = make_legacy_user(self.company, 'responsable')
        api = auth(user)
        r = api.post(f'{BASE}/dossiers-export/', {})
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)


class TestPermissionsComptabilite(TestCase):
    """Critère d'acceptation NTLOG43 (adapté export) : comptabilite -> 403
    PATCH, 200 GET."""

    def setUp(self):
        self.company = make_company()
        self.user = make_role_user(self.company, [DOUANE_COMPTABILITE_VOIR])
        self.api = auth(self.user)
        self.dossier = DossierExport.objects.create(
            company=self.company, numero='EXP-PERM-TEST')

    def test_get_autorise(self):
        r = self.api.get(f'{BASE}/dossiers-export/')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

    def test_patch_refuse(self):
        r = self.api.patch(
            f'{BASE}/dossiers-export/{self.dossier.id}/', {'note': 'x'})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, r.data)

    def test_post_refuse(self):
        r = self.api.post(f'{BASE}/dossiers-export/', {})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, r.data)

    def test_pieces_ecriture_refusee_aussi(self):
        r = self.api.post(f'{BASE}/dossiers-export-pieces/', {
            'dossier': self.dossier.id, 'type_piece': 'eur1',
        })
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, r.data)


class TestPermissionsCompteFinSansCode(TestCase):
    """Un rôle FIN qui ne porte NI douane_responsable NI aucun autre droit
    d'écriture ne doit PAS écrire (motif core.permissions._user_has_or_legacy :
    un compte avec rôle fin passe par has_erp_permission(code) SANS repli
    is_responsable)."""

    def test_role_fin_vide_refuse_ecriture(self):
        company = make_company()
        user = make_role_user(company, [])
        api = auth(user)
        r = api.post(f'{BASE}/dossiers-export/', {})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, r.data)

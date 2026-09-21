"""NTASS29 — Permissions RBAC dédiées assurances (garde des viewsets).

Critère d'acceptation : un utilisateur porteur d'un rôle FIN sans
``assurances_voir`` n'accède PAS à ``/assurances`` ; un Directeur/Admin (ou
superuser, qui hérite de tout) y accède ; un Commercial voit en lecture seule
si ``assurances_voir`` lui est accordé explicitement mais reste BLOQUÉ en
écriture sans ``assurances_gerer``.

NB (périmètre) : l'ENREGISTREMENT des codes dans le référentiel
``roles.permissions-disponibles`` (``roles.ALL_PERMISSIONS``) exige une écriture
hors périmètre FINANCE (``apps/roles``) et est laissé au run plateforme. Ce test
vérifie que les VIEWSETS de ``apps.assurances`` sont bien gardés par ces codes
via ``HasPermissionOrLegacy``/``ScopedPermission`` — ce qui est entièrement dans
le périmètre et ne dépend pas de la présence du code au catalogue."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.assurances.models import Assureur, PoliceAssurance

User = get_user_model()

BASE = '/api/django/assurances/polices/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_role_fk_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AssurancesRbacTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p29', 'P29')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='DEC-2026-090',
            type_police=PoliceAssurance.TypePolice.DECENNALE,
            date_effet=today, date_echeance=today + datetime.timedelta(days=365))

    def test_role_fin_sans_permission_est_refuse(self):
        # Un « Technicien » : rôle fin SANS assurances_voir → 403.
        tech = make_role_fk_user(self.company, 'tech', ['sav_voir'])
        resp = auth(tech).get(BASE)
        self.assertEqual(resp.status_code, 403)

    def test_role_avec_assurances_voir_lit_seulement(self):
        # Un « Commercial » avec assurances_voir explicite → lecture OK…
        commercial = make_role_fk_user(
            self.company, 'commercial', ['assurances_voir'])
        api = auth(commercial)
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 200)
        # …mais écriture REFUSÉE sans assurances_gerer.
        resp = api.post(BASE, {
            'assureur': self.assureur.id,
            'numero_police': 'DEC-2026-091',
            'type_police': PoliceAssurance.TypePolice.DECENNALE,
            'date_effet': datetime.date.today().isoformat(),
            'date_echeance': (
                datetime.date.today() + datetime.timedelta(days=365)).isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_role_avec_gerer_peut_ecrire(self):
        gestionnaire = make_role_fk_user(
            self.company, 'gestion', ['assurances_voir', 'assurances_gerer'])
        resp = auth(gestionnaire).post(BASE, {
            'assureur': self.assureur.id,
            'numero_police': 'DEC-2026-092',
            'type_police': PoliceAssurance.TypePolice.DECENNALE,
            'date_effet': datetime.date.today().isoformat(),
            'date_echeance': (
                datetime.date.today() + datetime.timedelta(days=365)).isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_superuser_acces_complet(self):
        su = User.objects.create_user(
            username='dir', password='x', company=self.company,
            is_superuser=True, is_staff=True)
        resp = auth(su).get(BASE)
        self.assertEqual(resp.status_code, 200)

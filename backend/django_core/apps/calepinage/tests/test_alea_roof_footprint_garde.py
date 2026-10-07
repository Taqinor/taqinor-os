"""ALEA38 — ``GET crm/leads/<id>/roof-footprint/`` gardée comme la fiche lead.

Constat C-ALEA-013 (sonde V4 LCOUT-3) : la route n'exigeait que
``IsAuthenticated`` — un compte portail ou un Commercial terrain (sans
``crm_voir``) obtenait 400/404 selon l'existence du lead (oracle d'existence),
et un lead hors portée déclenchait un appel Overpass. La vue, les permissions
et la portée sont RÉELLES ; la seule doublure est le client HTTP sortant
(``requests.post``, frontière réseau externe).
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    COMMERCIAL_PERMISSIONS, COMMERCIAL_TERRAIN_PERMISSIONS,
    PORTAIL_CLIENT_PERMISSIONS,
)

User = get_user_model()

POINT = {'lat': 33.5731, 'lng': -7.5898}
ABSENT = 99999999


def _url(lead_id):
    return f'/api/django/crm/leads/{lead_id}/roof-footprint/'


class RoofFootprintGardeTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor ALEA38', slug='taqinor-alea38')

        def _role(nom, perms):
            return Role.objects.create(
                company=self.company, nom=nom, permissions=list(perms))

        commercial = _role('Commercial', COMMERCIAL_PERMISSIONS)
        self.proprietaire = User.objects.create_user(
            username='alea38-proprio', password='x', company=self.company,
            role=commercial)
        self.hors_portee = User.objects.create_user(
            username='alea38-autre', password='x', company=self.company,
            role=commercial)
        self.terrain = User.objects.create_user(
            username='alea38-terrain', password='x', company=self.company,
            role=_role('Commercial terrain', COMMERCIAL_TERRAIN_PERMISSIONS))
        self.portail = User.objects.create_user(
            username='alea38-portail', password='x', company=self.company,
            role=_role('Portail client', PORTAIL_CLIENT_PERMISSIONS),
            portee=User.PORTEE_PORTAIL_CLIENT)
        self.lead = Lead.objects.create(
            company=self.company, nom='Toit ALEA38', roof_point=POINT,
            owner=self.proprietaire)
        self.api = APIClient()

    def _get(self, user, lead_id):
        self.api.force_authenticate(user)
        return self.api.get(_url(lead_id))

    def _reponse_overpass_vide(self):
        reponse = mock.Mock()
        reponse.raise_for_status.return_value = None
        reponse.json.return_value = {'elements': []}
        return reponse

    def test_portail_refuse(self):
        with mock.patch('requests.post') as overpass:
            self.assertEqual(self._get(self.portail, self.lead.pk).status_code,
                             403)
            self.assertEqual(self._get(self.portail, ABSENT).status_code, 403)
        overpass.assert_not_called()

    def test_commercial_terrain_refuse(self):
        with mock.patch('requests.post') as overpass:
            self.assertEqual(
                self._get(self.terrain, self.lead.pk).status_code, 403)
            self.assertEqual(self._get(self.terrain, ABSENT).status_code, 403)
        overpass.assert_not_called()

    def test_hors_portee_comme_absent(self):
        with mock.patch('requests.post') as overpass:
            hors = self._get(self.hors_portee, self.lead.pk)
            absent = self._get(self.hors_portee, ABSENT)
        self.assertEqual(hors.status_code, 404)
        self.assertEqual(absent.status_code, 404)
        self.assertEqual(hors.json(), absent.json())
        overpass.assert_not_called()

    def test_aucun_appel_overpass_si_refuse(self):
        with mock.patch('requests.post') as overpass:
            overpass.return_value = self._reponse_overpass_vide()
            for user in (self.portail, self.terrain, self.hors_portee):
                self._get(user, self.lead.pk)
            overpass.assert_not_called()
            # Dans la portée : comportement actuel — Overpass interrogé, 200.
            ok = self._get(self.proprietaire, self.lead.pk)
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertEqual(ok.json()['polygon'], [])
        overpass.assert_called_once()

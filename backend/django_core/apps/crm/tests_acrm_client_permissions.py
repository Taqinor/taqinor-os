"""ACRM3 (C-ACRM-001) — l'annuaire clients exige un code fin de lecture.

Avant : toutes les lectures de ``ClientViewSet`` et la relance de dormance
étaient ouvertes à « tout rôle authentifié » — le Commercial terrain (app
Visites seule) et l'Admin RH listaient les clients (200), cherchaient des
leads avec leur téléphone, et posaient une note de relance au chatter (201)
(sonde V_VA LVIEW1-1).

Après : lectures = ``crm_voir`` OU le code de lecture d'un module qui consomme
l'annuaire (``sav_voir``, ``installation_voir``) ; relance = ``crm_modifier``.
Le Technicien (``sav_voir`` sans ``crm_voir``) garde la liste et la
recherche, mais l'autocomplete ne lui rend aucun lead. Le Commercial est
inchangé. Après chaque 403, le chatter du lead est intact.

Rôles RÉELS de ``permissions_registre`` ; aucun mock.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client, Lead, LeadActivity
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    ADMIN_RH_PERMISSIONS, COMMERCIAL_PERMISSIONS,
    COMMERCIAL_TERRAIN_PERMISSIONS, TECHNICIEN_PERMISSIONS,
    VIEWER_PERMISSIONS)

User = get_user_model()
BASE = '/api/django/crm/clients/'


class ClientPermissionsTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM3 Solaire', slug='acrm3-clients')
        self.users = {}
        for nom, perms in (
                ('Commercial', COMMERCIAL_PERMISSIONS),
                ('Commercial terrain', COMMERCIAL_TERRAIN_PERMISSIONS),
                ('Admin RH', ADMIN_RH_PERMISSIONS),
                ('Viewer', VIEWER_PERMISSIONS),
                ('Technicien', TECHNICIEN_PERMISSIONS)):
            role = Role.objects.create(
                company=self.company, nom=nom, permissions=list(perms),
                est_systeme=True)
            self.users[nom] = User.objects.create_user(
                username=f'acrm3-{nom.replace(" ", "-").lower()}',
                password='x', company=self.company, role=role)
        self.client_c = Client.objects.create(
            company=self.company, nom='Témoin', prenom='Client',
            telephone='+212661909901', email='temoin-acrm3@example.com')
        # ``societe`` distincte : l'autocomplete déduplique par (nom, ICE)
        # et masquerait sinon le lead derrière le client homonyme — la
        # présence/absence de la source « lead » ne serait plus observable.
        self.lead = Lead.objects.create(
            company=self.company, nom='Témoin', prenom='Lead',
            societe='Témoin Lead SARL',
            telephone='+212661909902', owner=self.users['Commercial'],
            client=self.client_c)
        self.client_v = Client.objects.create(
            company=self.company, nom='Témoin', prenom='Viewer',
            telephone='+212661909903')
        self.lead_v = Lead.objects.create(
            company=self.company, nom='Témoin', prenom='LeadViewer',
            telephone='+212661909904', owner=self.users['Viewer'],
            client=self.client_v)

    def _api(self, nom):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.users[nom])}'))
        return api

    def _lectures(self, api, client_id):
        return {
            'list': api.get(BASE).status_code,
            'retrieve': api.get(f'{BASE}{client_id}/').status_code,
            'search': api.get(f'{BASE}search/', {'q': 'Témoin'}).status_code,
            'documents': api.get(
                f'{BASE}{client_id}/documents/').status_code,
            'dormants': api.get(f'{BASE}dormants/').status_code,
            'mon_portefeuille': api.get(
                f'{BASE}mon-portefeuille/').status_code,
        }

    def _nb_activites(self):
        return LeadActivity.objects.filter(
            lead__in=[self.lead, self.lead_v]).count()

    def test_terrain_et_rh_refuses(self):
        for nom in ('Commercial terrain', 'Admin RH'):
            avant = self._nb_activites()
            api = self._api(nom)
            lectures = self._lectures(api, self.client_c.pk)
            self.assertEqual(lectures, {cle: 403 for cle in lectures}, nom)
            resp = api.post(f'{BASE}{self.client_c.pk}/relancer-dormance/')
            self.assertEqual(resp.status_code, 403, nom)
            self.assertEqual(self._nb_activites(), avant, nom)

    def test_viewer_ne_relance_pas(self):
        api = self._api('Viewer')
        lectures = self._lectures(api, self.client_v.pk)
        self.assertEqual(lectures, {cle: 200 for cle in lectures})
        avant = self._nb_activites()
        resp = api.post(f'{BASE}{self.client_v.pk}/relancer-dormance/')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._nb_activites(), avant)

    def test_technicien_garde_liste_sans_leads(self):
        api = self._api('Technicien')
        self.assertEqual(api.get(BASE).status_code, 200)
        resp = api.get(f'{BASE}search/', {'q': 'Témoin'})
        self.assertEqual(resp.status_code, 200)
        sources = {r.get('source') for r in resp.data['results']}
        self.assertNotIn('lead', sources)
        self.assertNotIn('+212661909902', str(resp.data))

    def test_commercial_inchange(self):
        api = self._api('Commercial')
        lectures = self._lectures(api, self.client_c.pk)
        self.assertEqual(lectures, {cle: 200 for cle in lectures})
        resp = api.get(f'{BASE}search/', {'q': 'Témoin'})
        self.assertIn('lead', {r.get('source') for r in resp.data['results']})
        avant = self._nb_activites()
        resp = api.post(f'{BASE}{self.client_c.pk}/relancer-dormance/')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(self._nb_activites(), avant + 1)

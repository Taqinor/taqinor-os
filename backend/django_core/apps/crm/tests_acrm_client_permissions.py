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
    ADMIN_RH_PERMISSIONS, COMMERCIAL_PERMISSIONS, COMMERCIAL_RESP_PERMISSIONS,
    RESPONSABLE_PERMISSIONS,
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

    def test_satellites_crm_lecture_bornee_au_module(self):
        """APFS116 (D-APFS-4) — la LISTE des 22 vues satellites du CRM
        (équipes, objectifs, playbooks, prévisions, canaux, tags, motifs,
        règles d'attribution, modèles de message, profils de site, vues
        enregistrées…) exige un code du module crm : Admin RH, Commercial
        terrain et Technicien 403 ; le Commercial passe la garde."""
        from apps.crm.urls import router
        satellites = {
            'EquipeCommercialeViewSet', 'ObjectifCommercialViewSet', 'PlaybookViewSet',
            'PlaybookEtapeViewSet', 'PlaybookTacheViewSet', 'ForecastEntryViewSet',
            'ParrainageViewSet', 'PlanActiviteViewSet', 'ConcurrentPerteViewSet',
            'PlanCompteViewSet', 'RevueCompteViewSet', 'DefiViewSet', 'VisiteExterneViewSet',
            'AppareilEquipeViewSet', 'SalleVenteViewSet', 'LeadTagViewSet', 'MotifPerteViewSet',
            'CanalViewSet', 'SiteProfileViewSet', 'SavedViewViewSet', 'MessageTemplateViewSet',
            'RegleAttributionViewSet'}
        routes = {vs.__name__: f'/api/django/crm/{prefixe}/'
                  for prefixe, vs, _b in router.registry if vs.__name__ in satellites}
        self.assertEqual(set(routes), satellites)
        for nom in ('Admin RH', 'Commercial terrain', 'Technicien', 'Commercial'):
            api = self._api(nom)
            for vue, url in sorted(routes.items()):
                code = api.get(url).status_code
                if nom == 'Commercial':
                    self.assertNotIn(code, (401, 403), f'{nom} {vue} {url}')
                else:
                    self.assertEqual(code, 403, f'{nom} {vue} {url}')
            # QJ-EQUIPE-3 — « ce navigateur » reste ouvert à TOUT rôle (le
            # Header l'appelle pour chaque utilisateur connecté).
            code = api.post('/api/django/crm/appareils-equipe/ce-navigateur/',
                            {}, format='json').status_code
            self.assertNotIn(code, (401, 403), f'{nom} ce-navigateur')

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

    def _objets_satellites(self, owner):
        """ADRG4 — un objet par route DELETE satellite non parquée (12)."""
        import datetime
        import secrets
        from apps.crm import models_clients as m
        jour = datetime.date(2026, 11, 11)
        lead = Lead.objects.create(company=self.company, nom='ADRG4', owner=owner)
        client = Client.objects.create(company=self.company, nom='ADRG4 Client')
        plan = m.PlanCompte.objects.create(company=self.company, client=client)
        playbook = m.Playbook.objects.create(company=self.company, nom='PB ADRG4')
        stage = m.PlaybookEtape._meta.get_field('stage').choices[0][0]  # règle #2
        etape = m.PlaybookEtape.objects.create(playbook=playbook, stage=stage)
        return {
            'parrainages': m.Parrainage.objects.create(
                company=self.company, parrain=client),
            'concurrents-perte': m.ConcurrentPerte.objects.create(
                company=self.company, lead=lead, concurrent_nom='X'),
            'plans-activite': m.PlanActivite.objects.create(
                company=self.company, nom='Plan ADRG4'),
            'forecast-entries': m.ForecastEntry.objects.create(
                company=self.company, lead=lead),
            'plans-compte': plan,
            'revues-compte': m.RevueCompte.objects.create(plan=plan, date_revue=jour),
            'playbook-taches': m.PlaybookTache.objects.create(etape=etape, libelle='T'),
            'playbook-etapes': etape,
            'playbooks': playbook,
            'defis': m.Defi.objects.create(
                company=self.company, nom='Défi', periode_debut=jour, periode_fin=jour,
                metrique=m.ObjectifCommercial.Metric.NB_LEADS),
            'partenaires': m.Partenaire.objects.create(
                company=self.company, nom='Partenaire', token_acces=secrets.token_hex(16)),
            'appareils-equipe': m.AppareilEquipe.objects.create(
                company=self.company, appareil_id='adrg4-appareil'),
        }

    def test_suppressions_satellites_exigent_crm_supprimer(self):
        """ADRG4 — Commercial et Responsable LIVRÉS : 403 ``crm_supprimer`` et
        objet présent sur les 12 routes ; Commercial responsable : passe la
        garde (204 sur les objets non bornés par la portée lead/client)."""
        for nom, perms in (('Responsable', RESPONSABLE_PERMISSIONS),
                           ('Commercial responsable', COMMERCIAL_RESP_PERMISSIONS)):
            role = Role.objects.create(
                company=self.company, nom=nom, permissions=list(perms), est_systeme=True)
            self.users[nom] = User.objects.create_user(
                username=f'adrg4-{nom.replace(" ", "-").lower()}', password='x',
                company=self.company, role=role)
        objets = self._objets_satellites(self.users['Commercial responsable'])
        for nom in ('Commercial', 'Responsable'):
            api = self._api(nom)
            for route, obj in objets.items():
                resp = api.delete(f'/api/django/crm/{route}/{obj.pk}/')
                self.assertEqual(resp.status_code, 403, f'{nom} {route}')
                self.assertIn('crm_supprimer', str(resp.data), f'{nom} {route}')
                self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists(), route)
        api = self._api('Commercial responsable')
        portee = {'parrainages', 'concurrents-perte', 'forecast-entries',
                  'plans-compte', 'revues-compte'}  # bornés par lead/client
        for route, obj in objets.items():
            code = api.delete(f'/api/django/crm/{route}/{obj.pk}/').status_code
            if route in portee:
                self.assertNotEqual(code, 403, route)
            else:
                self.assertEqual(code, 204, route)

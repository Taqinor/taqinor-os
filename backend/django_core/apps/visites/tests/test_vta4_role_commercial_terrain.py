"""VTA4 — permissions ``visites_*`` et le rôle « Commercial terrain ».

Commande fondateur 2026-09-12 : « l'utilisateur qui fera la visite n'aura
probablement pas l'accès CRM ». Ce module prouve que cette phrase est VRAIE
côté serveur, pas seulement côté écran :

* les 4 codes sont RENOMMÉS ``visites_*`` et l'ancien préfixe ``crm_visite_*``
  n'ouvre plus rien (un rôle resté sur l'ancien code est refusé — c'est ce que
  la data migration ``roles.0004`` répare pour les rôles déjà en base) ;
* le rôle « Commercial terrain » est SEMÉ par ``init_roles``, porte exactement
  les 3 droits métier + le marqueur ``app_visites_voir`` (donc l'accueil ne lui
  montre QUE la tuile Visites), travaille normalement dans l'app Visites, et
  reçoit 403 sur ``/api/django/crm/leads/`` ;
* il ne peut PAS se donner le feu vert à lui-même ;
* le Directeur et le rôle Technicien sont INTOUCHÉS.
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import (
    ALL_PERMISSIONS, CANONICAL_SYSTEM_ROLES, COMMERCIAL_TERRAIN_PERMISSIONS,
    DIRECTEUR_PERMISSIONS, PERMISSION_MODULE, Role, TECHNICIEN_PERMISSIONS,
    cles_apps_autorisees, permission_app,
)
from authentication.models import Company

User = get_user_model()

CODES_VISITE = ['visites_voir', 'visites_creer', 'visites_modifier',
                'visites_valider']
ANCIENS_CODES = ['crm_visite_voir', 'crm_visite_creer', 'crm_visite_modifier',
                 'crm_visite_valider']


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CodesDePermissionTests(TestCase):
    """Le registre lui-même : nouveaux codes en place, anciens disparus."""

    def test_les_quatre_codes_sont_declares(self):
        for code in CODES_VISITE:
            self.assertIn(code, ALL_PERMISSIONS)

    def test_les_anciens_codes_ont_disparu_du_registre(self):
        for code in ANCIENS_CODES:
            self.assertNotIn(code, ALL_PERMISSIONS)

    def test_module_proprietaire_est_visites_pas_crm(self):
        """Sans ça, l'éditeur de rôles masquerait le droit aux sociétés qui
        n'ont pas le module CRM, et le montrerait à celles sans Visites."""
        for code in CODES_VISITE:
            self.assertEqual(PERMISSION_MODULE.get(code), 'visites')

    def test_marqueur_d_app_hors_du_registre(self):
        """Mécanique ODY26 : ``app_visites_voir`` RETIRE, il n'accorde pas —
        l'inscrire dans ``ALL_PERMISSIONS`` restreindrait mécaniquement le
        Directeur, qui en dérive."""
        self.assertEqual(permission_app('visites'), 'app_visites_voir')
        self.assertNotIn('app_visites_voir', ALL_PERMISSIONS)


class RoleCommercialTerrainTests(TestCase):
    """Le rôle seedé : contenu exact et liste blanche d'apps."""

    def test_role_present_dans_les_roles_canoniques(self):
        noms = [nom for nom, _ in CANONICAL_SYSTEM_ROLES]
        self.assertIn('Commercial terrain', noms)

    def test_contenu_exact_du_role(self):
        self.assertEqual(
            COMMERCIAL_TERRAIN_PERMISSIONS,
            ['visites_voir', 'visites_creer', 'visites_modifier',
             'app_visites_voir'])

    def test_il_ne_se_valide_jamais_lui_meme(self):
        self.assertNotIn('visites_valider', COMMERCIAL_TERRAIN_PERMISSIONS)

    def test_aucun_droit_crm(self):
        self.assertFalse([c for c in COMMERCIAL_TERRAIN_PERMISSIONS
                          if c.startswith('crm_')])

    def test_accueil_ne_montre_que_la_tuile_visites(self):
        """Liste BLANCHE d'apps : un seul marqueur ⇒ une seule app visible."""
        self.assertEqual(
            cles_apps_autorisees(COMMERCIAL_TERRAIN_PERMISSIONS), {'visites'})

    def test_init_roles_seme_le_role_pour_chaque_societe(self):
        Company.objects.create(nom='VTA4 Société A', slug='vta4-a')
        Company.objects.create(nom='VTA4 Société B', slug='vta4-b')
        call_command('init_roles')
        roles = Role.objects.filter(nom='Commercial terrain')
        self.assertEqual(roles.count(), 2)
        for role in roles:
            self.assertTrue(role.est_systeme)
            self.assertEqual(role.permissions,
                             list(COMMERCIAL_TERRAIN_PERMISSIONS))

    def test_init_roles_est_idempotent(self):
        Company.objects.create(nom='VTA4 Idempotence', slug='vta4-idem')
        call_command('init_roles')
        call_command('init_roles')
        self.assertEqual(
            Role.objects.filter(nom='Commercial terrain').count(), 1)


class RolesIntouchesTests(TestCase):
    """Ce que VTA4 ne devait PAS toucher."""

    def test_technicien_reste_sans_droit_visite(self):
        """Le rôle Technicien porte ~25 droits POST-vente et sa route
        d'accueil ``/ma-journee`` appartient à ``installations`` : lui greffer
        la visite terrain mélangerait deux métiers."""
        self.assertFalse([c for c in TECHNICIEN_PERMISSIONS
                          if c.startswith('visites_')])
        self.assertFalse([c for c in TECHNICIEN_PERMISSIONS
                          if c.startswith('crm_visite_')])

    def test_directeur_garde_les_quatre_droits(self):
        for code in CODES_VISITE:
            self.assertIn(code, DIRECTEUR_PERMISSIONS)

    def test_directeur_n_est_pas_restreint_a_une_app(self):
        self.assertIsNone(cles_apps_autorisees(DIRECTEUR_PERMISSIONS))


class PorteeServeurDuCommercialTerrainTests(TestCase):
    """Le point du groupe VTA, prouvé par des requêtes RÉELLES."""

    @classmethod
    def setUpTestData(cls):
        from apps.crm.models import Lead

        cls.company = Company.objects.create(nom='VTA4 Solaire', slug='vta4-s')
        # Tenant-distinctness : une SECONDE société réelle, avec ses données.
        cls.autre = Company.objects.create(nom='VTA4 Concurrent',
                                           slug='vta4-c')
        cls.terrain = cls._user(cls.company, 'vta4-terrain',
                                COMMERCIAL_TERRAIN_PERMISSIONS)
        cls.terrain_autre = cls._user(cls.autre, 'vta4-terrain-autre',
                                      COMMERCIAL_TERRAIN_PERMISSIONS)
        cls.ancien = cls._user(cls.company, 'vta4-ancien-code', ANCIENS_CODES)
        cls.lead = Lead.objects.create(
            company=cls.company, nom='Bennani', ville='Bouskoura')
        cls.lead_autre = Lead.objects.create(
            company=cls.autre, nom='Client concurrent', ville='Rabat')

    @staticmethod
    def _user(company, username, permissions):
        role = Role.objects.create(company=company, nom=f'role-{username}',
                                   permissions=list(permissions))
        return User.objects.create_user(
            username=username, password='x', company=company,
            role_legacy='normal', role=role)

    def test_il_travaille_dans_l_app_visites(self):
        api = auth(self.terrain)
        creation = api.post('/api/django/visites/visites/',
                            {'lead': self.lead.id}, format='json')
        self.assertEqual(creation.status_code, 201, creation.data)
        liste = api.get('/api/django/visites/visites/')
        self.assertEqual(liste.status_code, 200, liste.data)

    def test_il_recoit_403_sur_les_leads_du_crm(self):
        """LE point du groupe VTA : la frontière est SERVEUR, pas un écran
        caché. Sans ``crm_voir``, l'annuaire des leads lui est fermé."""
        reponse = auth(self.terrain).get('/api/django/crm/leads/')
        self.assertEqual(reponse.status_code, 403, reponse.status_code)

    def test_il_ne_peut_pas_valider(self):
        api = auth(self.terrain)
        visite_id = api.post('/api/django/visites/visites/',
                             {'lead': self.lead.id},
                             format='json').data['id']
        refus = api.post(f'/api/django/visites/visites/{visite_id}/valider/',
                         {}, format='json')
        self.assertEqual(refus.status_code, 403, refus.status_code)

    def test_l_ancien_code_n_ouvre_plus_rien(self):
        """Un rôle resté sur ``crm_visite_voir`` est REFUSÉ — c'est exactement
        ce que la data migration ``roles.0004`` évite en production."""
        reponse = auth(self.ancien).get('/api/django/visites/visites/')
        self.assertEqual(reponse.status_code, 403, reponse.status_code)

    def test_isolation_entre_deux_commerciaux_terrain_de_societes_distinctes(self):
        from apps.visites.models import VisiteTerrain

        VisiteTerrain.objects.create(company=self.company, lead=self.lead,
                                     commercial=self.terrain)
        VisiteTerrain.objects.create(company=self.autre, lead=self.lead_autre,
                                     commercial=self.terrain_autre)
        lignes = auth(self.terrain_autre).get(
            '/api/django/visites/visites/').data
        self.assertEqual([ligne['lead'] for ligne in lignes],
                         [self.lead_autre.id])

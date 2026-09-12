"""VTA7 — la notification d'assignation d'une visite terrain.

Sans ce message, un commercial terrain ne découvrait sa visite qu'en ouvrant
l'app — alors que sa journée venait de changer. Ce que le test prouve :

* à la CRÉATION, l'assigné reçoit une notification dédiée (clé
  ``visite_terrain_assignee``) dont le lien pointe ``/visites/<id>`` ;
* à la RÉASSIGNATION, le NOUVEL assigné est prévenu ; un PATCH qui ne touche
  pas ``commercial`` ne sonne la cloche de personne ;
* on ne se notifie jamais soi-même ;
* une visite sans assigné n'envoie rien ;
* la cloche est ouverte à TOUT rôle (``IsAnyRole``) : un « Commercial
  terrain », qui n'a aucun droit CRM, lit bien sa notification.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.notifications.models import EventType, Notification
from apps.roles.models import COMMERCIAL_TERRAIN_PERMISSIONS, Role
from apps.visites.models import VisiteTerrain
from authentication.models import Company

User = get_user_model()

BUREAU = ['visites_voir', 'visites_creer', 'visites_modifier',
          'visites_valider']


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AssignationBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='VTA7 Solaire', slug='vta7-a')
        # Tenant-distinctness : une SECONDE société RÉELLE, avec ses données.
        cls.autre = Company.objects.create(nom='VTA7 Concurrent',
                                           slug='vta7-b')
        cls.bureau = cls._user(cls.company, 'vta7-bureau', BUREAU)
        cls.terrain = cls._user(cls.company, 'vta7-terrain',
                                COMMERCIAL_TERRAIN_PERMISSIONS)
        cls.terrain2 = cls._user(cls.company, 'vta7-terrain2',
                                 COMMERCIAL_TERRAIN_PERMISSIONS)
        cls.etranger = cls._user(cls.autre, 'vta7-etranger', BUREAU)
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

    @staticmethod
    def _assignations(user):
        return Notification.objects.filter(
            recipient=user,
            event_type=EventType.VISITE_TERRAIN_ASSIGNEE)


class NotificationDAssignationTests(AssignationBase):
    def test_la_creation_previent_l_assigne(self):
        reponse = auth(self.bureau).post(
            '/api/django/visites/visites/',
            {'lead': self.lead.id, 'commercial': self.terrain.id,
             'date_prevue': '2026-09-15'}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        notification = self._assignations(self.terrain).get()
        self.assertEqual(notification.company_id, self.company.id)
        self.assertEqual(notification.link,
                         f'/visites/{reponse.data["id"]}')
        self.assertIn('15/09/2026', notification.body)
        self.assertIn('Bennani', notification.body)

    def test_on_ne_se_notifie_jamais_soi_meme(self):
        """S'assigner une visite ne mérite pas une cloche."""
        reponse = auth(self.bureau).post(
            '/api/django/visites/visites/',
            {'lead': self.lead.id, 'commercial': self.bureau.id},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(self._assignations(self.bureau).count(), 0)

    def test_une_visite_sans_assigne_n_envoie_rien(self):
        """Sans ``commercial``, le serveur assigne le créateur — donc rien."""
        reponse = auth(self.bureau).post(
            '/api/django/visites/visites/', {'lead': self.lead.id},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.VISITE_TERRAIN_ASSIGNEE).count(), 0)

    def test_la_reassignation_previent_le_nouvel_assigne(self):
        visite = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, commercial=self.terrain)
        reponse = auth(self.bureau).patch(
            f'/api/django/visites/visites/{visite.id}/',
            {'commercial': self.terrain2.id}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(self._assignations(self.terrain2).count(), 1)
        # L'ancien assigné ne reçoit pas une seconde cloche.
        self.assertEqual(self._assignations(self.terrain).count(), 0)

    def test_un_patch_qui_ne_reassigne_pas_ne_sonne_personne(self):
        visite = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, commercial=self.terrain)
        reponse = auth(self.bureau).patch(
            f'/api/django/visites/visites/{visite.id}/',
            {'notes': 'Accès par le portail arrière.'}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(self._assignations(self.terrain).count(), 0)

    def test_la_cloche_est_lisible_par_un_commercial_terrain(self):
        """``IsAnyRole`` — un rôle sans aucun droit CRM lit ses notifications."""
        auth(self.bureau).post(
            '/api/django/visites/visites/',
            {'lead': self.lead.id, 'commercial': self.terrain.id},
            format='json')
        reponse = auth(self.terrain).get('/api/django/notifications/')
        self.assertEqual(reponse.status_code, 200, reponse.status_code)
        donnees = reponse.data
        lignes = (donnees['results'] if isinstance(donnees, dict)
                  and 'results' in donnees else donnees)
        self.assertTrue(any(
            ligne['event_type'] == EventType.VISITE_TERRAIN_ASSIGNEE
            for ligne in lignes), lignes)

    def test_isolation_societe(self):
        """La visite d'une autre société ne notifie personne chez nous."""
        VisiteTerrain.objects.create(
            company=self.autre, lead=self.lead_autre,
            commercial=self.etranger)
        auth(self.etranger).post(
            '/api/django/visites/visites/',
            {'lead': self.lead_autre.id}, format='json')
        self.assertEqual(self._assignations(self.terrain).count(), 0)
        self.assertEqual(self._assignations(self.terrain2).count(), 0)


class EventTypeTests(TestCase):
    def test_la_cle_est_declaree_et_distincte(self):
        self.assertEqual(EventType.VISITE_TERRAIN_ASSIGNEE,
                         'visite_terrain_assignee')
        self.assertNotEqual(EventType.VISITE_TERRAIN_ASSIGNEE,
                            EventType.VISITE_TERRAIN_VALIDEE)

    def test_elle_a_un_producteur(self):
        """Garde YEVNT7 — un EventType sans producteur est un orphelin."""
        from core import event_coverage

        self.assertNotIn('visite_terrain_assignee',
                         event_coverage.unproduced_eventtypes())

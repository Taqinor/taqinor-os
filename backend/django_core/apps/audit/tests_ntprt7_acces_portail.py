"""NTPRT7 — Audit des accès portail.

Couvre :

* ``recorder.record(..., via_portail=True)`` pose le drapeau additif sur la
  ligne créée (défaut ``False`` — aucune régression pour les appelants
  existants qui ne le passent pas) ;
* le nouveau choix ``Action.PAYMENT`` tient dans ``max_length`` ;
* l'onglet « Accès portail » (``GET /api/django/audit/portail/``) ne renvoie
  QUE les lignes ``via_portail=True``, scopées société, réservé au Directeur
  (même garde que le reste du Journal — ``CanViewActivityLog``) ;
* ``AuditLogSerializer`` expose ``via_portail``.

Run :
    python manage.py test apps.audit.tests_ntprt7_acces_portail -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit import recorder
from apps.audit.models import AuditLog
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_directeur(company, username):
    role = Role.objects.create(
        company=company, nom=f'Directeur-{username}',
        permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
    return User.objects.create_user(
        username=username, password='pw', role_legacy='admin',
        role=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RecorderViaPortailTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt7-co-a', 'NTPRT7 Société A')

    def test_via_portail_defaut_faux(self):
        recorder.record(
            AuditLog.Action.LOGIN, user=None, company=self.company,
            detail='connexion interne')
        entry = AuditLog.objects.get(company=self.company)
        self.assertFalse(entry.via_portail)

    def test_via_portail_pose_le_drapeau(self):
        recorder.record(
            AuditLog.Action.LOGIN, user=None, company=self.company,
            detail='connexion portail', via_portail=True)
        entry = AuditLog.objects.get(company=self.company)
        self.assertTrue(entry.via_portail)

    def test_action_payment_tient_dans_max_length(self):
        field = AuditLog._meta.get_field('action')
        self.assertLessEqual(len('payment'), field.max_length)
        self.assertIn('payment', dict(AuditLog.Action.choices))


class SerializerViaPortailTests(TestCase):
    def test_champ_expose(self):
        from apps.audit.serializers import AuditLogSerializer
        company = make_company('ntprt7-co-ser', 'NTPRT7 Sérialiseur')
        entry = AuditLog.objects.create(
            company=company, action=AuditLog.Action.ACCEPT,
            via_portail=True)
        data = AuditLogSerializer(entry).data
        self.assertTrue(data['via_portail'])


class PortalAccessEndpointTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt7-co-b', 'NTPRT7 Société B')
        self.directeur = make_directeur(self.company, 'ntprt7-dir')
        AuditLog.objects.create(
            company=self.company, action=AuditLog.Action.ACCEPT,
            actor_username='client-x', via_portail=True,
            detail='Devis accepté via le portail client')
        AuditLog.objects.create(
            company=self.company, action=AuditLog.Action.CREATE,
            actor_username='admin-interne', via_portail=False,
            detail='Création interne, sans rapport avec le portail')

    def test_endpoint_ne_renvoie_que_le_via_portail(self):
        api = auth(self.directeur)
        res = api.get('/api/django/audit/portail/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['count'], 1)
        self.assertTrue(res.data['results'][0]['via_portail'])

    def test_endpoint_reserve_au_directeur(self):
        viewer = User.objects.create_user(
            username='ntprt7-viewer', password='pw',
            role_legacy='utilisateur', company=self.company)
        api = auth(viewer)
        res = api.get('/api/django/audit/portail/')
        self.assertEqual(res.status_code, 403)

    def test_endpoint_scope_societe(self):
        autre = make_company('ntprt7-co-c', 'NTPRT7 Société C')
        AuditLog.objects.create(
            company=autre, action=AuditLog.Action.ACCEPT,
            actor_username='client-y', via_portail=True)
        api = auth(self.directeur)
        res = api.get('/api/django/audit/portail/')
        self.assertEqual(res.data['count'], 1)

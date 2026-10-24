"""FG23 — vue des évènements de sécurité + alerte d'échecs de connexion.

L'endpoint security/ (réservé au Directeur) ne renvoie que les actions de
sécurité ; une alerte SECURITY_ALERT est journalisée quand le seuil d'échecs
consécutifs (FG22) est atteint."""
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from authentication import password_policy as pp
from apps.audit.models import AuditLog
from apps.audit import recorder
from apps.parametres.models import CompanyProfile

User = get_user_model()


def _company(slug='fg23-co', nom='FG23 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class FG23SecurityEventsTest(TestCase):
    def setUp(self):
        self.company = _company()
        # Directeur : journal_activite_voir via role_legacy admin + can_view.
        from apps.roles.models import Role
        from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.dir = User.objects.create_user(
            username='fg23_dir', password='pw', role_legacy='admin',
            role=role, company=self.company)
        self.api = APIClient()
        token = str(AccessToken.for_user(self.dir))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        # Quelques lignes : un login (sécurité) + une création (non-sécurité).
        AuditLog.objects.create(
            company=self.company, action=AuditLog.Action.LOGIN,
            actor_username='fg23_dir')
        AuditLog.objects.create(
            company=self.company, action=AuditLog.Action.CREATE,
            actor_username='fg23_dir', object_repr='Devis')

    def test_security_endpoint_only_security_actions(self):
        r = self.api.get('/api/django/audit/security/')
        self.assertEqual(r.status_code, 200, r.content)
        actions = {row['action'] for row in r.data['results']}
        self.assertIn('login', actions)
        self.assertNotIn('create', actions)

    def test_enf11_limit_invalide_400_pas_500(self):
        """ENF11 — `limit` négatif / illisible = 400 (le slice négatif
        levait une 500) ; > 500 reste plafonné, valeur valide inchangée."""
        for url in ('/api/django/audit/security/',
                    '/api/django/audit/portail/'):
            # api-fuzz full 24/10 : vide ou répété = hors schéma (400).
            for bad in ('-29404', '0', 'abc', '', '5&limit=6'):
                r = self.api.get(url + '?limit=' + bad)
                self.assertEqual(r.status_code, 400, (url, bad, r.content))
            # ``search`` porteur d'un caractère nul levait PostgreSQL (500) :
            # aucune ligne ne peut correspondre → liste vide (règle de core).
            r = self.api.get(url + '?search=%00x')
            self.assertEqual(r.status_code, 200, (url, r.content))
            self.assertEqual(r.data['results'], [])
            self.assertEqual(self.api.get(url + '?limit=9999').status_code, 200)
        r = self.api.get('/api/django/audit/security/?limit=1')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['results']), 1)

    def test_security_endpoint_requires_directeur(self):
        viewer = User.objects.create_user(
            username='fg23_viewer', password='pw', role_legacy='utilisateur',
            company=self.company)
        api = APIClient()
        token = str(AccessToken.for_user(viewer))
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        r = api.get('/api/django/audit/security/')
        self.assertEqual(r.status_code, 403)


class FG23AlertTest(TestCase):
    def test_security_alert_logged_on_lockout(self):
        company = _company(slug='fg23-alert', nom='FG23 Alert')
        CompanyProfile.objects.create(
            company=company, lockout_max_attempts=2,
            lockout_duration_minutes=10)
        user = User.objects.create_user(
            username='fg23_locked', password='pw', company=company)
        # `record` ne journalise que dans une requête : on en simule une.
        recorder.begin_request(RequestFactory().post('/login/'))
        try:
            pp.register_failed_login(user)
            pp.register_failed_login(user)  # atteint le seuil → alerte + verrou
        finally:
            recorder.end_request()
        self.assertTrue(AuditLog.objects.filter(
            company=company, action=AuditLog.Action.SECURITY_ALERT).exists())

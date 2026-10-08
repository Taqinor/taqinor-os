"""ASEC8 — aucun secret ne sort du journal d'audit.

Le diff automatique trace le CHANGEMENT d'un champ secret (``totp_secret``,
``password``, tout champ chiffré) avec ``***`` comme valeurs ; la restitution
« as-of » rend ``***`` ; la migration 0009 caviarde les lignes déjà écrites ;
un champ ordinaire garde ses valeurs.
"""
import importlib

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient

from apps.audit import recorder
from apps.audit.models import AuditLog
from authentication.models import Company

User = get_user_model()


class CaviardageSecretsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASEC8', slug='asec8-co')
        self.cible = User.objects.create_user(
            username='asec8_cible', password='Ancien-mdp-8!',
            company=self.company, first_name='Avant')
        self.su = User.objects.create_superuser(
            username='asec8_su', password='x', email='su@asec8.ma')
        self.su.company = self.company
        self.su.save()
        self.ct = ContentType.objects.get_for_model(User)

    def _en_requete(self, geste):
        requete = RequestFactory().post('/')
        requete.user = self.su
        recorder.begin_request(requete)
        try:
            geste()
        finally:
            recorder.end_request()

    def _changement(self, champ):
        for ligne in AuditLog.objects.filter(
                content_type=self.ct, object_id=str(self.cible.pk),
                changes__isnull=False).order_by('-pk'):
            for change in ligne.changes:
                if change.get('field') == champ:
                    return change
        return None

    def test_diff_totp_secret_caviarde(self):
        def geste():
            self.cible.totp_secret = 'JBSWY3DPEHPK3PXP'
            self.cible.save()
        self._en_requete(geste)
        change = self._changement('totp_secret')
        self.assertIsNotNone(change, 'le changement doit rester tracé')
        self.assertEqual((change['old'], change['new']), ('***', '***'))
        self.assertNotIn('JBSWY3DPEHPK3PXP', str(AuditLog.objects.filter(
            object_id=str(self.cible.pk)).values_list('changes', flat=True)))

    def test_diff_password_caviarde(self):
        ancien_hash = self.cible.password

        def geste():
            self.cible.set_password('Nouveau-mdp-8!')
            self.cible.save()
        self._en_requete(geste)
        change = self._changement('password')
        self.assertIsNotNone(change)
        self.assertEqual((change['old'], change['new']), ('***', '***'))
        self.assertNotIn(ancien_hash, str(change))

    def test_as_of_caviarde(self):
        AuditLog.objects.create(
            company=self.company, action=AuditLog.Action.UPDATE,
            content_type=self.ct, object_id=str(self.cible.pk),
            changes=[{'field': 'totp_secret', 'old': '', 'new': 'SECRETCLAIR'},
                     {'field': 'first_name', 'old': 'Avant', 'new': 'Apres'}])
        api = APIClient()
        api.force_authenticate(self.su)
        resp = api.get(
            f'/api/django/audit/objets/authentication.customuser/'
            f'{self.cible.pk}/as-of/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['fields']['totp_secret'], '***')
        self.assertEqual(resp.data['fields']['first_name'], 'Apres')
        self.assertNotIn('SECRETCLAIR', str(resp.data))

    def test_migration_caviarde_lignes_existantes(self):
        ligne = AuditLog.objects.create(
            company=self.company, action=AuditLog.Action.UPDATE,
            content_type=self.ct, object_id=str(self.cible.pk),
            changes=[{'field': 'totp_secret', 'old': 'A', 'new': 'B'},
                     {'field': 'password', 'old': 'h1', 'new': 'h2'},
                     {'field': 'first_name', 'old': 'X', 'new': 'Y'}])
        migration = importlib.import_module(
            'apps.audit.migrations.0009_asec8_caviardage_secrets')
        migration.caviarder_lignes(django_apps, None)
        ligne.refresh_from_db()
        par_champ = {c['field']: (c['old'], c['new']) for c in ligne.changes}
        self.assertEqual(par_champ['totp_secret'], ('***', '***'))
        self.assertEqual(par_champ['password'], ('***', '***'))
        self.assertEqual(par_champ['first_name'], ('X', 'Y'))

    def test_champ_ordinaire_inchange(self):
        def geste():
            self.cible.first_name = 'Apres'
            self.cible.save()
        self._en_requete(geste)
        change = self._changement('first_name')
        self.assertIsNotNone(change)
        self.assertEqual((change['old'], change['new']), ('Avant', 'Apres'))

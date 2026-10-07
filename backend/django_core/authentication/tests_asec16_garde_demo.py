"""ASEC16 — commandes et assistant de démonstration réservés à
``Company.est_demo=True``.

Une société RÉELLE au slug ``taqinor-demo`` (``est_demo=False``) est refusée
par reset_demo_company, seed_demo, seed_demo_company et l'assistant, avec
DEBUG vrai comme faux, sans aucune ligne supprimée ni créée ; une société
démo est réinitialisée ; un échec du re-seed laisse les données d'origine
intactes (suppression et re-seed dans une seule transaction).
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from authentication.management.commands import seed_demo_company
from authentication.models import Company

User = get_user_model()


class GardeDemoTests(TestCase):
    def setUp(self):
        self.reelle = Company.objects.create(
            nom='Société réelle', slug='taqinor-demo', est_demo=False)
        User.objects.create_user(
            username='asec16_reel', password='x', company=self.reelle)

    def _compte(self):
        return (Company.objects.count(), User.objects.count(),
                User.objects.filter(company=self.reelle).count())

    def test_reset_refuse_societe_reelle_slug_demo(self):
        avant = self._compte()
        for debug in (True, False):
            with self.subTest(debug=debug), override_settings(DEBUG=debug):
                with self.assertRaises(CommandError) as ctx:
                    call_command('reset_demo_company', slug='taqinor-demo',
                                 force=True, verbosity=0)
                self.assertIn('est_demo', str(ctx.exception))
                self.assertEqual(self._compte(), avant)

    def test_seed_refuse_hors_est_demo_meme_debug(self):
        avant = self._compte()
        for debug in (True, False):
            with self.subTest(debug=debug), override_settings(DEBUG=debug):
                with self.assertRaises(CommandError) as ctx:
                    call_command('seed_demo', force=True, verbosity=0)
                self.assertIn('est_demo', str(ctx.exception))
                with self.assertRaises(CommandError) as ctx:
                    call_command('seed_demo_company', slug='taqinor-demo',
                                 force=True, verbosity=0)
                self.assertIn('est_demo', str(ctx.exception))
                self.assertEqual(self._compte(), avant)
        self.reelle.refresh_from_db()
        self.assertFalse(self.reelle.est_demo)

    def test_assistant_refuse_hors_est_demo(self):
        su = User.objects.create_superuser(
            username='asec16_su', password='x', email='su@asec16.ma')
        api = APIClient()
        api.force_authenticate(su)
        avant = self._compte()
        resp = api.post('/api/django/auth/demo-wizard/',
                        {'slug': 'taqinor-demo', 'profil': 'mixte',
                         'densite': 'leger'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('est_demo', str(resp.data))
        self.assertEqual(self._compte(), avant)

    @override_settings(DEBUG=True)
    def test_reset_atomique(self):
        demo = Company.objects.create(
            nom='Démo', slug='asec16-demo', est_demo=True)
        sentinelle = User.objects.create_user(
            username='asec16_sentinelle', password='x', company=demo)
        with mock.patch.object(
                seed_demo_company.Command, '_seed_leads',
                side_effect=ValueError('donnée invalide')):
            with self.assertRaises(ValueError):
                call_command('reset_demo_company', slug='asec16-demo',
                             force=True, verbosity=0)
        self.assertTrue(Company.objects.filter(pk=demo.pk).exists())
        self.assertTrue(User.objects.filter(pk=sentinelle.pk).exists())

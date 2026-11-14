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

    def test_neutraliser_contacts_demo_dry_run_puis_appliquer(self):
        """AMSG62 (D-AMSG-6) — dry-run par défaut (0 écriture), puis
        ``--appliquer --sauf <id>`` neutralise tout sauf l'exclu et le témoin."""
        import ast
        from io import StringIO

        from django.apps import apps as django_apps
        from django.contrib.contenttypes.models import ContentType

        from authentication.management.commands.neutraliser_contacts_demo import SEED
        Client = django_apps.get_model('crm', 'Client')
        Fournisseur = django_apps.get_model('stock', 'Fournisseur')
        AuditLog = django_apps.get_model('audit', 'AuditLog')
        fiches = []
        for noeud in ast.walk(ast.parse(SEED.read_text(encoding='utf-8'))):  # adresses lues du seed
            if isinstance(noeud, ast.Assign) and getattr(noeud.targets[0], 'id', '') == 'clients_data':
                for nom, prenom, email, tel, _adresse in ast.literal_eval(noeud.value):
                    fiches.append(Client.objects.create(
                        company=self.reelle, nom=nom, prenom=prenom, email=email, telephone=tel))
            if isinstance(noeud, ast.Call) and getattr(noeud.func, 'attr', '') == 'create' \
                    and 'Fournisseur' in ast.unparse(noeud.func):
                kw = {k.arg: ast.literal_eval(k.value) for k in noeud.keywords if k.arg != 'company'}
                fiches.append(Fournisseur.objects.create(company=self.reelle, **kw))
        self.assertEqual((len(fiches), sum(isinstance(f, Fournisseur) for f in fiches)), (7, 2))
        temoin = Client.objects.create(company=self.reelle, nom='Témoin', prenom='Réel',
                                       email='temoin@client-reel.ma', telephone='+212611111111')

        def etat():
            return [type(f).objects.values_list('email', 'telephone').get(pk=f.pk)
                    for f in fiches + [temoin]]

        avant, out = etat(), StringIO()
        call_command('neutraliser_contacts_demo', societe='taqinor-demo', stdout=out)
        self.assertEqual(etat(), avant)  # dry-run : 0 écriture
        self.assertIn('7 fiche(s) concernée(s)', out.getvalue())
        for f in fiches:
            self.assertNotIn(f.email, out.getvalue())  # jamais l'adresse complète
        exclu = fiches[0]
        out = StringIO()
        call_command('neutraliser_contacts_demo', societe='taqinor-demo', appliquer=True,
                     sauf=[exclu.pk], stdout=out)
        self.assertIn('6 fiche(s) neutralisée(s)', out.getvalue())
        apres = etat()
        self.assertEqual(apres[0], avant[0])  # l'exclu
        self.assertEqual(apres[-1], avant[-1])  # le témoin
        for (email, tel), f in zip(apres[1:-1], fiches[1:]):
            self.assertTrue(email.endswith('@example.invalid'), email)
            self.assertTrue(tel.startswith('+212600'), tel)
            self.assertEqual(AuditLog.objects.filter(
                content_type=ContentType.objects.get_for_model(f), object_id=str(f.pk),
                detail__startswith='AMSG62').count(), 1)

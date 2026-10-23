"""NTPLT47 — générateur de données à l'échelle : garde-fou DEBUG + création."""
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from authentication.models import Company


class SeedScaleGuardTests(TestCase):
    @override_settings(DEBUG=False)
    def test_refuses_outside_debug_without_force(self):
        with self.assertRaises(CommandError):
            call_command('seed_scale', '--companies', '1', stdout=StringIO())

    @override_settings(DEBUG=False)
    def test_force_flag_allows_outside_debug(self):
        call_command('seed_scale', '--companies', '1', '--users', '0',
                     '--leads', '0', '--devis', '0', '--lignes', '0',
                     '--mouvements', '0', '--force-je-sais', stdout=StringIO())
        self.assertTrue(Company.objects.filter(nom__startswith='[SEED_SCALE]')
                        .exists())


@override_settings(DEBUG=True)
class SeedScaleCreationTests(TestCase):
    def test_seeds_companies_and_users(self):
        call_command('seed_scale', '--companies', '2', '--users', '3',
                     '--leads', '0', '--devis', '0', '--lignes', '0',
                     '--mouvements', '0', stdout=StringIO())
        self.assertEqual(
            Company.objects.filter(nom__startswith='[SEED_SCALE]').count(), 2)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.assertEqual(
            User.objects.filter(username__startswith='seed_scale_u').count(), 3)

    def test_idempotent_by_tag(self):
        call_command('seed_scale', '--companies', '2', '--users', '0',
                     '--leads', '0', '--devis', '0', '--lignes', '0',
                     '--mouvements', '0', stdout=StringIO())
        call_command('seed_scale', '--companies', '2', '--users', '0',
                     '--leads', '0', '--devis', '0', '--lignes', '0',
                     '--mouvements', '0', stdout=StringIO())
        # Relancer avec le même --companies ne double pas les sociétés taguées.
        self.assertEqual(
            Company.objects.filter(nom__startswith='[SEED_SCALE]').count(), 2)

    def test_missing_faker_raises(self):
        with mock.patch.dict('sys.modules', {'faker': None}):
            with self.assertRaises(CommandError):
                call_command('seed_scale', '--companies', '1',
                             stdout=StringIO())


@override_settings(DEBUG=True)
class SeedScaleMouvementTests(TestCase):
    def test_seeds_mouvement_stock(self):
        """ERR119 — ``--mouvements 1`` ne doit plus lever LookupError."""
        from django.apps import apps as django_apps
        MouvementStock = django_apps.get_model('stock', 'MouvementStock')
        call_command('seed_scale', '--companies', '1', '--users', '0',
                     '--leads', '0', '--devis', '0', '--lignes', '0',
                     '--mouvements', '1', stdout=StringIO())
        mv = MouvementStock.objects.filter(reference__startswith='SEED-MV-')
        self.assertEqual(mv.count(), 1)
        m = mv.first()
        self.assertIsNotNone(m.company_id)
        self.assertEqual(m.company_id, m.produit.company_id)
        self.assertEqual(m.quantite_apres, m.quantite_avant + m.quantite)


@override_settings(DEBUG=True)
class SeedScaleOrphanProduitCollisionTests(TestCase):
    def test_orphan_products_same_name_same_company_no_integrity_error(self):
        """Load-smoke : deux produits orphelins de même nom réaffectés à la
        même société ne doivent pas violer ``stock_produit_company_nom_sans_sku_uniq``."""
        import random
        from django.apps import apps as django_apps
        from core.management.commands.seed_scale import Command
        Produit = django_apps.get_model('stock', 'Produit')
        co = Company.objects.create(nom='[SEED_SCALE] collision', slug='seed-scale-collision')
        pks = []

        def fake_seed(label, count, **kw):
            for _ in range(2):
                # sku NULL comme les produits Faker du seeder (NULL distincts
                # pour (company, sku) ; '' collisionnerait sur CETTE contrainte).
                p = Produit(nom='genou', sku=None, company=None, prix_vente=0)
                p.save()
                pks.append(p.pk)

        random.seed(0)
        Command._seed_mouvements_stock(
            2, [co.pk], fake_seed, {'stock.produit': pks}, lambda *a: [],
            django_apps)
        # `pks` EST la liste portée par `pools` : les ajouts de fake_seed y
        # sont visibles au moment de la réaffectation.
        noms = list(Produit.objects.filter(pk__in=pks).values_list('nom', flat=True))
        self.assertEqual(len(noms), len(set(noms)))
        self.assertEqual(
            Produit.objects.filter(pk__in=pks, company_id=co.pk).count(), 2)

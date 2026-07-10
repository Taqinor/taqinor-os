"""SCA20 — Registre de hooks « à la création d'une société » + catalogue.

Vérifie que :
* un signup neuf obtient rôles + profil + catalogue + types d'activité +
  niveaux de relance ;
* les hooks sont idempotents (double exécution sans doublon) ;
* le comportement du signup existant est préservé (admin Directeur créé) ;
* ``manage.py seed_company`` rejoue les seeds sur une société existante.
"""
from io import StringIO

from django.core.management import call_command
from rest_framework.test import APIClient

from testkit.base import TenantAPITestCase
from testkit.factories import CompanyFactory


class SignupHooksRegistryTest(TenantAPITestCase):
    def test_registre_idempotent_pas_de_doublon(self):
        from core.signup_hooks import (
            register_signup_hook, registered_hooks, run_signup_hooks,
        )
        appels = {'n': 0}

        def hook(company, *, user=None):
            appels['n'] += 1

        register_signup_hook('test_hook_sca20', hook)
        register_signup_hook('test_hook_sca20', hook)  # ré-enregistre = remplace
        noms = registered_hooks()
        self.assertEqual(noms.count('test_hook_sca20'), 1)
        c = CompanyFactory(nom='HookCo', slug='hookco')
        run_signup_hooks(c)
        self.assertEqual(appels['n'], 1)

    def test_hook_qui_leve_est_isole(self):
        from core.signup_hooks import register_signup_hook, run_signup_hooks

        def boom(company, *, user=None):
            raise RuntimeError('boom')

        register_signup_hook('boom_sca20', boom)
        c = CompanyFactory(nom='BoomCo', slug='boomco')
        res = run_signup_hooks(c)  # ne lève pas
        self.assertIn('erreur', res['boom_sca20'])


class SignupSeedsCatalogueTest(TenantAPITestCase):
    def test_signup_neuf_obtient_roles_profil_catalogue(self):
        api = APIClient()
        r = api.post('/api/django/auth/register-company/', {
            'company_nom': 'Nouvelle SARL',
            'username': 'boss-new',
            'password': 'motdepasse123',
            'email': 'boss@new.ma',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        from authentication.models import Company, CustomUser
        company = Company.objects.get(nom='Nouvelle SARL')

        # Rôles système présents.
        from apps.roles.models import Role
        self.assertTrue(Role.objects.filter(
            company=company, nom='Directeur').exists())
        # Profil présent.
        from apps.parametres.models import CompanyProfile
        self.assertTrue(CompanyProfile.objects.filter(company=company).exists())
        # Types d'activité + niveaux de relance seedés.
        from apps.records.models import ActivityType
        from apps.ventes.models import FollowupLevel
        self.assertTrue(ActivityType.objects.filter(company=company).exists())
        self.assertTrue(FollowupLevel.objects.filter(company=company).exists())
        # Catalogue seedé (au moins un produit).
        from apps.stock.models import Produit
        self.assertTrue(Produit.objects.filter(company=company).exists())
        # Admin Directeur créé (comportement signup préservé).
        boss = CustomUser.objects.get(username='boss-new')
        self.assertEqual(boss.company_id, company.id)
        self.assertEqual(boss.role_legacy, CustomUser.ROLE_ADMIN)
        # XPLT19 — membre de sa société d'attache.
        self.assertIn(company.id, [c.id for c in boss.societes_operables()])

    def test_seed_company_command_idempotent(self):
        # Société sans catalogue → seed_company l'ajoute, deux passages = pas de
        # doublon.
        company = CompanyFactory(nom='Rattrapage', slug='rattrapage')
        out = StringIO()
        call_command('seed_company', 'rattrapage', stdout=out)
        from apps.stock.models import Produit
        n1 = Produit.objects.filter(company=company).count()
        self.assertGreater(n1, 0)
        call_command('seed_company', 'rattrapage', stdout=out)
        n2 = Produit.objects.filter(company=company).count()
        self.assertEqual(n1, n2)  # idempotent : additif seulement

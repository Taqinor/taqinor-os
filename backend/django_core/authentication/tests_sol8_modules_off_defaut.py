"""SOL8 — modules éteints par défaut À LA CRÉATION, jamais en backfill.

L'invariant le plus important n'est pas ce que le semis ÉCRIT, c'est ce qu'il
N'ÉCRIT PAS : une société PRÉEXISTANTE ne doit recevoir AUCUNE ligne. TAQINOR
utilise `douane` et `scm` en production — un backfill les éteindrait.
"""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from authentication.models import Company
from authentication.module_seeds import (
    MODULES_OFF_PAR_DEFAUT, PACK_PAYS_MAROC, modules_a_eteindre,
    semer_modules_off_par_defaut,
)
from core import feature_flags
from core.models import ModuleToggle

User = get_user_model()


class SemisTenantNeufTests(TestCase):
    def test_semis_ecrit_les_modules_rares_eteints(self):
        company = Company.objects.create(nom='Neuve MA', slug='neuve-ma')
        ecrites = semer_modules_off_par_defaut(company)
        self.assertEqual(sorted(ecrites), sorted(MODULES_OFF_PAR_DEFAUT))
        lignes = dict(
            ModuleToggle.objects.filter(company=company)
            .values_list('module', 'actif'))
        self.assertEqual(sorted(lignes), sorted(MODULES_OFF_PAR_DEFAUT))
        self.assertTrue(all(actif is False for actif in lignes.values()))

    def test_pack_pays_seulement_hors_maroc(self):
        maroc = Company.objects.create(nom='MA', slug='sol8-ma')
        self.assertEqual(maroc.pays, 'MA')
        for cle in PACK_PAYS_MAROC:
            self.assertNotIn(cle, modules_a_eteindre(maroc))

        france = Company.objects.create(nom='FR', slug='sol8-fr', pays='FR')
        for cle in PACK_PAYS_MAROC:
            self.assertIn(cle, modules_a_eteindre(france))
        semer_modules_off_par_defaut(france)
        eteints = set(
            ModuleToggle.objects.filter(company=france, actif=False)
            .values_list('module', flat=True))
        self.assertTrue(set(PACK_PAYS_MAROC).issubset(eteints))

    def test_pays_insensible_a_la_casse(self):
        company = Company.objects.create(nom='ma', slug='sol8-ma-min', pays='ma')
        for cle in PACK_PAYS_MAROC:
            self.assertNotIn(cle, modules_a_eteindre(company))

    def test_semis_idempotent(self):
        company = Company.objects.create(nom='Idem', slug='sol8-idem')
        semer_modules_off_par_defaut(company)
        avant = ModuleToggle.objects.filter(company=company).count()
        self.assertEqual(semer_modules_off_par_defaut(company), [])
        self.assertEqual(
            ModuleToggle.objects.filter(company=company).count(), avant)

    def test_semis_n_ecrase_jamais_une_reactivation(self):
        """Un module rallumé par l'admin le reste (get_or_create seulement)."""
        company = Company.objects.create(nom='Reac', slug='sol8-reac')
        ModuleToggle.objects.create(
            company=company, module='pos', actif=True)
        semer_modules_off_par_defaut(company)
        self.assertTrue(
            ModuleToggle.objects.get(company=company, module='pos').actif)


class AucunBackfillTests(TestCase):
    """Le cœur de SOL8 : ZÉRO ligne écrite pour une société préexistante."""

    def test_les_hooks_de_signup_ne_portent_pas_le_semis(self):
        from core import signup_hooks

        for nom in signup_hooks.registered_hooks():
            self.assertNotIn(
                'module', nom.lower(),
                f'hook « {nom} » : le semis SOL8 ne doit JAMAIS passer par le '
                'registre de hooks (rejoué par seed_company sur une société '
                'existante = backfill).')

    def test_run_signup_hooks_n_ecrit_aucun_toggle(self):
        from core.signup_hooks import run_signup_hooks

        existante = Company.objects.create(
            nom='Préexistante', slug='sol8-preexistante')
        run_signup_hooks(existante)
        self.assertEqual(
            ModuleToggle.objects.filter(company=existante).count(), 0,
            'un hook de signup a écrit un ModuleToggle : backfill interdit')

    def test_seed_company_n_ecrit_aucun_toggle(self):
        """`manage.py seed_company` sur une société EXISTANTE : 0 ligne."""
        existante = Company.objects.create(
            nom='Historique', slug='sol8-historique')
        call_command('seed_company', 'sol8-historique',
                     stdout=StringIO(), stderr=StringIO())
        self.assertEqual(
            ModuleToggle.objects.filter(company=existante).count(), 0,
            'seed_company a éteint des modules sur une société existante '
            '(TAQINOR utilise douane/scm en vrai) : backfill interdit')

    def test_autres_societes_intactes(self):
        voisine = Company.objects.create(nom='Voisine', slug='sol8-voisine')
        neuve = Company.objects.create(nom='Neuve', slug='sol8-neuve')
        semer_modules_off_par_defaut(neuve)
        self.assertEqual(
            ModuleToggle.objects.filter(company=voisine).count(), 0)


class ReactivationEnUnClicTests(TestCase):
    """Une clé éteinte au semis doit pouvoir être rallumée depuis l'écran."""

    def setUp(self):
        self.company = Company.objects.create(nom='Clic', slug='sol8-clic')
        semer_modules_off_par_defaut(self.company)

    def test_catalogue_expose_les_modules_eteints(self):
        catalogue = {
            row['key']: row for row in
            feature_flags.catalogue_modules(self.company)}
        for cle in ('pos', 'promotions', 'douane', 'transport', 'scm'):
            self.assertIn(cle, catalogue)
            self.assertFalse(catalogue[cle]['actif'], cle)

    def test_catalogue_expose_aussi_une_cle_sans_manifeste(self):
        """`magasin` n'a pas de manifeste backend : il reste rallumables."""
        catalogue = {
            row['key']: row for row in
            feature_flags.catalogue_modules(self.company)}
        self.assertIn('magasin', catalogue)
        self.assertFalse(catalogue['magasin']['actif'])
        self.assertTrue(catalogue['magasin']['installable'])
        self.assertTrue(catalogue['magasin']['label'])

    def test_reactivation_d_une_cle_sans_manifeste(self):
        feature_flags.activer_module(self.company, 'magasin')
        self.assertTrue(feature_flags.module_actif(self.company, 'magasin'))
        self.assertNotIn(
            'magasin', feature_flags.modules_desactives(self.company))

    def test_reactivation_d_un_module_avec_manifeste(self):
        feature_flags.activer_module(self.company, 'pos')
        self.assertTrue(feature_flags.module_actif(self.company, 'pos'))

    def test_cle_totalement_inconnue_reste_refusee(self):
        with self.assertRaises(feature_flags.DependencyError):
            feature_flags.activer_module(self.company, 'nimportequoi')

    def test_catalogue_inchange_sans_aucun_toggle(self):
        """Non-régression : sans ligne, le catalogue est celui d'avant SOL8."""
        vierge = Company.objects.create(nom='Vierge', slug='sol8-vierge')
        cles = {row['key'] for row in feature_flags.catalogue_modules(vierge)}
        self.assertNotIn('magasin', cles)
        self.assertIn('pos', cles)


class SignupPublicTests(TestCase):
    """Bout en bout : le signup public sème bien les modules éteints."""

    def test_register_company_seme_les_modules(self):
        url = reverse('auth_register_company')
        resp = self.client.post(url, {
            'company_nom': 'Solaire SOL8',
            'username': 'sol8admin',
            'email': 'sol8@example.com',
            'password': 'MotDePasse!2026',
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 201, resp.content)
        company = Company.objects.get(id=resp.json()['company_id'])
        eteints = set(
            ModuleToggle.objects.filter(company=company, actif=False)
            .values_list('module', flat=True))
        self.assertEqual(eteints, set(MODULES_OFF_PAR_DEFAUT))
        # Pack pays NON appliqué : un tenant créé par le signup est marocain.
        for cle in PACK_PAYS_MAROC:
            self.assertNotIn(cle, eteints)

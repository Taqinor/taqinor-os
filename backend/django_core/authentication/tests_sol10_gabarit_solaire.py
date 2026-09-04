"""SOL10 — gabarit de tenant « Solaire » : compose l'existant, n'invente rien.

Le test le plus important est celui du CHECKED-FACTS : hors Maroc, aucune ligne
de prix n'est écrite. Le catalogue seedé du dépôt est en MAD ; il n'existe
aucune source de prix EUR, donc le gabarit s'arrête à la STRUCTURE.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.adminops.plan_seeds import CODE_SOLAIRE
from apps.parametres.models import CompanyProfile
from apps.reporting.models import ALL_DASHBOARD_CARDS, DashboardConfig
from apps.stock.models import Categorie, Produit
from authentication.models import Company
from authentication.module_seeds import MODULES_OFF_PAR_DEFAUT
from authentication.tenant_templates import (
    CARTES_SOLAIRES, appliquer_gabarit_solaire,
)
from core import feature_flags
from core.models import ModuleToggle


class GabaritSolaireTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Installateur MA', slug='sol10-ma')

    def test_compose_les_cinq_briques(self):
        rapport = appliquer_gabarit_solaire(self.company)
        self.assertEqual(sorted(rapport['modules_eteints']),
                         sorted(MODULES_OFF_PAR_DEFAUT))
        self.assertEqual(rapport['plan'], CODE_SOLAIRE)
        self.assertTrue(rapport['roles'])
        self.assertTrue(rapport['catalogue']['categories'])
        self.assertEqual(sorted(rapport['dashboard']),
                         sorted(CARTES_SOLAIRES))

    def test_plan_solaire_assigne_au_profil(self):
        appliquer_gabarit_solaire(self.company)
        profil = CompanyProfile.objects.get(company=self.company)
        self.assertIsNotNone(profil.plan)
        self.assertEqual(profil.plan.code, CODE_SOLAIRE)

    def test_le_metier_solaire_reste_accessible_sous_le_plan(self):
        appliquer_gabarit_solaire(self.company)
        hors = feature_flags.modules_desactives(self.company)
        for cle in ('crm', 'ventes', 'stock', 'installations', 'sav'):
            self.assertNotIn(cle, hors, cle)
        # Les verticaux parqués, eux, sortent bien du plan.
        for cle in ('mrp', 'sante', 'education'):
            self.assertIn(cle, hors, cle)

    def test_modules_rares_eteints(self):
        appliquer_gabarit_solaire(self.company)
        eteints = set(
            ModuleToggle.objects.filter(company=self.company, actif=False)
            .values_list('module', flat=True))
        self.assertTrue(set(MODULES_OFF_PAR_DEFAUT).issubset(eteints))

    def test_dashboard_solaire_pose_par_palier(self):
        appliquer_gabarit_solaire(self.company)
        configs = {
            c.menu_tier: c.cards for c in
            DashboardConfig.objects.filter(company=self.company, user=None)}
        self.assertEqual(sorted(configs), sorted(CARTES_SOLAIRES))
        for palier, cartes in configs.items():
            self.assertTrue(cartes, palier)
            for carte in cartes:
                self.assertIn(carte, ALL_DASHBOARD_CARDS, carte)

    def test_structure_de_catalogue_posee(self):
        appliquer_gabarit_solaire(self.company)
        noms = set(
            Categorie.objects.filter(company=self.company)
            .values_list('nom', flat=True))
        self.assertIn('Panneaux photovoltaïques', noms)
        self.assertIn('Onduleurs hybrides', noms)
        self.assertIn('Batteries', noms)

    def test_idempotent(self):
        appliquer_gabarit_solaire(self.company)
        avant = (
            Categorie.objects.filter(company=self.company).count(),
            DashboardConfig.objects.filter(company=self.company).count(),
            ModuleToggle.objects.filter(company=self.company).count(),
        )
        rapport = appliquer_gabarit_solaire(self.company)
        apres = (
            Categorie.objects.filter(company=self.company).count(),
            DashboardConfig.objects.filter(company=self.company).count(),
            ModuleToggle.objects.filter(company=self.company).count(),
        )
        self.assertEqual(avant, apres)
        self.assertEqual(rapport['modules_eteints'], [])
        self.assertEqual(rapport['catalogue']['categories'], [])

    def test_isolation_multi_tenant(self):
        voisine = Company.objects.create(nom='Voisine', slug='sol10-voisine')
        appliquer_gabarit_solaire(self.company)
        self.assertEqual(
            Categorie.objects.filter(company=voisine).count(), 0)
        self.assertEqual(
            DashboardConfig.objects.filter(company=voisine).count(), 0)
        self.assertIsNone(
            CompanyProfile.objects.filter(company=voisine).first())


class CheckedFactsHorsMarocTests(TestCase):
    """Hors Maroc : STRUCTURE SEULE — jamais un prix inventé."""

    def setUp(self):
        self.france = Company.objects.create(
            nom='Installateur FR', slug='sol10-fr', pays='FR')

    def test_aucun_produit_ni_prix_hors_maroc(self):
        appliquer_gabarit_solaire(
            self.france, avec_catalogue_produits=True)
        self.assertEqual(
            Produit.objects.filter(company=self.france).count(), 0,
            "un produit (donc un prix) a été seedé pour un tenant hors Maroc : "
            'le catalogue du dépôt est en MAD, aucune source EUR n\'existe.')

    def test_la_structure_est_bien_posee_hors_maroc(self):
        rapport = appliquer_gabarit_solaire(self.france)
        self.assertTrue(rapport['catalogue']['categories'])
        self.assertFalse(rapport['catalogue']['produits'])
        self.assertTrue(
            Categorie.objects.filter(company=self.france).exists())

    def test_pack_pays_eteint_hors_maroc(self):
        appliquer_gabarit_solaire(self.france)
        eteints = set(
            ModuleToggle.objects.filter(company=self.france, actif=False)
            .values_list('module', flat=True))
        for cle in ('einvoice', 'fiscal', 'paie'):
            self.assertIn(cle, eteints, cle)

    def test_au_maroc_le_catalogue_reste_opt_in(self):
        maroc = Company.objects.create(nom='MA', slug='sol10-optin')
        rapport = appliquer_gabarit_solaire(maroc)
        self.assertFalse(rapport['catalogue']['produits'])
        self.assertEqual(Produit.objects.filter(company=maroc).count(), 0)

    def test_le_hook_de_signup_ne_seede_aucun_prix_hors_maroc(self):
        """Le trou réel : le hook SCA20 seedait le catalogue MAD partout."""
        from apps.stock.signup_hooks import seed_catalogue_hook

        seed_catalogue_hook(self.france)
        self.assertEqual(
            Produit.objects.filter(company=self.france).count(), 0)

    def test_le_hook_de_signup_seede_toujours_au_maroc(self):
        """Non-régression SCA20 : un tenant marocain garde son catalogue."""
        from apps.stock.signup_hooks import seed_catalogue_hook

        maroc = Company.objects.create(nom='MA hook', slug='sol10-hook-ma')
        seed_catalogue_hook(maroc)
        self.assertGreater(
            Produit.objects.filter(company=maroc).count(), 0)


class CommandeGabaritTests(TestCase):
    def test_commande_applique_et_rend_compte(self):
        Company.objects.create(nom='CLI', slug='sol10-cli')
        sortie = StringIO()
        call_command('appliquer_gabarit_solaire', 'sol10-cli', stdout=sortie)
        texte = sortie.getvalue()
        self.assertIn('Gabarit solaire appliqué', texte)
        self.assertIn('Plan de licence assigné', texte)
        self.assertIn('structure seule', texte)

    def test_commande_refuse_un_slug_inconnu(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command('appliquer_gabarit_solaire', 'inexistant',
                         stdout=StringIO())

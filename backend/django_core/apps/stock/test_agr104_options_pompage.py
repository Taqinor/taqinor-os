"""AGR104 — articles des options du kit pompage (prix à renseigner) + rôles
des articles existants (migration de données gardée sur « rôle vide »).
"""
import importlib
from io import StringIO

from django.apps import apps as django_apps
from django.core.management import call_command
from django.test import TestCase

from apps.stock.management.commands import seed_catalogue as seed_mod
from apps.stock.models import Produit
from authentication.models import Company
from core.product_roles import ROLES_POMPAGE

migration = importlib.import_module(
    'apps.stock.migrations.0162_agr104_roles_pompage')


def _seed(company):
    out = StringIO()
    call_command('seed_catalogue', company_slug=company.slug, stdout=out)
    return out.getvalue()


class OptionsPompageTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='agr104-co', defaults={'nom': 'AGR104 Co'})[0]

    def test_options_creees_a_prix_vide_avec_role_declare(self):
        _seed(self.co)
        for nom, sku, role, _q, _s in seed_mod.OPTIONS_POMPAGE:
            p = Produit.objects.get(company=self.co, sku=sku)
            self.assertEqual(p.nom, nom)
            self.assertEqual(p.role_pompage, role)
            self.assertIn(role, ROLES_POMPAGE)
            self.assertEqual(p.prix_vente, 0)
            self.assertEqual(p.prix_achat, 0)

    def test_sept_options_du_kit(self):
        self.assertEqual(
            {r for _n, _s, r, _q, _t in seed_mod.OPTIONS_POMPAGE},
            {'sonde_niveau', 'compteur_eau', 'cable_descente',
             'colonne_refoulement', 'clapet', 'tuyauterie', 'bassin'})

    def test_seeder_rejoue_deux_fois_aucun_doublon_aucun_prix_modifie(self):
        _seed(self.co)
        avant = dict(Produit.objects.filter(company=self.co)
                     .values_list('sku', 'prix_vente'))
        nb = Produit.objects.filter(company=self.co).count()
        _seed(self.co)
        self.assertEqual(Produit.objects.filter(company=self.co).count(), nb)
        apres = dict(Produit.objects.filter(company=self.co)
                     .values_list('sku', 'prix_vente'))
        self.assertEqual(avant, apres)
        for _n, sku, _r, _q, _s in seed_mod.OPTIONS_POMPAGE:
            self.assertEqual(
                Produit.objects.filter(company=self.co, sku=sku).count(), 1)

    def test_option_existante_jamais_reecrite(self):
        Produit.objects.create(
            company=self.co, nom='Clapet saisi par le fondateur',
            sku='CLAP-AR', prix_vente=77, role_pompage='')
        _seed(self.co)
        p = Produit.objects.get(company=self.co, sku='CLAP-AR')
        self.assertEqual(p.nom, 'Clapet saisi par le fondateur')
        self.assertEqual(p.prix_vente, 77)
        self.assertEqual(p.role_pompage, '')


class Pompage(TestCase):
    """AGQ36 (C-AGQ-004) — le kit minimum a un article de structure AU SOL
    à chiffrer (rôle ``structure_sol``), jamais la structure de toiture."""

    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='agq36-co', defaults={'nom': 'AGQ36 Co'})[0]

    def test_structure_sol_semee_a_prix_vide(self):
        from apps.stock.selectors import produits_pompage
        from core.product_roles import est_panneau
        _seed(self.co)
        p = Produit.objects.get(company=self.co, sku='STR-SOL-PMP')
        self.assertEqual(p.role_pompage, 'structure_sol')
        self.assertEqual(p.prix_vente, 0)
        self.assertEqual(p.prix_achat, 0)
        # Jamais lu comme un panneau (puissance crête, décompte de modules).
        self.assertFalse(est_panneau(p.nom))
        self.assertEqual(p.fiche_technique.struct_type_pose, 'sol')
        roles = {e['sku']: e.get('role_pompage')
                 for e in produits_pompage(self.co)}
        self.assertEqual(roles.get('STR-SOL-PMP'), 'structure_sol')
        # La structure de TOITURE reste sans rôle pompage.
        for toit in Produit.objects.filter(company=self.co,
                                           nom='Structures acier'):
            self.assertNotEqual(toit.role_pompage, 'structure_sol')

    def test_structure_sol_rejouee_sans_doublon_prix_saisi_garde(self):
        _seed(self.co)
        Produit.objects.filter(company=self.co, sku='STR-SOL-PMP').update(
            prix_vente=450)
        _seed(self.co)
        qs = Produit.objects.filter(company=self.co, sku='STR-SOL-PMP')
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.get().prix_vente, 450)


class MigrationRolesTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='agr104-mig-co', defaults={'nom': 'AGR104 Mig Co'})[0]
        _seed(self.co)
        # Le seeder ne déclare pas le rôle des SKU historiques : état de prod.
        Produit.objects.filter(company=self.co).exclude(
            sku__in=[r[1] for r in seed_mod.OPTIONS_POMPAGE]
        ).update(role_pompage='')

    def _role(self, sku):
        return Produit.objects.get(company=self.co, sku=sku).role_pompage

    def test_roles_declares_par_code(self):
        migration.declarer_roles(django_apps, None)
        self.assertEqual(self._role('PMP-IMM-5.5T'), 'pompe')
        self.assertEqual(self._role('PMP-SUR-3T'), 'pompe')
        self.assertEqual(self._role('PMP-OSP-30-8'), 'pompe')
        self.assertEqual(self._role('VEI-SI23-5.5-380'), 'variateur_pompage')
        self.assertEqual(self._role('VEI-SI22-AFF'), 'afficheur_variateur')
        self.assertEqual(self._role('PARA-DC-T2-1000'), 'protection_dc')
        self.assertEqual(self._role('CAB-6MM-M'), 'cable_dc')
        # protections AC : jamais déclarées
        self.assertEqual(self._role('DISJ-AC-C-16-1P'), '')

    def test_aucun_prix_ni_nom_touche(self):
        avant = {p.sku: (p.nom, p.prix_vente, p.prix_achat)
                 for p in Produit.objects.filter(company=self.co)}
        migration.declarer_roles(django_apps, None)
        apres = {p.sku: (p.nom, p.prix_vente, p.prix_achat)
                 for p in Produit.objects.filter(company=self.co)}
        self.assertEqual(avant, apres)

    def test_role_deja_saisi_pas_reecrit(self):
        Produit.objects.filter(
            company=self.co, sku='PMP-IMM-3M').update(role_pompage='bassin')
        migration.declarer_roles(django_apps, None)
        self.assertEqual(self._role('PMP-IMM-3M'), 'bassin')

    def test_aller_retour(self):
        migration.declarer_roles(django_apps, None)
        migration.declarer_roles(django_apps, None)  # idempotent
        self.assertEqual(self._role('PMP-IMM-4T'), 'pompe')
        migration.retirer_roles(django_apps, None)
        self.assertEqual(self._role('PMP-IMM-4T'), '')
        self.assertEqual(self._role('VEI-SI22-AFF'), '')
        # les options du seeder (rôle déclaré à la création) ne sont pas dans
        # la table de la migration : le retour n'y touche pas.
        self.assertEqual(self._role('SONDE-NIV'), 'sonde_niveau')

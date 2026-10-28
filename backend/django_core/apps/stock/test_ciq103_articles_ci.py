"""CIQ103 — articles C&I génériques « prix à renseigner » + rôle C&I des
articles existants (migration de données gardée sur « rôle vide »).
"""
import importlib
from io import StringIO

from django.apps import apps as django_apps
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.stock.management.commands import seed_catalogue as seed_mod
from apps.stock.models import FicheTechnique, Produit
from authentication.models import Company
from core.electrique.cables import SECTIONS_MM2_CI
from core.electrique.protections import CALIBRES_DISJONCTEUR_CI_A
from core.product_roles import ROLES_CI, TYPES_POSE

migration = importlib.import_module(
    'apps.stock.migrations.0164_ciq103_roles_ci_existants')

ROLES_ATTENDUS = {
    'compteur_injection', 'controleur_injection', 'logger_supervision',
    'cable_ac', 'protection_ac', 'coffret_ac', 'coffret_dc', 'structure_ci',
    'cellule_mt', 'protection_dc', 'mise_a_la_terre', 'etudes_ingenierie', 'pose_structure', 'pose_modules',
    'raccordement_ac', 'mise_en_service', 'dossier_raccordement',
    'levage_acces', 'transport_ci', 'om_ci',
}


def _seed(company):
    out = StringIO()
    call_command('seed_catalogue', company_slug=company.slug, stdout=out)
    return out.getvalue()


class TestListe(SimpleTestCase):
    def test_roles_et_types_dans_le_vocabulaire(self):
        for (_n, _s, role, pose, _q, _t,
             _f) in seed_mod.ARTICLES_CI_PRIX_A_RENSEIGNER:
            self.assertIn(role, ROLES_CI)
            if pose:
                self.assertIn(pose, TYPES_POSE)

    def test_couverture_des_roles(self):
        roles = {r for _n, _s, r, _p, _q, _t, _f
                 in seed_mod.ARTICLES_CI_PRIX_A_RENSEIGNER}
        self.assertEqual(roles, ROLES_ATTENDUS)
        # aucun onduleur ni batterie C&I inventés
        self.assertNotIn('onduleur_string_tri', roles)
        self.assertNotIn('batterie_ci', roles)

    def test_sections_et_calibres_exactement_les_listes_du_moteur(self):
        sections = [f['cable_section_mm2'] for *_x, f
                    in seed_mod.ARTICLES_CI_PRIX_A_RENSEIGNER
                    if f and f['type_fiche'] == 'cable']
        self.assertEqual(sorted(sections),
                         sorted(float(s) for s in SECTIONS_MM2_CI))
        for prot in ('disjoncteur', 'sectionneur'):
            calibres = [f['prot_calibre_a'] for *_x, f
                        in seed_mod.ARTICLES_CI_PRIX_A_RENSEIGNER
                        if f and f.get('prot_type') == prot]
            self.assertEqual(sorted(calibres),
                             sorted(float(c) for c in
                                    CALIBRES_DISJONCTEUR_CI_A))

    def test_noms_sans_le_mot_panneau(self):
        for nom, *_x in seed_mod.ARTICLES_CI_PRIX_A_RENSEIGNER:
            self.assertNotIn('panneau', nom.lower())

    def test_skus_semes(self):
        for _n, sku, *_x in seed_mod.ARTICLES_CI_PRIX_A_RENSEIGNER:
            self.assertIn(sku, seed_mod.SKUS_SEMES)


NOUVEAUX_SKUS_CCAT10 = (
    'CI-PROT-DC', 'CI-PARAF-DC', 'CI-PARAF-AC', 'CI-TERRE',
    'CI-STRUCT-INCL', 'CI-STRUCT-PLAT-FIXE', 'CI-STRUCT-SOL')


class PariteCompositionTests(SimpleTestCase):
    """CCAT10 — chaque poste que ``composer_ci`` cherche par rôle ET fiche a
    un article semé : parité calculée par la composition elle-même."""

    @staticmethod
    def _catalogue():
        return [{
            'id': 1000 + j, 'nom': nom, 'sku': sku, 'marque': '',
            'role_devis': '', 'role_ci': role, 'classement': 'declare',
            'type_pose': pose, 'fiche': dict(fiche) if fiche else None,
            'prix_connu': False, 'eligible_ci': True,
            'motif_exclusion': None}
            for j, (nom, sku, role, pose, _q, _s, fiche) in enumerate(
                seed_mod.ARTICLES_CI_PRIX_A_RENSEIGNER)]

    def test_chaque_poste_demande_par_la_composition_a_un_article_seme(self):
        from apps.ventes.moteur_ci.composition import composer_ci
        cat = self._catalogue()
        par_id = {p['id']: p['sku'] for p in cat}
        ond = {'combinaison': [{'produit': 1, 'nom': 'Ond', 'kw_ac': 50,
                                'quantite': 1}]}
        for pose in TYPES_POSE:
            comp = composer_ci(
                60, cat, onduleurs=ond, forfaits={}, entrees={
                    'module': {'produit': 999, 'designation': 'Module',
                               'pmax_wc': 710, 'prix_connu': True},
                    'phase': 'tri', 'tension': 'BT', 'type_pose': pose,
                    'longueur_dc_m': 40, 'longueur_ac_m': 30,
                    'nb_points_raccordement': 1, 'revente_choisie': False})
            codes = [a.get('code') for a in comp['alertes']]
            self.assertNotIn('POSTE_ABSENT_CATALOGUE', codes, pose)
            skus = {par_id.get(ligne['produit']) for ligne in comp['lignes']}
            for sku in ('CI-PROT-DC', 'CI-PARAF-DC', 'CI-PARAF-AC',
                        'CI-TERRE'):
                self.assertIn(sku, skus, (pose, sku))
            structure = next(ligne for ligne in comp['lignes']
                             if ligne['role'] == 'structure_ci')
            self.assertIsNotNone(structure['produit'], pose)
            self.assertTrue(
                [p for p in cat if p['id'] == structure['produit']
                 and p['type_pose'] == pose], pose)

    def test_nouveaux_skus_a_prix_vide_et_sans_marque_inventee(self):
        lignes = {row[1]: row for row
                  in seed_mod.ARTICLES_CI_PRIX_A_RENSEIGNER}
        for sku in NOUVEAUX_SKUS_CCAT10:
            self.assertIn(sku, lignes)
        for sku in ('CI-PROT-DC', 'CI-PARAF-DC', 'CI-PARAF-AC'):
            fiche = lignes[sku][6]
            self.assertEqual(fiche['type_fiche'], 'protection')
        self.assertEqual(lignes['CI-PROT-DC'][6]['prot_cote'], 'dc')
        self.assertEqual(lignes['CI-PARAF-DC'][6]['prot_type'], 'parafoudre')
        self.assertEqual(lignes['CI-PARAF-AC'][6]['prot_cote'], 'ac')


class ArticlesCiTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='ciq103-co', defaults={'nom': 'CIQ103 Co'})[0]

    def test_articles_crees_a_prix_vide_avec_role_declare(self):
        _seed(self.co)
        for (nom, sku, role, pose, _q, _s,
             fiche) in seed_mod.ARTICLES_CI_PRIX_A_RENSEIGNER:
            p = Produit.objects.get(company=self.co, sku=sku)
            self.assertEqual(p.nom, nom)
            self.assertEqual(p.role_ci, role)
            self.assertEqual(p.type_pose, pose)
            self.assertEqual(p.prix_vente, 0)
            self.assertEqual(p.prix_achat, 0)
            self.assertIsNone(p.role_devis)  # role_devis non touché

    def test_fiches_portent_seulement_la_grandeur_de_designation(self):
        _seed(self.co)
        cables = FicheTechnique.objects.filter(
            produit__company=self.co, type_fiche='cable')
        self.assertTrue(cables.exists())
        for f in cables:
            self.assertIn(f.cable_section_mm2,
                          [float(s) for s in SECTIONS_MM2_CI])
            self.assertEqual(f.cable_cote, 'ac')
            self.assertEqual(f.cable_ame, 'cu')
        disj = FicheTechnique.objects.filter(
            produit__company=self.co, type_fiche='protection',
            prot_type='disjoncteur')
        self.assertTrue(disj.exists())
        for f in disj:
            self.assertIn(f.prot_calibre_a,
                          [float(c) for c in CALIBRES_DISJONCTEUR_CI_A])
            self.assertIsNone(f.prot_pouvoir_coupure_ka)
            self.assertIsNone(f.prot_tension_v)
        for f in FicheTechnique.objects.filter(
                produit__company=self.co, type_fiche='structure'):
            self.assertIsNone(f.struct_masse_kg_m2)
        for f in FicheTechnique.objects.filter(
                produit__company=self.co, type_fiche='limiteur'):
            self.assertIsNone(f.lim_onduleurs_max)
            self.assertEqual(f.lim_marques, [])

    def test_aucun_article_ci_avec_un_prix(self):
        _seed(self.co)
        skus = [s for _n, s, *_x in seed_mod.ARTICLES_CI_PRIX_A_RENSEIGNER]
        self.assertFalse(Produit.objects.filter(
            company=self.co, sku__in=skus, prix_vente__gt=0).exists())

    def test_seeder_rejoue_deux_fois_aucun_doublon_aucun_prix_modifie(self):
        _seed(self.co)
        avant = dict(Produit.objects.filter(company=self.co)
                     .values_list('sku', 'prix_vente'))
        nb = Produit.objects.filter(company=self.co).count()
        nb_fiches = FicheTechnique.objects.filter(
            produit__company=self.co).count()
        _seed(self.co)
        self.assertEqual(Produit.objects.filter(company=self.co).count(), nb)
        self.assertEqual(FicheTechnique.objects.filter(
            produit__company=self.co).count(), nb_fiches)
        apres = dict(Produit.objects.filter(company=self.co)
                     .values_list('sku', 'prix_vente'))
        self.assertEqual(avant, apres)

    def test_prix_saisi_jamais_reecrit(self):
        _seed(self.co)
        Produit.objects.filter(company=self.co, sku='CI-OM').update(
            prix_vente=5000)
        _seed(self.co)
        self.assertEqual(
            Produit.objects.get(company=self.co, sku='CI-OM').prix_vente, 5000)

    def test_ccat10_nouveaux_articles_prix_zero_et_idempotents(self):
        _seed(self.co)
        for sku in NOUVEAUX_SKUS_CCAT10:
            qs = Produit.objects.filter(company=self.co, sku=sku)
            self.assertEqual(qs.count(), 1, sku)
            self.assertEqual(qs.get().prix_vente, 0, sku)
            self.assertEqual(qs.get().prix_achat, 0, sku)
        _seed(self.co)
        for sku in NOUVEAUX_SKUS_CCAT10:
            self.assertEqual(Produit.objects.filter(
                company=self.co, sku=sku).count(), 1, sku)

    def test_ccat10_cables_ac_marque_nexans_seulement_si_vide(self):
        _seed(self.co)
        cables = Produit.objects.filter(
            company=self.co, sku__startswith='CI-CAB-AC-')
        self.assertTrue(cables.exists())
        for p in cables:
            self.assertEqual(p.marque, 'Nexans', p.sku)
        un = cables.first()
        Produit.objects.filter(pk=un.pk).update(marque='Autre')
        _seed(self.co)
        un.refresh_from_db()
        self.assertEqual(un.marque, 'Autre')

    def test_smart_meter_recoit_son_role_ci_au_seed(self):
        _seed(self.co)
        p = Produit.objects.get(company=self.co, sku='SMART-MET')
        self.assertEqual(p.role_ci, 'compteur_injection')


class MigrationRolesCiTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='ciq103-mig', defaults={'nom': 'CIQ103 Mig'})[0]

    def test_aller_retour(self):
        p = Produit.objects.create(
            company=self.co, nom='Smart Meter', sku='SMART-MET',
            prix_vente=1500)
        migration.declarer_roles_ci(django_apps, None)
        p.refresh_from_db()
        self.assertEqual(p.role_ci, 'compteur_injection')
        self.assertEqual(p.nom, 'Smart Meter')
        self.assertEqual(p.prix_vente, 1500)
        migration.retirer_roles_ci(django_apps, None)
        p.refresh_from_db()
        self.assertEqual(p.role_ci, '')

    def test_role_deja_saisi_jamais_reecrit(self):
        p = Produit.objects.create(
            company=self.co, nom='Smart Meter', sku='SMART-MET',
            prix_vente=1500, role_ci='controleur_injection')
        migration.declarer_roles_ci(django_apps, None)
        p.refresh_from_db()
        self.assertEqual(p.role_ci, 'controleur_injection')
        migration.retirer_roles_ci(django_apps, None)
        p.refresh_from_db()
        self.assertEqual(p.role_ci, 'controleur_injection')

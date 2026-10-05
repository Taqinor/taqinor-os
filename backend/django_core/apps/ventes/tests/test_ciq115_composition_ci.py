"""CIQ115 — composition C&I serveur (BOQ).

Catalogue = les onduleurs Huawei seedés + les articles C&I génériques de
CIQ103 (``seed_catalogue.ARTICLES_CI_PRIX_A_RENSEIGNER``), lus dans les tables
du seeder (jamais recopiés). Module PUR : aucun Django, aucune base.
"""
import ast
import math
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from apps.stock.management.commands.seed_catalogue import (
    ARTICLES_CI_PRIX_A_RENSEIGNER, CATALOGUE, ht_at,
)
from apps.ventes.moteur_ci.composition import composer_ci
from apps.ventes.moteur_ci.onduleurs import combiner_onduleurs
from core.electrique.cables import SECTIONS_MM2_CI

CHEMIN = (Path(__file__).resolve().parent.parent / 'moteur_ci'
          / 'composition.py')
MODULE = {'produit': 999, 'designation': 'Panneau 710 W', 'pmax_wc': 710,
          'prix_connu': True}


def _catalogue():
    out = []
    for i, (nom, sku, _c, ttc, _a, _q, _s) in enumerate(CATALOGUE):
        if sku.startswith('OND-R-HUA-') and sku.endswith('T'):
            out.append({
                'id': i + 1, 'nom': nom, 'marque': 'Huawei',
                'role_devis': 'onduleur_reseau',
                'role_ci': 'onduleur_string_tri', 'classement': 'fiche',
                'type_pose': '', 'fiche': None, 'prix_connu': True,
                'eligible_ci': True, 'motif_exclusion': None,
                'kw_ac': float(sku.split('-')[3][:-1]),
                'prix': ht_at(ttc, Decimal('20'))})
    for j, (nom, _sku, role, pose, _q, _s, fiche) in enumerate(
            ARTICLES_CI_PRIX_A_RENSEIGNER):
        out.append({
            'id': 1000 + j, 'nom': nom, 'marque': '', 'role_devis': '',
            'role_ci': role, 'classement': 'declare', 'type_pose': pose,
            'fiche': dict(fiche) if fiche else None, 'prix_connu': False,
            'eligible_ci': True, 'motif_exclusion': None})
    return out


def _onduleurs(cat, kwc, chaines=None):
    candidats = [{'produit': p['id'], 'nom': p['nom'], 'kw_ac': p['kw_ac'],
                  'prix': p['prix'], 'triphase': True, 'eligible_ci': True}
                 for p in cat if p['role_ci'] == 'onduleur_string_tri']
    r = combiner_onduleurs(kwc, candidats, phase='tri')
    if chaines is not None:
        r = {**r, 'chaines': chaines}
    return r


def _cles(objet):
    if isinstance(objet, dict):
        for k, v in objet.items():
            yield k
            yield from _cles(v)
    elif isinstance(objet, list):
        for v in objet:
            yield from _cles(v)


def _entrees(**kw):
    base = {'module': MODULE, 'phase': 'tri', 'tension': 'BT',
            'type_pose': 'bac_acier', 'longueur_dc_m': 40,
            'longueur_ac_m': 30, 'nb_points_raccordement': 1,
            'revente_choisie': False}
    base.update(kw)
    return base


class CompositionTests(TestCase):
    def setUp(self):
        self.cat = _catalogue()

    def _lignes(self, comp, role):
        return [ligne for ligne in comp['lignes'] if ligne['role'] == role]

    def test_cable_dc_somme_des_chaines_fois_longueur(self):
        chaines = [{'produit': 1, 'nb_modules': 70, 'nb_chaines': 5,
                    'bloquants': []},
                   {'produit': 2, 'nb_modules': 71, 'nb_chaines': 5,
                    'bloquants': []}]
        ond = {'combinaison': [{'produit': 1, 'nom': 'A', 'kw_ac': 50,
                                'quantite': 2}], 'chaines': chaines}
        comp = composer_ci(100, self.cat, onduleurs=ond,
                           entrees=_entrees(longueur_dc_m=40), forfaits={})
        dc = self._lignes(comp, 'cable_dc')[0]
        self.assertEqual(dc['quantite'], 10 * 40)
        self.assertNotEqual(dc['quantite'], 60)

    def test_onduleur_150_a_30m_cable_ac_bareme_etendu(self):
        ond = {'combinaison': [{'produit': 1, 'nom': 'Ond 150',
                                'kw_ac': 150, 'quantite': 1}]}
        comp = composer_ci(190, self.cat, onduleurs=ond,
                           entrees=_entrees(longueur_ac_m=30), forfaits={})
        ac = self._lignes(comp, 'cable_ac')[0]
        if ac['motif'] and 'bureau' in ac['motif']:
            self.assertTrue(ac['a_confirmer_visite'])
        else:
            # section prise dans le barème ÉTENDU (> 25 mm²), jamais 25 par défaut
            self.assertIsNotNone(ac['produit'])
            section = next(p['fiche']['cable_section_mm2'] for p in self.cat
                           if p['id'] == ac['produit'])
            self.assertIn(section, SECTIONS_MM2_CI)
            self.assertGreater(section, 25.0)
        self.assertEqual(ac['quantite'], 30)

    def test_longueur_non_declaree_sans_quantite(self):
        ond = {'combinaison': [{'produit': 1, 'nom': 'X', 'kw_ac': 50,
                                'quantite': 1}]}
        comp = composer_ci(60, self.cat, onduleurs=ond,
                           entrees=_entrees(longueur_ac_m=None), forfaits={})
        ac = self._lignes(comp, 'cable_ac')[0]
        self.assertIsNone(ac['quantite'])
        self.assertTrue(ac['a_confirmer_visite'])

    def test_trois_onduleurs_sans_revente_comptage_present(self):
        ond = {'combinaison': [{'produit': 1, 'nom': 'X', 'kw_ac': 50,
                                'quantite': 3}]}
        comp = composer_ci(180, self.cat, onduleurs=ond, entrees=_entrees(),
                           forfaits={})
        comptage = [ligne for ligne in comp['lignes'] if ligne['role'] in (
            'compteur_injection', 'controleur_injection')]
        self.assertEqual(len(comptage), 1)
        self.assertIn('à confirmer fournisseur', comptage[0]['motif'])
        self.assertEqual(len(self._lignes(comp, 'logger_supervision')), 1)

    def test_lim_onduleurs_max_publie_fixe_la_quantite(self):
        cat = [dict(p) for p in self.cat]
        for p in cat:
            if p['role_ci'] == 'controleur_injection':
                p['fiche'] = {**(p['fiche'] or {}), 'lim_onduleurs_max': 2}
        ond = {'combinaison': [{'produit': 1, 'nom': 'X', 'kw_ac': 50,
                                'quantite': 3}]}
        comp = composer_ci(180, cat, onduleurs=ond, entrees=_entrees(),
                           forfaits={})
        ligne = self._lignes(comp, 'controleur_injection')[0]
        self.assertEqual(ligne['quantite'], 2)

    def test_aucun_hybride_ni_batterie(self):
        comp = composer_ci(100, self.cat, onduleurs=_onduleurs(self.cat, 100),
                           entrees=_entrees(), forfaits={})
        for ligne in comp['lignes']:
            self.assertNotIn(ligne['role'], ('batterie', 'batterie_ci',
                                             'onduleur_hybride'))
            self.assertNotIn('hybride', (ligne['designation'] or '').lower())
        self.assertEqual([o['cle'] for o in comp['options']], ['om'])

    def test_forfaits_non_regles_prix_a_renseigner_et_incomplet(self):
        comp = composer_ci(100, self.cat, onduleurs=_onduleurs(self.cat, 100),
                           entrees=_entrees(), forfaits={})
        pose = self._lignes(comp, 'pose_modules')[0]
        self.assertFalse(pose['prix_connu'])
        self.assertIn('prix à renseigner', pose['motif'])
        self.assertTrue(comp['incomplet'])
        self.assertIn(pose['designation'], comp['prix_a_renseigner'])

    def test_forfait_regle_chiffre(self):
        forfaits = {'pose_modules': {'fixe_ht': '1000', 'par_kwc_ht': '50',
                                     'par_panneau_ht': None,
                                     'source': 'Devis pose', 'date': None}}
        comp = composer_ci(100, self.cat, onduleurs=_onduleurs(self.cat, 100),
                           entrees=_entrees(), forfaits=forfaits)
        pose = self._lignes(comp, 'pose_modules')[0]
        self.assertTrue(pose['prix_connu'])
        self.assertEqual(Decimal(pose['prix_unitaire_ht']), Decimal('6000.00'))

    def test_site_mt_sans_visite_alerte_sans_cellule(self):
        comp = composer_ci(300, self.cat, onduleurs=_onduleurs(self.cat, 300),
                           entrees=_entrees(tension='MT'), forfaits={})
        self.assertEqual(self._lignes(comp, 'cellule_mt'), [])
        self.assertTrue(any(a['code'] == 'CI_POSTE_LIVRAISON'
                            for a in comp['alertes']))

    def test_structure_du_type_de_pose(self):
        comp = composer_ci(100, self.cat, onduleurs=_onduleurs(self.cat, 100),
                           entrees=_entrees(type_pose='toit_plat_leste'),
                           forfaits={})
        structure = self._lignes(comp, 'structure_ci')[0]
        article = next(p for p in self.cat if p['id'] == structure['produit'])
        self.assertEqual(article['type_pose'], 'toit_plat_leste')
        self.assertEqual(structure['quantite'], math.ceil(100000 / 710))

    def test_aucune_cle_prix_achat(self):
        comp = composer_ci(100, self.cat, onduleurs=_onduleurs(self.cat, 100),
                           entrees=_entrees(), forfaits={})
        cles = set(_cles(comp))
        self.assertNotIn('prix_achat', cles)
        self.assertNotIn('marge', cles)


class GardeAstTests(TestCase):
    def test_module_pur(self):
        arbre = ast.parse(CHEMIN.read_text(encoding='utf-8'))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ImportFrom):
                mod = noeud.module or ''
            elif isinstance(noeud, ast.Import):
                mod = noeud.names[0].name
            else:
                continue
            self.assertFalse(mod.startswith(('django', 'apps', 'rest_framework')),
                             mod)

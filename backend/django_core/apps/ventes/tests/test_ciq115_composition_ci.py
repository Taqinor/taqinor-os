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
    ARTICLES_CI_PRIX_A_RENSEIGNER, CATALOGUE, FICHES, FICHES_TECHNIQUES,
    ROLES_CI_ARTICLES_EXISTANTS, ht_at,
)
from apps.ventes.moteur_ci.composition import (
    ROLES_SUPERVISION_CI, ROLES_TABLEAU_CI, composer_ci, groupe_client_du_role,
)
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
        # D-CMP-2 — 2 conducteurs (+ / −) × 10 chaînes × 40 m aller simple.
        self.assertEqual(dc['quantite'], 2 * 10 * 40)
        self.assertNotEqual(dc['quantite'], 10 * 40)
        hyp = next(h for h in comp['hypotheses'] if h['cle'] == 'cable_dc_m')
        self.assertEqual(hyp['valeur'], 800)
        self.assertIn('2 × 10 chaînes × 40 m', hyp['source'])

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

    def test_longueur_non_declaree_estimee_jamais_vide(self):
        # Fondateur 26/10/2026 — devis préliminaire : 30 m par onduleur,
        # chiffré, ajusté après la visite (jamais une ligne vide).
        ond = {'combinaison': [{'produit': 1, 'nom': 'X', 'kw_ac': 50,
                                'quantite': 1}]}
        comp = composer_ci(60, self.cat, onduleurs=ond,
                           entrees=_entrees(longueur_ac_m=None), forfaits={})
        ac = self._lignes(comp, 'cable_ac')[0]
        self.assertEqual(ac['quantite'], 30.0)
        self.assertTrue(ac['a_confirmer_visite'])
        self.assertFalse(ac.get('a_chiffrer_visite'))

    def test_cable_dc_et_structure_estimes_avant_visite(self):
        # Chaînes non calculées : 1 chaîne / 12 panneaux, 2 × chaînes × 30 m ;
        # type de toit inconnu : toit plat lesté.
        ond = {'combinaison': [{'produit': 1, 'nom': 'X', 'kw_ac': 50,
                                'quantite': 1}]}
        comp = composer_ci(40, self.cat, onduleurs=ond,
                           entrees=_entrees(longueur_dc_m=None, type_pose=''),
                           forfaits={})
        nb_pan = math.ceil(40 * 1000 / 710)
        dc = self._lignes(comp, 'cable_dc')[0]
        self.assertEqual(dc['quantite'], 2 * math.ceil(nb_pan / 12) * 30.0)
        structure = self._lignes(comp, 'structure_ci')[0]
        poses = {p['id']: p['type_pose'] for p in self.cat}
        self.assertEqual(poses[structure['produit']], 'toit_plat_leste')
        self.assertEqual(comp['a_chiffrer_visite'], [])

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

    # ── ADEV82 : composition cohérente avec le devis écrit ──────────────────

    def test_palier_prix_unitaire_ht_de_la_ligne_est_le_prix_de_palier(self):
        cat = [dict(p) for p in self.cat]
        for p in cat:
            if p['role_ci'] == 'structure_ci' and p['type_pose'] == 'bac_acier':
                p.update(prix_connu=True, prix_vente_ht=Decimal('300'), tva_pct=Decimal('20'),
                         paliers_prix_vente=[{'seuil_min': 1, 'seuil_max': None,
                                              'prix_vente_ttc': '240'}])
        module = dict(MODULE, prix_vente_ht=Decimal('1000'), tva_pct=Decimal('10'),
                      paliers_prix_vente=[{'seuil_min': 1, 'seuil_max': None,
                                           'prix_vente_ttc': '880'}])
        comp = composer_ci(100, cat, onduleurs=_onduleurs(cat, 100),
                           entrees=_entrees(module=module), forfaits={})
        structure = self._lignes(comp, 'structure_ci')[0]
        self.assertEqual(structure['prix_unitaire_ht'], '200.00')
        self.assertEqual(self._lignes(comp, 'panneau')[0]['prix_unitaire_ht'], '800.00')

    def test_compteur_compatible_tarife_prefere_au_controleur_sans_prix(self):
        cat = [dict(p) for p in self.cat]
        for p in cat:
            if p['role_ci'] == 'onduleur_string_tri':
                p['fiche'] = {'ond_compteurs_compatibles': ['DTSU666-H']}
        cat += [{'id': 5000, 'nom': 'Smart Meter DTSU666-H', 'marque': 'Huawei',
                 'role_devis': '', 'role_ci': 'compteur_injection', 'classement': 'declare',
                 'type_pose': '', 'fiche': None, 'prix_connu': True,
                 'prix_vente_ht': Decimal('1800'), 'eligible_ci': True,
                 'motif_exclusion': None},
                {'id': 5001, 'nom': 'Compteur générique', 'marque': '',
                 'role_devis': '', 'role_ci': 'compteur_injection', 'classement': 'declare',
                 'type_pose': '', 'fiche': None, 'prix_connu': True,
                 'prix_vente_ht': Decimal('900'), 'eligible_ci': True,
                 'motif_exclusion': None}]
        self.assertTrue(any(p['role_ci'] == 'controleur_injection' and not p['prix_connu']
                            for p in cat))
        comp = composer_ci(100, cat, onduleurs=_onduleurs(cat, 100), entrees=_entrees(),
                           forfaits={})
        comptage = [ligne for ligne in comp['lignes'] if ligne['role'] in (
            'compteur_injection', 'controleur_injection')]
        self.assertEqual(len(comptage), 1)
        self.assertEqual(comptage[0]['produit'], 5000)
        self.assertTrue(comptage[0]['prix_connu'])

    def test_logger_a_fiche_publiee_n_est_plus_a_confirmer(self):
        cat = [dict(p) for p in self.cat if p['role_ci'] != 'logger_supervision']
        cat.append({'id': 5002, 'nom': 'SmartLogger 3000', 'marque': 'Huawei',
                    'role_devis': '', 'role_ci': 'logger_supervision', 'classement': 'declare',
                    'type_pose': '', 'fiche': {'log_onduleurs_max': 80}, 'prix_connu': True,
                    'prix_vente_ht': Decimal('4500'), 'eligible_ci': True,
                    'motif_exclusion': None})
        ond = {'combinaison': [{'produit': 1, 'nom': 'X', 'kw_ac': 50, 'quantite': 3}]}
        comp = composer_ci(180, cat, onduleurs=ond, entrees=_entrees(), forfaits={})
        logger = self._lignes(comp, 'logger_supervision')[0]
        self.assertEqual(logger['produit'], 5002)
        self.assertFalse(logger['a_confirmer_visite'])
        self.assertIsNone(logger['motif'])
        self.assertEqual(logger['quantite'], 1)

    # ── CMP10 (D-CMP-6) : comptage / logger de la marque des onduleurs ───────

    @staticmethod
    def _accessoire(id_, nom, role, marque, prix='900', fiche=None):
        return {'id': id_, 'nom': nom, 'marque': marque, 'role_devis': '', 'role_ci': role,
                'classement': 'declare', 'type_pose': '', 'fiche': fiche, 'prix_connu': True,
                'prix_vente_ht': Decimal(prix), 'eligible_ci': True, 'motif_exclusion': None}

    def _cat_marque(self, marque, *accessoires):
        cat = [dict(p, marque=marque) if p['role_ci'] == 'onduleur_string_tri' else dict(p)
               for p in self.cat if p['role_ci'] not in ('logger_supervision',)]
        return cat + list(accessoires)

    def _comptage_et_logger(self, cat, kwc=180):
        premier = next(p for p in cat if p['role_ci'] == 'onduleur_string_tri')
        ond = {'combinaison': [{'produit': premier['id'], 'nom': premier['nom'],
                                'kw_ac': premier['kw_ac'], 'quantite': 3}]}
        comp = composer_ci(kwc, cat, onduleurs=ond, entrees=_entrees(), forfaits={})
        comptage = [ligne for ligne in comp['lignes'] if ligne['role'] in (
            'compteur_injection', 'controleur_injection')]
        self.assertEqual(len(comptage), 1)
        return comp, comptage[0], self._lignes(comp, 'logger_supervision')

    def _codes(self, comp):
        return {a['code'] for a in comp['alertes']}

    def test_deye_et_compteur_huawei_seul_garde_l_article_et_alerte_la_marque(self):
        cat = self._cat_marque('Deye', self._accessoire(
            5100, 'Smart Meter DTSU666-H', 'compteur_injection', 'Huawei'))
        comp, comptage, _logger = self._comptage_et_logger(cat)
        self.assertEqual(comptage['produit'], 5100)
        alerte = next(a for a in comp['alertes'] if a['code'] == 'COMPTAGE_MARQUE_A_CONFIRMER')
        self.assertTrue(alerte['interne'])
        self.assertIn('deye', alerte['message'])

    def test_deye_et_compteur_deye_prend_le_compteur_deye(self):
        cat = self._cat_marque(
            'Deye',
            self._accessoire(5100, 'Smart Meter DTSU666-H', 'compteur_injection', 'Huawei'),
            self._accessoire(5101, 'Compteur Deye triphasé', 'compteur_injection', 'Deye'))
        comp, comptage, _logger = self._comptage_et_logger(cat)
        self.assertEqual(comptage['produit'], 5101)
        self.assertNotIn('COMPTAGE_MARQUE_A_CONFIRMER', self._codes(comp))

    def test_compteur_declare_compatible_par_la_fiche_prefere_a_la_marque(self):
        cat = self._cat_marque(
            'Deye',
            self._accessoire(5090, 'Compteur Deye', 'compteur_injection', 'Deye'),
            self._accessoire(5100, 'Smart Meter DTSU666-H', 'compteur_injection', 'Huawei'))
        for p in cat:
            if p['role_ci'] == 'onduleur_string_tri':
                p['fiche'] = {'ond_compteurs_compatibles': ['DTSU666-H']}
        _comp, comptage, _logger = self._comptage_et_logger(cat)
        # La fiche passe devant la marque, même quand la marque a le plus petit id.
        self.assertEqual(comptage['produit'], 5100)

    def test_logger_de_la_marque_des_onduleurs_ou_alerte(self):
        huawei = self._accessoire(5200, 'SmartLogger 3000', 'logger_supervision', 'Huawei',
                                  fiche={'log_onduleurs_max': 80})
        deye = self._accessoire(5201, 'Logger Deye', 'logger_supervision', 'Deye',
                                fiche={'log_onduleurs_max': 40})
        comp, _c, logger = self._comptage_et_logger(self._cat_marque('Deye', huawei, deye))
        self.assertEqual(logger[0]['produit'], 5201)
        self.assertNotIn('LOGGER_MARQUE_A_CONFIRMER', self._codes(comp))
        comp, _c, logger = self._comptage_et_logger(self._cat_marque('Deye', huawei))
        self.assertEqual(logger[0]['produit'], 5200)
        alerte = next(a for a in comp['alertes'] if a['code'] == 'LOGGER_MARQUE_A_CONFIRMER')
        self.assertIn('deye', alerte['message'])

    def test_catalogue_mono_marque_inchange_sans_alerte(self):
        cat = self._cat_marque(
            'Huawei',
            self._accessoire(5100, 'Smart Meter DTSU666-H', 'compteur_injection', 'Huawei'),
            self._accessoire(5102, 'Compteur générique', 'compteur_injection', '', '300'),
            self._accessoire(5200, 'SmartLogger 3000', 'logger_supervision', 'Huawei'))
        comp, comptage, logger = self._comptage_et_logger(cat)
        self.assertEqual(comptage['produit'], 5100)
        self.assertEqual(logger[0]['produit'], 5200)
        self.assertFalse(self._codes(comp) & {'COMPTAGE_MARQUE_A_CONFIRMER',
                                              'LOGGER_MARQUE_A_CONFIRMER'})

    # ── R3.5 (fondateur 28/10/2026) : Smart Meter choisi PAR CALIBRE ─────────

    def _compteurs_huawei(self):
        return [
            self._accessoire(5300, 'Smart Meter Huawei DTSU666-H 100 A (raccordement direct)',
                             'compteur_injection', 'Huawei', '2000',
                             {'type_fiche': 'limiteur', 'lim_mode': 'compteur_direct',
                              'lim_calibre_a': 100}),
            self._accessoire(5301, 'Smart Meter Huawei DTSU666-H 250 A (avec TC)',
                             'compteur_injection', 'Huawei', '3000',
                             {'type_fiche': 'limiteur', 'lim_mode': 'compteur_tc',
                              'lim_calibre_a': 250}),
            self._accessoire(5302, 'Smart Meter Huawei DTSU666-H + TC externes (> 250 A)',
                             'compteur_injection', 'Huawei', '4000',
                             {'type_fiche': 'limiteur', 'lim_mode': 'compteur_tc_externe',
                              'lim_calibre_a': None}),
            self._accessoire(5303, 'Smart Meter', 'compteur_injection', 'Huawei', '1500')]

    def _comptage_ondu(self, cat, quantite, kwc=None):
        premier = next(p for p in cat if p['role_ci'] == 'onduleur_string_tri'
                       and p['kw_ac'] == 50)
        ond = {'combinaison': [{'produit': premier['id'], 'nom': premier['nom'],
                                'kw_ac': 50, 'quantite': quantite}]}
        comp = composer_ci(kwc or 60 * quantite, cat, onduleurs=ond, entrees=_entrees(),
                           forfaits={})
        comptage = [li for li in comp['lignes']
                    if li['role'] in ('compteur_injection', 'controleur_injection')]
        self.assertEqual(len(comptage), 1)
        return comp, comptage[0]

    def test_compteur_du_plus_petit_calibre_suffisant(self):
        cat = self._cat_marque('Huawei', *self._compteurs_huawei())
        # 1 × 50 kW triphasé : I = 72,2 A ⇒ le 100 A direct.
        comp, ligne = self._comptage_ondu(cat, 1)
        self.assertEqual(ligne['produit'], 5300)
        self.assertEqual(ligne['designation'],
                         'Smart Meter Huawei DTSU666-H 100 A (raccordement direct)')
        self.assertEqual(ligne['quantite'], 1)
        # Un seul onduleur : aucun motif « fournisseur », rien à confirmer.
        self.assertIsNone(ligne['motif'])
        self.assertFalse(ligne['a_confirmer_visite'])
        hyp = next(h for h in comp['hypotheses'] if h['cle'] == 'comptage_courant_a')
        self.assertEqual(hyp['valeur'], round(50000 / (400 * math.sqrt(3)), 1))
        self.assertEqual(hyp['statut'], 'calculee')
        self.assertNotIn('COMPTAGE_CALIBRE_A_CONFIRMER', self._codes(comp))
        # 3 × 50 kW : I = 216,5 A ⇒ le 250 A à TC ; fiche muette sur le nombre
        # d'onduleurs pilotés ⇒ « à confirmer fournisseur » (nb_ond > 1).
        comp, ligne = self._comptage_ondu(cat, 3)
        self.assertEqual(ligne['produit'], 5301)
        self.assertIn('à confirmer fournisseur', ligne['motif'])
        # 5 × 50 kW : I = 360,8 A > 250 A ⇒ TC externes (sans borne).
        comp, ligne = self._comptage_ondu(cat, 5)
        self.assertEqual(ligne['produit'], 5302)

    def test_compteur_sans_calibre_seulement_en_repli_avec_alerte(self):
        compteurs = self._compteurs_huawei()
        # Les compteurs à calibre SANS prix : le Smart Meter sans calibre
        # (legacy) tarifé sert de repli, alerte interne.
        for c in compteurs[:3]:
            c['prix_connu'] = False
            c.pop('prix_vente_ht')
        comp, ligne = self._comptage_ondu(self._cat_marque('Huawei', *compteurs), 1)
        self.assertEqual(ligne['produit'], 5303)
        alerte = next(a for a in comp['alertes'] if a['code'] == 'COMPTAGE_CALIBRE_A_CONFIRMER')
        self.assertTrue(alerte['interne'])
        self.assertIn('72.2 A', alerte['message'])
        # Calibre trop petit (100 A seul) tarifé, legacy tarifé : jamais un
        # compteur sous-dimensionné — repli legacy + alerte.
        petit = self._compteurs_huawei()[:1] + self._compteurs_huawei()[3:]
        comp, ligne = self._comptage_ondu(self._cat_marque('Huawei', *petit), 3)
        self.assertEqual(ligne['produit'], 5303)
        self.assertIn('COMPTAGE_CALIBRE_A_CONFIRMER', self._codes(comp))

    def test_preference_de_marque_dans_l_ensemble_eligible(self):
        # Onduleurs Deye : le compteur Deye 250 A passe devant le Huawei 100 A
        # (tous deux éligibles à 72 A) — CMP10 DANS l'ensemble éligible.
        deye = self._accessoire(5310, 'Compteur Deye 250 A', 'compteur_injection', 'Deye',
                                '2500', {'type_fiche': 'limiteur', 'lim_calibre_a': 250})
        cat = self._cat_marque('Deye', *self._compteurs_huawei(), deye)
        comp, ligne = self._comptage_ondu(cat, 1)
        self.assertEqual(ligne['produit'], 5310)
        self.assertFalse(self._codes(comp) & {'COMPTAGE_MARQUE_A_CONFIRMER',
                                              'COMPTAGE_CALIBRE_A_CONFIRMER'})
        # Sans compteur Deye : le plus petit Huawei éligible + alerte de marque.
        comp, ligne = self._comptage_ondu(self._cat_marque('Deye', *self._compteurs_huawei()), 1)
        self.assertEqual(ligne['produit'], 5300)
        self.assertIn('COMPTAGE_MARQUE_A_CONFIRMER', self._codes(comp))

    # ── R3.6 (fondateur 28/10/2026) : une clé wifi PAR ONDULEUR ──────────────

    def _dongle(self, marque='Huawei', prix='1000'):
        return self._accessoire(5400, 'Clé wifi %s SDongleA-05' % marque, 'logger_supervision',
                                marque, prix, {'type_fiche': 'logger', 'log_type': 'dongle',
                                               'log_onduleurs_max': 1})

    def _central(self):
        return self._accessoire(5401, 'SmartLogger 3000', 'logger_supervision', 'Huawei',
                                '4500', {'type_fiche': 'logger', 'log_onduleurs_max': 80})

    def test_une_cle_wifi_par_onduleur(self):
        cat = self._cat_marque('Huawei', self._dongle(), self._central())
        comp, _l = self._comptage_ondu(cat, 1)
        supervision = self._lignes(comp, 'logger_supervision')
        self.assertEqual([(li['produit'], li['quantite']) for li in supervision], [(5400, 1)])
        self.assertNotIn('SUPERVISION_LOGGER_A_CONFIRMER', self._codes(comp))
        comp, _l = self._comptage_ondu(cat, 3)
        supervision = self._lignes(comp, 'logger_supervision')
        # 3 clés, AUCUN logger central composé ; alerte interne « à confirmer ».
        self.assertEqual([(li['produit'], li['quantite']) for li in supervision], [(5400, 3)])
        alerte = next(a for a in comp['alertes']
                      if a['code'] == 'SUPERVISION_LOGGER_A_CONFIRMER')
        self.assertTrue(alerte['interne'])
        self.assertIn('logger central à confirmer selon la marque', alerte['message'])

    def test_sans_cle_de_la_marque_logger_central_des_deux_onduleurs(self):
        # Onduleurs Deye, seule une clé Huawei : comportement d'hier (logger
        # central dès 2 onduleurs, rien pour un seul).
        cat = self._cat_marque('Deye', self._dongle('Huawei'), self._central())
        comp, _l = self._comptage_ondu(cat, 1)
        self.assertEqual(self._lignes(comp, 'logger_supervision'), [])
        comp, _l = self._comptage_ondu(cat, 3)
        supervision = self._lignes(comp, 'logger_supervision')
        self.assertEqual([li['produit'] for li in supervision], [5401])

    def test_semis_r3_compteurs_huawei_et_cle_wifi(self):
        # R3.5 / R3.6 — les articles SEMÉS (tables du seeder, jamais
        # recopiées) : un onduleur Huawei 50 kW ⇒ le Smart Meter 100 A et UNE
        # clé wifi ; trois ⇒ le 250 A à TC et trois clés.
        skus = ('SMART-MET', 'SM-HUA-100A', 'SM-HUA-250A-TC', 'SM-HUA-TC-EXT', 'WIFI-DON')
        semis = []
        for i, (nom, sku, _c, ttc, _a, _q, _s) in enumerate(CATALOGUE):
            if sku in skus:
                semis.append({
                    'id': 7000 + i, 'nom': nom, 'sku': sku,
                    'marque': FICHES[sku]['marque'], 'role_devis': '',
                    'role_ci': ROLES_CI_ARTICLES_EXISTANTS[sku], 'classement': 'declare',
                    'type_pose': '', 'fiche': FICHES_TECHNIQUES.get(sku),
                    'prix_connu': True, 'prix_vente_ht': ht_at(ttc, Decimal('20')),
                    'eligible_ci': True, 'motif_exclusion': None})
        self.assertEqual({p['sku'] for p in semis}, set(skus))
        par_sku = {p['sku']: p for p in semis}
        self.assertEqual([par_sku[s]['prix_vente_ht'] for s in skus[1:4]],
                         [Decimal('2000.00'), Decimal('3000.00'), Decimal('4000.00')])
        self.assertEqual(par_sku['WIFI-DON']['prix_vente_ht'], Decimal('1000.00'))
        for sku in skus[1:4]:
            self.assertIsNone(par_sku[sku]['fiche'].get('lim_onduleurs_max'))
        cat = self._cat_marque('Huawei', *semis)
        for quantite, compteur in ((1, 'SM-HUA-100A'), (3, 'SM-HUA-250A-TC')):
            comp, ligne = self._comptage_ondu(cat, quantite)
            self.assertEqual(ligne['produit'], par_sku[compteur]['id'], quantite)
            supervision = self._lignes(comp, 'logger_supervision')
            self.assertEqual([(li['produit'], li['quantite']) for li in supervision],
                             [(par_sku['WIFI-DON']['id'], quantite)])
            self.assertNotIn('COMPTAGE_CALIBRE_A_CONFIRMER', self._codes(comp))

    def test_groupes_client_des_roles(self):
        # R3.4 — le comptage SORT du Tableau : groupe « supervision_ci ».
        for role in ('compteur_injection', 'controleur_injection', 'logger_supervision'):
            self.assertEqual(groupe_client_du_role(role), 'supervision_ci', role)
            self.assertNotIn(role, ROLES_TABLEAU_CI)
        self.assertEqual(ROLES_SUPERVISION_CI, {'compteur_injection', 'controleur_injection',
                                                'logger_supervision'})
        for role in ('coffret_dc', 'coffret_ac', 'protection_ac', 'protection_dc',
                     'mise_a_la_terre'):
            self.assertEqual(groupe_client_du_role(role), 'tableau_ci', role)
        self.assertEqual(groupe_client_du_role('pose_modules'), 'installation_ci')
        self.assertIsNone(groupe_client_du_role('cable_ac'))

    # ── ADEV83 : protections DC, parafoudres DC/AC, mise à la terre ──────────

    @staticmethod
    def _article(id_, nom, role, fiche=None, prix='500'):
        return {'id': id_, 'nom': nom, 'marque': '', 'role_devis': '', 'role_ci': role,
                'classement': 'declare', 'type_pose': '', 'fiche': fiche,
                'prix_connu': True, 'prix_vente_ht': Decimal(prix), 'eligible_ci': True,
                'motif_exclusion': None}

    def _cat_protections(self, n_mppt=4):
        cat = [dict(p) for p in self.cat]
        for p in cat:
            if p['role_ci'] == 'onduleur_string_tri':
                p['fiche'] = {'ond_n_mppt': n_mppt}
        return cat + [
            self._article(6000, 'Sectionneur DC 1000 V', 'protection_dc',
                          {'prot_type': 'sectionneur', 'prot_cote': 'dc'}, '320'),
            self._article(6001, 'Parafoudre DC type 2', 'protection_dc',
                          {'prot_type': 'parafoudre', 'prot_cote': 'dc'}, '650'),
            self._article(6002, 'Parafoudre AC type 2', 'protection_ac',
                          {'prot_type': 'parafoudre', 'prot_cote': 'ac'}, '700'),
            self._article(6003, 'Kit de mise à la terre C&I', 'mise_a_la_terre', None, '1200')]

    @staticmethod
    def _ond_50(cat, quantite=2, chaines=None):
        ondu = next(p for p in cat if p['role_ci'] == 'onduleur_string_tri' and p['kw_ac'] == 50)
        ond = {'combinaison': [{'produit': ondu['id'], 'nom': ondu['nom'], 'kw_ac': 50,
                                'quantite': quantite}]}
        if chaines is not None:
            ond['chaines'] = chaines
        return ond

    def test_protections_dc_une_par_chaine_jamais_par_mppt(self):
        # R3.1 / R3.2 (fondateur 28/10/2026) — protection DC ET parafoudre DC :
        # une par CHAÎNE conçue (Σ nb_chaines), jamais par MPPT ni par onduleur.
        cat = self._cat_protections(n_mppt=4)
        chaines = [{'produit': 1, 'nb_modules': 80, 'nb_chaines': 5, 'bloquants': []},
                   {'produit': 1, 'nb_modules': 75, 'nb_chaines': 6, 'bloquants': []}]
        comp = composer_ci(110, cat, onduleurs=self._ond_50(cat, chaines=chaines),
                           entrees=_entrees(mise_a_la_terre_necessaire=True), forfaits={})
        par_produit = {ligne['produit']: ligne for ligne in comp['lignes']}
        self.assertEqual(par_produit[6000]['quantite'], 11)      # 5 + 6 chaînes
        self.assertNotEqual(par_produit[6000]['quantite'], 8)    # jamais 2 × 4 MPPT
        self.assertEqual(par_produit[6001]['quantite'], 11)
        self.assertEqual(par_produit[6000]['designation'], 'Protection DC par chaîne')
        self.assertEqual(par_produit[6001]['designation'], 'Parafoudre DC par chaîne')
        for pid in (6000, 6001):
            self.assertFalse(par_produit[pid]['a_confirmer_visite'])
            self.assertIsNone(par_produit[pid]['motif'])
        self.assertEqual(par_produit[6002]['quantite'], 1)
        self.assertEqual(par_produit[6003]['quantite'], 1)
        for pid, prix in ((6000, '320'), (6001, '650'), (6002, '700'), (6003, '1200')):
            self.assertTrue(par_produit[pid]['prix_connu'])
            self.assertEqual(par_produit[pid]['prix_unitaire_ht'], prix)
        # Le disjoncteur AC n'est jamais pris pour un parafoudre (ni l'inverse).
        disj = [ligne for ligne in comp['lignes'] if ligne['role'] == 'protection_ac'
                and ligne['produit'] != 6002]
        self.assertTrue(disj)
        self.assertNotIn('POSTE_ABSENT_CATALOGUE', [a['code'] for a in comp['alertes']])

    def test_protections_dc_chaines_non_concues_estimees(self):
        # Sans conception de chaînes : plafond(panneaux ÷ 12), à confirmer.
        cat = self._cat_protections()
        comp = composer_ci(110, cat, onduleurs=self._ond_50(cat), entrees=_entrees(),
                           forfaits={})
        attendu = math.ceil(math.ceil(110 * 1000 / 710) / 12)
        for pid in (6000, 6001):
            ligne = next(li for li in comp['lignes'] if li['produit'] == pid)
            self.assertEqual(ligne['quantite'], attendu)
            self.assertTrue(ligne['a_confirmer_visite'])
            self.assertIn('chaînes non conçues : %d chaînes estimées' % attendu,
                          ligne['motif'])

    def test_protections_dc_chaines_bloquantes_a_chiffrer_visite(self):
        cat = self._cat_protections()
        chaines = [{'produit': 1, 'nb_modules': 80, 'nb_chaines': 5,
                    'bloquants': ['tension de chaîne hors plage']}]
        comp = composer_ci(110, cat, onduleurs=self._ond_50(cat, chaines=chaines),
                           entrees=_entrees(), forfaits={})
        for pid in (6000, 6001):
            ligne = next(li for li in comp['lignes'] if li['produit'] == pid)
            self.assertIsNone(ligne['quantite'])
            self.assertTrue(ligne['a_chiffrer_visite'])
        self.assertIn('Protection DC par chaîne', comp['a_chiffrer_visite'])
        self.assertIn('Parafoudre DC par chaîne', comp['a_chiffrer_visite'])

    def test_triphase_disjoncteur_et_parafoudre_ac_4p(self):
        # R3.3 — triphasé : disjoncteur « … 4P — sortie … », parafoudre AC 4P
        # (article à 4 pôles préféré, la désignation du moteur gagne).
        cat = self._cat_protections() + [
            self._article(6010, 'Parafoudre AC 2P', 'protection_ac',
                          {'prot_type': 'parafoudre', 'prot_cote': 'ac', 'prot_poles': 2}, '300'),
            self._article(6011, 'Parafoudre AC tétrapolaire', 'protection_ac',
                          {'prot_type': 'parafoudre', 'prot_cote': 'ac', 'prot_poles': 4}, '800')]
        comp = composer_ci(110, cat, onduleurs=self._ond_50(cat), entrees=_entrees(),
                           forfaits={})
        parafoudres = [li for li in comp['lignes']
                       if li['role'] == 'protection_ac' and li['produit'] in (6002, 6010, 6011)]
        self.assertEqual([(li['produit'], li['designation']) for li in parafoudres],
                         [(6011, 'Parafoudre AC 4P')])
        disj = [li for li in comp['lignes'] if li['role'] == 'protection_ac'
                and li['produit'] not in (6002, 6010, 6011)]
        self.assertEqual(len(disj), 2)
        for ligne in disj:
            self.assertRegex(ligne['designation'], r'^Disjoncteur AC \d+ A 4P — sortie ')
            if ligne['produit'] is not None:
                self.assertNotEqual(ligne['designation'], next(
                    p['nom'] for p in cat if p['id'] == ligne['produit']))

    def test_monophase_2p_et_repli_parafoudre_sans_poles(self):
        cat = [dict(p, role_ci='onduleur_string_mono') if p['role_ci'] == 'onduleur_string_tri'
               else dict(p) for p in self._cat_protections()]
        cat += [self._article(6011, 'Parafoudre AC tétrapolaire', 'protection_ac',
                              {'prot_type': 'parafoudre', 'prot_cote': 'ac', 'prot_poles': 4},
                              '800')]
        ondu = next(p for p in cat if p['role_ci'] == 'onduleur_string_mono')
        ond = {'combinaison': [{'produit': ondu['id'], 'nom': 'Mono', 'kw_ac': 10,
                                'quantite': 1}]}
        comp = composer_ci(12, cat, onduleurs=ond, entrees=_entrees(phase='mono'), forfaits={})
        parafoudre = [li for li in comp['lignes'] if li['produit'] in (6002, 6011)]
        # Aucun 2P au catalogue : repli sur le parafoudre sans pôles publiés,
        # jamais le 4P.
        self.assertEqual([(li['produit'], li['designation']) for li in parafoudre],
                         [(6002, 'Parafoudre AC 2P')])
        disj = next(li for li in comp['lignes'] if li['role'] == 'protection_ac'
                    and li['produit'] not in (6002, 6011))
        self.assertRegex(disj['designation'], r'^Disjoncteur AC \d+ A 2P — sortie Mono$')

    def test_mise_a_la_terre_jamais_automatique(self):
        # R3.7 — ajoutée seulement si la visite la dit nécessaire ; inconnue ⇒
        # alerte interne non bloquante ; non nécessaire ⇒ rien.
        cat = self._cat_protections()
        for besoin, ligne_attendue, alerte_attendue in ((None, False, True),
                                                        (False, False, False),
                                                        (True, True, False)):
            comp = composer_ci(110, cat, onduleurs=self._ond_50(cat), forfaits={},
                               entrees=_entrees(mise_a_la_terre_necessaire=besoin))
            terre = self._lignes(comp, 'mise_a_la_terre')
            self.assertEqual(bool(terre), ligne_attendue, besoin)
            if terre:
                self.assertEqual(terre[0]['quantite'], 1)
                self.assertEqual(terre[0]['produit'], 6003)
            alertes = [a for a in comp['alertes'] if a['code'] == 'CI_MISE_A_LA_TERRE_VISITE']
            self.assertEqual(bool(alertes), alerte_attendue, besoin)
            for alerte in alertes:
                self.assertTrue(alerte['interne'])
                self.assertNotEqual(alerte['niveau'], 'bloquant')
                self.assertIn('visite technique', alerte['message'])

    def test_roles_absents_alerte_interne_composition_inchangee(self):
        # Un catalogue SANS ces rôles (le semis CCAT10 les crée désormais :
        # voir le test suivant) — l'alerte interne reste le filet.
        roles_retires = {'protection_dc', 'protection_ac', 'mise_a_la_terre'}
        cat = [p for p in self.cat if p['role_ci'] not in roles_retires]
        ond = {'combinaison': [{'produit': 1, 'nom': 'X', 'kw_ac': 50, 'quantite': 2}]}
        comp = composer_ci(110, cat, onduleurs=ond, forfaits={},
                           entrees=_entrees(mise_a_la_terre_necessaire=True))
        absents = [a for a in comp['alertes'] if a['code'] == 'POSTE_ABSENT_CATALOGUE']
        self.assertEqual({a['champ'] for a in absents},
                         {'composition.protection_dc', 'composition.parafoudre_dc',
                          'composition.parafoudre_ac', 'composition.mise_a_la_terre'})
        self.assertTrue(all(a['interne'] and a['niveau'] != 'bloquant' for a in absents))
        roles = {ligne['role'] for ligne in comp['lignes']}
        self.assertNotIn('protection_dc', roles)
        self.assertNotIn('mise_a_la_terre', roles)
        for nom in ('Parafoudre', 'Mise à la terre', 'Protection DC'):
            self.assertFalse(any(nom in d for d in comp['prix_a_renseigner']), nom)

    def test_postes_semes_a_prix_vide_composes_a_completer(self):
        # CCAT10 — le semis crée protection DC, parafoudres et mise à la terre
        # à prix vide : le poste n'est plus « absent », il est composé et dit
        # « prix à renseigner ».
        ond = {'combinaison': [{'produit': 1, 'nom': 'X', 'kw_ac': 50, 'quantite': 2}]}
        comp = composer_ci(110, self.cat, onduleurs=ond, forfaits={},
                           entrees=_entrees(mise_a_la_terre_necessaire=True))
        self.assertFalse([a for a in comp['alertes']
                          if a['code'] == 'POSTE_ABSENT_CATALOGUE'])
        roles = {ligne['role'] for ligne in comp['lignes']}
        self.assertTrue({'protection_dc', 'protection_ac', 'mise_a_la_terre'} <= roles)
        for nom in ('Parafoudre DC', 'Parafoudre AC', 'Mise à la terre', 'Protection DC'):
            self.assertTrue(any(nom in d for d in comp['prix_a_renseigner']), nom)

    def test_coffrets_au_bareme_par_onduleur_et_par_panneau(self):
        # Fondateur 26/10/2026 — coffrets C&I tarifés comme le tableau
        # résidentiel : par onduleur + par panneau.
        for p in self.cat:
            if p['role_ci'] in ('coffret_dc', 'coffret_ac'):
                p['prix_connu'] = True
                p['bareme_coffret'] = {'par_onduleur_ht': Decimal('500'),
                                       'par_panneau_ht': Decimal('20')}
        comp = composer_ci(100, self.cat, onduleurs=_onduleurs(self.cat, 100),
                           entrees=_entrees(), forfaits={})
        nb_pan = math.ceil(100 * 1000 / 710)
        dc = self._lignes(comp, 'coffret_dc')[0]
        ac = self._lignes(comp, 'coffret_ac')[0]
        nb_ond = dc['quantite']
        attendu = Decimal(500 * nb_ond + 20 * nb_pan)
        self.assertTrue(dc['prix_connu'] and ac['prix_connu'])
        self.assertEqual(Decimal(ac['prix_unitaire_ht']), attendu)
        self.assertAlmostEqual(Decimal(dc['prix_unitaire_ht']) * nb_ond, attendu,
                               delta=Decimal('0.01') * nb_ond)
        self.assertFalse(any('Coffret' in d for d in comp['prix_a_renseigner']))

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

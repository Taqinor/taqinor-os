# -*- coding: utf-8 -*-
"""CALX246 — RATTACHER CHAQUE LIGNE DE BORDEREAU À UNE RÉFÉRENCE D'ARTICLE.

LE CONSTAT
----------
``core/electrique/nomenclature.py`` produisait des désignations EN CLAIR
(« Coffret de chaînes DC (string box) », « Rail de fixation aluminium ») sans
aucun identifiant produit : on ne pouvait commander depuis ce bordereau.
``apps.stock.selectors.specs_for_produit`` était déjà employé par le module
électrique — mais jamais pour rattacher une ligne à un ARTICLE.

CE QUE CES TESTS ARMENT
-----------------------
1. correspondance POSÉE — la ligne porte ``produit_id`` et ``reference`` ;
2. correspondance ABSENTE — les deux champs valent ``None`` et la ligne est
   publiée exactement comme avant (jamais un article deviné) ;
3. produit d'une AUTRE société — REFUSÉ en le NOMMANT, la ligne reste sans
   référence ;
4. la garde de mot-prix de l'export tableur, REJOUÉE sur le bordereau.

Tests PURS : le noyau se calcule sans base, et la résolution du catalogue est
exercée avec une doublure du sélecteur du stock (le vrai sélecteur est
company-scopé, c'est lui qui rend ``None`` pour une autre société).
"""
from __future__ import annotations

import types
import unittest
from unittest import mock

from apps.calepinage.services import electrique
from apps.calepinage.services.export_tableur import verifier_absence_de_prix
from core.electrique.cables import dimensionner_cables
from core.electrique.chaines import concevoir_chaines
from core.electrique.nomenclature import nomenclature
from core.electrique.protections import concevoir_protections
from core.electrique.onduleurs import dimensionner_onduleurs
from core.electrique.types import (
    EntreeElectrique, GroupePan, SpecModule, SpecOnduleur,
)

MODULE = SpecModule(vmp_v=41.4, voc_v=49.3, isc_a=18.59, imp_a=17.59,
                    pmax_wc=710.0, designation='CS7N-710')
ONDULEUR = SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=500.0,
                        v_max_abs=600.0, i_max_mppt_a=26.0, ac_kw=5.0,
                        phases=1, designation='Deye SG05LP3')

#: Une règle de bordereau de structure SOURCÉE (CALX247) — sans elle, aucune
#: ligne « Structure » n'existe, donc rien à rattacher par catégorie.
REGLE_STRUCTURE = {
    'rails_par_module': 2.0, 'pinces_par_module': 2.0,
    'pinces_supplement': 2.0, 'crochets_par_module': 3.0,
    'crochets_minimum': 4.0,
    'source': "Décision fondateur 21/09/2026 — règle de pose TAQINOR",
}


class _Calepinage:
    """Le strict minimum que le bordereau lit sur un pivot — aucun ORM."""

    pk = 1
    #: Une société NON nulle : c'est elle qui borne la lecture du catalogue
    #: (``get_produit_scoped``). ``None`` voudrait dire « calcul hors base »,
    #: et aucune référence ne serait alors résolue — ce que teste
    #: ``test_sans_societe_aucune_reference_n_est_resolue``.
    company = 'SOCIETE'
    resultat = None
    roof_layout = None


class _Produit:
    """Le produit du catalogue, réduit à ce que la référence lui demande."""

    def __init__(self, pk, reference='', marque='', nom=''):
        self.pk = pk
        self.reference = reference
        self.marque = marque
        self.nom = nom


def _entree(nb_modules=20, dc_m=30.0, ac_m=12.0):
    return EntreeElectrique(
        module=MODULE, onduleur=ONDULEUR,
        groupes=(GroupePan(label='Sud', nb_modules=nb_modules,
                           azimut_deg=180.0, inclinaison_deg=15.0),),
        dc_m=dc_m, ac_m=ac_m, phases=1)


def _bordereau(references=None, regle=REGLE_STRUCTURE):
    entree = _entree()
    chaines = concevoir_chaines(entree)
    evaluation = dimensionner_onduleurs(entree, chaines.puissance_kwc)
    protections = concevoir_protections(entree, chaines, evaluation)
    cables = dimensionner_cables(entree, chaines, protections)
    return nomenclature(entree, chaines, protections, cables,
                        regle_bom_structure=regle, references=references)


def _par_categorie(resultat, categorie):
    return [ligne for ligne in resultat.lignes
            if ligne.categorie == categorie]


class CorrespondancePoseeTest(unittest.TestCase):
    """1 — la correspondance posée rattache la ligne à son article."""

    def test_un_repere_rattache_la_ligne_de_cet_organe(self):
        resultat = _bordereau(references={
            'QAC1': {'produit_id': 77, 'reference': 'DISJ-C32'}})
        lignes = [ligne for ligne in resultat.lignes
                  if ligne.designation.startswith('QAC1')]
        self.assertTrue(lignes, 'aucun organe QAC1 au bordereau')
        for ligne in lignes:
            self.assertEqual(ligne.produit_id, 77)
            self.assertEqual(ligne.reference, 'DISJ-C32')

    def test_une_categorie_rattache_les_lignes_sans_repere(self):
        resultat = _bordereau(references={
            'Structure': {'produit_id': 12, 'reference': 'RAIL-ALU'}})
        lignes = _par_categorie(resultat, 'Structure')
        self.assertEqual(len(lignes), 3)
        for ligne in lignes:
            self.assertEqual(ligne.produit_id, 12)
            self.assertEqual(ligne.reference, 'RAIL-ALU')

    def test_le_repere_prime_sur_la_categorie(self):
        resultat = _bordereau(references={
            'QAC1': {'produit_id': 77, 'reference': 'DISJ-C32'},
            'Protection AC': {'produit_id': 1, 'reference': 'GENERIQUE'}})
        ligne = next(ligne for ligne in resultat.lignes
                     if ligne.designation.startswith('QAC1'))
        self.assertEqual(ligne.reference, 'DISJ-C32')

    def test_le_cable_se_rattache_par_son_repere(self):
        resultat = _bordereau(references={
            'W1': {'produit_id': 5, 'reference': 'H1Z2Z2K-6'}})
        ligne = next(ligne for ligne in resultat.lignes
                     if ligne.categorie == 'Câblage DC')
        self.assertEqual(ligne.produit_id, 5)
        self.assertEqual(ligne.reference, 'H1Z2Z2K-6')


class CorrespondanceAbsenteTest(unittest.TestCase):
    """2 — sans correspondance, la ligne d'aujourd'hui, champ pour champ."""

    def test_les_deux_champs_valent_null(self):
        for ligne in _bordereau().lignes:
            with self.subTest(designation=ligne.designation):
                self.assertIsNone(ligne.produit_id)
                self.assertIsNone(ligne.reference)

    def test_le_reste_de_la_ligne_est_inchange(self):
        sans = _bordereau()
        avec = _bordereau(references={
            'QAC1': {'produit_id': 77, 'reference': 'DISJ-C32'}})
        self.assertEqual(
            [(ligne.categorie, ligne.designation, ligne.quantite,
              ligne.unite, ligne.spec) for ligne in sans.lignes],
            [(ligne.categorie, ligne.designation, ligne.quantite,
              ligne.unite, ligne.spec) for ligne in avec.lignes])
        self.assertEqual(sans.alertes, avec.alertes)

    def test_une_clef_inconnue_ne_rattache_rien(self):
        resultat = _bordereau(references={
            'QZZ9': {'produit_id': 99, 'reference': 'FANTOME'}})
        self.assertEqual(
            [ligne.produit_id for ligne in resultat.lignes
             if ligne.produit_id is not None], [])


class ProduitDUneAutreSocieteTest(unittest.TestCase):
    """3 — le produit d'une autre société est REFUSÉ en le nommant."""

    def _resoudre(self, correspondances, catalogue):
        # Le vrai ``get_produit_scoped`` est BORNÉ société : un produit d'une
        # autre société lui est INTROUVABLE (``None``), jamais « interdit ».
        # La doublure reproduit exactement ça.
        with mock.patch('apps.stock.selectors.get_produit_scoped',
                        side_effect=lambda company, pk: catalogue.get(pk)):
            return electrique._references_nomenclature(
                object(), correspondances, 'réglage société')

    def test_un_produit_hors_catalogue_est_nomme(self):
        references, alertes = self._resoudre(
            {'QAC1': 404}, catalogue={})
        self.assertEqual(references, {})
        self.assertEqual(len(alertes), 1)
        self.assertIn('QAC1', alertes[0])
        self.assertIn('404', alertes[0])
        self.assertIn('catalogue de la société', alertes[0])

    def test_un_produit_du_catalogue_donne_sa_reference(self):
        references, alertes = self._resoudre(
            {'QAC1': 77},
            catalogue={77: _Produit(77, reference='DISJ-C32')})
        self.assertEqual(alertes, [])
        self.assertEqual(references['QAC1'],
                         {'produit_id': 77, 'reference': 'DISJ-C32'})

    def test_sans_reference_catalogue_la_designation_fait_foi(self):
        references, _alertes = self._resoudre(
            {'Structure': 12},
            catalogue={12: _Produit(12, marque='K2', nom='Rail SingleRail')})
        self.assertEqual(references['Structure']['reference'],
                         'K2 Rail SingleRail')

    def test_les_bonnes_correspondances_survivent_a_la_mauvaise(self):
        references, alertes = self._resoudre(
            {'QAC1': 77, 'Structure': 404},
            catalogue={77: _Produit(77, reference='DISJ-C32')})
        self.assertIn('QAC1', references)
        self.assertNotIn('Structure', references)
        self.assertEqual(len(alertes), 1)

    def test_aucune_correspondance_ne_lit_le_catalogue(self):
        with mock.patch('apps.stock.selectors.get_produit_scoped') as sonde:
            references, alertes = electrique._references_nomenclature(
                object(), None, '')
        sonde.assert_not_called()
        self.assertEqual((references, alertes), ({}, []))


class AucunPrixTest(unittest.TestCase):
    """4 — la garde de mot-prix de l'export tableur, rejouée ici."""

    def test_le_bordereau_ne_charrie_aucun_mot_d_argent(self):
        resultat = _bordereau(references={
            'QAC1': {'produit_id': 77, 'reference': 'DISJ-C32'},
            'Structure': {'produit_id': 12, 'reference': 'RAIL-ALU'}})
        entetes = ['Catégorie', 'Désignation', 'Quantité', 'Unité',
                   'Spécification', 'Produit', 'Référence']
        lignes = [[ligne.categorie, ligne.designation, ligne.quantite,
                   ligne.unite, ligne.spec, ligne.produit_id,
                   ligne.reference] for ligne in resultat.lignes]
        # Ne lève pas = aucune cellule ne porte prix / marge / montant / TVA.
        verifier_absence_de_prix(entetes, lignes)

    def test_la_reference_resolue_ne_porte_aucun_prix(self):
        with mock.patch('apps.stock.selectors.get_produit_scoped',
                        side_effect=lambda company, pk: _Produit(
                            pk, reference='DISJ-C32')):
            references, _alertes = electrique._references_nomenclature(
                object(), {'QAC1': 77}, 'réglage société')
        self.assertEqual(sorted(references['QAC1']),
                         ['produit_id', 'reference'])


class BordereauDuCalepinageTest(unittest.TestCase):
    """Le CROCHET de phase 2 : les trois services atteignent enfin
    ``nomenclature()``."""

    def _pieces(self):
        entree = _entree()
        chaines = concevoir_chaines(entree)
        evaluation = dimensionner_onduleurs(entree, chaines.puissance_kwc)
        protections = concevoir_protections(entree, chaines, evaluation)
        cables = dimensionner_cables(entree, chaines, protections)
        conception = types.SimpleNamespace(chaines=chaines.chaines,
                                           resultat=chaines)
        noyau = {'entree': entree, 'protections': protections,
                 'cables': cables}
        return conception, noyau

    def _servir(self, *, reglages=None, equipements=(), catalogue=None):
        conception, noyau = self._pieces()
        catalogue = catalogue or {}
        with mock.patch.object(electrique, '_reglages_electrique_societe',
                               return_value=reglages or {}), \
                mock.patch('apps.stock.selectors.get_produit_scoped',
                           side_effect=lambda c, pk: catalogue.get(pk)), \
                mock.patch('apps.stock.selectors.specs_for_produit',
                           return_value={}):
            return electrique._bordereau_du_calepinage(
                _Calepinage(), conception, noyau, equipements=equipements)

    def test_un_coffret_pose_dans_le_plan_donne_sa_ligne(self):
        servi = self._servir(equipements=[
            {'id': 'eq1', 'type': 'coffret_dc', 'label': 'Coffret Sud',
             'capaciteEntrees': 6}])
        designations = [ligne['designation'] for ligne in servi['lignes']]
        self.assertTrue(any('Coffret de chaînes DC' in texte
                            for texte in designations), designations)
        self.assertTrue(any('Coffret Sud' in texte
                            for texte in designations))

    def test_sans_coffret_pose_le_motif_de_calx230_est_publie(self):
        servi = self._servir()
        self.assertTrue(
            any("aucun coffret DC n'est posé dans le plan" in texte
                for texte in servi['alertes']), servi['alertes'])
        self.assertFalse(any('Coffret de chaînes DC' in ligne['designation']
                             for ligne in servi['lignes']))

    def test_la_regle_de_structure_sourcee_vient_des_reglages(self):
        sans = self._servir()
        self.assertFalse([ligne for ligne in sans['lignes']
                          if ligne['categorie'] == 'Structure'])
        avec = self._servir(reglages={'regle_bom_structure': {
            'valeur': REGLE_STRUCTURE, 'source': REGLE_STRUCTURE['source']}})
        self.assertEqual(len([ligne for ligne in avec['lignes']
                              if ligne['categorie'] == 'Structure']), 3)

    def test_une_regle_de_structure_sans_source_ne_publie_rien(self):
        servi = self._servir(reglages={'regle_bom_structure': {
            'valeur': REGLE_STRUCTURE, 'source': ''}})
        self.assertFalse([ligne for ligne in servi['lignes']
                          if ligne['categorie'] == 'Structure'])

    def test_les_correspondances_societe_posent_la_reference(self):
        servi = self._servir(
            reglages={'correspondances_nomenclature': {
                'valeur': {'QAC1': 77}, 'source': 'réglage société'}},
            catalogue={77: _Produit(77, reference='DISJ-C32')})
        lignes = [ligne for ligne in servi['lignes']
                  if ligne['designation'].startswith('QAC1')]
        self.assertTrue(lignes)
        for ligne in lignes:
            self.assertEqual(ligne['produit_id'], 77)
            self.assertEqual(ligne['reference'], 'DISJ-C32')

    def test_sans_noyau_le_bordereau_est_vide_sans_second_motif(self):
        servi = electrique._bordereau_du_calepinage(
            _Calepinage(), None, None)
        self.assertEqual(servi, {'lignes': [], 'alertes': []})

    def test_chaque_ligne_publie_ses_sept_clefs(self):
        for ligne in self._servir()['lignes']:
            self.assertEqual(
                sorted(ligne),
                ['categorie', 'designation', 'produit_id', 'quantite',
                 'reference', 'spec', 'unite'])

    def test_une_cle_de_reglage_hors_registre_est_refusee(self):
        with self.assertRaises(KeyError):
            electrique._valeur_reglee({}, 'cle_inventee')

    def test_sans_societe_aucune_reference_n_est_resolue(self):
        # Calcul hors base (aucune société) : le catalogue n'est pas
        # interrogeable, donc aucune référence — jamais celle d'ailleurs.
        references, alertes = electrique._references_nomenclature(
            None, {'QAC1': 77}, 'réglage société')
        self.assertEqual(references, {})
        self.assertEqual(len(alertes), 1)
        self.assertIn('QAC1', alertes[0])


if __name__ == '__main__':      # pragma: no cover
    unittest.main()

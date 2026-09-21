# -*- coding: utf-8 -*-
"""CALX227 — LE MÉTRÉ DE CÂBLE PAR TRONÇON ET PAR SECTION.

LE CONSTAT
----------
``core/electrique/nomenclature.py`` produisait UNE ligne de câblage par
repère (``W1``, ``W2``) avec ``longueur_m × nb_conducteurs`` : un dossier à
dix tronçons de trois sections sortait DEUX lignes, et le magasinier ne savait
pas quoi couper.

PARITÉ CITÉE
------------
PV*SOL exporte sa liste de pièces en CSV avec des numéros d'article
(https://help.valentin-software.com/pvsol/en/pages/plans-and-parts-list/) ;
OpenSolar décrit un BOM automatique couvrant les câbles
(https://www.opensolar.com/shop/).

CE QUE CES TESTS ARMENT
-----------------------
* trois sections ⇒ trois lignes, dont la SOMME des longueurs égale la somme
  des tronçons ;
* aucune ligne pour une section non calculable — et son omission est NOMMÉE
  par le service de tronçons ;
* aucun prix nulle part (la garde de mot-prix de l'export tableur, rejouée).

Tests PURS : ni base, ni réseau.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.export_tableur import verifier_absence_de_prix
from apps.calepinage.services.troncons import (
    COTE_AC, COTE_DC, COTE_TERRE, metre_de_cable,
)
from core.electrique.cables import dimensionner_cables
from core.electrique.chaines import concevoir_chaines
from core.electrique.nomenclature import nomenclature
from core.electrique.onduleurs import dimensionner_onduleurs
from core.electrique.protections import concevoir_protections
from core.electrique.types import (
    EntreeElectrique, GroupePan, SpecModule, SpecOnduleur,
)

MODULE = SpecModule(vmp_v=41.4, voc_v=49.3, isc_a=18.59, imp_a=17.59,
                    pmax_wc=710.0, designation='CS7N-710')
ONDULEUR = SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=500.0,
                        v_max_abs=600.0, i_max_mppt_a=26.0, ac_kw=5.0,
                        phases=1, designation='Deye SG05LP3')


def _troncon(identifiant, cote, longueur, section, conducteurs=2):
    """Un tronçon PUBLIÉ, réduit aux champs que le métré lit."""
    return {'id': identifiant, 'cote': cote, 'longueur_m': longueur,
            'section_mm2': section, 'nb_conducteurs': conducteurs}


#: Trois sections DC réelles sur cinq tronçons — le cas du plan.
TROIS_SECTIONS = [
    _troncon('ch1', COTE_DC, 18.4, 6.0),
    _troncon('ch2', COTE_DC, 12.0, 6.0),
    _troncon('ch3', COTE_DC, 30.5, 10.0),
    _troncon('ch4', COTE_DC, 8.25, 16.0),
    _troncon('ch5', COTE_AC, 34.7, 10.0, conducteurs=3),
]


class TroisSectionsTest(unittest.TestCase):
    """Trois sections ⇒ trois lignes, et la somme est ARMÉE."""

    def test_une_ligne_par_couple_cote_section(self):
        lignes = metre_de_cable(TROIS_SECTIONS)
        self.assertEqual([(ligne['cote'], ligne['section_mm2'])
                          for ligne in lignes],
                         [(COTE_DC, 6.0), (COTE_DC, 10.0), (COTE_DC, 16.0),
                          (COTE_AC, 10.0)])

    def test_trois_sections_dc_rendent_trois_lignes(self):
        dc = [ligne for ligne in metre_de_cable(TROIS_SECTIONS)
              if ligne['cote'] == COTE_DC]
        self.assertEqual(len(dc), 3)

    def test_la_somme_des_longueurs_egale_la_somme_des_troncons(self):
        lignes = metre_de_cable(TROIS_SECTIONS)
        self.assertAlmostEqual(
            sum(ligne['longueur_m'] for ligne in lignes),
            sum(troncon['longueur_m'] for troncon in TROIS_SECTIONS),
            places=2)

    def test_chaque_ligne_nomme_ses_troncons(self):
        lignes = {(ligne['cote'], ligne['section_mm2']): ligne
                  for ligne in metre_de_cable(TROIS_SECTIONS)}
        self.assertEqual(lignes[(COTE_DC, 6.0)]['repere_des_troncons'],
                         ['ch1', 'ch2'])
        self.assertAlmostEqual(lignes[(COTE_DC, 6.0)]['longueur_m'], 30.4,
                               places=2)

    def test_les_cinq_champs_sont_toujours_presents(self):
        for ligne in metre_de_cable(TROIS_SECTIONS):
            self.assertEqual(
                sorted(ligne),
                ['cote', 'longueur_m', 'nb_conducteurs',
                 'repere_des_troncons', 'section_mm2'])

    def test_les_cotes_sortent_dans_l_ordre_du_courant(self):
        lignes = metre_de_cable([
            _troncon('t1', COTE_TERRE, 10.0, 16.0, conducteurs=1),
            _troncon('t2', COTE_AC, 20.0, 10.0, conducteurs=3),
            _troncon('t3', COTE_DC, 30.0, 6.0),
        ])
        self.assertEqual([ligne['cote'] for ligne in lignes],
                         [COTE_DC, COTE_AC, COTE_TERRE])


class SectionNonCalculableTest(unittest.TestCase):
    """Aucune ligne pour une section non calculable — l'omission est nommée."""

    def test_un_troncon_sans_section_ne_produit_aucune_ligne(self):
        lignes = metre_de_cable([
            _troncon('ch1', COTE_DC, 18.4, 6.0),
            _troncon('ch5', COTE_TERRE, 9.0, None, conducteurs=1),
        ])
        self.assertEqual([(ligne['cote'], ligne['section_mm2'])
                          for ligne in lignes], [(COTE_DC, 6.0)])

    def test_un_troncon_sans_longueur_ne_produit_aucune_ligne(self):
        lignes = metre_de_cable([
            _troncon('ch1', COTE_DC, None, 6.0),
        ])
        self.assertEqual(lignes, [])

    def test_l_omission_est_nommee_par_le_service_de_troncons(self):
        # Le motif de la section non calculable est celui que
        # ``_dimensionner_troncon`` prononce déjà, tronçon par tronçon et par
        # cause racine : le métré ne le réécrit pas, il s'abstient.
        from apps.calepinage.services.troncons import _troncons_du_document

        servi = _troncons_du_document({'electrical': {'cheminements': [
            {'id': 'ch5', 'cote': 'terre', 'de': 'eq1', 'vers': 'eq9',
             'longueurSaisieM': 9.0},
        ]}}, {'norme': {'applicable': False,
                        'motif': "aucune norme électrique n'est choisie"}})
        self.assertEqual(metre_de_cable(servi['troncons']), [])
        self.assertTrue(servi['omissions'])
        omission = servi['omissions'][0]
        self.assertEqual(omission['troncon'], 'ch5')
        self.assertEqual(omission['champ'], 'section_mm2')
        self.assertIn("aucune norme électrique n'est choisie",
                      omission['motif'])

    def test_une_liste_vide_rend_une_liste_vide(self):
        self.assertEqual(metre_de_cable([]), [])
        self.assertEqual(metre_de_cable(None), [])


class ConducteursNonHomogenesTest(unittest.TestCase):
    """Deux nombres de conducteurs sur un couple : aucun n'est choisi."""

    def test_le_nombre_de_conducteurs_devient_null(self):
        lignes = metre_de_cable([
            _troncon('ch1', COTE_AC, 10.0, 10.0, conducteurs=3),
            _troncon('ch2', COTE_AC, 5.0, 10.0, conducteurs=5),
        ])
        self.assertEqual(len(lignes), 1)
        self.assertIsNone(lignes[0]['nb_conducteurs'])
        self.assertAlmostEqual(lignes[0]['longueur_m'], 15.0, places=2)


def _entree(nb_modules=20):
    return EntreeElectrique(
        module=MODULE, onduleur=ONDULEUR,
        groupes=(GroupePan(label='Sud', nb_modules=nb_modules,
                           azimut_deg=180.0, inclinaison_deg=15.0),),
        dc_m=30.0, ac_m=12.0, phases=1)


def _pieces():
    entree = _entree()
    chaines = concevoir_chaines(entree)
    evaluation = dimensionner_onduleurs(entree, chaines.puissance_kwc)
    protections = concevoir_protections(entree, chaines, evaluation)
    cables = dimensionner_cables(entree, chaines, protections)
    return entree, chaines, protections, cables


class NomenclatureLitLeMetreTest(unittest.TestCase):
    """La nomenclature lit CETTE liste quand elle existe, l'ancienne sinon."""

    def _lignes_de_cablage(self, metre=None):
        entree, chaines, protections, cables = _pieces()
        resultat = nomenclature(entree, chaines, protections, cables,
                                metre_cable=metre)
        return [ligne for ligne in resultat.lignes
                if ligne.categorie in ('Câblage DC', 'Câblage AC')]

    def test_sans_metre_la_sortie_est_celle_d_aujourd_hui(self):
        lignes = self._lignes_de_cablage()
        self.assertEqual(len(lignes), 2)
        self.assertTrue(any('H1Z2Z2-K' in ligne.designation
                            for ligne in lignes))

    def test_avec_metre_une_ligne_par_couple(self):
        lignes = self._lignes_de_cablage(metre_de_cable(TROIS_SECTIONS))
        self.assertEqual(len(lignes), 4)
        self.assertEqual([ligne.categorie for ligne in lignes],
                         ['Câblage DC', 'Câblage DC', 'Câblage DC',
                          'Câblage AC'])

    def test_la_designation_reprend_celle_du_cable_dimensionne(self):
        lignes = self._lignes_de_cablage(metre_de_cable(TROIS_SECTIONS))
        self.assertTrue(lignes[0].designation.startswith(
            'Câble solaire Nexans H1Z2Z2-K'))
        self.assertIn('6,0 mm²', lignes[0].designation)

    def test_la_quantite_multiplie_par_les_conducteurs(self):
        lignes = self._lignes_de_cablage(metre_de_cable(TROIS_SECTIONS))
        # 18,4 + 12,0 = 30,4 m de cheminement × 2 conducteurs DC.
        self.assertAlmostEqual(lignes[0].quantite, 60.8, places=1)
        self.assertIn('ch1, ch2', lignes[0].spec)

    def test_un_couple_sans_conducteurs_homogenes_publie_le_cheminement(self):
        metre = metre_de_cable([
            _troncon('ch1', COTE_AC, 10.0, 10.0, conducteurs=3),
            _troncon('ch2', COTE_AC, 5.0, 10.0, conducteurs=5),
        ])
        lignes = self._lignes_de_cablage(metre)
        self.assertEqual(len(lignes), 1)
        self.assertAlmostEqual(lignes[0].quantite, 15.0, places=1)
        self.assertIn('non homogène', lignes[0].spec)

    def test_la_ligne_de_metre_se_rattache_a_une_reference(self):
        entree, chaines, protections, cables = _pieces()
        resultat = nomenclature(
            entree, chaines, protections, cables,
            metre_cable=metre_de_cable(TROIS_SECTIONS),
            references={'W1': {'produit_id': 5, 'reference': 'H1Z2Z2K'}})
        lignes = [ligne for ligne in resultat.lignes
                  if ligne.categorie == 'Câblage DC']
        for ligne in lignes:
            self.assertEqual(ligne.produit_id, 5)

    def test_aucun_prix_dans_le_metre_publie(self):
        entree, chaines, protections, cables = _pieces()
        resultat = nomenclature(entree, chaines, protections, cables,
                                metre_cable=metre_de_cable(TROIS_SECTIONS))
        entetes = ['Catégorie', 'Désignation', 'Quantité', 'Unité',
                   'Spécification']
        lignes = [[ligne.categorie, ligne.designation, ligne.quantite,
                   ligne.unite, ligne.spec] for ligne in resultat.lignes]
        # Ne lève pas = aucune cellule ne porte prix / marge / montant / TVA.
        verifier_absence_de_prix(entetes, lignes)


if __name__ == '__main__':      # pragma: no cover
    unittest.main()

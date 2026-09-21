# -*- coding: utf-8 -*-
"""CALX237 — le GABARIT de schéma par pays, sans supposer une norme au Maroc.

LES TROIS CAS DEMANDÉS
----------------------
1. **Norme française applicable** — gabarit ``fr`` : la chaîne dessinée est
   celle d'aujourd'hui, octet pour octet, et le gabarit ne cite QUE les
   textes que le verdict de norme porte déjà.
2. **Norme déclarée par la société** — gabarit ``societe`` : même dessin, et
   le libellé NOMME le texte qui le fonde (``services/norme.py`` refuse déjà
   une norme sans référence).
3. **Aucune norme** — gabarit ``neutre`` : la planche passe en mode
   TOPOLOGIE et ne montre AUCUN calibre ni AUCUNE section ; un bandeau dit
   pourquoi et nomme le réglage manquant.

ET CE QUI N'EXISTE PAS
----------------------
Aucun gabarit marocain, aucun symbole marocain, aucune référence marocaine :
il n'existe aucun texte normatif marocain dans ce dépôt, et les textes
français ne s'impriment pas sur un chantier qui ne les a pas choisis
(décision fondateur D1).

``SimpleTestCase`` : aucune base de données — ``norme_applicable`` se
construit depuis un dict de réglages.

Run :
    python manage.py test apps.calepinage.tests.test_calx237_gabarits_pays
"""
from __future__ import annotations

import pathlib
import re

from django.test import SimpleTestCase

from core.electrique import concevoir
from core.electrique.types import (
    EntreeElectrique, GroupePan, SpecModule, SpecOnduleur,
)

from apps.calepinage.services.norme import NORME_FRANCAISE, norme_applicable
from apps.calepinage.services.sld import (
    GABARIT_FR, GABARIT_NEUTRE, GABARIT_SOCIETE, gabarit_de_schema,
    rendu_du_schema,
)

SERVICE_SLD = (pathlib.Path(__file__).resolve().parents[1]
               / 'services' / 'sld.py').read_text(encoding='utf-8')

MODULE = SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                    pmax_wc=550.0, temp_coeff_voc_pct_c=-0.27,
                    temp_coeff_pmax_pct_c=-0.35,
                    designation='Canadian Solar 550 Wc')
ONDULEUR = SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=850.0,
                        v_max_abs=1000.0, i_max_mppt_a=26.0, ac_kw=10.0,
                        v_demarrage_v=90.0,
                        designation='Deye SUN-10K-SG05LP3')

#: Le texte que la société déclare pour fonder SON gabarit — une saisie de
#: test, jamais un texte normatif marocain (il n'en existe aucun ici).
TEXTE_SOCIETE = 'Cahier des charges interne — édition 2026, §4 protections'

NORME_FRANCE = norme_applicable({'imagerie': {'pays': 'fr'}})
NORME_SOCIETE = norme_applicable({
    'imagerie': {'pays': 'ma'},
    'norme_electrique': {'norme': 'interne_societe',
                         'reference': TEXTE_SOCIETE},
})
NORME_ABSENTE = norme_applicable({'imagerie': {'pays': 'ma'}})

#: Ce qu'une planche SANS norme ne doit jamais montrer : une section de
#: câble (mm²) ou l'en-tête de colonne des calibres.
MARQUEURS_DE_CALIBRE = ('mm²', 'Calibre / section')


def _entree():
    return EntreeElectrique(module=MODULE, onduleur=ONDULEUR,
                            groupes=(GroupePan('Sud', 24, 180.0, 15.0),),
                            dc_m=30.0, ac_m=12.0)


def _textes(svg):
    return re.findall(r'>([^<>]+)</text>', svg)


class NormeFrancaiseTest(SimpleTestCase):
    """1 — le gabarit français : aucun changement de dessin."""

    def setUp(self):
        self.gabarit = gabarit_de_schema(NORME_FRANCE)

    def test_le_code_est_fr(self):
        self.assertEqual(self.gabarit['code'], GABARIT_FR)
        self.assertEqual(self.gabarit['norme'], NORME_FRANCAISE)

    def test_le_gabarit_ne_degrade_pas_la_planche(self):
        self.assertFalse(self.gabarit['standard'])
        self.assertEqual(self.gabarit['bandeau'], '')

    def test_les_references_sont_celles_du_verdict_de_norme(self):
        """Rien n'est recopié ici : chaque texte vient du verdict."""
        du_verdict = {NORME_FRANCE['reference']} | {
            coefficient['reference']
            for coefficient in NORME_FRANCE['coefficients'].values()}
        self.assertTrue(self.gabarit['references'])
        self.assertEqual(set(self.gabarit['references']) - du_verdict, set())

    def test_le_dessin_est_celui_d_aujourd_hui(self):
        entree = _entree()
        resultat = concevoir(entree)
        self.assertEqual(
            rendu_du_schema(entree, resultat, gabarit=self.gabarit)['svg'],
            rendu_du_schema(entree, resultat)['svg'])


class NormeSocieteDeclareeTest(SimpleTestCase):
    """2 — la société déclare SON gabarit en nommant le texte qui le fonde."""

    def setUp(self):
        self.gabarit = gabarit_de_schema(NORME_SOCIETE)

    def test_la_norme_declaree_est_applicable(self):
        self.assertTrue(NORME_SOCIETE['applicable'])

    def test_le_code_est_societe(self):
        self.assertEqual(self.gabarit['code'], GABARIT_SOCIETE)

    def test_le_libelle_nomme_le_texte_qui_le_fonde(self):
        self.assertIn(TEXTE_SOCIETE, self.gabarit['libelle'])
        self.assertIn(TEXTE_SOCIETE, self.gabarit['references'])

    def test_le_dessin_n_est_pas_degrade(self):
        self.assertFalse(self.gabarit['standard'])
        entree = _entree()
        resultat = concevoir(entree)
        self.assertEqual(
            rendu_du_schema(entree, resultat, gabarit=self.gabarit)['svg'],
            rendu_du_schema(entree, resultat)['svg'])


class AucuneNormeTest(SimpleTestCase):
    """3 — pays « ma » sans norme : topologie seule, et le bandeau le dit."""

    def setUp(self):
        self.gabarit = gabarit_de_schema(NORME_ABSENTE)
        self.entree = _entree()
        self.resultat = concevoir(self.entree)
        self.svg = rendu_du_schema(self.entree, self.resultat,
                                   gabarit=self.gabarit)['svg']

    def test_le_code_est_neutre_et_il_est_nomme(self):
        self.assertEqual(self.gabarit['code'], GABARIT_NEUTRE)
        self.assertIn('neutre', self.gabarit['libelle'].lower())

    def test_aucune_reference_n_est_citee(self):
        self.assertEqual(self.gabarit['references'], ())
        self.assertEqual(self.gabarit['reference'], '')
        self.assertIsNone(self.gabarit['norme'])

    def test_la_planche_ne_montre_aucun_calibre_ni_section(self):
        for marqueur in MARQUEURS_DE_CALIBRE:
            self.assertNotIn(marqueur, self.svg,
                             'Sans norme choisie, « %s » ne doit pas être '
                             'imprimé sur la planche.' % marqueur)
        for protection in self.resultat.protections:
            if protection.calibre:
                self.assertNotIn(protection.calibre, self.svg,
                                 'Le calibre « %s » reste dessiné alors '
                                 "qu'aucune norme ne le fonde."
                                 % protection.calibre)

    def test_les_reperes_et_designations_restent_lisibles(self):
        """La topologie reste COMPLÈTE : le client doit pouvoir nommer ce
        qu'il a."""
        for protection in self.resultat.protections:
            self.assertIn('data-repere="%s"' % protection.repere, self.svg)

    def test_le_bandeau_nomme_le_reglage_manquant(self):
        self.assertIn('Norme électrique', self.gabarit['bandeau'])
        self.assertIn('ma', self.gabarit['bandeau'])
        self.assertTrue(any('Norme électrique' in texte
                            for texte in _textes(self.svg)),
                        'Le bandeau doit être DESSINÉ, pas seulement rendu '
                        'dans la réponse.')

    def test_le_bandeau_ne_reintroduit_aucun_calibre(self):
        for marqueur in MARQUEURS_DE_CALIBRE:
            self.assertNotIn(marqueur, self.gabarit['bandeau'])

    def test_le_svg_reste_un_document_clos(self):
        self.assertTrue(self.svg.endswith('</svg>'))
        self.assertEqual(self.svg.count('</svg>'), 1)


class AucunGabaritMarocainTest(SimpleTestCase):
    """Aucun symbole ni référence marocaine n'est inventé (D1)."""

    def test_le_service_ne_declare_aucun_gabarit_marocain(self):
        codes = re.findall(r"^GABARIT_(\w+) = '(\w+)'", SERVICE_SLD,
                           flags=re.MULTILINE)
        self.assertEqual(sorted(code for _nom, code in codes),
                         ['fr', 'neutre', 'societe'])

    def test_aucune_norme_marocaine_n_est_citee(self):
        for interdit in ('NM ', 'IMANOR', 'ONEE 15', 'norme marocaine'):
            self.assertNotIn(interdit, SERVICE_SLD)

    def test_un_gabarit_absent_vaut_la_planche_d_aujourd_hui(self):
        """``gabarit=None`` — comportement d'aujourd'hui, strictement."""
        entree = _entree()
        resultat = concevoir(entree)
        self.assertEqual(rendu_du_schema(entree, resultat,
                                         gabarit=None)['svg'],
                         rendu_du_schema(entree, resultat)['svg'])

    def test_un_verdict_illisible_bascule_en_neutre(self):
        """Pas de norme lisible ⇒ on OMET, jamais un barème supposé."""
        self.assertEqual(gabarit_de_schema(None)['code'], GABARIT_NEUTRE)
        self.assertEqual(gabarit_de_schema({})['code'], GABARIT_NEUTRE)

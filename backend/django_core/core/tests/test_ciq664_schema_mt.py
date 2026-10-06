# -*- coding: utf-8 -*-
"""CIQ664 — schéma unifilaire : un ÉTAGE MT dessiné seulement pour un site MT.

Le moteur électrique pur ne dessine l'étage moyenne tension (transformateur,
cellule, protection de découplage, [compteur de production], [limiteur
d'injection]) QUE si on lui donne un ``etage_mt`` — renseigné depuis un relevé
de visite MT validé, jamais déduit. Chaque bloc est « à confirmer » (aucune
règle sourcée), la protection de découplage dit que ses réglages relèvent de
l'étude du distributeur, et un site BT garde la planche d'avant octet pour
octet. Aucune valeur électrique n'est inventée.

Aucune base de données : ``unittest`` pur.
"""

import dataclasses
import unittest
import xml.etree.ElementTree as ET

from core.electrique import concevoir
from core.electrique.schema import (
    MENTION_A_CONFIRMER,
    MENTION_DECOUPLAGE,
    _CARACTERES_TITRE,
    _lignes_sous_titre,
    blocs_du_schema,
    rendre_schema,
)
from core.electrique.types import (
    EntreeElectrique,
    EtageMt,
    GroupePan,
    SpecModule,
    SpecOnduleur,
    TransformateurMt,
)

MODULE_550 = SpecModule(vmp_v=41.5, voc_v=49.5, isc_a=13.9, imp_a=13.26,
                        pmax_wc=550.0, temp_coeff_voc_pct_c=-0.25,
                        temp_coeff_pmax_pct_c=-0.35)

ETAGE = EtageMt(
    transformateurs=(TransformateurMt(nb=1, kva=400.0),),
    cellule='cellule disjoncteur existante')


def _entree(**kwargs):
    return EntreeElectrique(
        module=MODULE_550,
        onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=200.0, mppt_v_max=850.0,
                              v_max_abs=1000.0, i_max_mppt_a=26.0, ac_kw=12.0,
                              phases=3, v_demarrage_v=200.0),
        groupes=(GroupePan("Sud", 12, 180.0, 15.0),
                 GroupePan("Ouest", 12, 270.0, 15.0)),
        dc_m=25.0, ac_m=15.0, phases=3, **kwargs)


def _clefs(entree, **kwargs):
    return [b.clef for b in blocs_du_schema(entree, concevoir(entree),
                                            **kwargs)]


def _blocs(entree, **kwargs):
    return {b.clef: b for b in blocs_du_schema(entree, concevoir(entree),
                                               **kwargs)}


class EtageMtDessine(unittest.TestCase):
    def test_entree_mt_transformateur_cellule_et_decouplage_sont_presents(self):
        clefs = _clefs(_entree(etage_mt=ETAGE))
        for clef in ('transformateur_mt', 'cellule_mt', 'decouplage_mt'):
            self.assertIn(clef, clefs)

    def test_ordre_tgbt_puis_etage_mt_puis_reseau(self):
        clefs = _clefs(_entree(etage_mt=ETAGE))
        self.assertEqual(
            clefs[clefs.index('tgbt'):],
            ['tgbt', 'transformateur_mt', 'cellule_mt', 'decouplage_mt',
             'reseau'])

    def test_chaque_bloc_mt_est_a_confirmer_en_tete_du_sous_titre(self):
        blocs = _blocs(_entree(etage_mt=ETAGE))
        for clef in ('transformateur_mt', 'cellule_mt', 'decouplage_mt'):
            self.assertTrue(blocs[clef].sous_titre.startswith(
                MENTION_A_CONFIRMER), clef)

    def test_la_mention_survit_a_la_coupe_de_la_boite(self):
        blocs = _blocs(_entree(etage_mt=ETAGE))
        for clef in ('transformateur_mt', 'cellule_mt', 'decouplage_mt'):
            lignes = _lignes_sous_titre(blocs[clef].sous_titre)
            self.assertIn(MENTION_A_CONFIRMER, ' '.join(lignes), clef)

    def test_decouplage_porte_les_reglages_du_distributeur_en_entier(self):
        bloc = _blocs(_entree(etage_mt=ETAGE))['decouplage_mt']
        # La phrase est coupée sur deux lignes de la boîte, jamais altérée.
        self.assertIn(MENTION_DECOUPLAGE, bloc.sous_titre.replace("\n", " "))
        lignes = ' '.join(_lignes_sous_titre(bloc.sous_titre))
        self.assertIn("réglages fixés par l'étude du distributeur", lignes)

    def test_les_titres_tiennent_dans_la_boite(self):
        for bloc in _blocs(_entree(etage_mt=EtageMt(
                compteur_production=True, injection_limitee=True))).values():
            self.assertLessEqual(len(bloc.titre), _CARACTERES_TITRE + 3,
                                 bloc.clef)

    def test_les_donnees_relevees_sont_reprises_telles_quelles(self):
        blocs = _blocs(_entree(etage_mt=ETAGE))
        self.assertIn('1 × 400 kVA', blocs['transformateur_mt'].sous_titre)
        self.assertIn('cellule disjoncteur existante',
                      blocs['cellule_mt'].sous_titre)

    def test_aucun_releve_dessine_quand_meme_les_blocs_a_confirmer(self):
        blocs = _blocs(_entree(etage_mt=EtageMt()))
        self.assertEqual(blocs['transformateur_mt'].sous_titre,
                         MENTION_A_CONFIRMER)
        self.assertEqual(blocs['cellule_mt'].sous_titre, MENTION_A_CONFIRMER)

    def test_niveau_standard_ne_publie_ni_puissance_ni_cellule(self):
        blocs = _blocs(_entree(etage_mt=ETAGE), standard=True)
        self.assertNotIn('kVA', blocs['transformateur_mt'].sous_titre)
        self.assertNotIn('disjoncteur', blocs['cellule_mt'].sous_titre)
        self.assertIn('1 u', blocs['transformateur_mt'].sous_titre)

    def test_aucun_rapport_de_transformation_invente(self):
        sans = _blocs(_entree(etage_mt=ETAGE))['transformateur_mt']
        self.assertNotRegex(sans.sous_titre, r'[0-9] kV[^A]')
        avec = _blocs(_entree(etage_mt=EtageMt(transformateurs=(
            TransformateurMt(1, 400.0, '20 kV / 400 V'),))))
        self.assertIn('20 kV / 400 V', avec['transformateur_mt'].sous_titre)


class BlocsFacultatifs(unittest.TestCase):
    def test_limiteur_absent_sans_injection_limitee(self):
        self.assertNotIn('limiteur_injection',
                         _clefs(_entree(etage_mt=ETAGE)))

    def test_limiteur_present_quand_la_sortie_du_moteur_le_dit(self):
        etage = dataclasses.replace(ETAGE, injection_limitee=True)
        clefs = _clefs(_entree(etage_mt=etage))
        self.assertEqual(
            clefs[clefs.index('decouplage_mt'):],
            ['decouplage_mt', 'limiteur_injection', 'reseau'])

    def test_compteur_de_production_mt_seulement_s_il_est_releve(self):
        self.assertNotIn('compteur_production_mt',
                         _clefs(_entree(etage_mt=ETAGE)))
        etage = dataclasses.replace(ETAGE, compteur_production=True)
        self.assertIn('compteur_production_mt',
                      _clefs(_entree(etage_mt=etage)))


class SiteBtInchange(unittest.TestCase):
    def test_sans_etage_mt_aucun_bloc_mt(self):
        clefs = _clefs(_entree())
        for clef in ('transformateur_mt', 'cellule_mt', 'decouplage_mt',
                     'limiteur_injection', 'compteur_production_mt'):
            self.assertNotIn(clef, clefs)

    def test_etage_none_est_la_planche_d_avant_octet_pour_octet(self):
        entree = _entree()
        self.assertIsNone(entree.etage_mt)
        resultat = concevoir(entree)
        explicite = dataclasses.replace(entree, etage_mt=None)
        self.assertEqual(rendre_schema(entree, resultat),
                         rendre_schema(explicite, concevoir(explicite)))
        svg = rendre_schema(entree, resultat)
        for mot in ('Transformateur MT', 'Cellule MT', 'découplage',
                    MENTION_A_CONFIRMER):
            self.assertNotIn(mot, svg)

    def test_l_etage_mt_ne_change_aucun_calcul(self):
        sans = concevoir(_entree())
        avec = concevoir(_entree(etage_mt=ETAGE))
        self.assertEqual(sans.protections, avec.protections)
        self.assertEqual(sans.cables, avec.cables)
        self.assertEqual(sans.bom, avec.bom)


class RenduSvg(unittest.TestCase):
    def test_le_svg_mt_est_du_xml_valide_avec_les_mentions(self):
        entree = _entree(etage_mt=dataclasses.replace(
            ETAGE, injection_limitee=True, compteur_production=True))
        svg = rendre_schema(entree, concevoir(entree))
        racine = ET.fromstring(svg)
        textes = ' | '.join(t.text or '' for t in racine.iter(
            '{http://www.w3.org/2000/svg}text'))
        for texte in ('Transformateur MT/BT', 'Cellule MT',
                      'Protection découplage', "Limiteur d'injection",
                      MENTION_A_CONFIRMER, "par l'étude du distributeur",
                      'réglages fixés'):
            self.assertIn(texte, textes)

    def test_aucun_prix_ni_marge_dans_le_schema_mt(self):
        entree = _entree(etage_mt=ETAGE)
        svg = rendre_schema(entree, concevoir(entree)).lower()
        for interdit in ('prix', 'mad', 'marge', 'dh'):
            self.assertNotIn(' %s ' % interdit, svg)


if __name__ == '__main__':
    unittest.main()

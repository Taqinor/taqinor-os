# -*- coding: utf-8 -*-
"""CALX210 — calibrer la protection ET le câble de CHAQUE branche AC.

``courant_emploi_ac`` calculait un Ib depuis UNE puissance AC d'onduleur et
``dimensionner_cables`` ne produisait qu'un ``W2`` unique : une installation à
N branches de micro-onduleurs n'avait ni calibre par branche ni section par
branche.

Ce module arme :

* trois branches ⇒ trois calibres ``QAC.1..3`` et trois sections ``W2.1..3``,
  chacune avec SON ``critere_dimensionnant`` et la source de son barème ;
* le cas à ZÉRO micro-onduleur rend exactement le ``W2`` d'aujourd'hui ;
* une branche à qui il manque un champ est OMISE en le nommant — jamais
  dimensionnée à zéro.

Aucune constante n'est posée ici ni dans le noyau : les barèmes
``AMPACITE_U1000R2V_*``, la cible ``CHUTE_CIBLE_AC_PCT`` et
``calibre_disjoncteur`` existaient déjà. ``SimpleTestCase``, aucune base.
"""

from django.test import SimpleTestCase

from core.electrique.cables import (
    CHUTE_CIBLE_AC_PCT,
    CRITERE_CHUTE,
    CRITERE_ECHAUFFEMENT,
    CRITERE_LES_DEUX,
    dimensionner_branches_ac,
    dimensionner_cables,
)
from core.electrique.chaines import concevoir_chaines
from core.electrique.protections import (
    calibre_disjoncteur,
    calibrer_branches_ac,
    concevoir_protections,
)
from core.electrique.types import (
    EntreeElectrique,
    GroupePan,
    SpecModule,
    SpecOnduleur,
)

MODULE = SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                    pmax_wc=550.0, temp_coeff_voc_pct_c=-0.27,
                    temp_coeff_pmax_pct_c=-0.35)
ONDULEUR = SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=850.0,
                        v_max_abs=1000.0, i_max_mppt_a=26.0, ac_kw=10.0,
                        v_demarrage_v=90.0)

#: La forme que CALX209 publie, complétée des trois grandeurs de cheminement.
TROIS_BRANCHES = (
    {'repere': 'BR1', 'unites': 8, 'i_branche_a': 8.0, 'longueur_m': 25.0,
     'tension_v': 230.0, 'phases': 1},
    {'repere': 'BR2', 'unites': 12, 'i_branche_a': 12.0, 'longueur_m': 60.0,
     'tension_v': 230.0, 'phases': 1},
    {'repere': 'BR3', 'unites': 4, 'i_branche_a': 4.0, 'longueur_m': 5.0,
     'tension_v': 230.0, 'phases': 1},
)


def _entree(nb_modules=20, **kw):
    return EntreeElectrique(module=MODULE, onduleur=ONDULEUR,
                            groupes=(GroupePan('Sud', nb_modules, 180.0, 15.0),),
                            dc_m=30.0, ac_m=12.0, **kw)


def _resultat_cables(entree, branches_ac=None):
    chaines = concevoir_chaines(entree)
    protections = concevoir_protections(entree, chaines)
    return dimensionner_cables(entree, chaines, protections,
                               branches_ac=branches_ac)


class TroisBranchesTroisCalibresTroisSections(SimpleTestCase):
    def test_trois_calibres_QAC(self):
        resultat = calibrer_branches_ac(TROIS_BRANCHES, phases=1,
                                        tension_reseau_v=230.0)
        self.assertEqual([p.repere for p in resultat.protections],
                         ['QAC.1', 'QAC.2', 'QAC.3'])
        self.assertEqual(resultat.omissions, ())
        # Chaque calibre est CELUI de la fonction existante, pas un autre.
        for protection, branche in zip(resultat.protections, TROIS_BRANCHES):
            attendu = calibre_disjoncteur(branche['i_branche_a'])
            self.assertIn('%d A' % int(attendu), protection.calibre)
            self.assertIn('NF C 15-100 §433.1', protection.regle_source)
            self.assertIn(branche['repere'], protection.designation)

    def test_trois_sections_W2_chacune_avec_son_critere(self):
        resultat = dimensionner_branches_ac(TROIS_BRANCHES, phases=1,
                                            tension_reseau_v=230.0)
        self.assertEqual([c.repere for c in resultat.cables],
                         ['W2.1', 'W2.2', 'W2.3'])
        self.assertEqual(resultat.omissions, ())
        for cable in resultat.cables:
            self.assertIn(cable.critere_dimensionnant,
                          (CRITERE_ECHAUFFEMENT, CRITERE_CHUTE,
                           CRITERE_LES_DEUX))
            self.assertEqual(cable.chute_cible_pct, CHUTE_CIBLE_AC_PCT)
            self.assertIn('IEC 60364-5-52', cable.regle_source)
            self.assertIn('UTE C 15-712-1', cable.regle_source)
            self.assertGreater(cable.section_mm2, 0)

    def test_la_branche_longue_demande_plus_de_cuivre(self):
        """60 m à 12 A contre 5 m à 4 A : la chute de tension tranche."""
        resultat = dimensionner_branches_ac(TROIS_BRANCHES, phases=1,
                                            tension_reseau_v=230.0)
        longue = resultat.cables[1]
        courte = resultat.cables[2]
        self.assertGreater(longue.section_mm2, courte.section_mm2)
        self.assertEqual(longue.critere_dimensionnant, CRITERE_CHUTE)

    def test_le_calibre_de_la_branche_entre_dans_la_verification(self):
        """``Ib ≤ In ≤ Iz`` : le calibre publié par CALX209 est repris."""
        calibres = {p.designation.split('branche ')[-1]: p.calibre
                    for p in calibrer_branches_ac(
                        TROIS_BRANCHES, tension_reseau_v=230.0).protections}
        self.assertEqual(len(calibres), 3)
        resultat = dimensionner_branches_ac(
            TROIS_BRANCHES, phases=1, tension_reseau_v=230.0,
            calibres={'BR1': 16.0, 'BR2': 16.0, 'BR3': 16.0})
        for cable in resultat.cables:
            self.assertEqual(cable.in_a, 16.0)
            self.assertGreaterEqual(cable.iz_a, 16.0)
            self.assertTrue(cable.conforme)

    def test_le_triphase_prend_le_bareme_triphase(self):
        branche = dict(TROIS_BRANCHES[0], phases=3, tension_v=400.0)
        resultat = dimensionner_branches_ac((branche,))
        cable = resultat.cables[0]
        self.assertEqual(cable.nb_conducteurs, 5)
        self.assertIn('barème triphasé', cable.regle_source)
        self.assertIn('√3', cable.regle_source)


class UneBrancheIncompleteEstOmiseEnNommantLeChamp(SimpleTestCase):
    def test_sans_courant_d_emploi(self):
        branches = ({'repere': 'BR1', 'unites': 8, 'longueur_m': 25.0},)
        calibres = calibrer_branches_ac(branches)
        self.assertEqual(calibres.protections, ())
        self.assertIn('i_branche_a', calibres.omissions[0])
        self.assertIn('BR1', calibres.omissions[0])
        sections = dimensionner_branches_ac(branches)
        self.assertEqual(sections.cables, ())
        self.assertIn('i_branche_a', sections.omissions[0])

    def test_sans_longueur(self):
        branches = ({'repere': 'BR1', 'i_branche_a': 8.0,
                     'tension_v': 230.0},)
        sections = dimensionner_branches_ac(branches)
        self.assertEqual(sections.cables, ())
        self.assertIn('longueur_m', sections.omissions[0])
        # Le CALIBRE, lui, n'a pas besoin de la longueur : il est produit.
        self.assertEqual(len(calibrer_branches_ac(branches).protections), 1)

    def test_sans_tension_nulle_part(self):
        branches = ({'repere': 'BR1', 'i_branche_a': 8.0,
                     'longueur_m': 25.0},)
        sections = dimensionner_branches_ac(branches)
        self.assertEqual(sections.cables, ())
        self.assertIn('tension_v', sections.omissions[0])
        # L'étiquette du calibre n'invente alors aucune tension.
        calibre = calibrer_branches_ac(branches).protections[0].calibre
        self.assertNotIn('V', calibre)

    def test_la_tension_de_l_installation_supplee_la_branche(self):
        branches = ({'repere': 'BR1', 'i_branche_a': 8.0,
                     'longueur_m': 25.0},)
        sections = dimensionner_branches_ac(branches, tension_reseau_v=230.0)
        self.assertEqual(sections.omissions, ())
        self.assertEqual(len(sections.cables), 1)


class ZeroMicroOnduleurRendLeW2DAujourdhui(SimpleTestCase):
    """Non-régression : la liaison AC unique est INCHANGÉE, champ par champ."""

    def test_sans_branches_le_resultat_est_identique(self):
        entree = _entree()
        reference = _resultat_cables(entree)
        for branches in (None, (), []):
            with self.subTest(branches=branches):
                self.assertEqual(_resultat_cables(entree, branches),
                                 reference)

    def test_le_repere_reste_W2(self):
        cables = _resultat_cables(_entree()).cables
        self.assertEqual([c.repere for c in cables], ['W1', 'W2'])

    def test_avec_branches_les_W2_pointes_remplacent_le_W2(self):
        cables = _resultat_cables(_entree(), TROIS_BRANCHES).cables
        self.assertEqual([c.repere for c in cables],
                         ['W1', 'W2.1', 'W2.2', 'W2.3'])
        self.assertNotIn('W2', [c.repere for c in cables])

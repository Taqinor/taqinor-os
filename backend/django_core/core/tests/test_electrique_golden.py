# -*- coding: utf-8 -*-
"""PV38 — trois dossiers GOLDEN de bout en bout + le contrat des tiroirs.

Trois installations représentatives passent par ``concevoir()`` et leurs nombres
publiables sont FIGÉS ici : mono réseau 8 panneaux, triphasé 24 panneaux sur
deux pans, hybride avec batterie. Un golden ne teste pas une fonction, il teste
un DOSSIER : si une règle change un calibre ou une section, ces tests le disent
avant qu'un client ne le voie.

La dernière classe verrouille le contrat de charge utile lu par
``frontend/src/features/ao/calepinage/TiroirElectrique.jsx`` — clé par clé, ni
plus ni moins : une clé en trop est du code mort côté écran, une clé en moins
est une ligne vide.

Aucune base de données : ``unittest`` pur.
"""

import ast
import os
import unittest

from core.electrique import SCHEMA_VERSION, VERSION_MOTEUR, concevoir
from core.electrique.types import (
    EntreeElectrique,
    GroupePan,
    SpecModule,
    SpecOnduleur,
)

MODULE_550 = SpecModule(vmp_v=41.5, voc_v=49.5, isc_a=13.9, imp_a=13.26,
                        pmax_wc=550.0, temp_coeff_voc_pct_c=-0.25,
                        temp_coeff_pmax_pct_c=-0.35)


def _repere(collection, repere):
    for element in collection:
        if element.repere == repere:
            return element
    return None


# ═══════════════════════════════ CAS 1 ═══════════════════════════════════════
class MonoReseauHuitPanneaux(unittest.TestCase):
    """Villa : 8 × 550 Wc = 4,4 kWc, onduleur réseau 4 kW monophasé."""

    def setUp(self):
        self.entree = EntreeElectrique(
            module=MODULE_550,
            onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=80.0, mppt_v_max=550.0,
                                  v_max_abs=600.0, i_max_mppt_a=16.0,
                                  ac_kw=4.0, phases=1, v_demarrage_v=90.0),
            groupes=(GroupePan("Sud", 8, 180.0, 20.0),),
            dc_m=12.0, ac_m=8.0, phases=1)
        self.resultat = concevoir(self.entree)

    def test_le_dossier_est_conforme(self):
        self.assertTrue(self.resultat.conformite.conforme,
                        self.resultat.conformite.bloquants)
        self.assertEqual(self.resultat.conformite.bloquants, ())

    def test_deux_chaines_de_quatre_une_par_mppt(self):
        self.assertEqual(self.resultat.nb_chaines, 2)
        self.assertEqual([c.nb_modules for c in self.resultat.chaines], [4, 4])
        self.assertEqual(sorted(c.mppt for c in self.resultat.chaines), [1, 2])
        self.assertAlmostEqual(self.resultat.puissance_kwc, 4.4, places=6)

    def test_les_deux_ratios(self):
        self.assertAlmostEqual(self.resultat.ratio_dc_ac.valeur, 1.1, places=6)
        self.assertAlmostEqual(self.resultat.ratio_ac_dc.valeur, 1.0 / 1.1,
                               places=6)
        self.assertTrue(self.resultat.ratio_dc_ac.dans_bornes)
        self.assertTrue(self.resultat.ratio_ac_dc.dans_bornes)

    def test_les_protections_retenues(self):
        reperes = [p.repere for p in self.resultat.protections]
        self.assertEqual(reperes, ["PDC1", "QDC1", "QAC1", "PAC1", "DDR1",
                                   "T1", "T2"])
        # 2 chaînes seulement : pas de fusible de chaîne (IEC 62548).
        self.assertIsNone(_repere(self.resultat.protections, "F1"))
        self.assertIn("20 A", _repere(self.resultat.protections,
                                      "QAC1").calibre)

    def test_les_sections_de_cable(self):
        dc = _repere(self.resultat.cables, "W1")
        ac = _repere(self.resultat.cables, "W2")
        self.assertEqual(dc.section_mm2, 2.5)
        self.assertEqual(ac.section_mm2, 2.5)
        self.assertLess(dc.chute_tension_pct, dc.chute_cible_pct)
        self.assertLess(ac.chute_tension_pct, ac.chute_cible_pct)
        self.assertTrue(dc.conforme and ac.conforme)

    def test_la_note_et_le_bordereau_sont_produits(self):
        self.assertTrue(self.resultat.note)
        self.assertTrue(self.resultat.bom)
        self.assertEqual(self.resultat.version_moteur, VERSION_MOTEUR)
        self.assertEqual(self.resultat.schema_version, SCHEMA_VERSION)


# ═══════════════════════════════ CAS 2 ═══════════════════════════════════════
class TriphaseVingtQuatrePanneauxDeuxPans(unittest.TestCase):
    """Commercial : 24 × 550 Wc = 13,2 kWc sur DEUX pans, onduleur 12 kW tri."""

    def setUp(self):
        self.entree = EntreeElectrique(
            module=MODULE_550,
            onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=200.0, mppt_v_max=850.0,
                                  v_max_abs=1000.0, i_max_mppt_a=26.0,
                                  ac_kw=12.0, phases=3, v_demarrage_v=200.0),
            groupes=(GroupePan("Sud", 12, 180.0, 15.0),
                     GroupePan("Ouest", 12, 270.0, 15.0)),
            dc_m=25.0, ac_m=15.0, phases=3)
        self.resultat = concevoir(self.entree)

    def test_le_dossier_est_conforme(self):
        self.assertTrue(self.resultat.conformite.conforme,
                        self.resultat.conformite.bloquants)

    def test_un_pan_par_entree_mppt(self):
        self.assertEqual(self.resultat.nb_chaines, 2)
        par_mppt = {}
        for chaine in self.resultat.chaines:
            par_mppt.setdefault(chaine.mppt, set()).add(chaine.pan)
        self.assertEqual(len(par_mppt), 2)
        for pans in par_mppt.values():
            self.assertEqual(len(pans), 1)
        self.assertEqual({c.pan for c in self.resultat.chaines},
                         {"Sud", "Ouest"})

    def test_chaines_de_douze_sous_la_tension_maximale(self):
        for chaine in self.resultat.chaines:
            self.assertEqual(chaine.nb_modules, 12)
            self.assertLess(chaine.voc_froid_v, 1000.0)
            self.assertGreater(chaine.vmp_chaud_v, 200.0)

    def test_le_triphase_change_le_disjoncteur_et_le_cable(self):
        disjoncteur = _repere(self.resultat.protections, "QAC1")
        self.assertIn("tétrapolaire", disjoncteur.designation)
        self.assertIn("400 V", disjoncteur.calibre)
        ac = _repere(self.resultat.cables, "W2")
        self.assertEqual(ac.nb_conducteurs, 5)
        self.assertEqual(ac.section_mm2, 2.5)

    def test_le_ratio_reste_dans_les_deux_conventions(self):
        self.assertAlmostEqual(self.resultat.ratio_dc_ac.valeur, 13.2 / 12.0,
                               places=6)
        self.assertTrue(self.resultat.ratio_dc_ac.dans_bornes)
        self.assertTrue(self.resultat.ratio_ac_dc.dans_bornes)

    def test_la_note_cite_les_deux_pans(self):
        note = "\n".join(self.resultat.note)
        self.assertIn("Sud", note)
        self.assertIn("Ouest", note)


# ═══════════════════════════════ CAS 3 ═══════════════════════════════════════
class HybrideAvecBatterie(unittest.TestCase):
    """Résidentiel hybride : 16 × 550 Wc = 8,8 kWc, onduleur 8 kW + stockage."""

    def setUp(self):
        self.entree = EntreeElectrique(
            module=MODULE_550,
            onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=80.0, mppt_v_max=550.0,
                                  v_max_abs=600.0, i_max_mppt_a=16.0,
                                  ac_kw=8.0, phases=1, v_demarrage_v=90.0),
            groupes=(GroupePan("Sud", 16, 180.0, 25.0),),
            dc_m=8.0, ac_m=6.0, phases=1, batterie=True)
        self.resultat = concevoir(self.entree)

    def test_le_dossier_est_conforme(self):
        self.assertTrue(self.resultat.conformite.conforme,
                        self.resultat.conformite.bloquants)

    def test_deux_chaines_de_huit(self):
        self.assertEqual(self.resultat.nb_chaines, 2)
        self.assertEqual([c.nb_modules for c in self.resultat.chaines], [8, 8])

    def test_le_stockage_amene_son_sectionnement_et_son_cablage(self):
        self.assertIsNotNone(_repere(self.resultat.protections, "QBAT1"))
        self.assertTrue(any(ligne.categorie == "Batterie"
                            for ligne in self.resultat.bom))

    def test_liaison_courte_donc_pas_de_parafoudre_dc(self):
        """8 m sous le seuil de 10 m, hors zone kéraunique (UTE C 15-712-1)."""
        self.assertIsNone(_repere(self.resultat.protections, "PDC1"))

    def test_le_disjoncteur_ac_suit_la_puissance(self):
        # Ib = 8000 / 230 = 34,8 A → calibre normalisé 40 A.
        self.assertIn("40 A", _repere(self.resultat.protections,
                                      "QAC1").calibre)
        self.assertEqual(_repere(self.resultat.cables, "W2").section_mm2, 4.0)


# ═══════════════════ Contrat de charge utile des tiroirs ═════════════════════
class ContratDesTiroirs(unittest.TestCase):
    """Les clés lues par ``TiroirElectrique.jsx``, ni plus ni moins."""

    def _resultat(self, **kwargs):
        entree = EntreeElectrique(
            module=MODULE_550,
            onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=80.0, mppt_v_max=550.0,
                                  v_max_abs=600.0, i_max_mppt_a=16.0,
                                  ac_kw=4.0, phases=1, v_demarrage_v=90.0),
            groupes=(GroupePan("Sud", 8, 180.0, 20.0),),
            dc_m=12.0, ac_m=8.0, phases=1, **kwargs)
        return concevoir(entree)

    def test_le_jeu_de_cles_est_exactement_celui_de_l_ecran(self):
        donnees = self._resultat().tiroirs["electrique"]
        self.assertEqual(set(donnees), {"chaine", "onduleurs", "ratio_dc_ac",
                                        "conformite"})
        self.assertEqual(set(donnees["chaine"]),
                         {"libelle_taille", "reste_texte"})
        self.assertEqual(set(donnees["onduleurs"]),
                         {"nombre_texte", "puissance_texte", "plafond_texte"})
        self.assertEqual(set(donnees["ratio_dc_ac"]),
                         {"texte", "fourchette_texte"})
        self.assertEqual(set(donnees["conformite"]),
                         {"conforme", "bloquant", "alerte",
                          "repartition_proposee"})

    def test_les_libelles_sont_en_francais_et_renseignes(self):
        donnees = self._resultat().tiroirs["electrique"]
        self.assertEqual(donnees["chaine"]["libelle_taille"],
                         "2 chaînes de 4 modules")
        self.assertEqual(donnees["chaine"]["reste_texte"], "")
        self.assertEqual(donnees["onduleurs"]["nombre_texte"], "1 onduleur")
        self.assertEqual(donnees["onduleurs"]["puissance_texte"], "4,0 kW AC")
        self.assertIn("kWc par onduleur",
                      donnees["onduleurs"]["plafond_texte"])
        self.assertEqual(donnees["ratio_dc_ac"]["texte"], "1,10")
        self.assertIn("1,35", donnees["ratio_dc_ac"]["fourchette_texte"])

    def test_un_dossier_conforme_ne_propose_rien(self):
        conformite = self._resultat().tiroirs["electrique"]["conformite"]
        self.assertTrue(conformite["conforme"])
        self.assertFalse(conformite["bloquant"])
        self.assertEqual(conformite["alerte"], "")
        self.assertIsNone(conformite["repartition_proposee"])

    def test_une_longueur_refusee_propose_la_repartition_conforme(self):
        resultat = self._resultat(longueur_chaine_forcee=30)
        conformite = resultat.tiroirs["electrique"]["conformite"]
        self.assertFalse(conformite["conforme"])
        self.assertTrue(conformite["bloquant"])
        self.assertIn("REFUSÉE", conformite["alerte"])
        proposition = conformite["repartition_proposee"]
        self.assertIsNotNone(proposition)
        self.assertEqual(proposition["patch"], {"taille_chaine": 4})
        self.assertEqual(proposition["texte"], "2 chaînes de 4 modules")

    def test_le_reste_est_annonce_quand_il_existe(self):
        entree = EntreeElectrique(
            module=MODULE_550,
            onduleur=SpecOnduleur(n_mppt=1, mppt_v_min=80.0, mppt_v_max=550.0,
                                  v_max_abs=600.0, i_max_mppt_a=40.0,
                                  ac_kw=6.0, phases=1, v_demarrage_v=90.0),
            groupes=(GroupePan("Sud", 13, 180.0, 20.0),),
            dc_m=12.0, ac_m=8.0, phases=1, longueur_chaine_forcee=4)
        donnees = concevoir(entree).tiroirs["electrique"]
        self.assertIn("réserve d'appoint", donnees["chaine"]["reste_texte"])


# ═══════════════════ Discipline de la note de calcul ═════════════════════════
class LaNoteNeContientAucunNombreEnDur(unittest.TestCase):
    """Chaque nombre d'une phrase vient du calcul — vérifié sur l'AST."""

    #: Chiffres ASCII uniquement : « mm² » porte un exposant que ``isdigit()``
    #: compte comme un chiffre, alors que c'est une UNITÉ, pas un nombre.
    CHIFFRES = "0123456789"

    def test_aucun_litteral_de_chaine_ne_porte_de_chiffre(self):
        chemin = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "electrique", "note.py")
        with open(chemin, "r", encoding="utf-8") as fh:
            arbre = ast.parse(fh.read(), filename=chemin)
        # Les docstrings expliquent le module (« PV38 ») : elles ne sont pas des
        # phrases de la note, seules les chaînes de CODE sont contrôlées.
        docstrings = set()
        for noeud in ast.walk(arbre):
            corps = getattr(noeud, "body", None)
            if not isinstance(corps, list) or not corps:
                continue
            premier = corps[0]
            if isinstance(premier, ast.Expr) \
                    and isinstance(premier.value, ast.Constant) \
                    and isinstance(premier.value.value, str):
                docstrings.add(id(premier.value))
        fautifs = []
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Constant) \
                    or not isinstance(noeud.value, str) \
                    or id(noeud) in docstrings:
                continue
            if any(caractere in self.CHIFFRES for caractere in noeud.value):
                fautifs.append(noeud.value[:60])
        self.assertEqual(
            fautifs, [],
            "un nombre écrit en dur dans une phrase de la note : %r" % (fautifs,))

    def test_la_note_enchaine_du_champ_au_bordereau(self):
        entree = EntreeElectrique(
            module=MODULE_550,
            onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=80.0, mppt_v_max=550.0,
                                  v_max_abs=600.0, i_max_mppt_a=16.0,
                                  ac_kw=4.0, phases=1, v_demarrage_v=90.0),
            groupes=(GroupePan("Sud", 8, 180.0, 20.0),),
            dc_m=12.0, ac_m=8.0, phases=1)
        note = concevoir(entree).note
        texte = "\n".join(note)
        for attendu in ("kWc crête installés", "fenêtre de tension",
                        "pan « Sud »", "onduleur(s) de", "ratio DC/AC",
                        "ratio AC/DC", "protection QAC", "câble W",
                        "bordereau"):
            self.assertIn(attendu, texte)
        self.assertNotIn("None", texte)

    def test_les_refus_sont_en_fin_de_note(self):
        entree = EntreeElectrique(
            module=MODULE_550,
            onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=80.0, mppt_v_max=550.0,
                                  v_max_abs=600.0, i_max_mppt_a=16.0,
                                  ac_kw=4.0, phases=1, v_demarrage_v=90.0),
            groupes=(GroupePan("Sud", 8, 180.0, 20.0),),
            dc_m=12.0, ac_m=8.0, phases=1, longueur_chaine_forcee=30)
        note = concevoir(entree).note
        self.assertTrue(any(ligne.startswith("REFUSÉ — ") for ligne in note))

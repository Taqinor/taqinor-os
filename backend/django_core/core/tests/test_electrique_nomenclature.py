# -*- coding: utf-8 -*-
"""PV37 — le bordereau REFLÈTE les calculs, il ne les précède pas.

Le test central de ce module est celui-ci : changer une entrée qui change une
protection ou une section DOIT changer le bordereau. C'est ce qui distingue une
nomenclature calculée d'une liste type recopiée à chaque dossier.

Aucune base de données : ``unittest`` pur.
"""

import unittest
from types import SimpleNamespace

from core.electrique.cables import dimensionner_cables
from core.electrique.chaines import concevoir_chaines
from core.electrique.nomenclature import (
    MOTIF_STRUCTURE_NON_SOURCEE, nomenclature, nomenclature_dict,
)
from core.electrique.onduleurs import dimensionner_onduleurs
from core.electrique.protections import concevoir_protections
from core.electrique.types import (
    EntreeElectrique,
    GroupePan,
    SpecModule,
    SpecOnduleur,
)


def _entree(nb_modules=18, longueur=6, n_mppt=1, dc_m=30.0, ac_m=10.0,
            phases=1, ac_kw=10.0, **kwargs):
    return EntreeElectrique(
        module=SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                          pmax_wc=550.0),
        onduleur=SpecOnduleur(n_mppt=n_mppt, mppt_v_min=120.0,
                              mppt_v_max=850.0, v_max_abs=1000.0,
                              i_max_mppt_a=60.0, ac_kw=ac_kw, phases=phases,
                              v_demarrage_v=90.0),
        groupes=(GroupePan("Sud", nb_modules, 180.0, 15.0),),
        dc_m=dc_m, ac_m=ac_m, phases=phases,
        longueur_chaine_forcee=longueur, **kwargs)


def _tout(entree):
    chaines = concevoir_chaines(entree)
    evaluation = dimensionner_onduleurs(entree)
    protections = concevoir_protections(entree, chaines, evaluation)
    cables = dimensionner_cables(entree, chaines, protections)
    return chaines, protections, cables


def _bordereau(entree):
    chaines, protections, cables = _tout(entree)
    return nomenclature(entree, chaines, protections, cables)


def _lignes(resultat, categorie):
    return [ligne for ligne in resultat.lignes if ligne.categorie == categorie]


class LeBordereauSuitLesProtections(unittest.TestCase):
    def test_chaque_protection_retenue_a_sa_ligne(self):
        entree = _entree(dc_m=30.0, batterie=True)
        chaines, protections, cables = _tout(entree)
        resultat = nomenclature(entree, chaines, protections, cables)
        designations = " | ".join(ligne.designation for ligne in resultat.lignes)
        for protection in protections.protections:
            self.assertIn(protection.repere, designations)

    def test_le_calibre_et_la_source_sont_repris_en_spec(self):
        entree = _entree(dc_m=30.0)
        chaines, protections, cables = _tout(entree)
        resultat = nomenclature(entree, chaines, protections, cables)
        for protection in protections.protections:
            ligne = next(item for item in resultat.lignes
                         if item.designation.startswith(protection.repere))
            self.assertIn(protection.calibre, ligne.spec)
            self.assertIn(protection.regle_source, ligne.spec)
            self.assertEqual(ligne.quantite, protection.quantite)

    def test_sans_parafoudre_exige_pas_de_ligne_parafoudre(self):
        """Liaison de 8 m hors zone kéraunique : le bordereau ne l'invente pas."""
        court = _bordereau(_entree(dc_m=8.0))
        long_ = _bordereau(_entree(dc_m=30.0))
        self.assertFalse(any("PDC1" in ligne.designation
                             for ligne in court.lignes))
        self.assertTrue(any("PDC1" in ligne.designation
                            for ligne in long_.lignes))

    def test_sans_fusible_exige_pas_de_ligne_fusible(self):
        deux_chaines = _bordereau(_entree(nb_modules=24, longueur=12))
        trois_chaines = _bordereau(_entree(nb_modules=18, longueur=6))
        self.assertFalse(any("F1" in ligne.designation
                             for ligne in deux_chaines.lignes))
        self.assertTrue(any("F1" in ligne.designation
                            for ligne in trois_chaines.lignes))


class LeBordereauSuitLesCables(unittest.TestCase):
    def test_la_section_du_bordereau_est_la_section_calculee(self):
        entree = _entree(dc_m=30.0)
        chaines, protections, cables = _tout(entree)
        resultat = nomenclature(entree, chaines, protections, cables)
        for cable in cables.cables:
            categorie = "Câblage DC" if cable.repere == "W1" else "Câblage AC"
            ligne = _lignes(resultat, categorie)[0]
            self.assertIn("%s mm²" % ("%.1f" % cable.section_mm2)
                          .replace(".", ","), ligne.designation)
            self.assertAlmostEqual(
                ligne.quantite,
                round(cable.longueur_m * cable.nb_conducteurs, 1), places=6)
            self.assertIn(cable.critere_dimensionnant, ligne.spec)

    def test_une_liaison_plus_longue_change_la_ligne_de_cable(self):
        court = _lignes(_bordereau(_entree(dc_m=10.0)), "Câblage DC")[0]
        long_ = _lignes(_bordereau(_entree(dc_m=120.0)), "Câblage DC")[0]
        self.assertNotEqual(court.designation, long_.designation)
        self.assertGreater(long_.quantite, court.quantite)


class StructureCoffretsEtStockage(unittest.TestCase):
    def test_la_structure_suit_le_nombre_de_modules(self):
        # CALX247 — les quantités de fixation ne sont plus devinées : sans
        # règle de bordereau SOURCÉE, aucune ligne « Structure » et le motif
        # est publié ; avec la règle saisie, les rails suivent les modules.
        sans_regle = _bordereau(_entree(nb_modules=18, longueur=6))
        self.assertEqual(_lignes(sans_regle, "Structure"), [])
        self.assertIn(MOTIF_STRUCTURE_NON_SOURCEE, sans_regle.alertes)

        regle = {"rails_par_module": 2, "pinces_par_module": 2,
                 "pinces_supplement": 2, "crochets_par_module": 1,
                 "crochets_minimum": 4,
                 "source": "fiche de pose du fabricant de structure (test)"}

        def _rails(nb_modules):
            entree = _entree(nb_modules=nb_modules, longueur=6)
            chaines, protections, cables = _tout(entree)
            resultat = nomenclature(entree, chaines, protections, cables,
                                    regle_bom_structure=regle)
            rails = [ligne for ligne in _lignes(resultat, "Structure")
                     if "rail" in ligne.designation.lower()]
            self.assertEqual(len(rails), 1, resultat.lignes)
            return rails[0].quantite

        self.assertEqual(_rails(18), 36)
        self.assertEqual(_rails(36), 72)

    def test_les_coffrets_dc_suivent_les_coffrets_reellement_poses(self):
        # CALX230 — plus de second coffret DEVINÉ au-delà de deux chaînes :
        # sans résultat de ``coffrets_dc`` (intégration non câblée), UN
        # coffret quel que soit le nombre de chaînes ; avec deux coffrets
        # réellement posés, deux lignes, une par organe.
        deux = _bordereau(_entree(nb_modules=24, longueur=12, n_mppt=2))
        trois = _bordereau(_entree(nb_modules=18, longueur=6))
        self.assertEqual(_lignes(deux, "Coffret")[0].quantite, 1)
        self.assertEqual(_lignes(trois, "Coffret")[0].quantite, 1)

        def _coffret(ident, chaines):
            return SimpleNamespace(
                id=ident, label=ident, capacite_entrees=2, chaines=chaines,
                isc_cumule_a=20.0, isc_propre_a=20.0, parent_id=None)

        poses = SimpleNamespace(
            coffrets=[_coffret("CDC1", ["S1", "S2"]),
                      _coffret("CDC2", ["S3"])],
            refus=(), omissions=())
        entree = _entree(nb_modules=18, longueur=6)
        chaines, protections, cables = _tout(entree)
        resultat = nomenclature(entree, chaines, protections, cables,
                                resultat_coffrets_dc=poses)
        lignes_dc = [ligne for ligne in _lignes(resultat, "Coffret")
                     if "string box" in ligne.designation]
        self.assertEqual(len(lignes_dc), 2, resultat.lignes)

    def test_le_stockage_ajoute_son_cablage(self):
        sans = _bordereau(_entree())
        avec = _bordereau(_entree(batterie=True))
        self.assertEqual(_lignes(sans, "Batterie"), [])
        self.assertTrue(_lignes(avec, "Batterie"))

    def test_aucune_ligne_ne_porte_de_prix(self):
        resultat = _bordereau(_entree(batterie=True, dc_m=30.0))
        for ligne in resultat.lignes:
            texte = "%s %s %s" % (ligne.categorie, ligne.designation,
                                  ligne.spec)
            for interdit in ("MAD", "DH", "prix", "€"):
                self.assertNotIn(interdit, texte)
            self.assertIn(ligne.unite, ("u", "m", "ens"))
            self.assertGreater(ligne.quantite, 0)

    def test_sans_module_pas_de_bordereau(self):
        entree = EntreeElectrique(
            module=SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                              pmax_wc=550.0),
            onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=850.0,
                                  v_max_abs=1000.0, i_max_mppt_a=26.0,
                                  ac_kw=0.0))
        resultat = _bordereau(entree)
        self.assertEqual(resultat.lignes, ())
        self.assertTrue(resultat.alertes)


class FormeHistoriqueDuBordereau(unittest.TestCase):
    """La forme de ``generate_boq`` est conservée — clé par clé."""

    def test_les_clefs_de_sortie_sont_celles_de_generate_boq(self):
        entree = _entree(dc_m=30.0)
        chaines, protections, cables = _tout(entree)
        sortie = nomenclature_dict(entree, chaines, protections, cables)
        self.assertEqual(set(sortie), {"items", "summary", "warnings"})
        self.assertEqual(
            set(sortie["summary"]),
            {"kwc", "n_panels", "strings", "phases", "ac_breaker_amp",
             "ac_cable_section_mm2", "n_lignes"})
        for item in sortie["items"]:
            self.assertEqual(set(item), {"categorie", "designation",
                                         "quantite", "unite", "spec"})

    def test_le_resume_reprend_les_valeurs_calculees(self):
        entree = _entree(nb_modules=18, longueur=6, dc_m=30.0, ac_kw=10.0)
        chaines, protections, cables = _tout(entree)
        sortie = nomenclature_dict(entree, chaines, protections, cables)
        resume = sortie["summary"]
        self.assertAlmostEqual(resume["kwc"], 9.9, places=3)
        self.assertEqual(resume["n_panels"], 18)
        self.assertEqual(resume["strings"], chaines.nb_chaines)
        self.assertEqual(resume["phases"], 1)
        self.assertEqual(resume["ac_breaker_amp"], protections.calibre_ac_a)
        section_ac = next(c.section_mm2 for c in cables.cables
                          if c.repere == "W2")
        self.assertEqual(resume["ac_cable_section_mm2"], section_ac)
        self.assertEqual(resume["n_lignes"], len(sortie["items"]))

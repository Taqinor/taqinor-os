# -*- coding: utf-8 -*-
"""CALX232 — dimensionner le coffret AC par ses DÉPARTS réels.

``core/electrique/nomenclature.py`` posait un coffret AC dès qu'un calibre
AC existait, avec une désignation FIGÉE et aucun compte de départs.
``apps.calepinage.services.coffrets.coffret_ac`` publie
``{departs, organes, calibre_tete_a, regle_source}`` — un départ par
branche AC de micro-onduleurs (CALX210) ou un départ unique en régime
chaîne ; le nombre d'organes publié égale celui de
``services/protections.py::organes_retenus`` ; la règle d'enveloppe citée
(NF C 15-100 §512.2) est celle qu'``core/electrique/protections.py`` cite
déjà pour ARM1 — jamais une nouvelle.

``SimpleTestCase`` pur — aucune base.
"""

from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.calepinage.services.coffrets import REGLE_ENVELOPPE_AC, coffret_ac
from apps.calepinage.services.protections import _ligne, organes_retenus
from core.electrique.chaines import concevoir_chaines
from core.electrique.onduleurs import dimensionner_onduleurs
from core.electrique.protections import concevoir_protections
from core.electrique.types import EntreeElectrique, GroupePan, SpecModule, SpecOnduleur

MODULE = SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                    pmax_wc=550.0)


def _entree(nb_modules=18, longueur=6, ac_kw=10.0, phases=1):
    return EntreeElectrique(
        module=MODULE,
        onduleur=SpecOnduleur(n_mppt=1, mppt_v_min=120.0, mppt_v_max=850.0,
                              v_max_abs=1000.0, i_max_mppt_a=60.0, ac_kw=ac_kw,
                              phases=phases, v_demarrage_v=90.0),
        groupes=(GroupePan("Sud", nb_modules, 180.0, 15.0),),
        dc_m=30.0, ac_m=10.0, phases=phases, longueur_chaine_forcee=longueur)


class RegimeChaine(SimpleTestCase):
    """Un onduleur de chaîne : un seul départ, la tête EST calibrée."""

    def test_un_seul_depart_et_organes_ac_retenus(self):
        entree = _entree()
        chaines = concevoir_chaines(entree)
        evaluation = dimensionner_onduleurs(entree)
        resultat_protections = concevoir_protections(entree, chaines, evaluation)
        conception = SimpleNamespace(resultat=SimpleNamespace(
            protections=resultat_protections.protections))

        resultat = coffret_ac(conception, branches=())

        self.assertEqual(resultat.departs, 1)
        self.assertEqual(resultat.regle_source, REGLE_ENVELOPPE_AC)
        self.assertIsNotNone(resultat.calibre_tete_a)
        self.assertAlmostEqual(
            resultat.calibre_tete_a, resultat_protections.calibre_ac_a)

    def test_le_nombre_d_organes_egale_organes_retenus(self):
        entree = _entree()
        chaines = concevoir_chaines(entree)
        evaluation = dimensionner_onduleurs(entree)
        resultat_protections = concevoir_protections(entree, chaines, evaluation)
        conception = SimpleNamespace(resultat=SimpleNamespace(
            protections=resultat_protections.protections))

        resultat = coffret_ac(conception, branches=())

        lignes = [_ligne(p) for p in resultat_protections.protections]
        organes_ac_checklist = [ligne for ligne in organes_retenus(
            {'organes': lignes, 'justifications': [], 'omissions': []})
            if ligne['cote'] == 'ac']
        self.assertEqual(resultat.organes, len(organes_ac_checklist))
        self.assertGreater(resultat.organes, 0)


class RegimeMicroTroisBranches(SimpleTestCase):
    """Trois branches de micro-onduleurs : trois départs, PAS de tête commune."""

    def test_trois_departs_pas_de_calibre_de_tete(self):
        branches = (
            {'repere': 'BR1', 'i_branche_a': 8.0},
            {'repere': 'BR2', 'i_branche_a': 12.0},
            {'repere': 'BR3', 'i_branche_a': 4.0},
        )
        conception = SimpleNamespace(resultat=SimpleNamespace(protections=()))

        resultat = coffret_ac(conception, branches=branches)

        self.assertEqual(resultat.departs, 3)
        self.assertIsNone(resultat.calibre_tete_a)
        self.assertEqual(resultat.regle_source, REGLE_ENVELOPPE_AC)

    def test_organes_ac_retenus_comptes_en_regime_micro(self):
        entree = _entree()
        chaines = concevoir_chaines(entree)
        evaluation = dimensionner_onduleurs(entree)
        resultat_protections = concevoir_protections(entree, chaines, evaluation)
        conception = SimpleNamespace(resultat=SimpleNamespace(
            protections=resultat_protections.protections))
        branches = ({'repere': 'BR1', 'i_branche_a': 8.0},
                    {'repere': 'BR2', 'i_branche_a': 12.0},
                    {'repere': 'BR3', 'i_branche_a': 4.0})

        resultat = coffret_ac(conception, branches=branches)

        organes_ac = [p for p in resultat_protections.protections
                      if p.cote == 'ac']
        self.assertEqual(resultat.organes, len(organes_ac))
        self.assertIn(
            "chaque départ porte son propre organe",
            " | ".join(resultat.omissions))


class DesignationDeriveeDuCalcul(SimpleTestCase):
    """Le coffret AC intégré à la nomenclature n'a plus de désignation figée."""

    def test_designation_reflete_departs_et_organes(self):
        from core.electrique.nomenclature import nomenclature

        entree = _entree()
        chaines = concevoir_chaines(entree)
        evaluation = dimensionner_onduleurs(entree)
        cables_protections = concevoir_protections(entree, chaines, evaluation)
        conception = SimpleNamespace(resultat=SimpleNamespace(
            protections=cables_protections.protections))
        resultat_coffret_ac = coffret_ac(conception, branches=())

        resultat_nomenclature = nomenclature(
            entree, resultat_coffret_ac=resultat_coffret_ac)
        ligne = next(ligne for ligne in resultat_nomenclature.lignes
                     if ligne.categorie == "Coffret")
        self.assertIn("1 départ(s)", ligne.designation)
        self.assertIn("organe(s) AC", ligne.spec)
        self.assertIn("NF C 15-100 §512.2", ligne.spec)

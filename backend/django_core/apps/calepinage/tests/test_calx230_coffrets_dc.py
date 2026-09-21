# -*- coding: utf-8 -*-
"""CALX230 — dimensionner un coffret DC par son nombre d'ENTRÉES réelles.

``core/electrique/nomenclature.py`` posait un ou deux coffrets DC par un
comptage écrit en dur (``1 if nb_chaines <= 2 else 2``, sans source).
``apps.calepinage.services.coffrets.coffrets_dc`` le remplace : un coffret
par équipement ``type: "coffret_dc"`` RÉELLEMENT posé
(``electrical.equipements[]``, contrat CALX201), chacun avec une capacité
d'entrées saisie, les chaînes réparties dedans, une répartition qui dépasse
la capacité REFUSÉE en la nommant, et les fusibles de chaîne portés par la
règle EXISTANTE (``core.electrique.protections`` — IEC 62548 §7.3.3, dès
trois chaînes en parallèle).

``SimpleTestCase`` pur — aucune base.
"""

from django.test import SimpleTestCase

from apps.calepinage.services.coffrets import ResultatCoffretsDc, coffrets_dc
from core.electrique.chaines import concevoir_chaines
from core.electrique.nomenclature import nomenclature
from core.electrique.protections import (
    SEUIL_CHAINES_PARALLELES_FUSIBLE,
    concevoir_protections,
)
from core.electrique.types import EntreeElectrique, GroupePan, SpecModule, SpecOnduleur

MODULE = SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                    pmax_wc=550.0)
ONDULEUR_1_MPPT = SpecOnduleur(n_mppt=1, mppt_v_min=120.0, mppt_v_max=850.0,
                               v_max_abs=1000.0, i_max_mppt_a=60.0, ac_kw=10.0,
                               v_demarrage_v=90.0)


def _entree(nb_modules, longueur, n_mppt=1):
    return EntreeElectrique(
        module=MODULE,
        onduleur=SpecOnduleur(n_mppt=n_mppt, mppt_v_min=120.0, mppt_v_max=850.0,
                              v_max_abs=1000.0, i_max_mppt_a=60.0, ac_kw=10.0,
                              v_demarrage_v=90.0),
        groupes=(GroupePan("Sud", nb_modules, 180.0, 15.0),),
        dc_m=30.0, longueur_chaine_forcee=longueur)


def _chaines(nb_modules=18, longueur=6, n_mppt=1):
    """Trois chaînes de 6 modules, toutes sur la même entrée MPPT."""
    entree = _entree(nb_modules, longueur, n_mppt)
    return concevoir_chaines(entree).chaines


def _equipement_dc(id_, label, capacite=None, parent_id=None):
    eq = {'id': id_, 'type': 'coffret_dc', 'label': label,
          'lng': -7.6, 'lat': 33.5, 'source': 'saisie'}
    if capacite is not None:
        eq['capaciteEntrees'] = capacite
    if parent_id is not None:
        eq['parentId'] = parent_id
    return eq


class CapaciteSuffisante(SimpleTestCase):
    def test_une_chaine_par_entree_capacite_suffisante(self):
        chaines = _chaines()
        self.assertEqual(len(chaines), 3)
        equipements = [_equipement_dc('eq1', 'Coffret toiture', capacite=4)]
        resultat = coffrets_dc(chaines, equipements)
        self.assertIsInstance(resultat, ResultatCoffretsDc)
        self.assertEqual(len(resultat.coffrets), 1)
        coffret = resultat.coffrets[0]
        self.assertEqual(coffret.id, 'eq1')
        self.assertEqual(len(coffret.chaines), 3)
        self.assertEqual(coffret.capacite_entrees, 4)
        self.assertEqual(resultat.refus, ())


class CapaciteDepassee(SimpleTestCase):
    def test_capacite_depassee_refuse_en_nommant(self):
        chaines = _chaines()
        equipements = [_equipement_dc('eq1', 'Coffret toiture', capacite=2)]
        resultat = coffrets_dc(chaines, equipements)
        self.assertEqual(len(resultat.coffrets[0].chaines), 2)
        self.assertTrue(resultat.refus)
        texte = " | ".join(resultat.refus)
        self.assertIn("1 chaîne(s) sans coffret DC", texte)

    def test_capacite_non_publiee_refuse_en_nommant_le_coffret(self):
        chaines = _chaines()
        equipements = [_equipement_dc('eq1', 'Coffret sans fiche')]
        resultat = coffrets_dc(chaines, equipements)
        self.assertEqual(resultat.coffrets[0].chaines, ())
        texte = " | ".join(resultat.refus)
        self.assertIn("Coffret sans fiche", texte)
        self.assertIn("capacité d'entrées non publiée", texte)


class AucunCoffretPose(SimpleTestCase):
    def test_aucun_coffret_pose_omet_la_ligne(self):
        chaines = _chaines()
        resultat = coffrets_dc(chaines, equipements=[])
        self.assertEqual(resultat.coffrets, ())
        self.assertTrue(resultat.omissions)
        self.assertIn("aucun coffret DC n'est posé", resultat.omissions[0])

    def test_aucune_chaine_aucun_coffret_rien_a_dire(self):
        resultat = coffrets_dc(chaines=(), equipements=[])
        self.assertEqual(resultat.coffrets, ())
        self.assertEqual(resultat.omissions, ())
        self.assertEqual(resultat.refus, ())


class NomenclatureRemplaceLeComptageEnDur(SimpleTestCase):
    """Le comptage en dur de la nomenclature EST remplacé (CALX230)."""

    def test_le_nombre_de_coffrets_suit_les_coffrets_reellement_poses(self):
        chaines = _chaines()
        equipements = [_equipement_dc('eq1', 'A', capacite=2),
                       _equipement_dc('eq2', 'B', capacite=2)]
        resultat_coffrets = coffrets_dc(chaines, equipements)
        entree = _entree(18, 6, n_mppt=1)
        resultat_nomenclature = nomenclature(
            entree, resultat_coffrets_dc=resultat_coffrets)
        lignes_coffret = [ligne for ligne in resultat_nomenclature.lignes
                          if ligne.categorie == "Coffret"]
        self.assertEqual(len(lignes_coffret), 2)

    def test_sans_coffret_pose_zero_ligne_coffret_dc(self):
        entree = _entree(18, 6, n_mppt=1)
        chaines = _chaines()
        resultat_coffrets = coffrets_dc(chaines, equipements=[])
        resultat_nomenclature = nomenclature(
            entree, resultat_coffrets_dc=resultat_coffrets)
        self.assertEqual(
            [ligne for ligne in resultat_nomenclature.lignes
             if ligne.categorie == "Coffret"], [])
        self.assertTrue(any("aucun coffret DC" in alerte
                            for alerte in resultat_nomenclature.alertes))


class LeNombreDeFusiblesEgaleConcevoirProtections(SimpleTestCase):
    """Le nombre de fusibles rendu égale celui de ``concevoir_protections``."""

    def test_trois_chaines_en_parallele_meme_compte_de_fusibles(self):
        entree = _entree(18, 6, n_mppt=1)
        resultat_chaines = concevoir_chaines(entree)
        self.assertGreaterEqual(
            len(resultat_chaines.chaines), SEUIL_CHAINES_PARALLELES_FUSIBLE)
        resultat_protections = concevoir_protections(entree, resultat_chaines)
        f1 = next(p for p in resultat_protections.protections
                  if p.repere == "F1")

        equipements = [_equipement_dc('eq1', 'Coffret unique',
                                      capacite=len(resultat_chaines.chaines))]
        resultat_coffrets = coffrets_dc(resultat_chaines.chaines, equipements)
        coffret = resultat_coffrets.coffrets[0]

        self.assertTrue(coffret.fusibles_requis)
        self.assertEqual(coffret.nb_fusibles, f1.quantite)

    def test_deux_chaines_en_parallele_aucun_fusible(self):
        entree = _entree(24, 12, n_mppt=2)
        resultat_chaines = concevoir_chaines(entree)
        equipements = [_equipement_dc('eq1', 'Coffret unique',
                                      capacite=len(resultat_chaines.chaines))]
        resultat_coffrets = coffrets_dc(resultat_chaines.chaines, equipements)
        coffret = resultat_coffrets.coffrets[0]
        self.assertFalse(coffret.fusibles_requis)
        self.assertEqual(coffret.nb_fusibles, 0)

"""Revue ACAL1629 — la phrase d'un refus météo du balayage dit le VRAI geste."""
from __future__ import annotations

from django.test import SimpleTestCase

from apps.calepinage.services import chaine_pertes as cp
from apps.calepinage.services import manquants_simulation as ms
from apps.calepinage.tasks import (
    MOTIF_BALAYAGE_METEO, motif_refus_balayage)


class MotifRefusBalayageTest(SimpleTestCase):
    def test_fenetre_pluriannuelle_dit_un_an(self):
        refus = cp.MeteoIndecise(cp.MOTIF_TMY_HORIZONTAL, champ='meteo.gi_w_m2')
        self.assertEqual(motif_refus_balayage(refus), MOTIF_BALAYAGE_METEO)
        self.assertIn('un an', motif_refus_balayage(refus))

    def test_mode_non_choisi_dit_choisissez_le_mode(self):
        with self.assertRaises(cp.MeteoIndecise) as ctx:
            cp.decision_meteo({})
        phrase = motif_refus_balayage(ctx.exception)
        self.assertEqual(phrase, ms.MOTIF_MODE_METEO_ABSENT)
        self.assertNotIn('un an', phrase)

    def test_mode_non_reconnu_dit_non_reconnu(self):
        refus = cp.MeteoIndecise(
            "Le mode météo saisi (« 'x' ») n'est pas reconnu.",
            champ=cp.CLE_REGLAGE_MODE_METEO)
        self.assertEqual(motif_refus_balayage(refus), ms.MOTIF_MODE_METEO_INCONNU)

    def test_autre_champ_garde_son_motif(self):
        refus = cp.MeteoIndecise('tel quel', champ='autre')
        self.assertEqual(motif_refus_balayage(refus), 'tel quel')

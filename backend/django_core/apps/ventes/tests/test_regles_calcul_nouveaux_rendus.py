"""Décision fondateur 08/10/2026 — « nouveaux rendus seulement ».

Un devis déjà envoyé (``regles_calcul = 1`` posé par la migration 0134) reste
rendu avec les règles d'origine ; un devis neuf naît aux règles corrigées.
"""
import importlib
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.ventes.domain.regles_calcul import (
    REGLES_CORRIGEES, REGLES_ORIGINE, calcul_corrige)


class ReglesCalculTests(SimpleTestCase):
    def test_devis_envoye_garde_les_regles_d_origine(self):
        self.assertFalse(calcul_corrige(SimpleNamespace(regles_calcul=REGLES_ORIGINE)))

    def test_devis_neuf_aux_regles_corrigees(self):
        self.assertTrue(calcul_corrige(SimpleNamespace(regles_calcul=REGLES_CORRIGEES)))

    def test_doublure_sans_champ_suit_les_regles_corrigees(self):
        self.assertTrue(calcul_corrige(SimpleNamespace()))

    def test_defaut_du_modele_est_corrige(self):
        from apps.ventes.models import Devis
        self.assertEqual(
            Devis._meta.get_field('regles_calcul').default, REGLES_CORRIGEES)

    def test_migration_fige_les_envoyes(self):
        mod = importlib.import_module(
            'apps.ventes.migrations.0134_regles_calcul_devis_envoyes')
        self.assertTrue(callable(mod.figer_devis_envoyes))

    def test_commande_dryrun_sans_ecriture(self):
        """La commande annule sa transaction : aucun mode d'écriture."""
        cmd = importlib.import_module(
            'apps.ventes.management.commands.regles_calcul_ecarts_dryrun')
        src = Path(cmd.__file__).read_text(encoding='utf-8')
        self.assertIn('set_rollback(True)', src)
        self.assertNotIn('.save(', src)

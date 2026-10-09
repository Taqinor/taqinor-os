"""Décision fondateur 08/10/2026 — « nouveaux rendus seulement ».

Un devis déjà envoyé (``regles_calcul = 1`` posé par la migration 0138) reste
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
            'apps.ventes.migrations.0138_regles_calcul_devis_envoyes')
        self.assertTrue(callable(mod.figer_devis_envoyes))

    def test_commande_dryrun_sans_ecriture(self):
        """La commande annule sa transaction : aucun mode d'écriture."""
        cmd = importlib.import_module(
            'apps.ventes.management.commands.regles_calcul_ecarts_dryrun')
        src = Path(cmd.__file__).read_text(encoding='utf-8')
        self.assertIn('set_rollback(True)', src)
        self.assertNotIn('.save(', src)


class FormateursReglesOrigineTests(SimpleTestCase):
    """AMOT24 / AMOT26 / AMOT45 / AMOT33 / AMOT27 — un devis aux règles
    d'origine garde les formats d'hier ; un devis corrigé prend les nouveaux."""

    def setUp(self):
        from apps.ventes.quote_engine.montants import poser_regles_origine
        self.addCleanup(poser_regles_origine, False)

    def test_pct_fr_origine_et_corrige(self):
        from apps.ventes.quote_engine import montants
        montants.poser_regles_origine(True)
        self.assertEqual(montants.pct_fr(2.5), '2.5')
        self.assertEqual(montants.pct_fr(20.0), '20')
        montants.poser_regles_origine(False)
        self.assertEqual(montants.pct_fr(2.5), '2,5')
        self.assertEqual(montants.pct_fr(20.0), '20')

    def test_fmt_dirhams_arrondi_origine_et_corrige(self):
        from apps.ventes.quote_engine import montants
        montants.poser_regles_origine(True)
        # ``round`` de Python : au pair.
        self.assertEqual(montants.fmt_dirhams(52650.5, sep=' '), '52 650')
        montants.poser_regles_origine(False)
        self.assertEqual(montants.fmt_dirhams(52650.5, sep=' '), '52 651')

    def test_lignes_remisees_catalogue_seul(self):
        from apps.ventes.quote_engine.montants import lignes_remisees
        it = {'prix_unit_ht': 1000, 'quantite': 2, 'pu_ht_remise': 950,
              'total_ht_remise': 1900}
        (_i, pu_cat, pu, tot_cat, tot, remisee) = lignes_remisees(
            [it], catalogue_seul=True)[0]
        self.assertEqual((pu_cat, pu, tot_cat, tot, remisee),
                         (1000.0, 1000.0, 2000.0, 2000.0, False))
        (_i, _c, pu, _tc, tot, remisee) = lignes_remisees([it])[0]
        self.assertEqual((pu, tot, remisee), (950.0, 1900.0, True))

    def test_option_recommandee_origine_toujours_avec(self):
        from apps.ventes.quote_engine.figures import option_recommandee
        quote = {'deux_options': True, 'recommended': 'Sans batterie'}
        self.assertEqual(option_recommandee(quote), 'sans')
        self.assertEqual(
            option_recommandee(dict(quote, regles_calcul_origine=True)),
            'avec')

    def test_repartition_mensuelle_historique(self):
        from apps.ventes.quote_engine.pricing import (
            CLE_SOLAIRE_MENSUELLE_HISTORIQUE, calculate_savings_roi)
        kw = {}  # modèle « estimation » : la série vient de la clé
        origine = calculate_savings_roi(5.0, 50000, 80000,
                                        forme_mensuelle_ghi=False, **kw)
        attendu = [round(origine['eco_s_ann'] * f)
                   for f in CLE_SOLAIRE_MENSUELLE_HISTORIQUE]
        self.assertEqual(origine['eco_s_monthly'], attendu)
        corrige = calculate_savings_roi(5.0, 50000, 80000, **kw)
        self.assertEqual(sum(corrige['eco_s_monthly']),
                         round(corrige['eco_s_ann']))

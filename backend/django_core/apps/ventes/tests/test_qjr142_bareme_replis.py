# -*- coding: utf-8 -*-
"""QJR142 — plus aucun repli silencieux sur de la monnaie dans ``bareme``.

Six replis d'un même patron, tous dans le module qui reconstitue la facture du
client : chacun rendait un nombre PLAUSIBLE et FAUX au lieu de dire qu'il ne
savait pas. Après QJR142, chacun rend ``None`` ou lève.

(a) un millésime inconnu retombait sur la grille ET la TVA 2026 pendant que la
    sortie réémettait le millésime DEMANDÉ ; le ``or`` avalait en prime une
    table vide ;
(b) ``tranche_du_kwh_mensuel`` chutait dans la boucle sélective et attribuait
    au client une tranche dont la borne BASSE dépasse sa consommation — avec
    un ``libelle`` client-facing ;
(c) ``falaise_sous_kwh_mensuel`` nommait une « marche » en zone PROGRESSIVE,
    où descendre sous la borne ne re-tarife rien ;
(d) une charge fixe illisible devenait 0,00 MAD, source « réglage société »
    comprise — donc ~29 kWh/mois fantômes à l'inversion ;
(e) la dichotomie abandonnait au-delà de sa borne et rendait ≈ 1 024 000
    kWh/mois sans drapeau ;
(f) un plafond TPPAN illisible valait 0,0 et ANNULAIT la taxe — un défaut de 0
    sur un PLAFOND inverse le sens de la garde.

Tests purs — aucune base, aucun réseau.
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine import bareme as B
from apps.ventes.quote_engine.pricing import TrancheTable


class MillesimeInconnuTests(SimpleTestCase):
    """(a) Facturer 2024 avec la grille 2026 en annonçant « 2024 » est un faux."""

    def test_un_millesime_inconnu_leve_au_lieu_de_facturer(self):
        with self.assertRaises(ValueError):
            B.facture_mad(359, millesime=2024)

    def test_le_message_nomme_les_millesimes_disponibles(self):
        with self.assertRaises(ValueError) as ctx:
            B.facture_mad(359, millesime=1999)
        for millesime in B.MILLESIMES:
            self.assertIn(str(millesime), str(ctx.exception))

    def test_les_charges_fixes_refusent_aussi_un_millesime_inconnu(self):
        """La TVA par ligne aussi retombait en silence sur 2026."""
        with self.assertRaises(ValueError):
            B.charges_fixes_ttc(2024)

    def test_une_table_vide_n_est_plus_avalee_par_le_or(self):
        original = B.MILLESIMES.get(2025)
        B.MILLESIMES[2025] = ()
        try:
            with self.assertRaises(ValueError):
                B.facture_mad(359, millesime=2025)
        finally:
            B.MILLESIMES[2025] = original

    def test_les_millesimes_connus_facturent_toujours(self):
        for millesime in (2025, 2026):
            self.assertGreater(
                B.facture_mad(359, millesime=millesime)['total_mad'], 0.0)


class TrancheSansChuteTests(SimpleTestCase):
    """(b) Jamais une tranche dont la borne basse dépasse la consommation."""

    #: Seuil sélectif AU-DESSUS du dernier plafond progressif — saisie
    #: parfaitement possible : ``TariffSettings.selective_threshold_kwh`` est
    #: éditable et rien ne l'interdit.
    TABLE = TrancheTable([(100, 1.0), (200, 2.0), (None, 3.0)],
                         selective_threshold=150, boundary_tolerance=10)

    def test_le_trou_entre_progressif_et_seuil_rend_none(self):
        self.assertIsNone(
            B.tranche_du_kwh_mensuel(120, tranches=self.TABLE))

    def test_aucune_tranche_rendue_n_a_une_borne_basse_trop_haute(self):
        """L'invariant, sur toute la grille : borne_basse ≤ consommation."""
        for kwh in range(1, 400, 7):
            tranche = B.tranche_du_kwh_mensuel(kwh, tranches=self.TABLE)
            if tranche is None:
                continue
            self.assertLessEqual(
                tranche['borne_basse_kwh'], float(kwh),
                'kwh=%d → %r' % (kwh, tranche['libelle']))

    def test_les_tranches_reellement_atteintes_restent_nommees(self):
        basse = B.tranche_du_kwh_mensuel(80, tranches=self.TABLE)
        self.assertIsNotNone(basse)
        self.assertEqual(basse['borne_basse_kwh'], 0.0)
        haute = B.tranche_du_kwh_mensuel(180, tranches=self.TABLE)
        self.assertIsNotNone(haute)
        self.assertEqual(haute['regime'], 'selectif')

    def test_la_grille_officielle_est_inchangee(self):
        """Aucune régression sur le barème réel (seuil 150 = dernier plafond)."""
        for kwh, rang in ((50, 1), (120, 2), (180, 3), (600, 6)):
            tranche = B.tranche_du_kwh_mensuel(kwh)
            self.assertIsNotNone(tranche, kwh)
            self.assertEqual(tranche['rang'], rang, kwh)


class FalaiseSeulementEnSelectifTests(SimpleTestCase):
    """(c) Une « marche » ne se vend que là où elle existe."""

    def test_aucune_marche_en_zone_progressive(self):
        actuelle = B.tranche_du_kwh_mensuel(120)
        self.assertEqual(actuelle['regime'], 'progressif')
        self.assertGreater(actuelle['rang'], 1)   # l'ancien code rendait donc
        self.assertIsNone(B.falaise_sous_kwh_mensuel(120))

    def test_la_marche_selective_est_conservee(self):
        falaise = B.falaise_sous_kwh_mensuel(600)
        self.assertIsNotNone(falaise)
        self.assertEqual(falaise['tranche_actuelle']['regime'], 'selectif')
        self.assertEqual(falaise['cible_kwh_mois'], 500.0)

    def test_la_marche_annoncee_re_tarife_vraiment_tout_le_mois(self):
        """Ce que la docstring promet : la facture CHUTE en franchissant."""
        falaise = B.falaise_sous_kwh_mensuel(600)
        cible = falaise['cible_kwh_mois']
        self.assertLess(B.facture_mad(cible)['energie_mad'] / cible,
                        B.facture_mad(600)['energie_mad'] / 600)


class ChargesFixesTests(SimpleTestCase):
    """(d) Une charge fixe illisible ne fabrique plus de consommation."""

    def test_une_valeur_illisible_leve(self):
        for illisible in ('x', object(), [1]):
            with self.assertRaises(ValueError, msg=repr(illisible)):
                B.facture_mad(359, charges_fixes_mad=illisible)

    def test_une_valeur_negative_leve(self):
        with self.assertRaises(ValueError):
            B.facture_mad(359, charges_fixes_mad=-1)

    def test_un_zero_explicite_reste_legitime_mais_le_DIT(self):
        detail = B.facture_mad(359, charges_fixes_mad=0)
        self.assertEqual(detail['location_entretien_mad'], 0.0)
        self.assertIn('aucune charge fixe', detail['charges_fixes_source'])

    def test_une_vraie_valeur_societe_est_inchangee(self):
        detail = B.facture_mad(359, charges_fixes_mad=45.0)
        self.assertEqual(detail['location_entretien_mad'], 45.0)
        self.assertEqual(detail['charges_fixes_source'], 'réglage société')

    def test_sans_reglage_la_source_reste_celle_des_factures(self):
        detail = B.facture_mad(359)
        self.assertEqual(detail['charges_fixes_source'], B.CHARGES_FIXES_SOURCE)


class DichotomieHorsPlageTests(SimpleTestCase):
    """(e) Hors plage, l'inversion le DIT au lieu de rendre sa borne."""

    def test_un_montant_hors_plage_rend_none(self):
        self.assertIsNone(
            B.kwh_depuis_facture_mad(1e9)['kwh_mensuel'])

    def test_le_none_n_est_jamais_la_borne_de_recherche(self):
        """Régression : ≈ 1 024 000 kWh/mois, parfaitement formé et faux."""
        sortie = B.kwh_depuis_facture_mad(1e9)
        self.assertNotEqual(sortie['kwh_mensuel'], B._PLAFOND_DICHOTOMIE_KWH)

    def test_les_montants_normaux_sont_inchanges(self):
        self.assertAlmostEqual(
            B.kwh_depuis_facture_mad(592.77)['kwh_mensuel'], 359.0, places=1)

    def test_la_serie_mensuelle_omet_tout_plutot_qu_un_trou(self):
        from apps.ventes import etude_horaire as EH
        kwh, detail = EH.serie_kwh_depuis_mad([1e9] * 12)
        self.assertIsNone(kwh)
        self.assertEqual(detail, {})


class PlafondTPPANTests(SimpleTestCase):
    """(f) Un défaut de 0 sur un PLAFOND inverse le sens de la garde."""

    def test_un_plafond_illisible_leve_au_lieu_d_annuler_la_taxe(self):
        for illisible in ('x', object(), 'cent'):
            with self.assertRaises(ValueError, msg=repr(illisible)):
                B.tppan_mad(359, jours=30, plafond_mad=illisible)

    def test_un_plafond_negatif_leve(self):
        with self.assertRaises(ValueError):
            B.tppan_mad(359, jours=30, plafond_mad=-5)

    def test_le_plafond_reel_borne_toujours(self):
        self.assertAlmostEqual(
            B.tppan_mad(5000, jours=30, plafond_mad=100.0), 100.0, places=6)

    def test_la_taxe_de_reference_est_inchangee(self):
        self.assertAlmostEqual(B.tppan_mad(359, jours=30), 56.80, places=2)

# -*- coding: utf-8 -*-
"""QJR140 — la capacité batterie d'un devis se lit PAR OPTION.

``capacite_batterie_du_devis`` additionnait TOUTE ligne classée batterie de
``devis.lignes.all()``, sans distinguer l'option qui la porte, alors que le
découpage existe en amont (``builder._repartir_options`` /
``_battery_kwh_from_items(avec_items, …)``). Sur un devis à plusieurs paliers
de stockage, elle additionnait donc des capacités qui ne coexistent dans AUCUNE
option vendue — un chiffre qui ne décrit rien de ce que le client peut acheter.

Atténuation vérifiée par l'audit : ``etude_horaire_pour_devis`` essaie d'abord
``batterie_kwh_utile``, puis ``data['batterie_kwh_total']`` (issu de la SEULE
option AVEC), donc la somme brute n'était atteinte que sans ``data``. Ces deux
chemins-là sont épinglés ici comme INCHANGÉS.
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.etude_horaire import (
    capacite_batterie_du_devis,
    ligne_dans_option,
)
from apps.ventes.models import LigneDevis
from apps.ventes.tests.test_quote_engine import (
    make_client, make_company, make_devis, make_produit, make_user,
)


class _LigneFactice:
    def __init__(self, variante):
        self.variante = variante


class AppartenanceALOptionTests(TestCase):
    """``ligne_dans_option`` — le contrat de ``LigneDevis.variante``."""

    def test_une_ligne_commune_compte_dans_les_deux_options(self):
        commune = _LigneFactice('')
        self.assertTrue(ligne_dans_option(commune, 'avec'))
        self.assertTrue(ligne_dans_option(commune, 'sans'))

    def test_une_ligne_variantee_ne_compte_que_dans_la_sienne(self):
        self.assertTrue(ligne_dans_option(_LigneFactice('avec'), 'avec'))
        self.assertFalse(ligne_dans_option(_LigneFactice('avec'), 'sans'))
        self.assertTrue(ligne_dans_option(_LigneFactice('sans'), 'sans'))
        self.assertFalse(ligne_dans_option(_LigneFactice('sans'), 'avec'))

    def test_sans_option_aucune_selection(self):
        for variante in ('', 'avec', 'sans'):
            self.assertTrue(ligne_dans_option(_LigneFactice(variante), None))

    def test_une_ligne_sans_champ_variante_est_commune(self):
        """Un double de test sans le champ récent ≡ ligne commune."""
        self.assertTrue(ligne_dans_option(object(), 'avec'))


class CapaciteParOptionTests(TestCase):
    """Le cœur du constat : un devis à DEUX paliers de stockage."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj,
            [('Module PV 550 W', '20', '1500')],
            reference='DEV-QJR140-0001')

    def _ligne(self, designation, quantite, variante, sku):
        return LigneDevis.objects.create(
            devis=self.devis,
            produit=make_produit(self.company, designation, sku, '9000'),
            designation=designation, quantite=Decimal(quantite),
            prix_unitaire=Decimal('9000'), remise=Decimal('0'),
            variante=variante)

    def _deux_paliers(self):
        """Deux paliers de stockage qui ne coexistent dans AUCUNE option."""
        self._ligne('Batterie LiFePO4 5 kWh', '1', 'sans', 'Q140-B5')
        self._ligne('Batterie LiFePO4 10 kWh', '1', 'avec', 'Q140-B10')

    def test_la_capacite_rendue_est_celle_d_UNE_option(self):
        self._deux_paliers()
        self.assertEqual(capacite_batterie_du_devis(self.devis, 'avec'), 10.0)
        self.assertEqual(capacite_batterie_du_devis(self.devis, 'sans'), 5.0)

    def test_la_somme_brute_ne_decrit_aucune_option_vendue(self):
        """Régression : 15 kWh n'est ni l'option AVEC ni l'option SANS."""
        self._deux_paliers()
        brute = capacite_batterie_du_devis(self.devis, option=None)
        self.assertEqual(brute, 15.0)
        self.assertNotEqual(brute, capacite_batterie_du_devis(self.devis, 'avec'))
        self.assertNotEqual(brute, capacite_batterie_du_devis(self.devis, 'sans'))

    def test_le_defaut_est_l_option_qui_porte_le_stockage(self):
        self._deux_paliers()
        self.assertEqual(capacite_batterie_du_devis(self.devis),
                         capacite_batterie_du_devis(self.devis, 'avec'))

    def test_une_ligne_commune_compte_dans_les_deux_options(self):
        self._ligne('Batterie LiFePO4 5 kWh', '2', '', 'Q140-BC')
        self.assertEqual(capacite_batterie_du_devis(self.devis, 'avec'), 10.0)
        self.assertEqual(capacite_batterie_du_devis(self.devis, 'sans'), 10.0)

    def test_un_devis_mono_option_est_inchange_a_l_octet(self):
        """Tout le parc existant : lignes communes ⇒ même résultat qu'avant."""
        self._ligne('Batterie LiFePO4 5 kWh', '3', '', 'Q140-BM')
        self.assertEqual(capacite_batterie_du_devis(self.devis, 'avec'),
                         capacite_batterie_du_devis(self.devis, option=None))

    def test_une_option_sans_batterie_rend_None_pas_zero(self):
        """« pas de stockage » n'est pas « stockage de capacité nulle »."""
        self._ligne('Batterie LiFePO4 10 kWh', '1', 'avec', 'Q140-BA')
        self.assertIsNone(capacite_batterie_du_devis(self.devis, 'sans'))
        self.assertEqual(capacite_batterie_du_devis(self.devis, 'avec'), 10.0)

    def test_un_devis_sans_aucune_batterie_rend_None(self):
        self.assertIsNone(capacite_batterie_du_devis(self.devis, 'avec'))
        self.assertIsNone(capacite_batterie_du_devis(self.devis, option=None))

    def test_les_quantites_sont_respectees_dans_l_option(self):
        self._ligne('Batterie LiFePO4 5 kWh', '3', 'avec', 'Q140-BQ')
        self._ligne('Batterie LiFePO4 5 kWh', '1', 'sans', 'Q140-BQ2')
        self.assertEqual(capacite_batterie_du_devis(self.devis, 'avec'), 15.0)
        self.assertEqual(capacite_batterie_du_devis(self.devis, 'sans'), 5.0)

    def test_lignes_illisibles_ne_levent_jamais(self):
        class _DevisCasse:
            lignes = None
        self.assertIsNone(capacite_batterie_du_devis(_DevisCasse(), 'avec'))


class CheminsAvecDataInchangesTests(TestCase):
    """« chemins avec ``data`` inchangés à l'octet » — les deux replis d'avant."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj,
            [('Module PV 550 W', '20', '1500')],
            reference='DEV-QJR140-0002')
        LigneDevis.objects.create(
            devis=self.devis,
            produit=make_produit(self.company, 'Batterie LiFePO4 10 kWh',
                                 'Q140D-B10', '9000'),
            designation='Batterie LiFePO4 10 kWh', quantite=Decimal('1'),
            prix_unitaire=Decimal('9000'), remise=Decimal('0'),
            variante='avec')

    def test_l_ordre_des_trois_replis_est_conserve(self):
        """La lecture des lignes reste le TROISIÈME choix, jamais le premier.

        On lit la source plutôt que de simuler tout le pipeline : ce qui est
        épinglé ici est l'ORDRE, et le fait que le repli sur les lignes demande
        désormais explicitement l'option AVEC.
        """
        import ast
        import inspect

        from apps.ventes import etude_horaire as EH

        source = inspect.getsource(EH._etude_horaire_pour_devis)
        i_explicite = source.index('capacite = batterie_kwh_utile')
        i_data = source.index("data.get('batterie_kwh_total')")
        i_lignes = source.index('capacite_batterie_du_devis(')
        self.assertLess(i_explicite, i_data)
        self.assertLess(i_data, i_lignes)

        # Et ce troisième appel nomme bien l'option.
        arbre = ast.parse(inspect.getsource(EH).lstrip())
        appels = [
            noeud for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Call)
            and isinstance(noeud.func, ast.Name)
            and noeud.func.id == 'capacite_batterie_du_devis'
        ]
        self.assertTrue(appels)
        for appel in appels:
            self.assertIn('option', [kw.arg for kw in appel.keywords],
                          'appel ligne %d sans option nommée' % appel.lineno)

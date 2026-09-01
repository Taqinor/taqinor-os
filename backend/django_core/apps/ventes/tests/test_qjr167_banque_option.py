# -*- coding: utf-8 -*-
"""QJR167 — la BANQUE de batteries d'un devis se lit PAR OPTION.

Frère non corrigé de QJR140 (``capacite_batterie_du_devis``), signalé au fold
du 30/08 : ``banque_batterie_du_devis`` additionnait encore TOUTE ligne
classée batterie de ``devis.lignes.all()`` sans distinguer l'option qui la
porte — le MÊME bug, sur un devis à deux paliers de stockage variantés, mais
qui alimente la surface CLIENT du curseur « N batteries »
(``apps.ventes.public_views._couverture_batterie_publique``, gardée par
``avec_ok``) : une banque « Les deux » — 15 kWh — n'est vendue nulle part.

AVANT ce commit, ``banque_batterie_du_devis(devis, 'sans')`` levait
``TypeError`` (la fonction ne prenait qu'un seul paramètre) : les tests
ci-dessous sont donc rouges par construction sur la révision précédente, pas
seulement sur la valeur retournée — exactement le même patron que
``test_qjr140_capacite_batterie_option.py``.
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.etude_horaire import banque_batterie_du_devis
from apps.ventes.models import LigneDevis
from apps.ventes.tests.test_quote_engine import (
    make_client, make_company, make_devis, make_produit, make_user,
)


class BanqueParOptionTests(TestCase):
    """Le cœur du constat : un devis à DEUX paliers de stockage variantés."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj,
            [('Module PV 550 W', '20', '1500')],
            reference='DEV-QJR167-0001')

    def _ligne(self, designation, quantite, variante, sku):
        return LigneDevis.objects.create(
            devis=self.devis,
            produit=make_produit(self.company, designation, sku, '9000'),
            designation=designation, quantite=Decimal(quantite),
            prix_unitaire=Decimal('9000'), remise=Decimal('0'),
            variante=variante)

    def _deux_paliers(self):
        """Deux paliers de stockage qui ne coexistent dans AUCUNE option."""
        self._ligne('Batterie LiFePO4 5 kWh', '1', 'sans', 'Q167-B5')
        self._ligne('Batterie LiFePO4 10 kWh', '1', 'avec', 'Q167-B10')

    def test_la_banque_rendue_est_celle_d_UNE_option(self):
        self._deux_paliers()
        avec = banque_batterie_du_devis(self.devis, 'avec')
        sans = banque_batterie_du_devis(self.devis, 'sans')
        self.assertEqual(avec['capacite_utile_totale_kwh'], 10.0)
        self.assertEqual(avec['nb_packs'], 1)
        self.assertEqual(sans['capacite_utile_totale_kwh'], 5.0)
        self.assertEqual(sans['nb_packs'], 1)

    def test_jamais_15_kwh_pour_l_option_avec(self):
        """Régression exacte du constat du fold du 30/08 : « jamais 15 »."""
        self._deux_paliers()
        avec = banque_batterie_du_devis(self.devis, 'avec')
        self.assertNotEqual(avec['capacite_utile_totale_kwh'], 15.0)

    def test_la_somme_brute_ne_decrit_aucune_option_vendue(self):
        self._deux_paliers()
        brute = banque_batterie_du_devis(self.devis, option=None)
        self.assertEqual(brute['capacite_utile_totale_kwh'], 15.0)
        self.assertEqual(brute['nb_packs'], 2)
        self.assertNotEqual(
            brute['capacite_utile_totale_kwh'],
            banque_batterie_du_devis(self.devis, 'avec')['capacite_utile_totale_kwh'])
        self.assertNotEqual(
            brute['capacite_utile_totale_kwh'],
            banque_batterie_du_devis(self.devis, 'sans')['capacite_utile_totale_kwh'])

    def test_le_defaut_est_l_option_qui_porte_le_stockage(self):
        self._deux_paliers()
        self.assertEqual(banque_batterie_du_devis(self.devis),
                         banque_batterie_du_devis(self.devis, 'avec'))

    def test_une_ligne_commune_compte_dans_les_deux_options(self):
        self._ligne('Batterie LiFePO4 5 kWh', '2', '', 'Q167-BC')
        self.assertEqual(
            banque_batterie_du_devis(self.devis, 'avec')['capacite_utile_totale_kwh'], 10.0)
        self.assertEqual(
            banque_batterie_du_devis(self.devis, 'sans')['capacite_utile_totale_kwh'], 10.0)

    def test_un_devis_mono_option_est_inchange_a_l_octet(self):
        """Tout le parc existant : lignes communes ⇒ même résultat qu'avant."""
        self._ligne('Batterie LiFePO4 5 kWh', '3', '', 'Q167-BM')
        self.assertEqual(banque_batterie_du_devis(self.devis, 'avec'),
                         banque_batterie_du_devis(self.devis, option=None))

    def test_une_option_sans_batterie_rend_None_pas_zero(self):
        """« pas de stockage » n'est pas « stockage de capacité nulle »."""
        self._ligne('Batterie LiFePO4 10 kWh', '1', 'avec', 'Q167-BA')
        self.assertIsNone(banque_batterie_du_devis(self.devis, 'sans'))
        self.assertIsNotNone(banque_batterie_du_devis(self.devis, 'avec'))

    def test_un_devis_sans_aucune_batterie_rend_None(self):
        self.assertIsNone(banque_batterie_du_devis(self.devis, 'avec'))
        self.assertIsNone(banque_batterie_du_devis(self.devis, option=None))

    def test_les_quantites_sont_respectees_dans_l_option(self):
        self._ligne('Batterie LiFePO4 5 kWh', '3', 'avec', 'Q167-BQ')
        self._ligne('Batterie LiFePO4 5 kWh', '1', 'sans', 'Q167-BQ2')
        avec = banque_batterie_du_devis(self.devis, 'avec')
        sans = banque_batterie_du_devis(self.devis, 'sans')
        self.assertEqual(avec['capacite_utile_totale_kwh'], 15.0)
        self.assertEqual(avec['nb_packs'], 3)
        self.assertEqual(sans['capacite_utile_totale_kwh'], 5.0)
        self.assertEqual(sans['nb_packs'], 1)

    def test_lignes_illisibles_ne_levent_jamais(self):
        class _DevisCasse:
            lignes = None
        self.assertIsNone(banque_batterie_du_devis(_DevisCasse(), 'avec'))


class AppelantPublicPasseLOptionTests(TestCase):
    """« les appelants publics passent l'option effective » — épinglé sur la
    source : ``_couverture_batterie_publique`` (public_views.py) est le seul
    appelant réel de ``banque_batterie_du_devis`` hors tests."""

    def test_couverture_batterie_publique_nomme_explicitement_l_option(self):
        import ast
        import inspect

        from apps.ventes import public_views as PV

        arbre = ast.parse(inspect.getsource(PV).lstrip())
        appels = [
            noeud for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Call)
            and isinstance(noeud.func, ast.Name)
            and noeud.func.id == 'banque_batterie_du_devis'
        ]
        self.assertTrue(
            appels, 'aucun appel à banque_batterie_du_devis trouvé '
                    'dans apps/ventes/public_views.py')
        for appel in appels:
            self.assertIn('option', [kw.arg for kw in appel.keywords],
                          'appel ligne %d sans option nommée' % appel.lineno)
            valeurs = [
                kw.value.value for kw in appel.keywords
                if kw.arg == 'option' and isinstance(kw.value, ast.Constant)]
            self.assertEqual(
                valeurs, ['avec'],
                'la surface COUVBAT ne rend le curseur que quand avec_ok '
                '(option AVEC) — appel ligne %d' % appel.lineno)

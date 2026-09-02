"""QJR405 (DR7, moitié ERP) — la courbe « votre consommation » publiée inverse
une facture **TOTALE** avec le barème COMPLET, jamais avec le modèle
énergie-seule.

CE QUE LE ROUGE PROUVAIT. ``public_views._monthly_consumption`` lit les
factures du lead (``facture_hiver`` / ``facture_ete``), c'est-à-dire ce que le
client a saisi dans « Votre facture d'électricité mensuelle (MAD) » : le TOTAL
de son papier — location de compteur, entretien de branchement et TPPAN
comprises. Le repli appelait ``kwh_from_bill(mad, utility=...)`` sans
``facture_totale=True``, donc l'inversion ÉNERGIE SEULE : les ~39,94 MAD de
lignes fixes et la TPPAN étaient attribués à de la CONSOMMATION.

    facture totale de référence pour 359 kWh/mois (barème 2026, ONEE) :
        énergie 496,03 + fixes 39,94 + TPPAN 56,80 = 592,77 MAD
    inversion énergie-seule (ancien chemin) : 429 kWh/mois  (+19,5 %)
    inversion barème complet (chaîne principale ``bareme``) : 359 kWh/mois

Ce fichier reste ensuite la GARDE DE NON-RÉGRESSION du chemin : il compare le
chemin de production à la chaîne principale ``bareme.facture_mad`` /
``bareme.kwh_depuis_facture_mad``, sans épingler aucun nombre inventé — chaque
attendu est DÉRIVÉ du barème lui-même.

Le second test verrouille le correctif M10 (19/08/2026) : un lead SANS
distributeur réel n'a pas de barème, ``kwh_from_bill`` le signale
(``estimation``) et la série part vide — la page masque le graphe au lieu de
publier une division par un forfait.
"""
from unittest import mock

from django.test import SimpleTestCase

from apps.ventes import public_views
from apps.ventes.quote_engine import bareme


#: Consommations de référence (kWh/mois) balayant le barème : sous le seuil
#: progressif, juste au-dessus, la facture SRM de référence du dépôt, et un
#: gros consommateur.
_KWH_DE_REFERENCE = (100.0, 150.0, 250.0, 359.0, 500.0)


class InversionFactureTotaleTests(SimpleTestCase):
    """Le chemin de production rend les MÊMES kWh que la chaîne principale."""

    def _serie(self, bills):
        with mock.patch(
                'apps.crm.selectors.lead_bills_for_devis', return_value=bills):
            return public_views._monthly_consumption(object())

    def test_facture_totale_rend_les_kwh_du_bareme_complet(self):
        """ROUGE avant QJR405 : la série valait l'inversion énergie-seule.

        Pour chaque consommation de référence on FABRIQUE la facture totale que
        le barème produit (``bareme.facture_mad``), on la donne au chemin de
        production comme facture d'hiver du lead, et on exige les kWh que la
        chaîne principale (``bareme.kwh_depuis_facture_mad``) rend sur cette
        même facture — c'est-à-dire la consommation de départ.
        """
        for kwh in _KWH_DE_REFERENCE:
            with self.subTest(kwh=kwh):
                detail = bareme.facture_mad(kwh)
                total = detail['total_mad']
                # La facture de référence contient BIEN des lignes fixes et de
                # la TPPAN : sans elles, le test ne prouverait rien.
                self.assertGreater(detail['location_entretien_mad'], 0)
                self.assertGreater(detail['tppan_mad'], 0)

                attendu = round(
                    bareme.kwh_depuis_facture_mad(total)['kwh_mensuel'])
                serie = self._serie({
                    'facture_hiver': total, 'facture_ete': None,
                    'ete_differente': False, 'distributeur': 'onee'})
                self.assertEqual(len(serie), 12)
                self.assertTrue(
                    all(v == attendu for v in serie),
                    'la série publiée doit valoir %s kWh/mois, obtenu %r'
                    % (attendu, sorted(set(serie))))
                # …et cette valeur est bien la consommation de départ.
                self.assertAlmostEqual(serie[0], round(kwh), delta=1)

    def test_ecart_avec_le_modele_energie_seule_est_ferme(self):
        """Le chemin ne rend plus l'inversion énergie-seule (l'ancien défaut).

        Sur la facture SRM de référence, les deux modèles divergent de ~19,5 % :
        le test échoue si la série retombe sur l'inversion énergie-seule.
        """
        from apps.ventes.quote_engine import pricing
        total = bareme.facture_mad(359.0)['total_mad']
        energie_seule = round(
            pricing.kwh_from_bill(total, utility='onee')['kwh_mensuel'])
        complet = round(bareme.kwh_depuis_facture_mad(total)['kwh_mensuel'])
        # Les deux modèles DOIVENT diverger, sinon ce test ne discrimine rien.
        self.assertNotEqual(energie_seule, complet)

        serie = self._serie({
            'facture_hiver': total, 'facture_ete': None,
            'ete_differente': False, 'distributeur': 'onee'})
        self.assertEqual(serie[0], complet)
        self.assertNotEqual(serie[0], energie_seule)

    def test_facture_ete_distincte_suit_le_meme_bareme(self):
        """Hiver et été passent tous les deux par le barème complet."""
        total_hiver = bareme.facture_mad(500.0)['total_mad']
        total_ete = bareme.facture_mad(250.0)['total_mad']
        serie = self._serie({
            'facture_hiver': total_hiver, 'facture_ete': total_ete,
            'ete_differente': True, 'distributeur': 'onee'})
        self.assertEqual(len(serie), 12)
        # Index 0 = Janvier (hiver) ; index 5 = Juin (été, mois 4..9).
        self.assertEqual(
            serie[0], round(bareme.kwh_depuis_facture_mad(
                total_hiver)['kwh_mensuel']))
        self.assertEqual(
            serie[5], round(bareme.kwh_depuis_facture_mad(
                total_ete)['kwh_mensuel']))
        self.assertLess(serie[5], serie[0])


class M10EstimationMasqueLeGrapheTests(SimpleTestCase):
    """Le correctif M10 (19/08/2026) n'est pas défait par QJR405."""

    def _serie(self, bills):
        with mock.patch(
                'apps.crm.selectors.lead_bills_for_devis', return_value=bills):
            return public_views._monthly_consumption(object())

    def test_sans_distributeur_la_serie_reste_vide(self):
        total = bareme.facture_mad(359.0)['total_mad']
        self.assertEqual(self._serie({
            'facture_hiver': total, 'facture_ete': None,
            'ete_differente': False, 'distributeur': None}), [])

    def test_facture_vide_reste_vide(self):
        self.assertEqual(self._serie({
            'facture_hiver': 0.0, 'facture_ete': None,
            'ete_differente': False, 'distributeur': 'onee'}), [])

    def test_facture_hors_plage_inversable_reste_vide(self):
        """QJR142/QJR158 — un montant qu'aucune consommation ne produit est
        signalé ``estimation`` et n'est jamais publié comme une mesure."""
        self.assertEqual(self._serie({
            'facture_hiver': 1e12, 'facture_ete': None,
            'ete_differente': False, 'distributeur': 'onee'}), [])

    def test_sans_facture_la_serie_reste_vide(self):
        self.assertEqual(self._serie(None), [])

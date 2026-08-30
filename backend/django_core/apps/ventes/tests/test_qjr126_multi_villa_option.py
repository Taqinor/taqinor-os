"""QJR126 — le « Total général » multi-villa ne somme plus les deux options.

``selectors.multi_villa_totaux`` calcule sur TOUTES les lignes du devis, et son
déclenchement dans le builder était HORS du garde ``_n > 1`` sans jamais tester
``deux_options`` : il suffisait qu'une ligne porte un ``groupe_index``. Sur un
devis à deux options ainsi groupé, la page 2 affichait deux totaux (un par
option) et la page 3 un « Total général » qui les ADDITIONNE — le montant sans
signification que QJR24 et PACT10 combattent partout ailleurs.

Second point : les replis ``_fmt2(t.get("ht_net", 0))`` /
``fmt(gt.get("ttc", 0))`` imprimaient « Total général : 0 MAD » d'apparence
factuelle si la clé manquait.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr126_multi_villa_option -v 2
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.ventes.quote_engine import generate_devis_premium as moteur
from apps.ventes.tests.test_qj30_multivilla_render import (
    make_client, make_company, make_devis, make_user)


#: Composition à DEUX options servables (réseau + hybride/batterie), groupée.
LIGNES_DEUX_OPTIONS_GROUPEES = [
    ('Onduleur réseau 10kW', '1', '11700', 1, 'Villa A'),
    ('Onduleur hybride 5kW', '1', '24000', 1, 'Villa A'),
    ('Batterie 5 kWh', '1', '14000', 1, 'Villa A'),
    ('Panneau mono 550W', '14', '1100', 1, 'Villa A'),
    ('Installation', '1', '4000', 2, 'Villa B'),
]

#: Même groupement, mais UNE seule option servable (deux onduleurs réseau).
LIGNES_UNE_OPTION_GROUPEES = [
    ('Installation commune', '1', '5000', 0, 'Commun'),
    ('Onduleur réseau 8kW', '1', '14000', 1, 'Villa A'),
    ('Panneau mono 550W', '10', '1400', 1, 'Villa A'),
    ('Onduleur réseau 5kW', '1', '11000', 2, 'Villa B'),
    ('Panneau mono 550W', '8', '1400', 2, 'Villa B'),
]


class TestBuilderNePosePasLaCleSurDeuxOptions(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _data(self, lignes, reference):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, lignes,
                           reference)
        return build_quote_data(devis)

    def test_devis_a_deux_options_groupe_na_pas_de_total_general(self):
        data = self._data(LIGNES_DEUX_OPTIONS_GROUPEES, 'DEV-QJR126-A')
        self.assertEqual(data['nb_options'], 2,
                         "la fixture doit bien chiffrer deux options")
        self.assertIsNone(data.get('multi_villa'))

    def test_le_pdf_n_imprime_aucun_total_general(self):
        data = self._data(LIGNES_DEUX_OPTIONS_GROUPEES, 'DEV-QJR126-B')
        html = moteur.render_html_for(data)
        self.assertNotIn('Total général', html)
        self.assertNotIn('Détail par propriété', html)

    def test_mono_option_groupee_garde_son_detail_par_propriete(self):
        data = self._data(LIGNES_UNE_OPTION_GROUPEES, 'DEV-QJR126-C')
        self.assertEqual(data['nb_options'], 1)
        self.assertIsNotNone(data.get('multi_villa'))
        # …et le total général EST la somme des groupes de la seule offre.
        mv = data['multi_villa']
        somme = sum(Decimal(str(g['totaux']['ttc'])) for g in mv['groupes'])
        self.assertAlmostEqual(float(somme),
                               float(mv['grand_total']['ttc']), places=2)
        self.assertAlmostEqual(float(mv['grand_total']['ttc']),
                               float(data['totaux_all']['ttc']), places=2)


class TestAucunZeroImprime(SimpleTestCase):
    """Un total manquant s'OMET — il ne s'écrit pas « 0 MAD »."""

    def _rendu(self, mv):
        ancien = moteur.MULTI_VILLA
        moteur.MULTI_VILLA = mv
        try:
            return moteur._multi_villa_html()
        finally:
            moteur.MULTI_VILLA = ancien

    def test_grand_total_manquant_omet_la_ligne(self):
        html = self._rendu({
            'groupes': [{'index': 1, 'label': 'Villa A',
                         'totaux': {'ht_net': 28000.0, 'ttc': 33600.0}}],
        })
        self.assertIn('Villa A', html)
        self.assertNotIn('Total général', html)
        self.assertNotIn('0&#160;MAD', html)

    def test_totaux_de_groupe_manquants_laissent_la_cellule_vide(self):
        html = self._rendu({
            'groupes': [{'index': 1, 'label': 'Villa A', 'totaux': {}}],
            'grand_total': {},
        })
        self.assertIn('Villa A', html)
        self.assertNotIn('Total général', html)
        # Aucun « 0 » d'apparence mesurée dans les cellules de montant.
        self.assertNotIn('>0,00<', html)

    def test_donnees_completes_rendues_a_l_identique(self):
        html = self._rendu({
            'groupes': [
                {'index': 1, 'label': 'Villa A',
                 'totaux': {'ht_net': 28000.0, 'ttc': 33600.0}},
                {'index': 2, 'label': 'Villa B',
                 'totaux': {'ht_net': 22000.0, 'ttc': 26400.0}},
            ],
            'grand_total': {'ht_net': 50000.0, 'ttc': 60000.0},
        })
        self.assertIn('Total général', html)
        self.assertIn('Villa A', html)
        self.assertIn('Villa B', html)

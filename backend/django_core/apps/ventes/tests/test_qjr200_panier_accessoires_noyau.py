"""QJR200 — le panier « accessoires Huawei » est une règle du NOYAU monnaie.

TEST ROUGE D'ABORD (contre-visite du 30/08/2026). Avant le correctif, le PDF
retirait le Smart Meter et la clé Wi-Fi de l'option dont l'onduleur n'est pas
Huawei (QF9, filtrage EN AMONT) pendant que la chaîne monnaie
(``utils.options.option_totaux`` / ``domain.argent.totaux``) continuait de les
additionner : sur le devis résidentiel COURANT (réseau Huawei + hybride Deye),
le total imprimé valait 100 040 et ``option_totaux`` 103 040 — deux prix pour
la même vente.

Le premier test de ce module rougissait donc AVANT le correctif.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr200_panier_accessoires_noyau -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)
from apps.ventes.utils.options import (
    AVEC_BATTERIE, SANS_BATTERIE, est_accessoire_huawei, option_lines,
    option_totaux, retirer_accessoires_huawei,
)


# Le devis résidentiel COURANT : une option réseau Huawei, une option hybride
# Deye + batterie, et les deux accessoires Huawei en lignes communes.
LIGNES_HUAWEI_DEYE = [
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33'),
    ('Smart Meter', '1', '1500'),
    ('Wifi Dongle', '1', '1000'),
    ('Panneau Canadian Solar 710W', '14', '1166.67'),
    ('Batterie Dyness 10 kWh', '1', '25000'),
    ('Structures acier', '14', '416.67'),
    ('Installation', '1', '5000'),
]


class TestQJR200PredicatUnique(TestCase):
    """La règle, lue sans base : un seul prédicat, deux adaptateurs."""

    def test_accessoire_reconnu_sur_les_deux_libelles(self):
        self.assertTrue(est_accessoire_huawei('Smart Meter'))
        self.assertTrue(est_accessoire_huawei('Wifi Dongle'))
        self.assertTrue(est_accessoire_huawei('Clé Wifi (dongle)'))
        self.assertFalse(est_accessoire_huawei('Onduleur hybride Deye 10kW'))
        self.assertFalse(est_accessoire_huawei('Panneau mono 550W'))

    def test_panier_deye_perd_ses_accessoires_panier_huawei_les_garde(self):
        """Adaptateur générique : la règle marche sur n'importe quelle rangée."""
        deye = [
            {'d': 'Onduleur hybride Deye 10kW', 'm': 'Deye'},
            {'d': 'Smart Meter', 'm': ''},
            {'d': 'Wifi Dongle', 'm': ''},
        ]
        huawei = [
            {'d': 'Onduleur réseau Huawei 10kW', 'm': 'Huawei'},
            {'d': 'Smart Meter', 'm': ''},
        ]
        garde = dict(classement=lambda r: r['d'],
                     marque=lambda r: f"{r['d']} {r['m']}")
        self.assertEqual(
            [r['d'] for r in retirer_accessoires_huawei(deye, **garde)],
            ['Onduleur hybride Deye 10kW'])
        self.assertEqual(len(retirer_accessoires_huawei(huawei, **garde)), 2)

    def test_sans_onduleur_les_accessoires_partent(self):
        """Conservateur, comme l'ancien ``builder._quote_is_huawei`` : sans
        onduleur identifiable, l'accessoire est orphelin."""
        rows = [{'d': 'Smart Meter'}, {'d': 'Installation'}]
        garde = dict(classement=lambda r: r['d'], marque=lambda r: r['d'])
        self.assertEqual(
            [r['d'] for r in retirer_accessoires_huawei(rows, **garde)],
            ['Installation'])


class TestQJR200TotalImprimeEgaleNoyau(TestCase):
    """LE ROUGE : total imprimé (PDF) == somme des paniers du noyau."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, LIGNES_HUAWEI_DEYE,
            reference='DEV-QJR200-0001', etude_params=dict(DEUX_OPTIONS))

    def _data(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        return build_quote_data(self.devis)

    def test_option_avec_deye_le_noyau_ne_compte_plus_les_accessoires(self):
        """ROUGE AVANT : ``option_totaux`` ajoutait Smart Meter + Wi-Fi (3 000
        TTC) que le PDF n'imprime pas sur l'option Deye."""
        data = self._data()
        noyau = option_totaux(self.devis, AVEC_BATTERIE)
        self.assertAlmostEqual(
            float(noyau['ttc']), float(data['total_avec']), delta=1,
            msg='le total du noyau et le total imprimé décrivent le même panier')

    def test_option_sans_huawei_garde_ses_accessoires(self):
        """L'option réseau Huawei les FACTURE : elle ne perd rien."""
        data = self._data()
        noyau = option_totaux(self.devis, SANS_BATTERIE)
        self.assertAlmostEqual(
            float(noyau['ttc']), float(data['total_sans']), delta=1)
        desigs = [li.designation for li in
                  option_lines(self.devis, SANS_BATTERIE)]
        self.assertIn('Smart Meter', desigs)
        self.assertIn('Wifi Dongle', desigs)

    def test_nomenclature_de_l_option_deye_omet_les_accessoires(self):
        """L'échéancier et le chantier lisent le MÊME panier que le PDF."""
        desigs = [li.designation for li in
                  option_lines(self.devis, AVEC_BATTERIE)]
        self.assertNotIn('Smart Meter', desigs)
        self.assertNotIn('Wifi Dongle', desigs)
        self.assertIn('Batterie Dyness 10 kWh', desigs)

    def test_ecart_de_3000_ttc_referme(self):
        """L'écart mesuré par la contre-visite, épinglé au dirham : les deux
        accessoires valent 2 500 HT = 3 000 TTC."""
        from apps.ventes.utils.options import (
            _garder_dans_avec, _totaux_canoniques,
        )
        lignes = list(self.devis.lignes.select_related('produit').all())
        # Le panier « avec » AVANT QJR200 : le split par mots-clés seul.
        avant = _totaux_canoniques(
            self.devis, [li for li in lignes if _garder_dans_avec(li)])
        apres = option_totaux(self.devis, AVEC_BATTERIE)
        self.assertEqual(avant['ttc'] - apres['ttc'], Decimal('3000.00'))

    def test_devis_mono_option_inchange(self):
        """Aucun devis mono-option ne bouge d'un centime."""
        mono = make_devis(
            self.company, self.user, self.client_obj, [
                ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33'),
                ('Smart Meter', '1', '1500'),
                ('Panneau Canadian Solar 710W', '14', '1166.67'),
            ], reference='DEV-QJR200-0002')
        total = option_totaux(mono)
        attendu = sum(
            (Decimal(str(li.total_ht)) for li in mono.lignes.all()),
            Decimal('0'))
        self.assertEqual(total['ht'], attendu)
        self.assertIn('Smart Meter',
                      [li.designation for li in option_lines(mono)])

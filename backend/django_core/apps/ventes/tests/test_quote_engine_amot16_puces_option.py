"""AMOT16 (C-AMOT-014, C-AMOT-015) — chaque puce de carte d'option est
générée depuis le panier ET la puissance de CETTE option : « N panneaux
<watt de l'option> W », et « Structures + installation complète » seulement
si l'option porte une ligne de structure et une ligne de pose.

Moteur réel (``build_quote_data``), lignes réelles. Test-du-test : remettre
le ``watt`` scalaire dans ``_bullets`` ⇒ ``test_watt_par_option`` échoue ;
remettre l'ajout inconditionnel ⇒ ``test_sans_structure_ni_pose`` échoue.
"""
from django.test import TestCase

from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)

_PUCE = 'Structures + installation complète'


class PucesOptionTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot16-co', nom='AMOT16')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.n = 0

    def _devis(self, extra=()):
        self.n += 1
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 550W', '10', '1000'),
            ('Panneau mono 710W', '10', '1300'),
            ('Onduleur réseau Huawei 5kW', '1', '8000'),
            ('Onduleur hybride Deye 5kW', '1', '15000'),
            ('Batterie Dyness 5kWh', '1', '20000'),
        ] + list(extra), reference=f'DEV-AMOT16-{self.n}',
            etude_params=dict(DEUX_OPTIONS))
        devis.lignes.filter(designation='Panneau mono 550W').update(
            variante='sans')
        devis.lignes.filter(designation='Panneau mono 710W').update(
            variante='avec')
        return devis

    @staticmethod
    def _data(devis):
        return build_quote_data(devis, clean_pdf_options({'pdf_mode': 'full'}))

    def test_watt_par_option(self):
        data = self._data(self._devis())
        self.assertEqual(data['sans_bullets'][0], '10 panneaux 550 W')
        self.assertEqual(data['avec_bullets'][0], '10 panneaux 710 W')

    def test_sans_structure_ni_pose(self):
        data = self._data(self._devis())
        self.assertNotIn(_PUCE, data['sans_bullets'])
        self.assertNotIn(_PUCE, data['avec_bullets'])

    def test_structure_et_pose_gardent_la_puce(self):
        data = self._data(self._devis(extra=[
            ('Structure acier', '10', '300'),
            ('Installation et mise en service', '1', '4000'),
        ]))
        self.assertIn(_PUCE, data['sans_bullets'])
        self.assertIn(_PUCE, data['avec_bullets'])

    def test_structure_sans_pose_pas_de_puce(self):
        data = self._data(self._devis(extra=[
            ('Structure acier', '10', '300')]))
        self.assertNotIn(_PUCE, data['sans_bullets'])

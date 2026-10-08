"""AMOT16 (C-AMOT-014, C-AMOT-015) — chaque puce de carte d'option vient du
panier ET de la puissance de CETTE option : « N panneaux <watt de l'option>
W », et « Structures + installation complète » seulement si l'option porte une
ligne de structure ET une ligne de pose.

Rejoue VA b25 (550 W « sans » / 710 W « avec », sans structure ni pose :
puces sans ``['10 panneaux 710 W', …, 'Structures + installation complète']``).

Test-du-test : remettre ``watt`` scalaire dans ``_bullets`` ⇒ rouge ; remettre
l'ajout inconditionnel ⇒ rouge.
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.models import LigneDevis
from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_produit,
    make_user)

STRUCTURES = 'Structures + installation complète'


class PucesOptionTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_ = make_client(self.company)

    def _ligne(self, devis, desig, qte, pu, variante=''):
        LigneDevis.objects.create(
            devis=devis,
            produit=make_produit(self.company, desig,
                                 f'{devis.reference[-4:]}-{desig[:12]}-{variante}',
                                 pu),
            designation=desig, quantite=Decimal(qte),
            prix_unitaire=Decimal(pu), remise=Decimal('0'), variante=variante)

    def _devis_variantes(self, ref, structure=False):
        devis = make_devis(self.company, self.user, self.client_, [],
                           reference=ref, etude_params=dict(DEUX_OPTIONS))
        self._ligne(devis, 'Panneau mono 550W', '10', '1000', 'sans')
        self._ligne(devis, 'Panneau mono 710W', '10', '1300', 'avec')
        self._ligne(devis, 'Onduleur réseau Huawei 5kW', '1', '8000', 'sans')
        self._ligne(devis, 'Onduleur hybride Deye 5kW', '1', '12000', 'avec')
        self._ligne(devis, 'Batterie Dyness 5kWh', '1', '15000', 'avec')
        if structure:
            self._ligne(devis, 'Structure aluminium', '10', '300')
            self._ligne(devis, 'Installation et mise en service', '1', '4000')
        return devis

    def test_puissance_par_option_et_pas_de_structure_inventee(self):
        data = build_quote_data(self._devis_variantes('DEV-AMOT16-0001'),
                                {'pdf_mode': 'full'})
        self.assertEqual(data['sans_bullets'][0], '10 panneaux 550 W')
        self.assertEqual(data['avec_bullets'][0], '10 panneaux 710 W')
        self.assertNotIn(STRUCTURES, data['sans_bullets'])
        self.assertNotIn(STRUCTURES, data['avec_bullets'])

    def test_structure_et_pose_gardent_la_puce(self):
        data = build_quote_data(
            self._devis_variantes('DEV-AMOT16-0002', structure=True),
            {'pdf_mode': 'full'})
        self.assertIn(STRUCTURES, data['sans_bullets'])
        self.assertIn(STRUCTURES, data['avec_bullets'])

    def test_regles_d_origine_inchangees(self):
        devis = self._devis_variantes('DEV-AMOT16-0003')
        devis.regles_calcul = 1
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertIn(STRUCTURES, data['sans_bullets'])

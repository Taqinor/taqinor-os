"""AMOT9 (C-AMOT-004) — le PDF lit le kWc du PROPRIÉTAIRE : une surcharge
``taille.kwc`` du registre vaut sur la fiche ET sur le document, même quand le
watt des panneaux est illisible ou qu'il n'y a pas de ligne panneau.

Rejoue la sonde VA S4 (« Panneau Jinko Tiger Neo » ×10 sans watt lisible,
``taille.kwc = 7.1`` : ``pdf=None stocke=7.1`` ; témoin 710 W : 7.5 / 7.5).

Test-du-test : remettre la condition ``if nb_panneaux > 0 and watt:`` autour
de ``_kwc_du_registre`` ⇒ ``test_sans_watt_registre`` échoue.
"""
from django.test import TestCase

from apps.ventes.domain.overrides import poser
from apps.ventes.domain.scenario import puissance_kwc_du_devis
from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user)


class KwcRegistreTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_ = make_client(self.company)

    def _devis(self, lignes, ref, kwc=None):
        devis = make_devis(self.company, self.user, self.client_, lignes,
                           reference=ref)
        if kwc is not None:
            devis.overrides = poser(devis, 'taille.kwc', kwc)
            devis.save(update_fields=['overrides'])
        return devis

    def test_lignes_avec_watt(self):
        devis = self._devis([('Panneau mono 750W', '10', '1100'),
                             ('Onduleur réseau 5kW', '1', '8000')],
                            'DEV-AMOT9-0001')
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertEqual(data['puissance_kwc'], 7.5)
        self.assertEqual(puissance_kwc_du_devis(devis), 7.5)

    def test_sans_watt_registre(self):
        devis = self._devis([('Panneau Jinko Tiger Neo', '10', '1100'),
                             ('Onduleur réseau 5kW', '1', '8000')],
                            'DEV-AMOT9-0002', kwc=7.1)
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertEqual(data['puissance_kwc'], 7.1)
        self.assertEqual(data['puissance_kwc'], puissance_kwc_du_devis(devis))

    def test_sans_panneau_registre(self):
        devis = self._devis([('Onduleur réseau 5kW', '1', '8000')],
                            'DEV-AMOT9-0003', kwc=7.1)
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertEqual(data['puissance_kwc'], 7.1)

    def test_sans_watt_sans_registre_reste_omis(self):
        devis = self._devis([('Panneau Jinko Tiger Neo', '10', '1100'),
                             ('Onduleur réseau 5kW', '1', '8000')],
                            'DEV-AMOT9-0004')
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertIsNone(data['puissance_kwc'])

    def test_registre_avec_watt(self):
        devis = self._devis([('Panneau mono 750W', '10', '1100'),
                             ('Onduleur réseau 5kW', '1', '8000')],
                            'DEV-AMOT9-0005', kwc=7.1)
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertEqual(data['puissance_kwc'], 7.1)

    def test_regles_d_origine_inchangees(self):
        devis = self._devis([('Panneau Jinko Tiger Neo', '10', '1100'),
                             ('Onduleur réseau 5kW', '1', '8000')],
                            'DEV-AMOT9-0006', kwc=7.1)
        devis.regles_calcul = 1
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertIsNone(data['puissance_kwc'])

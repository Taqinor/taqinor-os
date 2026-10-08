"""AMOT9 (C-AMOT-004) — le PDF lit le kWc du PROPRIÉTAIRE
(``domain.scenario.puissance_kwc_du_devis``) : une surcharge ``taille.kwc``
du registre vaut sur la fiche ET sur le document, même quand le watt des
panneaux est illisible ou qu'il n'y a aucune ligne panneau.

Moteur réel (``build_quote_data``), registre réel (``Devis.overrides``).
Test-du-test : remettre la condition ``if nb_panneaux > 0 and watt:`` autour
de la lecture du registre ⇒ ``test_sans_watt_avec_registre`` échoue.
"""
from django.test import TestCase

from apps.ventes.domain.scenario import puissance_kwc_du_devis
from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

_ONDULEUR = ('Onduleur réseau Huawei 5kW', '1', '8000')


class KwcRegistreTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot9-co', nom='AMOT9')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, lignes, ref, kwc_impose=None):
        devis = make_devis(self.company, self.user, self.client_obj, lignes,
                           reference=ref)
        if kwc_impose is not None:
            devis.overrides = {'taille.kwc': {'valeur': kwc_impose,
                                              'origine': 'manuel'}}
            devis.save(update_fields=['overrides'])
            devis.refresh_from_db()
        return devis

    @staticmethod
    def _kwc(devis):
        return build_quote_data(
            devis, clean_pdf_options({'pdf_mode': 'onepage'}))['puissance_kwc']

    def test_lignes_avec_watt_sans_registre(self):
        devis = self._devis([('Panneau mono 710W', '10', '1100'), _ONDULEUR],
                            'DEV-AMOT9-1')
        self.assertEqual(self._kwc(devis), 7.1)

    def test_sans_watt_avec_registre(self):
        devis = self._devis([('Panneau Jinko Tiger Neo', '10', '1100'),
                             _ONDULEUR], 'DEV-AMOT9-2', kwc_impose=7.1)
        self.assertEqual(self._kwc(devis), 7.1)
        # CLAUSE PERSISTANCE — kWc stocké (propriétaire) = kWc rendu.
        self.assertEqual(puissance_kwc_du_devis(devis), self._kwc(devis))

    def test_sans_watt_sans_registre_omis(self):
        devis = self._devis([('Panneau Jinko Tiger Neo', '10', '1100'),
                             _ONDULEUR], 'DEV-AMOT9-3')
        self.assertIsNone(self._kwc(devis))

    def test_sans_panneau_avec_registre(self):
        devis = self._devis([_ONDULEUR], 'DEV-AMOT9-4', kwc_impose=7.1)
        self.assertEqual(self._kwc(devis), 7.1)

    def test_registre_prime_sur_lignes(self):
        devis = self._devis([('Panneau mono 710W', '10', '1100'), _ONDULEUR],
                            'DEV-AMOT9-5', kwc_impose=6.5)
        self.assertEqual(self._kwc(devis), 6.5)

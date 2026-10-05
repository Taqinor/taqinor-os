"""ACAL60 (C-ACAL-035) — le moteur de devis compte les panneaux d'un layout
par ``lire_layout`` : ``_panneaux_du_layout`` disparaît, le badge « périmé »
et la planche du PDF voient le champ au sol.

Devis réel en base, ``peremption_layout_devis`` et ``build_quote_data``
réels ; un toit pavé garde le compte d'avant (non-régression).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_builder_compte_layout"
"""
from django.test import TestCase

from apps.ventes.domain.geometrie import lire_layout
from apps.ventes.quote_engine import builder
from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.selectors import peremption_layout_devis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user)

CHAMP_AU_SOL = {
    'zones': [],
    'poseSurfaces': [{'id': 'TERRAIN', 'kind': 'sol',
                      'label': 'Champ au sol', 'moduleWc': 550,
                      'rowAzimuthDeg': 90, 'tiltDeg': 25,
                      'engine': {'modules': 340}}],
}
TOIT = {
    'zones': [{'id': 'z1', 'label': 'Pan sud', 'geometry': {
        'count': 12, 'kwc': 6.6, 'azimuthDeg': 180, 'tiltDeg': 30}}],
    'result': {'panels': 12, 'kwc': 6.6},
}


class CompteDuLayout(TestCase):

    def _devis(self, panneaux, layout):
        company = make_company()
        user = make_user(company)
        devis = make_devis(company, user, make_client(company), [
            ('Onduleur réseau 100kW', '1', '90000'),
            ('Panneau mono 550W', str(panneaux), '1100'),
        ])
        devis.roof_layout = layout
        devis.save(update_fields=['roof_layout'])
        return devis

    def test_champ_au_sol_perime(self):
        devis = self._devis(300, CHAMP_AU_SOL)
        verdict = peremption_layout_devis(devis)
        self.assertEqual(verdict['layout_nb_panneaux'], 340)
        self.assertEqual(verdict['layout_nb_panneaux'],
                         lire_layout(CHAMP_AU_SOL).compte)
        self.assertTrue(verdict['layout_stale'])
        data = build_quote_data(devis, {})
        self.assertTrue(data['layout_stale'])

    def test_toit_pave_compte_inchange(self):
        devis = self._devis(12, TOIT)
        verdict = peremption_layout_devis(devis)
        self.assertEqual(verdict['layout_nb_panneaux'], 12)
        self.assertFalse(verdict['layout_stale'])
        self.assertFalse(build_quote_data(devis, {})['layout_stale'])

    def test_l_ancien_lecteur_a_disparu(self):
        self.assertFalse(hasattr(builder, '_panneaux_du_layout'))
        self.assertEqual(builder._compte_du_layout(CHAMP_AU_SOL), 340)
        self.assertEqual(builder._compte_du_layout(None), 0)

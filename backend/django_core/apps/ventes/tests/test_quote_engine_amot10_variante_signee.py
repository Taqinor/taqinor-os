"""AMOT10 (C-AMOT-005) — le document « option » téléchargé décrit UNE option
et UN total : quand la variante demandée rétrécit le document après une
signature de l'AUTRE option, ``display_total`` (et ``figures.total_affiche``)
est celui de la variante, jamais celui de l'option signée.

Moteur réel (``build_quote_data``), aucun mock. Test-du-test : retirer la
condition ``_variante_retrecit`` du bloc QJR401 ⇒ ``test_variante_avec``
échoue (display_total = total « sans » signé).
"""
from django.test import TestCase

from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)
from apps.ventes.utils.options import SANS_BATTERIE

_LIGNES = [
    ('Panneau mono 550W', '10', '1100'),
    ('Onduleur réseau Huawei 5kW', '1', '8000'),
    ('Onduleur hybride Deye 5kW', '1', '15000'),
    ('Batterie Dyness 5kWh', '1', '20000'),
]


class VarianteSigneeTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot10-co', nom='AMOT10')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, mode, ref):
        devis = make_devis(self.company, self.user, self.client_obj, _LIGNES,
                           reference=ref, etude_params=dict(DEUX_OPTIONS))
        Devis.objects.filter(pk=devis.pk).update(
            mode_installation=mode, option_acceptee=SANS_BATTERIE)
        devis.refresh_from_db()
        return devis

    def _data(self, devis, **opts):
        return build_quote_data(devis, clean_pdf_options(opts))

    def test_variante_avec(self):
        for i, mode in enumerate(('residentiel', 'commercial', 'industriel')):
            devis = self._devis(mode, f'DEV-AMOT10-{i}')
            data = self._data(devis, variante_option='avec')
            self.assertAlmostEqual(float(data['display_total']),
                                   float(data['totaux_all']['ttc']), places=2,
                                   msg=mode)
            self.assertAlmostEqual(float(data['display_total']),
                                   float(data['totaux_avec']['ttc']), places=2,
                                   msg=mode)
            self.assertGreater(float(data['display_total']),
                               float(data['totaux_sans']['ttc']))

    def test_sans_variante_option_signee(self):
        devis = self._devis('residentiel', 'DEV-AMOT10-9')
        data = self._data(devis)
        # QJR401 inchangé : sans variante, le total de l'option signée.
        self.assertAlmostEqual(float(data['display_total']),
                               float(data['totaux_sans']['ttc']), places=2)

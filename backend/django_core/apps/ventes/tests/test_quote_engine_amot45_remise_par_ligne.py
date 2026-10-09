"""AMOT45 (C-AMOT-057) — la remise ligne par ligne (QJRREM) est portée dans
les tableaux de l'agricole et de la page équipements commerciale /
industrielle par LE helper unique ``montants.lignes_remisees`` (extrait du
résidentiel) : P.U. catalogue barré + P.U. remisé, Σ des totaux de ligne =
Total HT.

Moteur réel (``build_quote_data`` annote ``pu_ht_remise`` /
``total_ht_remise``), gabarits réels. Test-du-test : remettre
``pu = _num(it.get("prix_unit_ht"))`` dans ``agricole/pages._lignes`` ⇒
``test_agricole_remise_par_ligne`` échoue (20 000,00 au lieu de 19 000,00).
"""
import html as _html

from django.test import TestCase

from apps.ventes.models import Devis
from apps.ventes.quote_engine.agricole import pages
from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.quote_engine.commercial import render as c_render
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.montants import fmt_centimes, lignes_remisees
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)


class RemiseParLigneTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot45-co', nom='AMOT45')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.n = 0

    def _data(self, mode, lignes):
        self.n += 1
        devis = make_devis(self.company, self.user, self.client_obj, lignes,
                           remise_globale='5',
                           reference=f'DEV-AMOT45-{self.n}')
        Devis.objects.filter(pk=devis.pk).update(mode_installation=mode)
        devis.refresh_from_db()
        return build_quote_data(devis, clean_pdf_options({'pdf_mode': 'full'}))

    def _somme_egale_total_ht(self, data):
        # Σ des totaux de ligne remisés = Sous-total HT − Remise (l'éventuel
        # arrondi au palier de 100 MAD reste sa ligne visible, ARRONDI-100).
        tot = data['totaux_all']
        somme = sum(ligne[4] for ligne in lignes_remisees(data['all_items']))
        self.assertAlmostEqual(
            somme, float(tot['ht_brut']) - float(tot['remise']), delta=0.02)

    def test_agricole_remise_par_ligne(self):
        data = self._data('agricole', [
            ('Pompe immergée OSP 30/8 10 CV', '1', '20000'),
            ('Panneau mono 550W', '14', '1100'),
        ])
        self._somme_egale_total_ht(data)
        h = _html.unescape(pages._lignes(data))
        self.assertIn('ag-was', h)
        self.assertIn(fmt_centimes(19000), h)
        self.assertIn(fmt_centimes(20000), h)

    def test_commercial_remise_par_ligne(self):
        data = self._data('commercial', [
            ('Panneau mono 550W', '40', '1100'),
            ('Onduleur réseau Huawei 20kW', '1', '30000'),
        ])
        self._somme_egale_total_ht(data)
        h = _html.unescape(c_render.build_html(c_renderer._augment(data)))
        self.assertIn('line-through', h)
        pu_rem = [ligne[2] for ligne in lignes_remisees(data['all_items'])]
        self.assertTrue(any(fmt_centimes(p) in h for p in pu_rem))

    def test_sans_remise_inchange(self):
        lignes = [('Panneau mono 550W', '14', '1100')]
        rows = lignes_remisees([{'prix_unit_ht': 1100.0, 'quantite': 14}])
        self.assertFalse(rows[0][5])
        self.assertEqual(rows[0][4], 1100.0 * 14)
        self.assertTrue(lignes)

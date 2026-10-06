"""CIQ316 — options proposées en HT, avec leur taux de TVA, comme le reste
du tableau des PDF C&I (page partagée commercial / industriel).

Rendu RÉEL : les montants imprimés sont les ``total_ht`` / ``total_ttc`` /
``taux_tva`` SERVIS par le builder (supplément canonique QJR616), sans aucun
recalcul dans le gabarit ; les ancres ``data-figure`` ne changent pas.
"""
import copy

from django.test import SimpleTestCase

from apps.ventes.quote_engine.commercial import render as c_render
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.commercial import sample_data as c_sample
from apps.ventes.quote_engine.figures import extract_figures
from apps.ventes.quote_engine.industriel import render as i_render
from apps.ventes.quote_engine.industriel import renderer as i_renderer
from apps.ventes.quote_engine.industriel import sample_data as i_sample
from apps.ventes.quote_engine.montants import fmt_centimes

#: Valeurs servies VOLONTAIREMENT non dérivables l'une de l'autre : un
#: recalcul dans le gabarit (HT × 1,2…) se verrait.
OPTIONS = [
    {"id": 1, "designation": "Batterie 10 kWh", "marque": "X", "quantite": 1,
     "taux_tva": 20, "prix_unit_ht": 40000, "prix_unit_ttc": 48000,
     "total_ht": 38123.45, "total_ttc": 45748.14},
    {"id": 2, "designation": "Borne de recharge", "marque": "Y",
     "quantite": 2, "taux_tva": 10, "prix_unit_ht": 9000,
     "prix_unit_ttc": 9900, "total_ht": 17321.09, "total_ttc": 19053.2},
]

GABARITS = (
    ("commercial", c_sample, c_renderer, c_render),
    ("industriel", i_sample, i_renderer, i_render),
)


def _rendu(sample, renderer, render, options):
    data = copy.deepcopy(sample.build())
    if options:
        data["options_proposees"] = copy.deepcopy(options)
    return render.build_html(renderer._augment(data))


class OptionsEnHt(SimpleTestCase):

    def test_montants_ht_servis_ttc_en_petit(self):
        for nom, sample, renderer, render in GABARITS:
            with self.subTest(gabarit=nom):
                html = _rendu(sample, renderer, render, OPTIONS)
                bloc = html[html.index("Options propos&eacute;es"):]
                bloc = bloc[:bloc.index("</table>")]
                self.assertIn("Total HT", bloc)
                self.assertIn("TVA %", bloc)
                for o in OPTIONS:
                    self.assertIn(f"{fmt_centimes(o['total_ht'])} MAD HT",
                                  bloc)
                    self.assertIn(f"{fmt_centimes(o['total_ttc'])} MAD TTC",
                                  bloc)
                    self.assertIn(f"{o['taux_tva']:g} %", bloc)

    def test_ancres_inchangees(self):
        for nom, sample, renderer, render in GABARITS:
            with self.subTest(gabarit=nom):
                avec = extract_figures(_rendu(sample, renderer, render,
                                              OPTIONS))
                sans = extract_figures(_rendu(sample, renderer, render, []))
                self.assertEqual(sorted(avec), sorted(sans))

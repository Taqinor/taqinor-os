"""CIQ320 — « Bon pour accord — pour la société » avec une case « Cachet »
sur les PDF C&I, remplie sur la copie signée (D-CIQ-11).

Rendu RÉEL des deux gabarits ; la copie signée reçoit ``signature_entreprise``
(forme du contrat ``acceptation_entreprise.json``, CIQ319) échappé par
``echapper_textes_client``. 3 et 4 pages tenues (WeasyPrint).
"""
import copy
import json
from pathlib import Path

from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.builder import echapper_textes_client
from apps.ventes.quote_engine.commercial import render as c_render
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.commercial import sample_data as c_sample
from apps.ventes.quote_engine.industriel import render as i_render
from apps.ventes.quote_engine.industriel import renderer as i_renderer
from apps.ventes.quote_engine.industriel import sample_data as i_sample

SIGNATURE = json.loads(
    (Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'acceptation_entreprise.json').read_text(encoding='utf-8')
)['signature_entreprise']['exemple']

GABARITS = (
    ("commercial", c_sample, c_renderer, c_render, 3, "c3-root"),
    ("industriel", i_sample, i_renderer, i_render, 4, "i3-root"),
)


def _rendu(sample, renderer, render, signature=None):
    data = copy.deepcopy(sample.build())
    if signature is not None:
        data["signature_entreprise"] = dict(signature)
    return render.build_html(renderer._augment(echapper_textes_client(data)))


def _case(html, racine):
    page = html[html.index(f'class="{racine}"'):]
    debut = page.index("pour la société")
    return page[debut:debut + 4000]


class BlocAcceptation(SimpleTestCase):

    def test_non_signe_libelles_et_cachet(self):
        for nom, sample, renderer, render, _p, racine in GABARITS:
            with self.subTest(gabarit=nom):
                case = _case(_rendu(sample, renderer, render), racine)
                for libelle in ("Raison sociale", "Nom et qualité du "
                                "signataire", "ICE", "Date", "Signature",
                                "Cachet de la société"):
                    self.assertIn(libelle, case)

    def test_signe_en_ligne_valeurs_imprimees(self):
        for nom, sample, renderer, render, _p, racine in GABARITS:
            with self.subTest(gabarit=nom):
                case = _case(_rendu(sample, renderer, render, SIGNATURE),
                             racine)
                self.assertIn(f"<b>{SIGNATURE['raison_sociale']}</b>", case)
                self.assertIn(f"<b>{SIGNATURE['signataire_nom']}, "
                              f"{SIGNATURE['signataire_qualite']}</b>", case)
                self.assertIn(f"<b>{SIGNATURE['ice']}</b>", case)
                self.assertIn(f"<b>{SIGNATURE['date']}</b>", case)
                self.assertIn("Cachet de la société", case)

    def test_texte_signe_echappe_une_fois(self):
        sig = dict(SIGNATURE, raison_sociale="A & <B> SARL")
        html = _rendu(c_sample, c_renderer, c_render, sig)
        self.assertIn("<b>A &amp; &lt;B&gt; SARL</b>", html)
        self.assertNotIn("&amp;amp;", html)


@tag("weasyprint")
class BlocAcceptationPages(SimpleTestCase):

    def test_pages_tenues(self):
        try:
            from weasyprint import HTML
        except Exception:  # pragma: no cover - libs natives absentes
            self.skipTest("weasyprint indisponible")
        for nom, sample, renderer, render, pages, _r in GABARITS:
            for signature in (None, SIGNATURE):
                with self.subTest(gabarit=nom, signe=bool(signature)):
                    html = _rendu(sample, renderer, render, signature)
                    self.assertEqual(len(HTML(string=html).render().pages),
                                     pages)

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
                # Date ISO servie, imprimée jj/mm/aaaa (« Le 24/10/2026 »).
                annee, mois, jour = SIGNATURE['date'][:10].split("-")
                self.assertIn(f"<b>{jour}/{mois}/{annee}</b>", case)
                self.assertNotIn(SIGNATURE['date'], case)
                self.assertIn("Cachet de la société", case)

    def test_texte_signe_echappe_une_fois(self):
        sig = dict(SIGNATURE, raison_sociale="A & <B> SARL")
        html = _rendu(c_sample, c_renderer, c_render, sig)
        self.assertIn("<b>A &amp; &lt;B&gt; SARL</b>", html)
        self.assertNotIn("&amp;amp;", html)


class Cpdf4ChoixOption(SimpleTestCase):
    """CPDF4 — deux cases « Sans / Avec batterie » + total TTC servi sur un
    devis à deux options non accepté ; rien sur mono-option ou accepté."""

    @staticmethod
    def _deux_options(sample, **plus):
        data = copy.deepcopy(sample.build())
        data["totaux_all"] = {"ttc": 1750000.0}
        data["option_batterie"] = {"totaux": {"ttc": 2100000.0}, "lignes": []}
        data.update(plus)
        return data

    def _case(self, sample, renderer, render, racine, data):
        html = render.build_html(renderer._augment(
            echapper_textes_client(data)))
        return _case(html, racine)

    def test_deux_options_deux_cases(self):
        for nom, sample, renderer, render, _p, racine in GABARITS:
            with self.subTest(gabarit=nom):
                case = self._case(sample, renderer, render, racine,
                                  self._deux_options(sample))
                self.assertIn("Sans batterie", case)
                self.assertIn("Avec batterie", case)
                self.assertIn("MAD TTC", case)

    def test_mono_option_ou_accepte_aucune_case(self):
        for nom, sample, renderer, render, _p, racine in GABARITS:
            with self.subTest(gabarit=nom):
                mono = copy.deepcopy(sample.build())
                self.assertNotIn("Sans batterie", self._case(
                    sample, renderer, render, racine, mono))
                accepte = self._deux_options(
                    sample, accepte_par_nom="A", date_acceptation="01/01/2026")
                self.assertNotIn("Sans batterie", self._case(
                    sample, renderer, render, racine, accepte))


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

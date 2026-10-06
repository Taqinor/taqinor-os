"""CIQ310 — bande légale du vendeur (RC, ICE, capital) sur la dernière page
des PDF C&I, par UNE fonction partagée (``premium_base.bande_legale``).

Rendu RÉEL des gabarits commercial et industriel (fixtures du moteur), avec
le repli fondateur puis un profil de société cliente (tenant) ; le
résidentiel imprime la MÊME chaîne qu'avant (golden
``split_sd_rendu_html`` inchangé pour lui + comparaison de chaînes ici).
"""
import copy

from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine import premium_base
from apps.ventes.quote_engine.commercial import render as c_render
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.commercial import sample_data as c_sample
from apps.ventes.quote_engine.industriel import render as i_render
from apps.ventes.quote_engine.industriel import renderer as i_renderer
from apps.ventes.quote_engine.industriel import sample_data as i_sample
from apps.ventes.quote_engine.residential import theme

from ._moteur_fixtures import donnees_residentiel, html_residentiel

GABARITS = (
    ("commercial", c_sample, c_renderer, c_render, 3, "c3-root"),
    ("industriel", i_sample, i_renderer, i_render, 4, "i3-root"),
)

TENANT = {"nom": "Soleil Atlas SARL", "rc": "RC 12345",
          "ice": "001122334000055", "email": "contact@soleil-atlas.ma",
          "telephone": "+212 5 22 00 00 00"}


def _rendu(sample, renderer, render, entreprise=None):
    data = copy.deepcopy(sample.build())
    if entreprise is not None:
        data["entreprise"] = dict(entreprise)
    d = renderer._augment(data)
    return d, render.build_html(d)


class BandeLegaleCi(SimpleTestCase):

    def test_repli_fondateur_sur_la_derniere_page(self):
        for nom, sample, renderer, render, _p, racine in GABARITS:
            with self.subTest(gabarit=nom):
                d, html = _rendu(sample, renderer, render)
                derniere = html[html.index(f'class="{racine}"'):]
                bande = premium_base.bande_legale(
                    d, theme.company_identity(d))
                self.assertIn(bande, derniere)
                self.assertIn("RC 691213", derniere)
                self.assertIn("ICE 003799642000067", derniere)
                self.assertIn("au capital de", derniere)

    def test_profil_societe_cliente(self):
        for nom, sample, renderer, render, _p, racine in GABARITS:
            with self.subTest(gabarit=nom):
                _d, html = _rendu(sample, renderer, render, TENANT)
                derniere = html[html.index(f'class="{racine}"'):]
                self.assertIn("<b>Soleil Atlas SARL</b>", derniere)
                self.assertIn("RC RC 12345", derniere)
                self.assertIn("ICE 001122334000055", derniere)
                self.assertNotIn("RC 691213", derniere)

    def test_residentiel_meme_chaine(self):
        for entreprise in (None, TENANT):
            with self.subTest(tenant=bool(entreprise)):
                surcharges = {"entreprise": dict(entreprise)} \
                    if entreprise else {}
                d = donnees_residentiel("deux", **surcharges)
                html = html_residentiel("deux", **surcharges)
                bande = premium_base.bande_legale(
                    d, theme.company_identity(d))
                self.assertIn(f'<div class="p3-legal">{bande} &middot;',
                              html)

    def test_valeurs_tenant_echappees(self):
        bande = premium_base.bande_legale(
            {"entreprise": {"nom": "A & <B>", "rc": "1<2"}}, {})
        self.assertIn("<b>A &amp; &lt;B&gt;</b>", bande)
        self.assertIn("RC 1&lt;2", bande)


@tag("weasyprint")
class BandeLegaleCiPages(SimpleTestCase):

    def test_pages_tenues(self):
        try:
            from weasyprint import HTML
        except Exception:  # pragma: no cover - libs natives absentes
            self.skipTest("weasyprint indisponible")
        for nom, sample, renderer, render, pages, _r in GABARITS:
            for entreprise in (None, TENANT):
                with self.subTest(gabarit=nom, tenant=bool(entreprise)):
                    _d, html = _rendu(sample, renderer, render, entreprise)
                    self.assertEqual(
                        len(HTML(string=html).render().pages), pages)

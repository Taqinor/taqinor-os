"""QJR651 — un seul harnais de rendu industriel / commercial et un seul kwc_str.

``industriel/render.py`` et ``commercial/render.py`` ne différaient que par
leur liste de pages ; les deux ``_kwc_str`` des couvertures étaient
identiques. Ils vivent désormais dans ``quote_engine/premium_base.py``.

Le rendu doit rester OCTET-IDENTIQUE : l'ancien harnais est rejoué ici, à la
lettre (``_ancien_build_html``, copie figée du code d'avant QJR651), et
comparé au nouveau sur les fixtures qx45 (industriel) et qx46 (commercial,
toutes catégories). Empreintes capturées sur le code d'avant QJR651, le
01/10/2026, pour mémoire : industriel 97135593…; commercial (hôtel)
d62a3b51…. Le test compare à l'ancien harnais plutôt qu'à ces empreintes pour
ne pas rougir quand une page (cover/equip/finance/trust) évolue légitimement.

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_premium_base_harnais -v 2
"""
import inspect

from django.test import SimpleTestCase

from apps.ventes.quote_engine import premium_base
from apps.ventes.quote_engine.commercial import categories
from apps.ventes.quote_engine.commercial import cover as c_cover
from apps.ventes.quote_engine.commercial import render as c_render
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.commercial import sample_data as c_sample
from apps.ventes.quote_engine.industriel import cover as i_cover
from apps.ventes.quote_engine.industriel import render as i_render
from apps.ventes.quote_engine.industriel import renderer as i_renderer
from apps.ventes.quote_engine.industriel import sample_data as i_sample


def _ancien_build_html(data, modules_pages):
    """Copie figée de l'ancien ``build_html`` (identique dans les deux
    marchés avant QJR651) — la référence de l'égalité octet pour octet."""
    from apps.ventes.quote_engine import montants
    from apps.ventes.quote_engine.residential import theme

    ident = theme.company_identity(data)
    ctx = {
        "d": data, "C": theme.C, "fmt": theme.fmt,
        "fmt_mad": montants.fmt_centimes,
        "fonts": {"display": theme.FONT_DISPLAY, "serif": theme.FONT_SERIF,
                  "sans": theme.FONT_SANS},
        "logo_dark": theme.logo_dark_b64(),
        "logo_color": theme.logo_color_b64(),
        "ident": ident, "theme": theme,
    }
    pages = [m.build(ctx) for m in modules_pages]
    total = len(pages)

    def _wrap(inner, n):
        foot = (theme.page_footer(data, ident, total_pages=total)
                .replace("{page}", str(n)))
        return f'<div class="page">{inner}{foot}</div>'

    body = "".join(_wrap(inner, n) for n, inner in enumerate(pages, start=1))
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>{theme.base_css()}</style></head>"
            f"<body>{body}</body></html>")


class HarnaisOctetIdentique(SimpleTestCase):

    def test_industriel_qx45(self):
        from apps.ventes.quote_engine.commercial import equip
        from apps.ventes.quote_engine.industriel import finance, trust
        data = i_renderer._augment(i_sample.build())
        attendu = _ancien_build_html(
            i_renderer._augment(i_sample.build()),
            [i_cover, equip, finance, trust])
        self.assertEqual(i_render.build_html(data), attendu)

    def test_commercial_qx46_toutes_categories(self):
        from apps.ventes.quote_engine.commercial import equip, trust
        for categorie in categories.METADATA:
            with self.subTest(categorie=categorie):
                data = c_renderer._augment(c_sample.build(categorie))
                attendu = _ancien_build_html(
                    c_renderer._augment(c_sample.build(categorie)),
                    [c_cover, equip, trust])
                self.assertEqual(c_render.build_html(data), attendu)


class UnSeulKwcStr(SimpleTestCase):

    def test_kwc_str_illisible_ou_absent(self):
        self.assertEqual(premium_base.kwc_str('abc'), '—')
        self.assertEqual(premium_base.kwc_str(None), '—')
        self.assertEqual(premium_base.kwc_str('abc'), premium_base.kwc_str(None))
        self.assertEqual(premium_base.kwc_str(None, defaut='?'), '?')

    def test_kwc_str_a_la_francaise(self):
        self.assertEqual(premium_base.kwc_str(10.65), '10,65')
        self.assertEqual(premium_base.kwc_str('10.00'), '10')
        self.assertEqual(premium_base.kwc_str(7.1), '7,1')

    def test_plus_de_kwc_str_local_dans_les_couvertures(self):
        for module in (i_cover, c_cover):
            with self.subTest(module=module.__name__):
                self.assertNotIn('def _kwc_str', inspect.getsource(module))
                self.assertFalse(hasattr(module, '_kwc_str'))

    def test_les_harnais_de_marche_delegent_au_harnais_commun(self):
        for module in (i_render, c_render):
            with self.subTest(module=module.__name__):
                source = inspect.getsource(module)
                self.assertIn('premium_base', source)
                self.assertNotIn('def _wrap', source)
                self.assertNotIn('def build_ctx', source)

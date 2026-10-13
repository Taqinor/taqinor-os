"""AMOT23 (C-AMOT-021) — le gabarit résidentiel 3 pages imprime l'annexe de
rétractation (CAD122) quand le bon de commande est signé au domicile, par
UNE fonction HTML pure partagée avec le legacy ; le pied « Page n / N » la
compte. Sans le drapeau : 3 pages, aucune annexe.

Rendu réel du gabarit (``render.build_html(renderer._augment(data))``).

Test-du-test : retirer l'appel dans ``residential/render.build_html`` ⇒
``test_annexe_presente_et_comptee`` échoue.
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine import annexe_domicile
from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine.residential import render, renderer
from apps.ventes.tests._quote_engine_common import _residential_sample_data

FORMULAIRE = 'Formulaire détachable de rétractation'


def _html(**extra):
    data = _residential_sample_data()
    data.update(extra)
    return render.build_html(renderer._augment(data))


def _nb_pages(html):
    return html.count('<div class="page">')


class AnnexeDomicileTests(SimpleTestCase):

    def test_annexe_presente_et_comptee(self):
        html = _html(signe_au_domicile=True)
        self.assertIn(FORMULAIRE, html)
        n = _nb_pages(html)
        self.assertEqual(n, _nb_pages(_html()) + 1)
        self.assertIn('/ %d' % n, html)

    def test_sans_drapeau_aucune_annexe(self):
        html = _html()
        self.assertNotIn(FORMULAIRE, html)

    def test_legacy_meme_fonction(self):
        corps = annexe_domicile.corps_annexe_domicile(
            ref='DEV-1', vendeur='SOCIETE',
            couleurs={'navy': '#000', 'texte': '#111', 'muet': '#222',
                      'fond': '#fff', 'filet': '#333'})
        self.assertIn(FORMULAIRE, corps)
        self.assertIs(G._corps_annexe_domicile,
                      annexe_domicile.corps_annexe_domicile)
        self.assertEqual(G.DELAI_RETRACTATION_DOMICILE_JOURS,
                         annexe_domicile.DELAI_RETRACTATION_DOMICILE_JOURS)


# ── AMOT53 (C-AMOT-021, D-AMOT-2 = a) — le une-page signé au domicile ──────
# porte l'annexe de rétractation en 2ᵉ page DÉCLARÉE : la page plein format
# du legacy (``page_annexe_domicile``, corps partagé AMOT23), jamais une copie
# de son HTML ; le pied des deux pages compte « 1 / 2 » et « 2 / 2 ». Sans le
# drapeau : le une-page d'hier (1 page, aucun « / 2 » — goldens inchangés).
# Complète l'assertion « une-page = 1 page » de ``test_quote_engine_formats``
# (cas général) par le seul cas « signé au domicile ».
# Test-du-test : retirer l'appel ``page_annexe_domicile(...)`` dans
# ``build_html_onepage`` ⇒ ``test_onepage_domicile_deux_pages`` échoue.

def _html_onepage(**extra):
    from apps.ventes.tests import _moteur_fixtures as mf
    with G._RENDER_LOCK:
        return G.render_html_for(mf.donnees_legacy(
            'deux', pdf_mode='onepage', **extra))


def _pages_legacy(html):
    return html.count('<div class="page"')


class OnePageAnnexeDomicileTests(SimpleTestCase):

    def test_onepage_domicile_deux_pages(self):
        html = _html_onepage(signe_au_domicile=True)
        self.assertEqual(_pages_legacy(html), 2)
        derniere = html.split('<div class="page"')[-1]
        self.assertIn(FORMULAIRE, derniere)
        self.assertIn('1&nbsp;/&nbsp;2', html.split('<div class="page"')[1])
        self.assertIn('2&nbsp;/&nbsp;2', derniere)

    def test_onepage_sans_drapeau_une_page(self):
        html = _html_onepage(signe_au_domicile=False)
        self.assertEqual(_pages_legacy(html), 1)
        self.assertNotIn(FORMULAIRE, html)
        self.assertNotIn('&nbsp;/&nbsp;2', html)

    def test_onepage_meme_page_que_le_plein_format(self):
        html = _html_onepage(signe_au_domicile=True)
        with G._RENDER_LOCK:
            from apps.ventes.tests import _moteur_fixtures as mf
            G.apply_quote_data(mf.donnees_legacy(
                'deux', pdf_mode='onepage', signe_au_domicile=True))
            corps = G._corps_annexe_domicile(
                ref=G.REF, vendeur=G.ENT_NOM_MARQUE,
                couleurs={'navy': G.CN, 'texte': G.CG7, 'muet': G.CG4,
                          'fond': G.CG1, 'filet': G.CG2},
                langue=G.LANGUE_SORTIE)
        self.assertIn(corps, html)

    def test_onepage_domicile_anglais(self):
        from apps.ventes.quote_engine import i18n_labels
        html = _html_onepage(signe_au_domicile=True, langue_sortie='en',
                             libelles_document=i18n_labels.libelles('en'))
        self.assertEqual(_pages_legacy(html), 2)
        self.assertIn('Detachable withdrawal form', html)
        self.assertNotIn(FORMULAIRE, html)

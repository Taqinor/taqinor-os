"""AMOT18 (C-AMOT-016, volet résidentiel) — le gabarit résidentiel n'imprime
plus aucun littéral d'identité TAQINOR (e-mail, téléphone, site, liens
``taqinor.ma/…``) pour une société IDENTIFIÉE : un champ vide est omis ; la
société sans aucun profil garde le repli fondateur (byte-identique).

Rendu réel du gabarit (``render.build_html(renderer._augment(data))``) sur
les données d'exemple du résidentiel.

Test-du-test : remettre le repli champ par champ de ``company_identity`` ⇒
``test_societe_identifiee_aucun_taqinor`` échoue.
"""
import re

from django.test import SimpleTestCase

from apps.ventes.quote_engine.residential import render, renderer, theme
from apps.ventes.tests._quote_engine_common import _residential_sample_data


def _html(entreprise, **extra):
    data = _residential_sample_data()
    data['entreprise'] = entreprise
    data.pop('site_url', None)
    data['links'] = {}
    data.update(extra)
    return render.build_html(renderer._augment(data))


def _texte(html):
    html = re.sub(r'<style>.*?</style>', ' ', html, flags=re.S)
    html = re.sub(r'data:[^"\')]+', ' ', html)
    return html


class IdentiteResidentielTests(SimpleTestCase):

    def test_societe_identifiee_aucun_taqinor(self):
        html = _html({'nom': 'PROBE N1 SARL', 'ice': '003333333000033'})
        texte = _texte(html).lower()
        # Logo, photo de couverture et garantie de pose : hors périmètre
        # (décision white-label) — on vise les littéraux de CONTACT et de
        # LIEN, ceux qui renvoient le client vers TAQINOR.
        for interdit in ('taqinor.ma', 'contact@taqinor', '+212 6 61 85 04 10'):
            self.assertNotIn(interdit, texte)
        self.assertIn('probe n1 sarl', texte)

    def test_signer_reel_conserve(self):
        lien = 'https://probe.example/proposition/client/tok-123'
        html = _html({'nom': 'PROBE N1 SARL'}, links={'signer': lien})
        self.assertIn('tok-123', html)
        self.assertNotIn('taqinor.ma/signer', html.lower())

    def test_sans_profil_repli_fondateur(self):
        ident = theme.company_identity({'entreprise': {}})
        self.assertEqual(ident['email'], 'contact@taqinor.com')
        self.assertEqual(ident['site'], 'taqinor.ma')

    def test_identite_champs_vides_omis(self):
        ident = theme.company_identity(
            {'entreprise': {'nom': 'PROBE N1 SARL'}})
        self.assertEqual(ident['email'], '')
        self.assertEqual(ident['phone'], '')
        self.assertEqual(ident['site'], '')
        pied = theme.page_footer({'ref': 'DEV-1'}, ident)
        self.assertNotIn('&nbsp;·&nbsp;  &nbsp;·&nbsp;', pied)
        self.assertNotIn('taqinor', pied.lower())

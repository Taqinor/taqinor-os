"""AMOT26 (C-AMOT-026) — tout montant client ENTIER du moteur passe par UN
formateur HALF_UP (``montants.fmt_dirhams``) ; la lettre de relance imprime
au CENTIME le montant réclamé (``fmt_centimes_mad``).

Rejoue VB : 52 650,50 → ``theme.fmt '52 650'``, ``_fr_mad '52 650'`` (arrondi
au pair de Python) contre l'écran ``Intl`` « 52 651 » ; lettre de relance à
1 234,50 → « Montant restant dû 1 234 ».

Test-du-test : remettre ``round(float(n))`` dans ``theme.fmt`` ⇒ rouge.
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine import montants
from apps.ventes.quote_engine.pricing import _fr_mad
from apps.ventes.quote_engine.residential import theme

NNBSP = ' '


def _chiffres(txt):
    return ''.join(c for c in txt if c.isdigit())


class ArrondiDirhamTests(SimpleTestCase):
    def setUp(self):
        montants.poser_regles_origine(False)
        self.addCleanup(montants.poser_regles_origine, False)

    def test_trois_formateurs_half_up(self):
        for x, attendu in ((52650.5, '52651'), (52651.5, '52652'),
                           (1234.5, '1235'), (52650.49, '52650')):
            with self.subTest(x=x):
                self.assertEqual(_chiffres(theme.fmt(x)), attendu)
                self.assertEqual(_chiffres(G.fmt(x)), attendu)
                self.assertEqual(_chiffres(_fr_mad(x)), attendu)

    def test_separateurs_conserves(self):
        self.assertEqual(theme.fmt(52650.5), f'52{NNBSP}651')
        self.assertEqual(G.fmt(52650.5), f'52{NNBSP}651 MAD')
        self.assertEqual(_fr_mad(1234567), f'1{NNBSP}234{NNBSP}567')

    def test_montants_ronds_inchanges(self):
        self.assertEqual(theme.fmt(23000), f'23{NNBSP}000')
        self.assertEqual(theme.fmt('abc'), 'abc')

    def test_regles_d_origine_arrondi_d_hier(self):
        montants.poser_regles_origine(True)
        self.assertEqual(_chiffres(theme.fmt(52650.5)), '52650')

    def test_lettre_relance_au_centime(self):
        from apps.ventes.quote_engine import extra_docs
        resume = {'reference': 'FAC-1', 'date_emission': '01/08/2026',
                  'date_echeance': '01/09/2026', 'total_ttc': 2000,
                  'montant_du': 1234.5, 'jours_retard': 10}
        client = {'nom': 'Client', 'prenom': '', 'email': '',
                  'telephone': '', 'adresse': ''}
        html = extra_docs.build_lettre_relance_html({}, client, resume, 1)
        self.assertIn(f'1{NNBSP}234,50', html.replace(' ', NNBSP))

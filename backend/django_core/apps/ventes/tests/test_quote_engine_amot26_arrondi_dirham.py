"""AMOT26 (C-AMOT-026) — tout montant client ENTIER du moteur s'arrondit par
UN formateur HALF_UP (``montants.fmt_dirhams``) — le dirham de l'écran — et
la lettre de relance imprime au CENTIME le montant qu'elle réclame.

Formateurs réels ; lettre rendue en HTML réel (``build_lettre_relance_html``).
Test-du-test : remettre
``round(float(n))`` dans ``theme.fmt`` ⇒ ``test_formateurs_half_up`` échoue
(52 650,5 → « 52 650 »).
"""

from django.test import SimpleTestCase

from apps.ventes.quote_engine import extra_docs
from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine.montants import fmt_dirhams
from apps.ventes.quote_engine.pricing import _fr_mad
from apps.ventes.quote_engine.residential import theme

_NNBSP = ' '


class ArrondiDirhamTests(SimpleTestCase):
    def test_formateurs_half_up(self):
        cas = {52650.5: f'52{_NNBSP}651', 52651.5: f'52{_NNBSP}652',
               1234.5: f'1{_NNBSP}235', 52650: f'52{_NNBSP}650'}
        for x, attendu in cas.items():
            with self.subTest(x=x):
                self.assertEqual(fmt_dirhams(x), attendu)
                self.assertEqual(theme.fmt(x), attendu)
                self.assertEqual(_fr_mad(x), attendu)
                self.assertEqual(G.fmt(x), attendu + ' MAD')

    def test_valeur_illisible(self):
        self.assertEqual(theme.fmt('abc'), 'abc')
        self.assertEqual(G.fmt(None), 'None')

    def test_lettre_relance_au_centime(self):
        """La ligne « Montant restant dû » de la lettre RENDUE imprime le
        montant réclamé au centime : 1 234,50 MAD, jamais « 1 234 »."""
        resume = {'reference': 'FAC-AMOT26-1', 'date_emission': '01/09/2026',
                  'date_echeance': '01/10/2026', 'total_ttc': 5000,
                  'montant_du': 1234.5, 'jours_retard': 8}
        html = extra_docs.build_lettre_relance_html(
            {'entreprise_nom': 'Société test'},
            {'nom': 'Alaoui', 'prenom': 'Karim'}, resume, 3)
        self.assertIn('1 234,50 MAD', html)
        self.assertNotIn(f'1{_NNBSP}234 MAD', html)

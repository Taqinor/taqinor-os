"""AMOT60 (C-AMOT-036) — la lettre de relance / mise en demeure réclame
l'EXIGIBLE (``montant_exigible`` : retenue de garantie non libérée exclue),
comme l'e-mail, le rappel planifié et le domaine de recouvrement ; une facture
payée, annulée ou sans exigible → 409 « Aucune somme exigible », sans PDF.

Rejoue VB (lettre « Montant restant dû 33 024 » contre un exigible e-mail de
32 524 ; facture payée → ``HTTP 200 application/pdf``).

Test-du-test : remettre ``"montant_du": facture.montant_du`` ⇒
``test_resume_reclame_l_exigible`` échoue.
"""
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.ventes.quote_engine import extra_docs as X


def _facture(statut='emise', du='33024', retenue='500'):
    du = Decimal(du)
    exigible = max(du - Decimal(retenue), Decimal('0'))
    return SimpleNamespace(
        reference='FAC-1', statut=statut, date_emission=None,
        date_echeance=None, total_ttc=Decimal('40000'), montant_du=du,
        montant_exigible=exigible, jours_retard=12)


class LettreRelanceExigibleTests(SimpleTestCase):
    def test_resume_reclame_l_exigible(self):
        resume = X._facture_resume(_facture())
        self.assertEqual(resume['montant_du'], Decimal('32524'))

    def test_lettre_imprime_l_exigible_au_centime(self):
        client = {'nom': 'Client', 'prenom': '', 'email': '',
                  'telephone': '', 'adresse': ''}
        html = X.build_lettre_relance_html(
            {}, client, X._facture_resume(_facture()), 3)
        self.assertIn('32 524,00', html)
        self.assertNotIn('33 024', html)

    def test_parite_avec_recouvrement(self):
        from apps.ventes.recouvrement import montant_exigible
        f = _facture()
        self.assertEqual(X.montant_reclame(f), montant_exigible(f))

    def test_refus_payee_annulee_sans_exigible(self):
        self.assertEqual(X.motif_refus_lettre_relance(_facture('payee')),
                         X.MSG_AUCUNE_SOMME_EXIGIBLE)
        self.assertEqual(X.motif_refus_lettre_relance(_facture('annulee')),
                         X.MSG_AUCUNE_SOMME_EXIGIBLE)
        self.assertEqual(
            X.motif_refus_lettre_relance(_facture(du='500', retenue='500')),
            X.MSG_AUCUNE_SOMME_EXIGIBLE)
        self.assertIsNone(X.motif_refus_lettre_relance(_facture()))

    def test_vue_refuse_en_409(self):
        """La vue consulte le motif AVANT tout rendu (aucun PDF produit)."""
        from pathlib import Path

        from apps.ventes import extra_docs_views as V
        src = Path(V.__file__).read_text(encoding='utf-8')
        self.assertLess(src.index('motif_refus_lettre_relance(facture)'),
                        src.index('render_lettre_relance_pdf(facture, niveau)'))
        self.assertIn('HTTP_409_CONFLICT', src)

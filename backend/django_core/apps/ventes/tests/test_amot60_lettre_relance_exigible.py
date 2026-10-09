"""AMOT60 (C-AMOT-036) — la lettre de relance / mise en demeure réclame
l'EXIGIBLE (``recouvrement.montant_exigible`` : reste dû − retenue de
garantie non libérée), comme l'e-mail et le rappel planifié ; une facture
payée, annulée ou sans exigible → 409 « Aucune somme exigible », aucun PDF.

Facture ORM réelle, propriétés réelles, endpoint réel. Test-du-test : remettre
``"montant_du": facture.montant_du`` dans ``_facture_resume`` ⇒
``test_montant_de_la_lettre_est_l_exigible`` échoue.
"""
from decimal import Decimal

from apps.ventes.models import Facture
from apps.ventes.quote_engine.extra_docs import _facture_resume
from apps.ventes.recouvrement import montant_exigible
from apps.ventes.tests.test_extra_docs import _Base


class LettreRelanceExigibleTests(_Base):
    def _url(self, facture, niveau=3):
        return (f'/api/django/ventes/factures/{facture.id}/'
                f'lettre-relance-premium/?niveau={niveau}')

    def test_montant_de_la_lettre_est_l_exigible(self):
        facture = self._facture()
        Facture.objects.filter(pk=facture.pk).update(
            retenue_garantie_mad=Decimal('500'))
        facture = Facture.objects.get(pk=facture.pk)
        self.assertGreater(facture.montant_du, facture.montant_exigible)
        resume = _facture_resume(facture)
        self.assertEqual(resume['montant_du'], facture.montant_exigible)
        # Parité lettre ↔ e-mail ↔ rappel planifié : LA même fonction.
        self.assertEqual(resume['montant_du'], montant_exigible(facture))
        resp = self.api.get(self._url(facture))
        self.assertEqual(resp.status_code, 200)

    def test_facture_payee_ou_annulee_409(self):
        for statut in (Facture.Statut.PAYEE, Facture.Statut.ANNULEE):
            with self.subTest(statut=statut):
                facture = self._facture()
                Facture.objects.filter(pk=facture.pk).update(statut=statut)
                resp = self.api.get(self._url(facture))
                self.assertEqual(resp.status_code, 409)
                self.assertIn('Aucune somme exigible', resp.data['detail'])

    def test_exigible_nul_409(self):
        facture = self._facture()
        Facture.objects.filter(pk=facture.pk).update(
            retenue_garantie_mad=facture.montant_du + Decimal('1'))
        facture = Facture.objects.get(pk=facture.pk)
        self.assertEqual(facture.montant_exigible, 0)
        self.assertEqual(self.api.get(self._url(facture)).status_code, 409)

"""PDF facture client — bloc « Déjà payé / Reste à payer » (fondateur,
05/10/2026).

Après le Total TTC : une ligne par règlement (date jj/mm/aaaa, mode,
référence, montant), « Total déjà payé », puis « Reste à payer »
(= ``Facture.montant_du``) ou « Facture soldée ». Rien n'est imprimé quand la
facture n'a aucun règlement. On teste le constructeur de données et le HTML
rendu (jamais le binaire WeasyPrint).
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.ventes.models import Facture, LigneFacture, Paiement
from apps.ventes.utils.pdf import (
    _company_context, _render_html, empreinte_donnees_facture_pdf,
    reglements_facture_pdf,
)
from authentication.models import Company

_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class TestPdfFactureDejaPaye(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='DPY Co', slug=f'dpy-{_nxt()}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cliente', telephone='+212600000701')
        # 125 000 HT × 20 % = 150 000 TTC.
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-DPY-{_nxt()}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, designation='Kit PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('125000'),
            taux_tva=Decimal('20.00'))

    def _payer(self, montant, jour, mode=Paiement.Mode.VIREMENT,
               reference='', statut=Paiement.Statut.ENCAISSE):
        return Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal(montant), date_paiement=jour, mode=mode,
            reference=reference, statut=statut)

    def _rendu(self):
        ctx = _company_context(company=self.company)
        ctx['facture'] = self.facture
        ctx['reglements'] = reglements_facture_pdf(self.facture)
        return _render_html('facture.html', ctx)

    def test_aucun_reglement_rien_d_imprime(self):
        self.assertIsNone(reglements_facture_pdf(self.facture))
        html = self._rendu()
        self.assertNotIn('Déjà payé', html)
        self.assertNotIn('Reste à payer', html)

    def test_paiements_et_reste_a_payer(self):
        self._payer('45000', date(2026, 8, 12), reference='VIR-0812')
        self._payer('45000', date(2026, 9, 2), Paiement.Mode.CHEQUE,
                    'CHQ-55120')
        self._payer('45000', date(2026, 9, 28))
        # Un chèque rejeté ne compte JAMAIS (YLEDG5).
        self._payer('9999', date(2026, 9, 29), Paiement.Mode.CHEQUE,
                    'CHQ-REJ', statut=Paiement.Statut.REJETE)

        bloc = reglements_facture_pdf(self.facture)
        self.assertEqual(len(bloc['lignes']), 3)
        self.assertEqual(bloc['lignes'][0]['date'], '12/08/2026')
        self.assertEqual(bloc['lignes'][1]['mode'], 'Chèque')
        self.assertEqual(bloc['total_deja_paye'], Decimal('135000'))
        self.assertEqual(bloc['reste_a_payer'], Decimal('15000.00'))
        self.assertFalse(bloc['soldee'])

        html = self._rendu()
        self.assertIn('Déjà payé', html)
        self.assertIn('12/08/2026 · Virement · VIR-0812', html)
        self.assertIn('02/09/2026 · Chèque · CHQ-55120', html)
        self.assertIn('Total déjà payé', html)
        self.assertIn('135000.00 MAD', html)
        self.assertIn('Reste à payer', html)
        self.assertIn('15000.00 MAD', html)
        self.assertNotIn('CHQ-REJ', html)
        self.assertNotIn('Facture soldée', html)

    def test_facture_soldee(self):
        self._payer('150000', date(2026, 9, 1))
        html = self._rendu()
        self.assertIn('Facture soldée', html)
        self.assertNotIn('Reste à payer', html)

    def test_un_paiement_change_l_empreinte_du_pdf(self):
        """Le PDF imprime le reste à payer : un encaissement doit forcer le
        re-rendu (PVFRESH), sinon le fichier servi serait périmé."""
        avant = empreinte_donnees_facture_pdf(self.facture)
        self._payer('1000', date(2026, 9, 1))
        self.assertNotEqual(empreinte_donnees_facture_pdf(self.facture), avant)

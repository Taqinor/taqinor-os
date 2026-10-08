"""ATOT22 (C-ATOT-004) — l'avoir et le complément de révision sont calculés
PAR TAUX, à partir de l'écart réel des bases par taux entre la version
facturée (V1) et la V2 : la TVA de l'avoir est celle de l'écart, jamais un
« taux mélangé » (``blended_tva_pct``).

Rejoue la sonde V1 TFAC-4, branche révision : V1 40 000 HT à 10 % + 60 000 HT
à 20 % entièrement facturée, V2 où la ligne à 10 % passe à 30 000 HT,
acceptée ⇒ avant : avoir à 16,67 %, TVA 1 571,70 ; attendu : HT 10 000,00,
TVA 1 000,00 à 10 %, TTC 11 000,00.

Test-du-test : remettre ``blended_tva_pct`` comme taux du document dans
``revision.rattacher_aval_financier_revision`` ⇒
``test_avoir_revision_tva_de_l_ecart`` échoue. Source réelle, aucun mock de
calcul (seuls l'e-mail et le stockage du PDF signé sont neutralisés, comme
dans ``test_revision_aval_financier``).
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from apps.crm.models import Lead
from apps.facturation.models import Avoir, Facture
from apps.ventes.domain.cycle_vie import accept_devis
from apps.ventes.domain.revision import reviser_devis
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)
from apps.ventes.utils.echeancier import creer_facture_tranche
from apps.ventes.utils.references import create_with_reference

A10 = 'Équipement à 10'
A20 = 'Installation à 20'
LIGNES = [(A10, '1', '40000', '10'), (A20, '1', '60000', '20')]


def _paniers(document):
    return [(Decimal(str(b['taux'])), Decimal(str(b['base_ht'])),
             Decimal(str(b['montant']))) for b in document.tva_par_taux]


@mock.patch('apps.ventes.domain.cycle_vie._send_acceptance_emails')
@mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf')
class RevisionParTauxTests(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.v1 = make_devis(self.company, self.user, self.client_obj,
                             LIGNES, reference='DEV-ATOT22-0001')
        lead = Lead.objects.create(company=self.company, nom='Lead ATOT22')
        Devis.objects.filter(pk=self.v1.pk).update(
            statut=Devis.Statut.ENVOYE, lead=lead)
        self.v1.refresh_from_db()

    def _accepter(self, devis):
        return accept_devis(devis=devis, user=self.user, nom='Client ATOT22',
                            date_acceptation=date.today(),
                            option='sans_batterie')

    def _facturer_tout(self, devis):
        while True:
            try:
                creer_facture_tranche(Devis.objects.get(pk=devis.pk),
                                      self.user, self.company,
                                      create_with_reference)
            except ValueError:
                break
        total = sum((Decimal(str(f.total_ttc)) for f in Facture.objects
                     .filter(devis=devis)
                     .exclude(statut=Facture.Statut.ANNULEE)),
                    Decimal('0'))
        self.assertEqual(total, Decimal('116000.00'))

    def _v2(self, prix):
        v2 = reviser_devis(self.v1, user=self.user)
        for designation, pu in prix.items():
            LigneDevis.objects.filter(
                devis=v2, designation=designation).update(
                    prix_unitaire=Decimal(pu))
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ENVOYE)
        v2.refresh_from_db()
        return self._accepter(v2)

    def test_avoir_revision_tva_de_l_ecart(self, *_):
        self.v1 = self._accepter(self.v1)
        self._facturer_tout(self.v1)
        self._v2({A10: '30000'})
        avoir = Avoir.objects.get(company=self.company)
        # CLAUSE PERSISTANCE — relu en base.
        avoir.refresh_from_db()
        self.assertEqual(avoir.montant_ht, Decimal('10000.00'))
        self.assertEqual(avoir.montant_tva, Decimal('1000.00'))
        self.assertEqual(avoir.montant_ttc, Decimal('11000.00'))
        self.assertEqual(avoir.taux_tva, Decimal('10'))
        self.assertEqual(
            [(t, m) for t, _b, m in _paniers(avoir)],
            [(Decimal('10'), Decimal('1000.00'))])

    def test_complement_revision_ventile(self, *_):
        self.v1 = self._accepter(self.v1)
        self._facturer_tout(self.v1)
        v2 = self._v2({A10: '50000', A20: '70000'})
        complement = Facture.objects.get(
            devis=v2, libelle__startswith='Complément révision')
        complement.refresh_from_db()
        self.assertEqual(complement.statut, Facture.Statut.BROUILLON)
        self.assertEqual(complement.montant_ttc, Decimal('23000.00'))
        self.assertEqual(complement.montant_ht, Decimal('20000.00'))
        self.assertEqual(complement.montant_tva, Decimal('3000.00'))
        self.assertEqual(_paniers(complement), [
            (Decimal('10'), Decimal('10000.00'), Decimal('1000.00')),
            (Decimal('20'), Decimal('10000.00'), Decimal('2000.00')),
        ])

    def test_complement_mono_taux(self, *_):
        self.v1 = self._accepter(self.v1)
        self._facturer_tout(self.v1)
        v2 = self._v2({A20: '70000'})
        complement = Facture.objects.get(
            devis=v2, libelle__startswith='Complément révision')
        self.assertEqual(complement.montant_ttc, Decimal('12000.00'))
        self.assertEqual(complement.montant_tva, Decimal('2000.00'))
        self.assertEqual(complement.taux_tva, Decimal('20'))

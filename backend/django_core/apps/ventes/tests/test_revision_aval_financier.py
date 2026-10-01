"""QJR560 / D-QJR5-11 — V2 d'un devis signé acceptée : BC et factures de la
V1 restent valables et passent à la V2, seul l'écart est régularisé (au
centime), commission apporteur non payée recalculée sur la V2.

ROUGE AVANT : accepter la V2 laissait le BC et la facture d'acompte sur la V1
(deux chaînes pour une seule vente), et la commission À_PAYER restait celle de
l'option de la V1.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_revision_aval_financier"
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from apps.crm.models import Apporteur, DealEnregistre, Lead
from apps.facturation.models import Avoir, Facture
from apps.ventes.domain.cycle_vie import (
    accept_devis, rattacher_aval_financier_revision, reviser_devis)
from apps.ventes.models import BonCommande, Devis, LigneDevis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)
from apps.ventes.utils.echeancier import creer_facture_tranche
from apps.ventes.utils.options import option_totaux
from apps.ventes.utils.references import create_with_reference

LIGNES = [('Panneau 550W', '10', '1000'), ('Installation', '1', '5000')]


def _ttc(devis):
    return Decimal(str(option_totaux(devis)['ttc']))


@mock.patch('apps.ventes.domain.cycle_vie._send_acceptance_emails')
@mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf')
class AvalFinancierRevision(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.lead = Lead.objects.create(company=self.company, nom='Lead 560')
        self.v1 = make_devis(self.company, self.user, self.client_obj,
                             LIGNES, reference='DEV-QJR560-0001')
        Devis.objects.filter(pk=self.v1.pk).update(
            statut=Devis.Statut.ENVOYE, lead=self.lead)
        self.v1.refresh_from_db()

    def _accepter(self, devis):
        return accept_devis(devis=devis, user=self.user, nom='Client 560',
                            date_acceptation=date.today(),
                            option='sans_batterie')

    def _reviser_prix(self, pu):
        v2 = reviser_devis(self.v1, user=self.user)
        ligne = v2.lignes.get(designation='Installation')
        LigneDevis.objects.filter(pk=ligne.pk).update(
            prix_unitaire=Decimal(pu))
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ENVOYE)
        v2.refresh_from_db()
        return v2

    def _bc(self, devis):
        return BonCommande.objects.create(
            company=self.company, reference='BC-QJR560-1', devis=devis,
            client=devis.client, statut=BonCommande.Statut.EN_ATTENTE)

    def _tranche(self, devis):
        return creer_facture_tranche(devis, self.user, self.company,
                                     create_with_reference)

    def test_acompte_et_bc_passent_a_la_v2_ecart_porte_par_l_echeancier(
            self, *_):
        self.v1 = self._accepter(self.v1)
        bc = self._bc(self.v1)
        acompte = self._tranche(self.v1)
        v2 = self._reviser_prix('7000')
        v2 = self._accepter(v2)

        bcs = BonCommande.objects.filter(
            company=self.company).exclude(statut=BonCommande.Statut.ANNULE)
        self.assertEqual(bcs.count(), 1)
        bc.refresh_from_db()
        self.assertEqual(bc.devis_id, v2.pk)
        acompte.refresh_from_db()
        self.assertEqual(acompte.devis_id, v2.pk)
        # Écart régularisé au centime : la suite de l'échéancier de la V2
        # solde EXACTEMENT le total de la V2.
        while True:
            try:
                self._tranche(Devis.objects.get(pk=v2.pk))
            except ValueError:
                break
        facture = sum(
            (Decimal(str(f.total_ttc)) for f in Facture.objects.filter(
                devis=v2).exclude(statut=Facture.Statut.ANNULEE)),
            Decimal('0'))
        self.assertEqual(facture, _ttc(v2))

    def test_vente_entierement_facturee_hausse_facture_complementaire(
            self, *_):
        self.v1 = self._accepter(self.v1)
        while True:
            try:
                self._tranche(Devis.objects.get(pk=self.v1.pk))
            except ValueError:
                break
        v2 = self._reviser_prix('7000')
        v2 = self._accepter(v2)
        ecart = _ttc(v2) - _ttc(self.v1)
        self.assertGreater(ecart, 0)
        complement = Facture.objects.get(
            devis=v2, libelle__startswith='Complément révision')
        self.assertEqual(complement.statut, Facture.Statut.BROUILLON)
        self.assertEqual(Decimal(str(complement.total_ttc)), ecart)

    def test_vente_entierement_facturee_baisse_avoir_au_centime(self, *_):
        self.v1 = self._accepter(self.v1)
        while True:
            try:
                self._tranche(Devis.objects.get(pk=self.v1.pk))
            except ValueError:
                break
        v2 = self._reviser_prix('3000')
        v2 = self._accepter(v2)
        ecart = _ttc(self.v1) - _ttc(v2)
        avoir = Avoir.objects.get(company=self.company)
        self.assertEqual(Decimal(str(avoir.total_ttc)), ecart)
        self.assertEqual(avoir.facture.devis_id, v2.pk)

    def test_sans_predecesseur_rien(self, *_):
        self.assertIsNone(
            rattacher_aval_financier_revision(self.v1, user=self.user))

    def test_commission_a_payer_recalculee_sur_la_v2(self, *_):
        apporteur = Apporteur.objects.create(
            company=self.company, nom='Apporteur 560',
            taux_commission_pct=Decimal('5.00'))
        deal = DealEnregistre.objects.create(
            company=self.company, apporteur=apporteur, lead=self.lead,
            statut=DealEnregistre.Statut.APPROUVE)
        self.v1 = self._accepter(self.v1)
        deal.refresh_from_db()
        self.assertEqual(deal.statut, DealEnregistre.Statut.A_PAYER)
        v2 = self._reviser_prix('7000')
        v2 = self._accepter(v2)
        deal.refresh_from_db()
        ht_v2 = Decimal(str(option_totaux(v2)['ht']))
        self.assertEqual(deal.montant_commission_du,
                         (ht_v2 * Decimal('5.00') / 100).quantize(
                             Decimal('0.01')))

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
from apps.ventes.domain.cycle_vie import accept_devis
from apps.ventes.domain.revision import (
    rattacher_aval_financier_revision, reviser_devis)
from apps.ventes.models import BonCommande, Devis, LigneDevis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)
from apps.ventes.utils.echeancier import creer_facture_tranche
from apps.ventes.utils.options import option_totaux
from apps.ventes.utils.references import create_with_reference
from core.events import devis_accepted

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

    # ── VNT51 — ``devis_accepted(avenant_de=…)`` ─────────────────────────
    def _avenants_publies(self, devis):
        recus = []

        def _ecoute(sender, **kwargs):
            recus.append(kwargs.get('avenant_de', 'absent'))

        devis_accepted.connect(_ecoute, weak=False)
        try:
            self._accepter(devis)
        finally:
            devis_accepted.disconnect(_ecoute)
        return recus

    def test_vnt51_v2_d_un_accepte_publie_avenant_de_v1(self, *_):
        self.assertEqual(self._avenants_publies(self.v1), [None])
        v2 = self._reviser_prix('7000')
        self.assertEqual(self._avenants_publies(v2), [self.v1.pk])

    def test_vnt51_v2_d_un_refuse_n_est_pas_un_avenant(self, *_):
        Devis.objects.filter(pk=self.v1.pk).update(
            statut=Devis.Statut.REFUSE)
        self.v1.refresh_from_db()
        v2 = self._reviser_prix('7000')
        self.assertEqual(self._avenants_publies(v2), [None])


# ── VNT58 — l'aperçu « Prix négocié » (lecture pure) ─────────────────────────

#: Panier 367 (V1 réelle 54 500) : 9 600 HT @10 % + 36 643,50 HT @20 %.
LIGNES_367 = [('Panneaux 10 %', '1', '9600.00', '10'),
              ('Installation 20 %', '1', '36643.50', '20')]


@mock.patch('apps.ventes.domain.cycle_vie._send_acceptance_emails')
@mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf')
class PrixNegocieApercu(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.v1 = make_devis(self.company, self.user, self.client_obj,
                             LIGNES_367, reference='DEV-VNT58-0010')
        Devis.objects.filter(pk=self.v1.pk).update(
            statut=Devis.Statut.ENVOYE)

    def _vente_avec_acompte_paye_et_brouillon(self):
        from apps.facturation.models import Paiement
        from apps.ventes.domain.facturation_vente import (
            creer_brouillon_tranche, facturer_vente)
        from apps.ventes.vente_facturation import plan_facturation
        v1 = accept_devis(devis=Devis.objects.get(pk=self.v1.pk),
                          user=self.user, nom='Client 367',
                          date_acceptation=date.today(),
                          option='sans_batterie')
        self.assertEqual(_ttc(v1), Decimal('54500.00'))
        # VNT62 — l'acceptation a posé le brouillon d'acompte : on l'émet.
        acompte, _p = facturer_vente(v1, nature='acompte', user=self.user,
                                     emettre=True)
        Paiement.objects.create(
            company=self.company, facture=acompte,
            montant=acompte.total_ttc, date_paiement=date.today())
        brouillon = creer_brouillon_tranche(
            v1, plan_facturation(v1)['prochaine'], self.user)
        return Devis.objects.get(pk=v1.pk), acompte, brouillon

    def _apercu(self, devis, **saisie):
        from apps.ventes.domain.negociation import apercu_prix_negocie
        return apercu_prix_negocie(devis, user=self.user, **saisie)

    def test_apercu_49000_remise_dix_effets_lus_sur_la_vente(self, *_):
        v1, acompte, brouillon = self._vente_avec_acompte_paye_et_brouillon()
        nb_devis = Devis.objects.count()
        a = self._apercu(v1, prix_ttc='49000')
        self.assertEqual(a['remise_pct'], '10.00')
        self.assertEqual(a['total_ttc'], '49000.00')
        self.assertEqual(a['devis_v2'], {'id': None, 'reference': None,
                                         'version': 2})
        self.assertEqual(a['factures_annulees'],
                         [{'reference': brouillon.reference}])
        self.assertEqual([f['reference'] for f in a['factures_reprises']],
                         [acompte.reference])
        self.assertEqual(a['ecart_ttc'], '-5500.00')
        self.assertEqual(
            Decimal(a['reste_a_facturer']),
            Decimal('49000.00') - Decimal(str(acompte.total_ttc)))
        self.assertEqual(a['regularisation'],
                         {'type': 'aucune', 'montant': '0.00'})
        # Rien n'est écrit.
        self.assertEqual(Devis.objects.count(), nb_devis)
        v1.refresh_from_db()
        self.assertEqual(v1.remise_globale, Decimal('0'))
        brouillon.refresh_from_db()
        self.assertEqual(brouillon.statut, Facture.Statut.BROUILLON)

    def test_apercu_refus_de_saisie(self, *_):
        from apps.ventes.domain.negociation import PrixNegocieRefuse
        v1, _a, _b = self._vente_avec_acompte_paye_et_brouillon()
        for saisie, code in (({'prix_ttc': '48950'}, 'prix_non_rond'),
                             ({'prix_ttc': '60000'}, 'prix_superieur'),
                             ({'prix_ttc': '54500'}, 'prix_identique'),
                             ({}, 'saisie_vide'),
                             ({'prix_ttc': '49000', 'remise_pct': '10'},
                              'saisie_double')):
            with self.subTest(code=code):
                with self.assertRaises(PrixNegocieRefuse) as ctx:
                    self._apercu(v1, **saisie)
                self.assertEqual(ctx.exception.code, code)
                self.assertEqual(ctx.exception.statut_http, 400)

    # ── VNT59 — appliquer : V2 créée ET acceptée en un geste ───────────────

    def _appliquer(self, devis, **saisie):
        from apps.ventes.domain.negociation import appliquer_prix_negocie
        return appliquer_prix_negocie(devis, user=self.user, **saisie)

    def test_appliquer_49000_v2_acceptee_sans_signature_ni_mail(
            self, store_pdf, emails):
        from django.core import mail
        from django.db import transaction
        from apps.ventes.models import DevisSignature
        from apps.ventes.selectors import devis_signes_en_vigueur
        v1, acompte, brouillon = self._vente_avec_acompte_paye_et_brouillon()
        store_pdf.reset_mock()
        emails.reset_mock()
        mail.outbox = []
        with transaction.atomic():
            r = self._appliquer(v1, prix_ttc='49000')
        v2 = Devis.objects.get(pk=r['devis_v2']['id'])
        self.assertEqual(v2.statut, Devis.Statut.ACCEPTE)
        self.assertTrue(v2.is_active)
        self.assertEqual(v2.remise_globale, Decimal('10.00'))
        self.assertIn('avenant négocié', v2.accepte_par_nom)
        self.assertEqual(_ttc(v2), Decimal('49000.00'))
        v1.refresh_from_db()
        self.assertFalse(v1.is_active)
        self.assertEqual(v1.superseded_by_id, v2.pk)
        brouillon.refresh_from_db()
        self.assertEqual(brouillon.statut, Facture.Statut.ANNULEE)
        self.assertFalse(Avoir.objects.filter(facture=brouillon).exists())
        acompte.refresh_from_db()
        self.assertEqual(acompte.devis_id, v2.pk)
        self.assertFalse(DevisSignature.objects.filter(devis=v2).exists())
        store_pdf.assert_not_called()
        emails.assert_not_called()
        self.assertEqual(mail.outbox, [])
        self.assertEqual(
            set(devis_signes_en_vigueur(self.company)
                .values_list('pk', flat=True)), {v2.pk})
        self.assertEqual(r['factures_annulees'],
                         [{'reference': brouillon.reference}])

    def test_appliquer_incident_de_rattachement_annule_tout(self, *_):
        v1, _acompte, brouillon = (
            self._vente_avec_acompte_paye_et_brouillon())
        nb_devis = Devis.objects.count()
        with mock.patch(
                'apps.ventes.domain.revision.'
                'rattacher_aval_financier_revision',
                side_effect=RuntimeError('incident')):
            with self.assertRaises(RuntimeError):
                self._appliquer(v1, prix_ttc='49000')
        self.assertEqual(Devis.objects.count(), nb_devis)
        v1.refresh_from_db()
        self.assertTrue(v1.is_active)
        self.assertIsNone(v1.superseded_by_id)
        brouillon.refresh_from_db()
        self.assertEqual(brouillon.statut, Facture.Statut.BROUILLON)

    def test_appliquer_double_clic_409_version_remplacee(self, *_):
        from apps.ventes.domain.negociation import PrixNegocieRefuse
        v1, _a, _b = self._vente_avec_acompte_paye_et_brouillon()
        r = self._appliquer(v1, prix_ttc='49000')
        with self.assertRaises(PrixNegocieRefuse) as ctx:
            self._appliquer(Devis.objects.get(pk=v1.pk), prix_ttc='49000')
        self.assertEqual(ctx.exception.statut_http, 409)
        corps = ctx.exception.corps()
        self.assertEqual(corps['code'], 'version_remplacee')
        self.assertEqual(corps['successeur']['id'], r['devis_v2']['id'])

    def test_appliquer_autre_vente_sur_le_lead_409(self, *_):
        from apps.ventes.domain.negociation import PrixNegocieRefuse
        lead = Lead.objects.create(company=self.company, nom='Lead VNT59')
        Devis.objects.filter(pk=self.v1.pk).update(lead=lead)
        v1, _a, _b = self._vente_avec_acompte_paye_et_brouillon()
        autre = make_devis(self.company, self.user, self.client_obj,
                           LIGNES_367, reference='DEV-VNT58-0020')
        Devis.objects.filter(pk=autre.pk).update(
            statut=Devis.Statut.ACCEPTE, lead=lead)
        nb_devis = Devis.objects.count()
        with self.assertRaises(PrixNegocieRefuse) as ctx:
            self._appliquer(v1, prix_ttc='49000')
        self.assertEqual(ctx.exception.statut_http, 409)
        self.assertEqual(ctx.exception.code, 'vente_active_existante')
        self.assertEqual(ctx.exception.corps()['vente_active']['id'],
                         autre.pk)
        self.assertEqual(Devis.objects.count(), nb_devis)

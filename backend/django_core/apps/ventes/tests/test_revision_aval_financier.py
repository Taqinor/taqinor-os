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


@mock.patch('apps.ventes.domain.cycle_vie._send_acceptance_emails')
@mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf')
class AvenantDeSurDevisAccepted(TestCase):
    """VNT51 — ``devis_accepted`` porte ``avenant_de`` = le prédécesseur de
    révision ACCEPTÉ (sélecteur ``predecesseur_accepte``, LA lecture),
    ``None`` pour une première vente ou la V2 d'un devis refusé/expiré."""

    setUp = AvalFinancierRevision.setUp
    _accepter = AvalFinancierRevision._accepter
    _reviser_prix = AvalFinancierRevision._reviser_prix

    def _capter(self):
        from core.events import devis_accepted
        recus = []

        def _recepteur(sender, devis, **kwargs):
            recus.append((devis.pk, kwargs.get('avenant_de', 'ABSENT')))
        devis_accepted.connect(_recepteur, weak=False, dispatch_uid='vnt51')
        self.addCleanup(devis_accepted.disconnect, dispatch_uid='vnt51')
        return recus

    def test_premiere_vente_avenant_de_none(self, *_):
        recus = self._capter()
        self._accepter(self.v1)
        self.assertEqual(recus, [(self.v1.pk, None)])

    def test_v2_d_un_accepte_avenant_de_v1(self, *_):
        from apps.ventes.selectors import predecesseur_accepte
        self.v1 = self._accepter(self.v1)
        recus = self._capter()
        v2 = self._accepter(self._reviser_prix('7000'))
        self.assertEqual(recus, [(v2.pk, self.v1.pk)])
        self.assertEqual(predecesseur_accepte(v2).pk, self.v1.pk)

    def _v2_apres(self, statut):
        from apps.ventes.selectors import predecesseur_accepte
        Devis.objects.filter(pk=self.v1.pk).update(statut=statut)
        self.v1.refresh_from_db()
        recus = self._capter()
        v2 = self._accepter(self._reviser_prix('7000'))
        self.assertEqual(recus, [(v2.pk, None)])
        self.assertIsNone(predecesseur_accepte(v2))

    def test_v2_d_un_refuse_avenant_de_none(self, *_):
        self._v2_apres(Devis.Statut.REFUSE)


#: Panier RÉEL du devis 367 (V1 Kharbachi) : 9 600 @10 + 36 643,50 @20, N=1.
PANIER_367 = [('Main d oeuvre', '1', '9600', '10'),
              ('Materiel', '1', '36643.50', '20')]


@mock.patch('apps.ventes.domain.cycle_vie._send_acceptance_emails')
@mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf')
class ApercuPrixNegocie(TestCase):
    """VNT58 — ``apercu_prix_negocie`` : lecture PURE (rien n'est écrit),
    solveur 54 500 → 49 000 = 10,00 %, effets lus sur ``etat_vente``."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.lead = Lead.objects.create(company=self.company, nom='Lead 1594')
        v1 = make_devis(self.company, self.user, self.client_obj, PANIER_367,
                        reference='DEV-VNT58-0367')
        Devis.objects.filter(pk=v1.pk).update(
            statut=Devis.Statut.ENVOYE, lead=self.lead)
        v1.refresh_from_db()
        for cible in ('_store_signed_pdf', '_send_acceptance_emails'):
            patcher = mock.patch(f'apps.ventes.domain.cycle_vie.{cible}')
            patcher.start()
            self.addCleanup(patcher.stop)
        self.v1 = accept_devis(devis=v1, user=self.user, nom='Client 367',
                               date_acceptation=date.today(),
                               option='sans_batterie')
        self.assertEqual(_ttc(self.v1), Decimal('54500.00'))

    def _tranche(self):
        return creer_facture_tranche(Devis.objects.get(pk=self.v1.pk),
                                     self.user, self.company,
                                     create_with_reference)

    def _apercu(self, **saisie):
        from apps.ventes.domain.negociation import apercu_prix_negocie
        return apercu_prix_negocie(
            Devis.objects.get(pk=self.v1.pk), user=self.user, **saisie)

    def _code(self, **saisie):
        from apps.ventes.domain.negociation import PrixNegocieErreur
        with self.assertRaises(PrixNegocieErreur) as ctx:
            self._apercu(**saisie)
        return ctx.exception.code

    def test_apercu_49000_remise_10_effets_rien_ecrit(self, *_):
        acompte = self._tranche()
        Facture.objects.filter(pk=acompte.pk).update(
            statut=Facture.Statut.PAYEE, reference='FAC-VNT58-0001')
        materiel = self._tranche()
        Facture.objects.filter(pk=materiel.pk).update(
            statut=Facture.Statut.BROUILLON)
        materiel.refresh_from_db()
        acompte.refresh_from_db()
        nb_devis, nb_factures = Devis.objects.count(), Facture.objects.count()

        a = self._apercu(prix_ttc='49000')

        self.assertEqual(a['remise_pct'], '10.00')
        self.assertEqual(a['total_ttc'], '49000.00')
        self.assertEqual(a['ecart_ttc'], '-5500.00')
        self.assertEqual(a['devis_v2'], {'id': None, 'reference': None,
                                         'version': 2})
        self.assertEqual(a['factures_annulees'],
                         [{'reference': materiel.reference}])
        self.assertEqual([f['reference'] for f in a['factures_reprises']],
                         ['FAC-VNT58-0001'])
        self.assertEqual(Decimal(a['reste_a_facturer']),
                         Decimal('49000.00') - Decimal(str(acompte.total_ttc)))
        self.assertEqual(a['regularisation'],
                         {'type': 'aucune', 'montant': '0.00'})
        # Lecture PURE.
        self.assertEqual(Devis.objects.count(), nb_devis)
        self.assertEqual(Facture.objects.count(), nb_factures)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.remise_globale, Decimal('0'))
        materiel.refresh_from_db()
        self.assertEqual(materiel.statut, Facture.Statut.BROUILLON)

    def test_remise_10_rend_le_meme_apercu(self, *_):
        self.assertEqual(self._apercu(remise_pct='10')['total_ttc'],
                         '49000.00')

    def test_refus_d_entree(self, *_):
        self.assertEqual(self._code(prix_ttc='48950'), 'prix_non_rond')
        self.assertEqual(self._code(prix_ttc='60000'), 'prix_superieur')
        self.assertEqual(self._code(prix_ttc='54500'), 'prix_identique')
        self.assertEqual(self._code(), 'saisie_vide')
        self.assertEqual(self._code(prix_ttc='49000', remise_pct='10'),
                         'saisie_double')

    def test_version_remplacee_409(self, *_):
        from apps.ventes.domain.negociation import PrixNegocieErreur
        v2 = reviser_devis(self.v1, user=self.user)
        with self.assertRaises(PrixNegocieErreur) as ctx:
            self._apercu(prix_ttc='49000')
        self.assertEqual(ctx.exception.statut_http, 409)
        self.assertEqual(ctx.exception.corps['code'], 'version_remplacee')
        self.assertEqual(ctx.exception.corps['successeur']['id'], v2.pk)

    def test_v2_d_un_expire_avenant_de_none(self, *_):
        self._v2_apres(Devis.Statut.EXPIRE)


@mock.patch('apps.ventes.domain.cycle_vie._send_acceptance_emails')
@mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf')
class AppliquerPrixNegocie(TestCase):
    """VNT59 (D-VNT-2) — « Prix négocié » : V2 créée ET acceptée en un geste
    (canal ``avenant_negocie``), brouillons de la V1 ANNULÉS (jamais
    supprimés), payé re-pointé, aucune signature / PDF / e-mail / CAPI, tout
    ou rien."""

    setUp = ApercuPrixNegocie.setUp
    _tranche = ApercuPrixNegocie._tranche

    def _acompte_paye_et_materiel_brouillon(self):
        acompte = self._tranche()
        Facture.objects.filter(pk=acompte.pk).update(
            statut=Facture.Statut.PAYEE, reference='FAC-VNT59-0001')
        materiel = self._tranche()
        Facture.objects.filter(pk=materiel.pk).update(
            statut=Facture.Statut.BROUILLON,
            reference=f'BROUILLON-{materiel.pk}')
        return acompte, materiel

    def _appliquer(self, prix='49000'):
        from apps.ventes.domain.negociation import appliquer_prix_negocie
        return appliquer_prix_negocie(Devis.objects.get(pk=self.v1.pk),
                                      prix_ttc=prix, user=self.user)

    def _erreur(self, prix='49000'):
        from apps.ventes.domain.negociation import PrixNegocieErreur
        with self.assertRaises(PrixNegocieErreur) as ctx:
            self._appliquer(prix)
        return ctx.exception

    def test_un_geste_v2_acceptee_brouillon_annule_paye_repointe(
            self, store_pdf, envoyer_mails):
        from django.core import mail
        from django.db import transaction
        from apps.ventes.models import DevisSignature
        from apps.ventes.selectors import devis_signes_en_vigueur
        acompte, materiel = self._acompte_paye_et_materiel_brouillon()
        nb_avoirs = Avoir.objects.count()
        mail.outbox = []
        with transaction.atomic():  # appelant englobant : rien ne part
            r = self._appliquer()
        v2 = Devis.objects.get(pk=r['devis_v2']['id'])
        self.assertEqual(r['remise_pct'], '10.00')
        self.assertEqual(r['total_ttc'], '49000.00')
        self.assertEqual(v2.statut, Devis.Statut.ACCEPTE)
        self.assertTrue(v2.is_active)
        self.assertEqual(v2.remise_globale, Decimal('10.00'))
        self.assertEqual(_ttc(v2), Decimal('49000.00'))
        self.assertTrue(v2.accepte_par_nom.endswith('avenant négocié'))
        self.v1.refresh_from_db()
        self.assertFalse(self.v1.is_active)
        self.assertEqual(self.v1.superseded_by_id, v2.pk)
        self.assertEqual(self.v1.statut, Devis.Statut.ACCEPTE)  # règle #4
        materiel.refresh_from_db()
        self.assertEqual(materiel.statut, Facture.Statut.ANNULEE)
        self.assertEqual(r['factures_annulees'],
                         [{'reference': materiel.reference}])
        self.assertEqual(Avoir.objects.count(), nb_avoirs)
        acompte.refresh_from_db()
        self.assertEqual(acompte.devis_id, v2.pk)
        self.assertFalse(DevisSignature.objects.filter(devis=v2).exists())
        store_pdf.assert_not_called()
        envoyer_mails.assert_not_called()
        self.assertEqual(mail.outbox, [])
        self.assertEqual(
            set(devis_signes_en_vigueur(self.company,
                                        lead_ids=[self.lead.pk])
                .values_list('pk', flat=True)), {v2.pk})

    def test_incident_de_rattachement_tout_annule(self, *_):
        acompte, materiel = self._acompte_paye_et_materiel_brouillon()
        nb_devis = Devis.objects.count()
        with mock.patch(
                'apps.ventes.domain.revision.rattacher_aval_financier_revision',
                side_effect=RuntimeError('panne')):
            with self.assertRaises(RuntimeError):
                self._appliquer()
        self.assertEqual(Devis.objects.count(), nb_devis)
        self.v1.refresh_from_db()
        self.assertTrue(self.v1.is_active)
        self.assertIsNone(self.v1.superseded_by_id)
        materiel.refresh_from_db()
        self.assertEqual(materiel.statut, Facture.Statut.BROUILLON)

    def test_double_clic_409_version_remplacee(self, *_):
        r = self._appliquer()
        exc = self._erreur()
        self.assertEqual(exc.statut_http, 409)
        self.assertEqual(exc.corps['code'], 'version_remplacee')
        self.assertEqual(exc.corps['successeur']['id'], r['devis_v2']['id'])

    def test_autre_vente_sur_le_lead_409(self, *_):
        autre = make_devis(self.company, self.user, self.client_obj,
                           PANIER_367, reference='DEV-VNT59-0389')
        Devis.objects.filter(pk=autre.pk).update(
            statut=Devis.Statut.ACCEPTE, lead=self.lead)
        nb_devis = Devis.objects.count()
        exc = self._erreur()
        self.assertEqual(exc.statut_http, 409)
        self.assertEqual(exc.corps['code'], 'vente_active_existante')
        self.assertEqual(exc.corps['vente_active']['id'], autre.pk)
        self.assertEqual(Devis.objects.count(), nb_devis)
        self.v1.refresh_from_db()
        self.assertTrue(self.v1.is_active)

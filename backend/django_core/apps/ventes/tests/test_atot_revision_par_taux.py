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
from apps.ventes.domain.revision import (
    rattacher_aval_financier_revision, reviser_devis,
)
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
        v2 = self._v2({A10: '30000'})
        # VNT64 — jamais un avoir d'écart sans confirmation : l'acceptation
        # le signale, le geste confirmé l'émet.
        self.assertFalse(Avoir.objects.filter(company=self.company).exists())
        rattacher_aval_financier_revision(v2, user=self.user,
                                          confirmer_avoir=True)
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

    def test_confirmer_avoir_revision_par_la_route(self, *_):
        """ATOT62 (C-ATOT-VER4-022) — la V2 acceptée par le flux normal reçoit
        par la route son avoir de 11 000 TTC à 10 % ; un second POST répond
        409 ``aucun_avoir_a_confirmer`` (rien d'écrit) ; rôle normal ⇒ 403.
        Mutant : appeler sans ``confirmer_avoir`` ⇒ échec."""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        self.v1 = self._accepter(self.v1)
        self._facturer_tout(self.v1)
        v2 = self._v2({A10: '30000'})
        url = f'/api/django/ventes/devis/{v2.pk}/confirmer-avoir-revision/'

        def client(user):
            api = APIClient()
            api.credentials(
                HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
            return api
        normal = get_user_model().objects.create_user(
            username='atot62_normal', password='x', role_legacy='normal',
            company=self.company)
        self.assertEqual(client(normal).post(url, {}, format='json')
                         .status_code, 403)
        resp = client(self.user).post(url, {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        avoir = Avoir.objects.get(company=self.company)
        avoir.refresh_from_db()  # CLAUSE PERSISTANCE — un seul avoir relu
        self.assertEqual(avoir.type, Avoir.Type.CORRECTION)
        self.assertEqual((avoir.montant_ht, avoir.montant_tva),
                         (Decimal('10000.00'), Decimal('1000.00')))
        self.assertEqual(resp.data['avoirs'], [{
            'reference': avoir.reference, 'montant_ttc': '11000.00',
            'facture': avoir.facture.reference}])
        encore = client(self.user).post(url, {}, format='json')
        self.assertEqual(encore.status_code, 409, encore.data)
        self.assertEqual(encore.data['code'], 'aucun_avoir_a_confirmer')
        self.assertEqual(Avoir.objects.filter(company=self.company).count(),
                         1)

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

    def test_taux_de_sens_opposes_deux_documents(self, *_):
        """ATOT44 (C-ATOT-VER-005, D-ATOT-VER-2 = séparés) — 10 % baisse,
        20 % monte : un complément à 20 % seul, un avoir à 10 % seul soumis à
        confirmation ; jamais un panier de TVA négatif. Mutant : remettre
        ``d_base * signe > 0`` ⇒ un complément de 13 000 à TVA 2 166,67."""
        self.v1 = self._accepter(self.v1)
        self._facturer_tout(self.v1)
        v2 = self._v2({A10: '30000', A20: '80000'})
        complement = Facture.objects.get(
            devis=v2, libelle__startswith='Complément révision')
        complement.refresh_from_db()
        self.assertEqual(complement.statut, Facture.Statut.BROUILLON)
        self.assertEqual(
            (complement.montant_ht, complement.montant_tva,
             complement.montant_ttc, complement.taux_tva),
            (Decimal('20000.00'), Decimal('4000.00'), Decimal('24000.00'),
             Decimal('20')))
        self.assertEqual([(t, m) for t, _b, m in _paniers(complement)],
                         [(Decimal('20'), Decimal('4000.00'))])
        self.assertFalse(Avoir.objects.filter(company=self.company).exists())
        # Rejeu NON confirmé : l'avoir reste à confirmer, pas de 2e complément.
        r = rattacher_aval_financier_revision(v2, user=self.user)
        self.assertEqual(r['avoir_a_confirmer'], Decimal('11000.00'))
        self.assertIsNone(r['document'])
        self.assertFalse(Avoir.objects.filter(company=self.company).exists())
        # Geste confirmé : l'avoir à 10 % seul, AUCUN second complément.
        rattacher_aval_financier_revision(v2, user=self.user,
                                          confirmer_avoir=True)
        avoir = Avoir.objects.get(company=self.company)
        avoir.refresh_from_db()
        self.assertEqual(
            (avoir.montant_ht, avoir.montant_tva, avoir.montant_ttc,
             avoir.taux_tva),
            (Decimal('10000.00'), Decimal('1000.00'), Decimal('11000.00'),
             Decimal('10')))
        self.assertEqual([(t, m) for t, _b, m in _paniers(avoir)],
                         [(Decimal('10'), Decimal('1000.00'))])
        self.assertEqual(Facture.objects.filter(
            devis=v2, libelle__startswith='Complément révision').count(), 1)
        # Σ complément − Σ avoir = écart de TTC des deux versions, au centime.
        self.assertEqual(complement.montant_ttc - avoir.montant_ttc,
                         Decimal('13000.00'))
        for doc in (complement, avoir):
            for _t, base, montant in _paniers(doc):
                self.assertGreater(base, 0)
                self.assertGreater(montant, 0)

    # ── ATOT45 — l'avoir d'écart passe par le constructeur unique ─────────

    def _vente_5x20_emise(self):
        """Devis accepté 12 000 TTC, échéancier 5 × 20 % entièrement émis
        (sonde C-ATOT-VER-004), aucun paiement."""
        d = make_devis(self.company, self.user, self.client_obj,
                       [('Panneau ATOT45', '10', '1000', '20')],
                       reference='DEV-ATOT45-0001')
        Devis.objects.filter(pk=d.pk).update(
            statut=Devis.Statut.ENVOYE,
            echeancier=[{'pct_or_montant': 20}] * 5)
        d = self._accepter(Devis.objects.get(pk=d.pk))
        while True:
            try:
                creer_facture_tranche(Devis.objects.get(pk=d.pk), self.user,
                                      self.company, create_with_reference)
            except ValueError:
                break
        factures = list(Facture.objects.filter(devis=d).exclude(
            statut=Facture.Statut.ANNULEE).order_by('pk'))
        self.assertEqual([f.total_ttc for f in factures],
                         [Decimal('2400.00')] * 5)
        return Devis.objects.get(pk=d.pk), factures

    def _negocier(self, devis):
        from apps.ventes.domain.negociation import appliquer_prix_negocie
        return appliquer_prix_negocie(devis, prix_ttc='9000', user=self.user,
                                      confirmer_avoir=True)

    def test_prix_negocie_avoirs_repartis_sous_le_creditable(self, *_):
        """C-ATOT-VER-004 — 9 000 négocié sur 5 × 2 400 émis : deux avoirs
        CORRECTION (2 400 + 600) sur deux factures distinctes, jamais un
        avoir de 3 000 sur une facture de 2 400 ; dû restant 9 000. Mutant :
        rappeler ``Avoir.objects.create`` ⇒ échec."""
        d, factures = self._vente_5x20_emise()
        r = self._negocier(d)
        avoirs = list(Avoir.objects.filter(company=self.company)
                      .order_by('-montant_ttc'))
        self.assertEqual([a.montant_ttc for a in avoirs],
                         [Decimal('2400.00'), Decimal('600.00')])
        self.assertEqual({a.type for a in avoirs}, {Avoir.Type.CORRECTION})
        self.assertEqual(len({a.facture_id for a in avoirs}), 2)
        for a in avoirs:
            a.refresh_from_db()
            self.assertLessEqual(a.montant_ttc, a.facture.total_ttc)
            self.assertEqual(a.montant_ht + a.montant_tva, a.montant_ttc)
        # CLAUSE PERSISTANCE — factures relues : statuts recalculés, dû 9 000.
        relues = [Facture.objects.get(pk=f.pk) for f in factures]
        self.assertEqual(sum((f.montant_du for f in relues), Decimal('0')),
                         Decimal('9000.00'))
        soldee = Facture.objects.get(pk=avoirs[0].facture_id)
        self.assertEqual(soldee.statut, Facture.Statut.PAYEE)
        self.assertEqual(r['devis_v2']['version'], 2)

    def test_prix_negocie_au_dela_du_creditable_409_rien_ecrit(self, *_):
        """Un écart (3 000) au-delà du Σ créditable (gestes commerciaux
        antérieurs sur quatre factures : reste 2 400) ⇒ 409
        ``avoir_au_dela_du_creditable`` ; aucune V2, aucun avoir d'écart."""
        from apps.ventes.domain.facturation_ops import creer_avoir_facture
        from apps.ventes.domain.negociation import PrixNegocieRefuse
        d, factures = self._vente_5x20_emise()
        for f in factures[:4]:
            creer_avoir_facture(facture=f, user=self.user, motif='Geste',
                                type_avoir=Avoir.Type.GESTE_COMMERCIAL)
        nb_devis, nb_avoirs = Devis.objects.count(), Avoir.objects.count()
        with self.assertRaises(PrixNegocieRefuse) as ctx:
            self._negocier(d)
        self.assertEqual(ctx.exception.code, 'avoir_au_dela_du_creditable')
        self.assertEqual(ctx.exception.statut_http, 409)
        self.assertEqual(Devis.objects.count(), nb_devis)
        self.assertEqual(Avoir.objects.count(), nb_avoirs)
        self.assertFalse(Avoir.objects.filter(
            type=Avoir.Type.CORRECTION).exists())
        d.refresh_from_db()
        self.assertTrue(d.is_active)

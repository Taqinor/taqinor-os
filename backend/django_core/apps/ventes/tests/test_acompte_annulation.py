"""
FG50 — Transfert / remboursement de l'acompte à l'annulation d'une facture.

Quand une facture porteuse de paiements (acompte) est annulée, l'admin peut :
  - transférer l'acompte vers une AUTRE facture du MÊME devis (les soldes des
    deux factures se redérivent) ;
  - le marquer remboursable (écriture Paiement négative de contre-passation).
Les deux gestes sont consignés dans le chatter. Une annulation SANS acompte (ou
sans directive) reste strictement inchangée.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_acompte_annulation -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, Facture, Paiement

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='fg50-co', nom='FG50 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='fg50@example.com'):
    return Client.objects.create(
        company=company, nom='Acompte', prenom='Client',
        email=email, telephone='+212600000050', adresse='Casablanca',
    )


def make_accepted_devis(company, client, ref='DEV-FG50-0001', mode='residentiel'):
    devis = Devis.objects.create(
        company=company, reference=f'{ref}-{MONTH}', client=client,
        statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20.00'),
        mode_installation=mode,
    )
    panneau = Produit.objects.create(
        company=company, nom='Panneau PV 450W', sku=f'PV-{ref}',
        prix_vente=Decimal('1000'), quantite_stock=100, tva=Decimal('10.00'),
    )
    onduleur = Produit.objects.create(
        company=company, nom='Onduleur 5kW', sku=f'OND-{ref}',
        prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'),
    )
    LigneDevis.objects.create(
        devis=devis, produit=panneau, designation='Panneau PV 450W',
        quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
        remise=Decimal('0'), taux_tva=Decimal('10.00'),
    )
    LigneDevis.objects.create(
        devis=devis, produit=onduleur, designation='Onduleur 5kW',
        quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
        remise=Decimal('0'), taux_tva=Decimal('20.00'),
    )
    return devis


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FG50AcompteAnnulation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='fg50_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        self.devis = make_accepted_devis(self.company, self.client_obj)

    def _facture(self, statut=Facture.Statut.EMISE, devis=None, type_f='acompte'):
        return Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-{Facture.objects.count()+1:04d}',
            devis=devis if devis is not None else self.devis,
            client=self.client_obj, statut=statut, type_facture=type_f,
            montant_ht=Decimal('4500'), montant_tva=Decimal('600'),
            montant_ttc=Decimal('5100'), created_by=self.admin,
        )

    def _pay(self, facture, montant='2000'):
        return Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal(montant),
            date_paiement=timezone.now().date(), mode='virement',
            created_by=self.admin,
        )

    def _annuler(self, facture, body=None):
        return self.api.post(
            f'/api/django/ventes/factures/{facture.id}/annuler/',
            body or {}, format='json',
        )

    def _historique(self, facture):
        return self.api.get(
            f'/api/django/ventes/factures/{facture.id}/historique/').data

    # ── 1. Transfert vers une autre facture du même devis ──
    def test_transfer_moves_acompte_to_target_and_rederives_soldes(self):
        source = self._facture()
        self._pay(source, '2000')
        cible = self._facture(type_f='intermediaire')

        self.assertEqual(source.montant_paye, Decimal('2000'))
        self.assertEqual(cible.montant_paye, Decimal('0'))

        r = self._annuler(source, {
            'acompte': {'action': 'transferer', 'facture_cible': cible.id}})
        self.assertEqual(r.status_code, 200, r.data)

        source.refresh_from_db()
        cible.refresh_from_db()
        # Source annulée, acompte parti (net 0) ; cible reçoit l'acompte.
        self.assertEqual(source.statut, Facture.Statut.ANNULEE)
        self.assertEqual(source.montant_paye, Decimal('0'))
        self.assertEqual(cible.montant_paye, Decimal('2000'))
        self.assertEqual(cible.montant_du, Decimal('3100'))
        # Tous les paiements pointent désormais la cible.
        self.assertEqual(
            Paiement.objects.filter(facture=source).count(), 0)
        self.assertEqual(
            Paiement.objects.filter(facture=cible).count(), 1)

    def test_transfer_logs_chatter_on_both_factures(self):
        source = self._facture()
        self._pay(source, '2000')
        cible = self._facture(type_f='intermediaire')
        self._annuler(source, {
            'acompte': {'action': 'transferer', 'facture_cible': cible.id}})

        src_hist = self._historique(source)
        cib_hist = self._historique(cible)
        self.assertTrue(any('transféré' in (a['body'] or '') for a in src_hist))
        self.assertTrue(any('reçu' in (a['body'] or '') for a in cib_hist))

    def test_transfer_to_other_devis_rejected(self):
        source = self._facture()
        self._pay(source, '2000')
        autre_devis = make_accepted_devis(
            self.company, self.client_obj, ref='DEV-FG50-0002')
        cible = self._facture(devis=autre_devis, type_f='intermediaire')

        r = self._annuler(source, {
            'acompte': {'action': 'transferer', 'facture_cible': cible.id}})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('même devis', r.data['detail'])
        # Rien n'a bougé : facture toujours émise, acompte intact.
        source.refresh_from_db()
        self.assertEqual(source.statut, Facture.Statut.EMISE)
        self.assertEqual(source.montant_paye, Decimal('2000'))

    def test_transfer_to_other_company_rejected(self):
        source = self._facture()
        self._pay(source, '2000')
        autre_company = make_company(slug='fg50-other', nom='Autre')
        autre_client = make_client(autre_company, email='other@example.com')
        autre_devis = make_accepted_devis(
            autre_company, autre_client, ref='DEV-FG50-OTH')
        cible = Facture.objects.create(
            company=autre_company, reference=f'FAC-OTH-{MONTH}',
            devis=autre_devis, client=autre_client,
            statut=Facture.Statut.EMISE, type_facture='acompte',
            montant_ht=Decimal('100'), montant_tva=Decimal('20'),
            montant_ttc=Decimal('120'),
        )
        r = self._annuler(source, {
            'acompte': {'action': 'transferer', 'facture_cible': cible.id}})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('inconnue', r.data['detail'].lower())
        source.refresh_from_db()
        self.assertEqual(source.statut, Facture.Statut.EMISE)

    def test_transfer_to_self_rejected(self):
        source = self._facture()
        self._pay(source, '2000')
        r = self._annuler(source, {
            'acompte': {'action': 'transferer', 'facture_cible': source.id}})
        self.assertEqual(r.status_code, 400, r.data)

    def test_transfer_without_acompte_rejected(self):
        source = self._facture()  # pas de paiement
        cible = self._facture(type_f='intermediaire')
        r = self._annuler(source, {
            'acompte': {'action': 'transferer', 'facture_cible': cible.id}})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Aucun acompte', r.data['detail'])

    # ── 1bis. AUD125 — ce que la cible peut ABSORBER ──
    def test_transfer_superieur_au_reste_du_de_la_cible_refuse(self):
        """AUD125 — un acompte de 30 000 déplacé sur une facture de solde de
        20 000 créait un trop-perçu de 10 000 INVISIBLE : ni la source ni la
        cible ne le signalaient. ROUGE avant le correctif."""
        source = self._facture()
        self._pay(source, '30000')
        cible = self._facture(type_f='intermediaire')
        # La cible ne doit que 5 100 : elle ne peut pas absorber 30 000.
        self.assertEqual(cible.montant_du, Decimal('5100.00'))

        r = self._annuler(source, {
            'acompte': {'action': 'transferer', 'facture_cible': cible.id}})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('dépasse le reste à payer', r.data['detail'])
        # RIEN n'a bougé : la source reste émise avec son acompte.
        source.refresh_from_db()
        cible.refresh_from_db()
        self.assertEqual(source.statut, Facture.Statut.EMISE)
        self.assertEqual(source.montant_paye, Decimal('30000'))
        self.assertEqual(cible.montant_paye, Decimal('0'))
        self.assertEqual(Paiement.objects.filter(facture=cible).count(), 0)

    def test_transfer_egal_au_reste_du_de_la_cible_passe(self):
        """Le transfert qui solde EXACTEMENT la cible reste autorisé (la
        garde est bornée au centime près, jamais plus stricte)."""
        source = self._facture()
        self._pay(source, '5100')
        cible = self._facture(type_f='intermediaire')

        r = self._annuler(source, {
            'acompte': {'action': 'transferer', 'facture_cible': cible.id}})
        self.assertEqual(r.status_code, 200, r.data)
        cible.refresh_from_db()
        self.assertEqual(cible.montant_paye, Decimal('5100'))
        self.assertEqual(cible.montant_du, Decimal('0'))

    # ── 2. Remboursement (contre-passation) ──
    def test_refund_creates_reversing_negative_paiement(self):
        source = self._facture()
        self._pay(source, '2000')
        self.assertEqual(source.montant_paye, Decimal('2000'))

        r = self._annuler(source, {'acompte': {'action': 'rembourser'}})
        self.assertEqual(r.status_code, 200, r.data)

        source.refresh_from_db()
        self.assertEqual(source.statut, Facture.Statut.ANNULEE)
        # Net retombe à 0 : l'acompte n'est plus « coincé ».
        self.assertEqual(source.montant_paye, Decimal('0'))
        paiements = list(Paiement.objects.filter(facture=source))
        self.assertEqual(len(paiements), 2)
        montants = sorted(p.montant for p in paiements)
        self.assertEqual(montants, [Decimal('-2000'), Decimal('2000')])

    def test_refund_logs_chatter(self):
        source = self._facture()
        self._pay(source, '2000')
        self._annuler(source, {'acompte': {'action': 'rembourser'}})
        hist = self._historique(source)
        self.assertTrue(
            any('remboursable' in (a['body'] or '') for a in hist))

    def test_refund_without_acompte_rejected(self):
        source = self._facture()
        r = self._annuler(source, {'acompte': {'action': 'rembourser'}})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Aucun acompte', r.data['detail'])

    # ── 3. Comportement historique préservé ──
    def test_plain_cancel_without_deposit_unchanged(self):
        source = self._facture()
        r = self._annuler(source)
        self.assertEqual(r.status_code, 200, r.data)
        source.refresh_from_db()
        self.assertEqual(source.statut, Facture.Statut.ANNULEE)
        # Aucun paiement créé, aucune note d'acompte.
        self.assertEqual(Paiement.objects.filter(facture=source).count(), 0)

    def test_plain_cancel_with_deposit_leaves_paiements_untouched(self):
        # AFAC12 (C-AFAC-002) — RÉÉCRIT explicitement : ce test FIGEAIT le
        # défaut (annulation sans directive = 200, acompte coincé sur une
        # facture morte). Désormais : 400 ``directive_acompte_requise``,
        # facture et paiement inchangés.
        source = self._facture()
        self._pay(source, '2000')
        statut_avant = Facture.objects.get(pk=source.pk).statut
        r = self._annuler(source)
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['code'], 'directive_acompte_requise')
        self.assertEqual(r.data['argent_rattache']['paiements'], '2000.00')
        source.refresh_from_db()
        self.assertEqual(source.statut, statut_avant)
        self.assertNotEqual(source.statut, Facture.Statut.ANNULEE)
        self.assertEqual(
            Paiement.objects.filter(facture=source).count(), 1)

    def test_invalid_acompte_action_rejected(self):
        source = self._facture()
        self._pay(source, '2000')
        r = self._annuler(source, {'acompte': {'action': 'foo'}})
        self.assertEqual(r.status_code, 400, r.data)

    def test_paid_facture_cannot_be_cancelled(self):
        source = self._facture(statut=Facture.Statut.PAYEE)
        r = self._annuler(source, {'acompte': {'action': 'rembourser'}})
        self.assertEqual(r.status_code, 400, r.data)

    def test_already_cancelled_rejected(self):
        source = self._facture(statut=Facture.Statut.ANNULEE)
        r = self._annuler(source, {'acompte': {'action': 'rembourser'}})
        self.assertEqual(r.status_code, 400, r.data)

    # ── VNT10 — le corps vit dans le service du domaine (sans HTTP) ──
    def test_vnt10_service_annuler_facture_sans_http(self):
        from apps.ventes.domain.annulation_facture import (
            AnnulationRefusee, annuler_facture,
        )
        source = self._facture()
        self._pay(source, '2000')
        with self.assertRaises(AnnulationRefusee) as ctx:
            annuler_facture(source, user=self.admin)
        self.assertEqual(
            ctx.exception.corps['code'], 'directive_acompte_requise')
        self.assertEqual(
            ctx.exception.corps['argent_rattache']['paiements'], '2000.00')
        libre = self._facture()
        rendu = annuler_facture(libre, user=self.admin)
        self.assertEqual(rendu.statut, Facture.Statut.ANNULEE)
        libre.refresh_from_db()
        self.assertEqual(libre.statut, Facture.Statut.ANNULEE)


class VNT11AnnulationAvecAvoir(TestCase):
    """VNT11 (D-VNT-1) — annuler une facture à référence LÉGALE émet son
    avoir de contre-passation CORRECTION (le devis est libéré, jamais de trou
    de numérotation) ; un ``BROUILLON-<id>`` s'annule sans avoir ;
    ``retirer_brouillons_de_la_vente`` annule (jamais ne supprime)."""

    def setUp(self):
        self.company = make_company(slug='vnt11-co', nom='VNT11 Co')
        self.client_obj = make_client(self.company, email='vnt11@example.com')
        self.admin = User.objects.create_user(
            username='vnt11_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        self.devis = make_accepted_devis(
            self.company, self.client_obj, ref='DEV-VNT11-0001')

    def _facture(self, reference, statut=Facture.Statut.EMISE,
                 ttc='1600.00', ht='1333.33', tva='266.67', type_f='solde'):
        return Facture.objects.create(
            company=self.company, reference=reference, devis=self.devis,
            client=self.client_obj, statut=statut, type_facture=type_f,
            montant_ht=Decimal(ht), montant_tva=Decimal(tva),
            montant_ttc=Decimal(ttc), created_by=self.admin,
        )

    def _avoirs(self, facture):
        from apps.ventes.models import Avoir
        return list(Avoir.objects.filter(facture=facture))

    def _annuler(self, facture, body=None):
        return self.api.post(
            f'/api/django/ventes/factures/{facture.id}/annuler/',
            body or {}, format='json')

    def test_emise_sans_argent_avoir_correction_et_devis_libere(self):
        from apps.ventes.models import Avoir
        from apps.ventes.selectors_facturation import (
            DevisDejaFacture, exiger_devis_facturable)
        f = self._facture(f'FAC-{MONTH}-0008')
        with self.assertRaises(DevisDejaFacture):
            exiger_devis_facturable(self.devis, 'complete')
        r = self._annuler(f)
        self.assertEqual(r.status_code, 200, r.data)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.ANNULEE)
        # Jamais de trou : le numéro légal reste porté par la facture annulée.
        self.assertEqual(f.reference, f'FAC-{MONTH}-0008')
        avoirs = self._avoirs(f)
        self.assertEqual(len(avoirs), 1)
        self.assertEqual(avoirs[0].type, Avoir.Type.CORRECTION)
        self.assertEqual(avoirs[0].statut, Avoir.Statut.EMISE)
        self.assertEqual(avoirs[0].total_ttc, Decimal('1600.00'))
        # Le devis est libéré : plus aucune facture active ne le ferme.
        exiger_devis_facturable(self.devis, 'complete')

    def test_brouillon_a_reference_legale_recoit_aussi_un_avoir(self):
        f = self._facture(f'FAC-{MONTH}-0042', statut=Facture.Statut.BROUILLON)
        r = self._annuler(f)
        self.assertEqual(r.status_code, 200, r.data)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.ANNULEE)
        self.assertEqual(len(self._avoirs(f)), 1)

    def test_brouillon_provisoire_annule_sans_avoir(self):
        f = self._facture('', statut=Facture.Statut.BROUILLON)
        self.assertTrue(f.reference.startswith('BROUILLON-'))
        r = self._annuler(f)
        self.assertEqual(r.status_code, 200, r.data)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.ANNULEE)
        self.assertEqual(self._avoirs(f), [])

    def test_rembourser_une_facture_legale_emet_aussi_l_avoir(self):
        f = self._facture(f'FAC-{MONTH}-0045')
        Paiement.objects.create(
            company=self.company, facture=f, montant=Decimal('1600'),
            date_paiement=timezone.now().date(), mode='virement',
            created_by=self.admin)
        r = self._annuler(f, {'acompte': {'action': 'rembourser'}})
        self.assertEqual(r.status_code, 200, r.data)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.ANNULEE)
        self.assertEqual(f.montant_paye, Decimal('0'))
        self.assertEqual(len(self._avoirs(f)), 1)

    def test_service_rend_l_avoir_de_l_annulation(self):
        from apps.ventes.domain.annulation_facture import annuler_facture
        legale = self._facture(f'FAC-{MONTH}-0009')
        rendu = annuler_facture(legale, user=self.admin, motif='Doublon')
        self.assertIsNotNone(rendu.avoir_annulation)
        self.assertEqual(rendu.avoir_annulation.motif, 'Doublon')
        brouillon = self._facture('', statut=Facture.Statut.BROUILLON)
        self.assertIsNone(
            annuler_facture(brouillon, user=self.admin).avoir_annulation)

    def test_retirer_brouillons_de_la_vente_annule_sans_supprimer(self):
        from apps.ventes.domain.annulation_facture import (
            retirer_brouillons_de_la_vente)
        provisoire = self._facture('', statut=Facture.Statut.BROUILLON)
        legale = self._facture(
            f'FAC-{MONTH}-0043', statut=Facture.Statut.BROUILLON)
        emise = self._facture(f'FAC-{MONTH}-0044')
        retires = retirer_brouillons_de_la_vente(
            self.devis, user=self.admin, motif='Prix négocié')
        self.assertEqual(sorted(f.pk for f in retires),
                         sorted([provisoire.pk, legale.pk]))
        for f in (provisoire, legale, emise):
            self.assertTrue(Facture.objects.filter(pk=f.pk).exists())
            f.refresh_from_db()
        self.assertEqual(provisoire.statut, Facture.Statut.ANNULEE)
        self.assertEqual(legale.statut, Facture.Statut.ANNULEE)
        self.assertEqual(emise.statut, Facture.Statut.EMISE)
        self.assertEqual(self._avoirs(provisoire), [])
        self.assertEqual(len(self._avoirs(legale)), 1)
        self.assertEqual(self._avoirs(emise), [])


class VNT12GarderEnAvance(TestCase):
    """VNT12 — directive ``garder_en_avance`` : une facture (même PAYÉE)
    s'annule, ses paiements deviennent une avance client NON affectée
    (XFAC1), les affectations ventilées sont défaites, l'avoir CORRECTION
    est émis ; sans directive → 400 ``directive_acompte_requise``."""

    def setUp(self):
        self.company = make_company(slug='vnt12-co', nom='VNT12 Co')
        self.client_obj = make_client(self.company, email='vnt12@example.com')
        self.admin = User.objects.create_user(
            username='vnt12_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        self.devis = make_accepted_devis(
            self.company, self.client_obj, ref='DEV-VNT12-0001')

    def _facture(self, reference, statut=Facture.Statut.EMISE):
        # FAC-0007 de Tijani : acompte 14 700 TTC (12 466,00 + 2 234,00).
        return Facture.objects.create(
            company=self.company, reference=reference, devis=self.devis,
            client=self.client_obj, statut=statut, type_facture='solde',
            montant_ht=Decimal('12466.00'), montant_tva=Decimal('2234.00'),
            montant_ttc=Decimal('14700.00'), created_by=self.admin,
        )

    def _annuler(self, facture, body=None):
        return self.api.post(
            f'/api/django/ventes/factures/{facture.id}/annuler/',
            body or {}, format='json')

    def test_payee_garder_en_avance(self):
        from apps.ventes.models import Avoir
        f = self._facture(f'FAC-{MONTH}-0007', statut=Facture.Statut.PAYEE)
        p = Paiement.objects.create(
            company=self.company, facture=f, montant=Decimal('14700'),
            date_paiement=timezone.now().date(), mode='virement',
            created_by=self.admin)
        r = self._annuler(f, {'acompte': {'action': 'garder_en_avance'}})
        self.assertEqual(r.status_code, 200, r.data)
        f.refresh_from_db()
        p.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.ANNULEE)
        self.assertEqual(f.montant_paye, Decimal('0'))
        # Le paiement devient une avance client NON affectée de 14 700.
        self.assertIsNone(p.facture_id)
        self.assertEqual(p.client_id, self.client_obj.id)
        self.assertEqual(p.statut_affectation,
                         Paiement.StatutAffectation.NON_AFFECTE)
        self.assertEqual(p.montant_disponible, Decimal('14700.00'))
        avoirs = list(Avoir.objects.filter(facture=f))
        self.assertEqual(len(avoirs), 1)
        self.assertEqual(avoirs[0].type, Avoir.Type.CORRECTION)
        self.assertEqual(avoirs[0].total_ttc, Decimal('14700.00'))

    def test_payee_sans_directive_400(self):
        f = self._facture(f'FAC-{MONTH}-0017', statut=Facture.Statut.PAYEE)
        Paiement.objects.create(
            company=self.company, facture=f, montant=Decimal('14700'),
            date_paiement=timezone.now().date(), mode='virement',
            created_by=self.admin)
        r = self._annuler(f)
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['code'], 'directive_acompte_requise')
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.PAYEE)
        # Rembourser une PAYÉE reste refusé : seule la garde en avance passe.
        r = self._annuler(f, {'acompte': {'action': 'rembourser'}})
        self.assertEqual(r.status_code, 400, r.data)

    def test_affectation_ventilee_defaite(self):
        from apps.ventes.domain.encaissements import (
            enregistrer_avance, ventiler_avance)
        f = self._facture(f'FAC-{MONTH}-0027')
        avance = enregistrer_avance(
            company=self.company, client=self.client_obj,
            montant=Decimal('20000'), date_paiement=timezone.now().date(),
            mode='virement', created_by=self.admin)
        ventiler_avance(paiement=avance, facture=f,
                        montant=Decimal('14700'), user=self.admin)
        f.refresh_from_db()
        self.assertEqual(f.montant_paye, Decimal('14700'))
        r = self._annuler(f, {'acompte': {'action': 'garder_en_avance'}})
        self.assertEqual(r.status_code, 200, r.data)
        avance.refresh_from_db()
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.ANNULEE)
        self.assertEqual(f.affectations_paiement.count(), 0)
        self.assertEqual(avance.montant_disponible, Decimal('20000.00'))
        self.assertEqual(avance.statut_affectation,
                         Paiement.StatutAffectation.NON_AFFECTE)

    def test_garder_sans_argent_refuse(self):
        f = self._facture(f'FAC-{MONTH}-0037')
        r = self._annuler(f, {'acompte': {'action': 'garder_en_avance'}})
        self.assertEqual(r.status_code, 400, r.data)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.EMISE)

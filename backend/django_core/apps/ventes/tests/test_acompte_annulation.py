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
        # Annulation SANS directive : statut bascule, paiements inchangés
        # (comportement strictement historique — l'acompte n'est pas traité).
        source = self._facture()
        self._pay(source, '2000')
        r = self._annuler(source)
        self.assertEqual(r.status_code, 200, r.data)
        source.refresh_from_db()
        self.assertEqual(source.statut, Facture.Statut.ANNULEE)
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

"""
Tests de l'échéancier devis → factures + paiements + solde (WS1, 2026-06-13).

Couvre : génération des tranches au bon pourcentage par mode, figures égales au
devis (split 10/20 préservé), paiements qui réduisent le solde, et le partage de
permissions Commerciale (responsable) vs propriétaire (admin) — la Commerciale
facture et encaisse, seul l'admin annule.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_facturation -v 2
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


def make_company(slug='fact-co', nom='Fact Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='fc@example.com'):
    return Client.objects.create(
        company=company, nom='Fact', prenom='Client',
        email=email, telephone='+212600000009', adresse='Casablanca',
    )


def make_accepted_devis(company, client, mode='residentiel'):
    """Devis ACCEPTÉ à 17 000 TTC : 15 000 HT + 2 000 TVA (split 10/20)."""
    devis = Devis.objects.create(
        company=company, reference=f'DEV-{MONTH}-9001', client=client,
        statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20.00'),
        mode_installation=mode,
    )
    panneau = Produit.objects.create(
        company=company, nom='Panneau PV 450W', sku='PV-450',
        prix_vente=Decimal('1000'), quantite_stock=100, tva=Decimal('10.00'),
    )
    onduleur = Produit.objects.create(
        company=company, nom='Onduleur 5kW', sku='OND-5',
        prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'),
    )
    # Ligne 1 : 10 × 1000 = 10 000 HT, TVA 10 % = 1000
    LigneDevis.objects.create(
        devis=devis, produit=panneau, designation='Panneau PV 450W',
        quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
        remise=Decimal('0'), taux_tva=Decimal('10.00'),
    )
    # Ligne 2 : 1 × 5000 = 5 000 HT, TVA 20 % = 1000
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


class TestEcheancierGeneration(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.resp = User.objects.create_user(
            username='fact_resp', password='x', role_legacy='responsable',
            company=self.company,
        )
        self.api = auth(self.resp)

    def _gen(self, devis):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/')

    def test_devis_total_is_17000(self):
        devis = make_accepted_devis(self.company, self.client_obj)
        self.assertEqual(devis.total_ht, Decimal('15000'))
        self.assertEqual(devis.total_tva, Decimal('2000'))
        self.assertEqual(devis.total_ttc, Decimal('17000'))

    def test_residentiel_acompte_is_30pct_of_ttc(self):
        devis = make_accepted_devis(self.company, self.client_obj, 'residentiel')
        r = self._gen(devis)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['type_facture'], 'acompte')
        self.assertEqual(Decimal(r.data['pourcentage']), Decimal('30.00'))
        # 30 % de 17 000 = 5 100 TTC ; HT 4 500 ; TVA 600 (split préservé)
        self.assertEqual(Decimal(r.data['total_ttc']), Decimal('5100.00'))
        self.assertEqual(Decimal(r.data['total_ht']), Decimal('4500.00'))
        self.assertEqual(Decimal(r.data['total_tva']), Decimal('600.00'))
        self.assertEqual(r.data['statut'], 'emise')  # postée

    def test_industriel_acompte_is_50pct(self):
        devis = make_accepted_devis(self.company, self.client_obj, 'industriel')
        r = self._gen(devis)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(r.data['pourcentage']), Decimal('50.00'))
        self.assertEqual(Decimal(r.data['total_ttc']), Decimal('8500.00'))

    def test_three_tranches_sum_exactly_to_devis_total(self):
        devis = make_accepted_devis(self.company, self.client_obj, 'residentiel')
        ttcs = []
        for _ in range(3):
            r = self._gen(devis)
            self.assertEqual(r.status_code, 201, r.data)
            ttcs.append(Decimal(r.data['total_ttc']))
        # 30/60/10 → 5100 / 10200 / 1700, somme = 17 000 au centime près
        self.assertEqual(sum(ttcs), Decimal('17000.00'))
        self.assertEqual(ttcs, [Decimal('5100.00'), Decimal('10200.00'),
                                Decimal('1700.00')])
        # 4e appel : échéancier complet → 400
        r4 = self._gen(devis)
        self.assertEqual(r4.status_code, 400)

    def test_references_are_distinct_and_sequential(self):
        devis = make_accepted_devis(self.company, self.client_obj)
        refs = [self._gen(devis).data['reference'] for _ in range(3)]
        self.assertEqual(len(set(refs)), 3)
        for ref in refs:
            self.assertTrue(ref.startswith(f'FAC-{MONTH}-'))

    def test_cannot_invoice_a_non_accepted_devis(self):
        devis = make_accepted_devis(self.company, self.client_obj)
        devis.statut = Devis.Statut.BROUILLON
        devis.save()
        r = self._gen(devis)
        self.assertEqual(r.status_code, 400)


class TestPaiementsEtSolde(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.resp = User.objects.create_user(
            username='pay_resp', password='x', role_legacy='responsable',
            company=self.company,
        )
        self.api = auth(self.resp)
        self.devis = make_accepted_devis(self.company, self.client_obj)
        self.acompte = Facture.objects.get(pk=self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/generer-facture/'
        ).data['id'])

    def _solde(self):
        d = self.api.get(f'/api/django/ventes/devis/{self.devis.id}/')
        return d.data['solde']

    def test_payment_reduces_facture_balance(self):
        r = self.api.post(
            f'/api/django/ventes/factures/{self.acompte.id}/enregistrer-paiement/',
            {'montant': '2000', 'date_paiement': '2026-06-13', 'mode': 'virement'},
            format='json',
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(r.data['montant_paye']), Decimal('2000.00'))
        self.assertEqual(Decimal(r.data['montant_du']), Decimal('3100.00'))
        self.assertEqual(r.data['statut'], 'emise')  # partiel → reste émise

    def test_full_payment_marks_facture_payee(self):
        r = self.api.post(
            f'/api/django/ventes/factures/{self.acompte.id}/enregistrer-paiement/',
            {'montant': '5100', 'date_paiement': '2026-06-13', 'mode': 'cheque'},
            format='json',
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(r.data['montant_du']), Decimal('0.00'))
        self.assertEqual(r.data['statut'], 'payee')

    def test_solde_math(self):
        # Avant paiement : facturé 5100, payé 0, restant 17000
        s = self._solde()
        self.assertEqual(Decimal(s['total_ttc']), Decimal('17000.00'))
        self.assertEqual(Decimal(s['facture']), Decimal('5100.00'))
        self.assertEqual(Decimal(s['paye']), Decimal('0.00'))
        self.assertEqual(Decimal(s['restant']), Decimal('17000.00'))
        # Encaisse l'acompte
        self.api.post(
            f'/api/django/ventes/factures/{self.acompte.id}/enregistrer-paiement/',
            {'montant': '5100', 'date_paiement': '2026-06-13', 'mode': 'virement'},
            format='json',
        )
        s = self._solde()
        self.assertEqual(Decimal(s['paye']), Decimal('5100.00'))
        self.assertEqual(Decimal(s['restant']), Decimal('11900.00'))

    def test_cancelled_facture_drops_out_of_facture_total(self):
        # Annule l'acompte via un admin → le facturé retombe à 0.
        admin = User.objects.create_user(
            username='pay_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        admin_api = auth(admin)
        r = admin_api.post(
            f'/api/django/ventes/factures/{self.acompte.id}/annuler/')
        self.assertEqual(r.status_code, 200, r.data)
        s = self._solde()
        self.assertEqual(Decimal(s['facture']), Decimal('0.00'))


class TestPermissions(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.meryem = User.objects.create_user(
            username='meryem', password='x', role_legacy='responsable',
            company=self.company,
        )
        self.owner = User.objects.create_user(
            username='owner', password='x', role_legacy='admin',
            company=self.company,
        )
        self.devis = make_accepted_devis(self.company, self.client_obj)

    def test_commerciale_can_invoice_and_register_payment(self):
        api = auth(self.meryem)
        gen = api.post(
            f'/api/django/ventes/devis/{self.devis.id}/generer-facture/')
        self.assertEqual(gen.status_code, 201, gen.data)
        fid = gen.data['id']
        pay = api.post(
            f'/api/django/ventes/factures/{fid}/enregistrer-paiement/',
            {'montant': '1000', 'date_paiement': '2026-06-13', 'mode': 'especes'},
            format='json',
        )
        self.assertEqual(pay.status_code, 201, pay.data)

    def test_commerciale_cannot_void_invoice(self):
        api = auth(self.meryem)
        fid = api.post(
            f'/api/django/ventes/devis/{self.devis.id}/generer-facture/').data['id']
        r = api.post(f'/api/django/ventes/factures/{fid}/annuler/')
        self.assertEqual(r.status_code, 403)

    def test_owner_can_void_invoice(self):
        api = auth(self.owner)
        fid = api.post(
            f'/api/django/ventes/devis/{self.devis.id}/generer-facture/').data['id']
        r = api.post(f'/api/django/ventes/factures/{fid}/annuler/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Paiement.objects.count(), 0)


class TestSurPaiementGuard(TestCase):
    """Garde sur-paiement : un encaissement > reste à payer est refusé."""

    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.resp = User.objects.create_user(
            username='sp_resp', password='x', role_legacy='responsable',
            company=self.company,
        )
        self.api = auth(self.resp)
        self.devis = make_accepted_devis(self.company, self.client_obj)
        # Acompte 30 % de 17 000 = 5 100 TTC.
        self.acompte = Facture.objects.get(pk=self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/generer-facture/'
        ).data['id'])

    def _pay(self, montant):
        return self.api.post(
            f'/api/django/ventes/factures/{self.acompte.id}/enregistrer-paiement/',
            {'montant': montant, 'date_paiement': '2026-06-13',
             'mode': 'virement'},
            format='json',
        )

    def test_overpayment_rejected(self):
        r = self._pay('6000')  # > 5 100
        self.assertEqual(r.status_code, 400)
        self.assertIn('dépasse', r.data['detail'])
        self.assertEqual(Paiement.objects.count(), 0)

    def test_exact_remaining_passes(self):
        r = self._pay('5100')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['statut'], 'payee')

    def test_partial_then_overpayment_rejected(self):
        self.assertEqual(self._pay('3000').status_code, 201)
        r = self._pay('3000')  # reste 2 100 → refusé
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Paiement.objects.count(), 1)

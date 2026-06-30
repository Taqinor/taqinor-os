"""DC37 — réconciliation série-à-la-réception → sav.Equipement (par produit).

Le selector `reconcile_serials_to_equipements` relie les numéros de série
capturés à la réception (FG61, `stock.LigneReceptionFournisseur.numeros_serie`)
au parc installé (`sav.Equipement`), par produit + série, scopé société.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.sav.models import Equipement
from apps.sav import selectors


def _company(slug='dc37-co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': 'DC37'})
    return company


def _produit(company, nom='Onduleur', sku='OND'):
    return Produit.objects.create(
        company=company, nom=nom, sku=sku,
        prix_achat=Decimal('100'), prix_vente=Decimal('200'))


def _installation(company, ref='CHT-DC37'):
    client = Client.objects.create(
        company=company, nom='Cli', prenom='T',
        email=f'c-{company.id}-{ref}@example.invalid')
    return Installation.objects.create(company=company, reference=ref, client=client)


class ReconcileSerialsTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.produit = _produit(self.company)
        self.inst = _installation(self.company)
        # Deux unités posées avec série, du même produit.
        self.eq1 = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst,
            numero_serie='SN-100')
        self.eq2 = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst,
            numero_serie='SN-200')

    def test_matched_and_unmatched_split(self):
        res = selectors.reconcile_serials_to_equipements(
            self.company, self.produit.id, ['SN-100', 'SN-200', 'SN-999'])
        self.assertEqual(res['matched'], {
            'SN-100': self.eq1.id, 'SN-200': self.eq2.id})
        self.assertEqual(res['unmatched'], ['SN-999'])

    def test_empty_serials_returns_empty(self):
        self.assertEqual(
            selectors.reconcile_serials_to_equipements(self.company, self.produit.id, None),
            {'matched': {}, 'unmatched': []})
        self.assertEqual(
            selectors.reconcile_serials_to_equipements(self.company, self.produit.id, []),
            {'matched': {}, 'unmatched': []})

    def test_whitespace_and_duplicates_normalized(self):
        res = selectors.reconcile_serials_to_equipements(
            self.company, self.produit.id, ['  SN-100 ', 'SN-100', ' ', None])
        self.assertEqual(res['matched'], {'SN-100': self.eq1.id})
        self.assertEqual(res['unmatched'], [])

    def test_match_requires_same_produit(self):
        autre = _produit(self.company, nom='Batterie', sku='BAT')
        res = selectors.reconcile_serials_to_equipements(
            self.company, autre.id, ['SN-100'])
        # Même série mais autre produit → non réconcilié.
        self.assertEqual(res['matched'], {})
        self.assertEqual(res['unmatched'], ['SN-100'])

    def test_tenant_isolation(self):
        other = _company(slug='dc37-co-2')
        res = selectors.reconcile_serials_to_equipements(
            other, self.produit.id, ['SN-100'])
        # La société B ne voit pas le parc de A.
        self.assertEqual(res['matched'], {})
        self.assertEqual(res['unmatched'], ['SN-100'])

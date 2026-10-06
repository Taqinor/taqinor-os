"""ASTK11 (D-ASTK-2) — montants des factures fournisseur servis UNIQUEMENT avec
`prix_achat_voir`, et fermeture du contournement d'AUD419.

Rejoue TEN-7 (factures-fournisseur list / comptes-a-payer / en-exception :
200 + montants pour un Commercial) et TEN-10 (compte légacy « normal » et
Viewer : paiements-fournisseur 403 MAIS factures-fournisseur 200 avec
`date_paiement` imbriqué).

Source réelle : `can_view_buy_prices` / `is_responsable` (aucun mock).

Run :
    python manage.py test apps.stock.test_astk_prix_achat_factures -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.stock.models import (
    FactureFournisseur, Fournisseur, LigneFactureFournisseur,
    PaiementFournisseur,
)
from authentication.models import Company

User = get_user_model()

BASES = ('/api/django/stock/factures-fournisseur/',
         '/api/django/achats/factures-fournisseur/')
CLES_INTERDITES = {
    'prix_unitaire_ht', 'montant_ht', 'montant_tva', 'montant_ttc',
    'montant_ttc_devise', 'solde_du', 'total_paye', 'paiements',
    'date_paiement', 'total_ht', 'total_tva',
}


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _cles(obj):
    trouvees = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            trouvees.add(k)
            trouvees |= _cles(v)
    elif isinstance(obj, list):
        for v in obj:
            trouvees |= _cles(v)
    return trouvees


def _rows(data):
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class PrixAchatFacturesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASTK11', slug='astk11-co')
        perms = dict(CANONICAL_SYSTEM_ROLES)

        def _role_user(nom):
            role = Role.objects.create(
                company=self.company, nom=nom, permissions=perms[nom])
            return User.objects.create_user(
                username=f'astk11-{nom.lower()}', password='x',
                company=self.company, role=role)

        self.commercial = _role_user('Commercial')
        self.viewer = _role_user('Viewer')
        self.admin = _role_user('Administrateur')
        self.assertFalse(self.commercial.can_view_buy_prices)
        self.assertFalse(self.viewer.can_view_buy_prices)
        self.assertTrue(self.admin.can_view_buy_prices)
        self.legacy = User.objects.create_user(
            username='astk11-legacy', password='x', company=self.company,
            role_legacy='normal')
        self.assertTrue(self.legacy.can_view_buy_prices)
        self.assertFalse(self.legacy.is_responsable)

        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK11', type='service')
        self.facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-ASTK11-1',
            fournisseur=self.fournisseur,
            date_facture=datetime.date(2026, 9, 1),
            montant_ht=Decimal('833.33'), montant_tva=Decimal('166.67'),
            montant_ttc=Decimal('1000'))
        LigneFactureFournisseur.objects.create(
            facture=self.facture, designation='Prestation', quantite=1,
            prix_unitaire_ht=Decimal('833.33'))
        PaiementFournisseur.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('400'), date_paiement=datetime.date(2026, 9, 10))

    def test_list_retrieve_sans_montants(self):
        for base in BASES:
            for user in (self.commercial, self.viewer):
                api = _api(user)
                rep = api.get(base)
                self.assertEqual(rep.status_code, 200, base)
                rows = _rows(rep.data)
                self.assertEqual(len(rows), 1)
                self.assertFalse(CLES_INTERDITES & _cles(rows),
                                 (base, CLES_INTERDITES & _cles(rows)))
                self.assertEqual(rows[0]['reference'], 'FF-ASTK11-1')
                rep = api.get(f'{base}{self.facture.pk}/')
                self.assertEqual(rep.status_code, 200)
                self.assertFalse(CLES_INTERDITES & _cles(rep.data))
                self.assertNotIn(b'date_paiement', rep.content)

    def test_comptes_a_payer_et_en_exception_403(self):
        for base in BASES:
            for user in (self.commercial, self.viewer):
                api = _api(user)
                self.assertEqual(
                    api.get(f'{base}comptes-a-payer/').status_code, 403)
                self.assertEqual(
                    api.get(f'{base}en-exception/').status_code, 403)

    def test_paiements_imbriques_masques(self):
        # TEN-10 — légacy « normal » : paiements-fournisseur 403 (AUD419)
        # ET plus de règlements imbriqués dans la facture.
        api = _api(self.legacy)
        self.assertEqual(
            api.get('/api/django/stock/paiements-fournisseur/').status_code,
            403)
        rep = api.get(f'{BASES[0]}{self.facture.pk}/')
        self.assertEqual(rep.status_code, 200)
        self.assertNotIn('paiements', rep.data)
        self.assertNotIn(b'date_paiement', rep.content)
        # Le légacy garde ses montants (repli can_view_buy_prices).
        self.assertEqual(Decimal(str(rep.data['montant_ttc'])),
                         Decimal('1000'))
        # Viewer : règlements imbriqués absents, endpoints paiements 403.
        api = _api(self.viewer)
        self.assertEqual(
            api.get('/api/django/stock/paiements-fournisseur/').status_code,
            403)
        rep = api.get(f'{BASES[0]}{self.facture.pk}/')
        self.assertNotIn('paiements', rep.data)

    def test_paiements_action_get_403_sans_prix(self):
        rep = _api(self.commercial).get(
            f'{BASES[0]}{self.facture.pk}/paiements/')
        self.assertEqual(rep.status_code, 403)

    def test_paiements_fournisseur_liste_403_pour_commercial(self):
        rep = _api(self.commercial).get(
            '/api/django/stock/paiements-fournisseur/')
        self.assertEqual(rep.status_code, 403)
        self.assertNotIn(b'montant', rep.content)

    def test_administrateur_inchange(self):
        api = _api(self.admin)
        for base in BASES:
            rep = api.get(f'{base}{self.facture.pk}/')
            self.assertEqual(rep.status_code, 200)
            self.assertEqual(Decimal(str(rep.data['montant_ttc'])),
                             Decimal('1000'))
            self.assertEqual(len(rep.data['paiements']), 1)
            self.assertIn('solde_du', rep.data)
            self.assertIn('prix_unitaire_ht', rep.data['lignes'][0])
            self.assertEqual(
                api.get(f'{base}comptes-a-payer/').status_code, 200)
            self.assertEqual(
                api.get(f'{base}en-exception/').status_code, 200)
        self.assertEqual(
            api.get('/api/django/stock/paiements-fournisseur/').status_code,
            200)

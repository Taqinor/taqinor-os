"""XPUR1 — Documents de conformité fournisseur + gate d'achat/paiement.

Couvre :
  * un fournisseur avec ARF expirée déclenche le warning à la création BCF ;
  * le blocage paiement (paramétrable, défaut OFF) refuse le PaiementFournisseur
    quand un document OBLIGATOIRE manque/est expiré, no-op si OFF ;
  * multi-tenant (documents scopés société) ;
  * notify_expiring_conformite_documents best-effort.

Run:
    python manage.py test apps.stock.test_xpur1_conformite_fournisseur -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AchatsParametres, DocumentConformiteFournisseur,
    FactureFournisseur, Fournisseur, Produit,
)
from apps.stock.services import (
    bcf_warning_conformite, check_paiement_conformite_gate,
    fournisseur_conformite_manquante, notify_expiring_conformite_documents,
)

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None, role_legacy='responsable'):
    role = None
    if permissions is not None:
        role = Role.objects.create(
            company=company, nom=f'r-{username}', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy=role_legacy)


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xpur1Base(TestCase):
    def setUp(self):
        self.company = _company('xpur1-co')
        self.user = _user(
            self.company, 'xpur1-user',
            permissions=['stock_modifier', 'stock_voir', 'prix_achat_voir',
                         # ASTK17-20 (D-ASTK-3) : l'acheteur porte les codes achats.
                         'achats_commander', 'achats_receptionner',
                         'achats_payer', 'catalogue_prix_modifier'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Panneaux Maroc')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='PV-XPUR1',
            prix_vente=Decimal('1000'), prix_achat=Decimal('600'))

    def _pieces_requises_valides(self, sauf=()):
        # ASTK188 — « en règle » = les 4 TYPES requis présents ET valides.
        for type_doc in ('arf', 'cnss', 'rc', 'assurance'):
            if type_doc in sauf:
                continue
            DocumentConformiteFournisseur.objects.create(
                company=self.company, fournisseur=self.fournisseur,
                type_document=type_doc,
                date_expiration=timezone.now().date() + timedelta(days=90),
                obligatoire=True)


class TestConformiteSelector(Xpur1Base):
    def test_fournisseur_sans_document_non_conforme(self):
        # ASTK188 — changé : sans aucune pièce, les 4 types requis manquent
        # (XPUR1 le disait « en règle »).
        problemes = fournisseur_conformite_manquante(self.fournisseur)
        self.assertEqual({p['type_document'] for p in problemes},
                         {'arf', 'cnss', 'rc', 'assurance'})
        self.assertIsNotNone(bcf_warning_conformite(self.fournisseur))

    def test_fournisseur_en_regle(self):
        self._pieces_requises_valides()
        self.assertEqual(fournisseur_conformite_manquante(self.fournisseur), [])
        self.assertIsNone(bcf_warning_conformite(self.fournisseur))

    def test_arf_expiree_remonte(self):
        DocumentConformiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            type_document=DocumentConformiteFournisseur.Type.ARF,
            date_expiration=timezone.now().date() - timedelta(days=5),
            obligatoire=True)
        self._pieces_requises_valides(sauf=('arf',))
        problemes = fournisseur_conformite_manquante(self.fournisseur)
        self.assertEqual(len(problemes), 1)
        self.assertEqual(problemes[0]['type_document'], 'arf')
        self.assertEqual(problemes[0]['motif'], 'expiré')
        self.assertIsNotNone(bcf_warning_conformite(self.fournisseur))

    def test_document_autre_type_ignore(self):
        # ASTK188 — une pièce « autre » ne couvre aucun type requis et ne
        # crée aucun problème de plus.
        self._pieces_requises_valides()
        DocumentConformiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            type_document=DocumentConformiteFournisseur.Type.AUTRE,
            date_expiration=timezone.now().date() - timedelta(days=5),
            obligatoire=False)
        self.assertEqual(fournisseur_conformite_manquante(self.fournisseur), [])

    def test_document_valide_ignore(self):
        DocumentConformiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            type_document=DocumentConformiteFournisseur.Type.ARF,
            date_expiration=timezone.now().date() + timedelta(days=90),
            obligatoire=True)
        types = {p['type_document'] for p in
                 fournisseur_conformite_manquante(self.fournisseur)}
        self.assertNotIn('arf', types)


class TestBcfWarningEndpoint(Xpur1Base):
    def test_bcf_creation_includes_warning_when_expired(self):
        DocumentConformiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            type_document=DocumentConformiteFournisseur.Type.ARF,
            date_expiration=timezone.now().date() - timedelta(days=1),
            obligatoire=True)
        resp = self.api.post('/api/django/stock/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'lignes': [{
                'produit': self.produit.id, 'quantite': 5,
                'prix_achat_unitaire': '600',
            }],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('conformite_warning', resp.data)

    def test_bcf_creation_no_warning_when_compliant(self):
        self._pieces_requises_valides()
        resp = self.api.post('/api/django/stock/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'lignes': [{
                'produit': self.produit.id, 'quantite': 5,
                'prix_achat_unitaire': '600',
            }],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertNotIn('conformite_warning', resp.data)


class TestPaiementGate(Xpur1Base):
    def setUp(self):
        super().setUp()
        self.facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR1-0001',
            fournisseur=self.fournisseur, montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'))

    def test_gate_off_by_default_allows_payment(self):
        DocumentConformiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            type_document=DocumentConformiteFournisseur.Type.ARF,
            date_expiration=timezone.now().date() - timedelta(days=1),
            obligatoire=True)
        # No exception raised — service is a no-op with the default OFF flag.
        check_paiement_conformite_gate(self.company, self.fournisseur)
        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': self.facture.id, 'montant': '1200',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_gate_on_blocks_payment_when_expired(self):
        AchatsParametres.objects.create(
            company=self.company, bloquer_paiement_conformite_expiree=True)
        DocumentConformiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            type_document=DocumentConformiteFournisseur.Type.ARF,
            date_expiration=timezone.now().date() - timedelta(days=1),
            obligatoire=True)
        with self.assertRaises(ValueError):
            check_paiement_conformite_gate(self.company, self.fournisseur)
        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': self.facture.id, 'montant': '1200',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_gate_on_allows_payment_when_compliant(self):
        AchatsParametres.objects.create(
            company=self.company, bloquer_paiement_conformite_expiree=True)
        self._pieces_requises_valides()
        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': self.facture.id, 'montant': '1200',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)


class TestMultiTenantIsolation(Xpur1Base):
    def test_documents_scoped_to_company(self):
        other_company = _company('xpur1-co-2')
        other_fournisseur = Fournisseur.objects.create(
            company=other_company, nom='Autre Fournisseur')
        DocumentConformiteFournisseur.objects.create(
            company=other_company, fournisseur=other_fournisseur,
            type_document=DocumentConformiteFournisseur.Type.ARF,
            date_expiration=timezone.now().date() - timedelta(days=1),
            obligatoire=True)
        resp = self.api.get('/api/django/stock/documents-conformite-fournisseur/')
        self.assertEqual(resp.status_code, 200)
        ids = [d['id'] for d in resp.data.get(
            'results', resp.data if isinstance(resp.data, list) else [])]
        other_docs = DocumentConformiteFournisseur.objects.filter(
            company=other_company).values_list('id', flat=True)
        for oid in other_docs:
            self.assertNotIn(oid, ids)


class TestNotifyExpiring(Xpur1Base):
    def test_best_effort_never_raises(self):
        DocumentConformiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            type_document=DocumentConformiteFournisseur.Type.ARF,
            date_expiration=timezone.now().date() + timedelta(days=5),
            obligatoire=True)
        count = notify_expiring_conformite_documents(self.company, jours=30)
        self.assertGreaterEqual(count, 0)

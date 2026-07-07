"""XSTK7 — Rapport de traçabilité bout-en-bout (rappel fabricant).

Couvre :
  * une série connue rend la chaîne complète (réception → emplacement
    entrepôt → équipement installé/client), datée ;
  * une série inconnue → 404 ;
  * cross-company → rien (jamais de fuite) ;
  * un lot connu (XSTK6) rend sa propre chaîne (réception + emplacement) ;
  * lecture via selectors cibles (installations/sav), jamais leurs models.

Run:
    python manage.py test apps.stock.test_xstk7_tracabilite_serie -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, LotEntrepot, Produit, ReceptionFournisseur,
)
from apps.stock.selectors import trace_serie

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xstk7Base(TestCase):
    def setUp(self):
        self.company = _company('xstk7-co')
        self.user = _user(
            self.company, 'xstk7-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur XSTK7')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur XSTK7', sku='OND-XSTK7',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'))

    def _reception_avec_serie(
            self, numero_serie, reference='REC-XSTK7-0001'):
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-{reference}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=1,
            prix_achat_unitaire=Decimal('1000'), quantite_recue=1)
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=reference, bon_commande=bcf,
            statut=ReceptionFournisseur.Statut.CONFIRME)
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=ligne, produit=self.produit,
            quantite=1, numeros_serie=[numero_serie])
        return rec


class TestChaineComplete(Xstk7Base):
    def test_serie_connue_rend_chaine_reception(self):
        self._reception_avec_serie('SN-XSTK7-001')
        result = trace_serie(self.company, numero_serie='SN-XSTK7-001')
        self.assertIsNotNone(result)
        self.assertEqual(
            result['reception']['bcf_reference'], 'BCF-REC-XSTK7-0001')
        self.assertEqual(
            result['reception']['fournisseur_nom'], self.fournisseur.nom)

    def test_serie_avec_equipement_installe_rend_client(self):
        from apps.installations.models import Installation
        from apps.crm.models import Client
        from apps.sav.models import Equipement

        self._reception_avec_serie('SN-XSTK7-002')
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='XSTK7')
        installation = Installation.objects.create(
            company=self.company, reference='CH-XSTK7-0001', client=client)
        Equipement.objects.create(
            company=self.company, produit=self.produit,
            numero_serie='SN-XSTK7-002', installation=installation)
        result = trace_serie(self.company, numero_serie='SN-XSTK7-002')
        self.assertIsNotNone(result)
        self.assertEqual(
            result['equipement']['chantier_reference'], 'CH-XSTK7-0001')
        self.assertIn('XSTK7', result['equipement']['client_nom'])

    def test_serie_inconnue_404(self):
        result = trace_serie(self.company, numero_serie='SN-INCONNUE')
        self.assertIsNone(result)

    def test_cross_company_rien(self):
        other_co = _company('xstk7-autre')
        other_fournisseur = Fournisseur.objects.create(
            company=other_co, nom='Autre fournisseur')
        other_produit = Produit.objects.create(
            company=other_co, nom='Autre produit', sku='OND-AUTRE',
            prix_vente=Decimal('2000'))
        bcf = BonCommandeFournisseur.objects.create(
            company=other_co, reference='BCF-AUTRE-0001',
            fournisseur=other_fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=other_produit, quantite=1,
            prix_achat_unitaire=Decimal('1000'), quantite_recue=1)
        rec = ReceptionFournisseur.objects.create(
            company=other_co, reference='REC-AUTRE-0001', bon_commande=bcf,
            statut=ReceptionFournisseur.Statut.CONFIRME)
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=ligne, produit=other_produit,
            quantite=1, numeros_serie=['SN-AUTRE-001'])
        result = trace_serie(self.company, numero_serie='SN-AUTRE-001')
        self.assertIsNone(result)


class TestChaineLot(Xstk7Base):
    def test_lot_connu_rend_sa_chaine(self):
        LotEntrepot.objects.create(
            company=self.company, produit=self.produit,
            numero_lot='LOT-XSTK7-001', quantite_recue=10,
            quantite_restante=7,
            reference_reception='REC-XSTK7-LOT-0001')
        result = trace_serie(self.company, numero_lot='LOT-XSTK7-001')
        self.assertIsNotNone(result)
        self.assertEqual(
            result['reception']['reception_reference'],
            'REC-XSTK7-LOT-0001')
        self.assertEqual(result['emplacement']['statut'], 'en_stock')

    def test_lot_inconnu_none(self):
        result = trace_serie(self.company, numero_lot='LOT-INCONNU')
        self.assertIsNone(result)


class TestEndpoint(Xstk7Base):
    def test_endpoint_serie_connue(self):
        self._reception_avec_serie('SN-XSTK7-003')
        url = '/api/django/stock/produits/tracer/?serie=SN-XSTK7-003'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('reception', resp.data)

    def test_endpoint_sans_parametre_400(self):
        url = '/api/django/stock/produits/tracer/'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_serie_inconnue_404(self):
        url = '/api/django/stock/produits/tracer/?serie=SN-INCONNUE'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 404)

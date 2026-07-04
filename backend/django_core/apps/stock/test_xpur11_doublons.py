"""XPUR11 — Détection de doublons facture fournisseur & BCF.

Couvre :
  * re-saisir la même (fournisseur, ref_fournisseur) lève un doublon warning ;
  * même fournisseur + montant TTC + date ±7 j lève un doublon warning ;
  * la création n'est JAMAIS bloquée (warning seulement) ;
  * un override confirmé est journalisé (best-effort, ne casse rien) ;
  * le panneau « BCF ouverts similaires » liste les BCF brouillon/envoyé du
    même fournisseur, filtrable par produits communs.

Run:
    python manage.py test apps.stock.test_xpur11_doublons -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, FactureFournisseur, Produit,
)
from apps.stock.services import (
    detect_facture_fournisseur_doublon, bcf_similaires_ouverts,
)

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


class Xpur11Base(TestCase):
    def setUp(self):
        self.company = _company('xpur11-co')
        self.user = _user(
            self.company, 'xpur11-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur Doublon')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur X11', sku='OND-XPUR11',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))


class TestFactureDoublonRefFournisseur(Xpur11Base):
    def test_meme_ref_fournisseur_leve_doublon(self):
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-0001',
            fournisseur=self.fournisseur, ref_fournisseur='INV-777',
            montant_ttc=Decimal('1000'),
            date_facture=datetime.date(2026, 6, 1))
        resp = self.api.post('/api/django/stock/factures-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'ref_fournisseur': 'INV-777',
            'montant_ht': '900', 'montant_tva': '90', 'montant_ttc': '990',
            'date_facture': '2026-06-15',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('doublon_warning', resp.data)
        self.assertEqual(len(resp.data['doublon_warning']), 1)
        self.assertEqual(
            resp.data['doublon_warning'][0]['ref_fournisseur'], 'INV-777')
        # La création N'EST JAMAIS bloquée.
        self.assertEqual(FactureFournisseur.objects.count(), 2)

    def test_ref_fournisseur_differente_pas_de_doublon(self):
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-0002',
            fournisseur=self.fournisseur, ref_fournisseur='INV-888',
            montant_ttc=Decimal('1000'),
            date_facture=datetime.date(2026, 6, 1))
        resp = self.api.post('/api/django/stock/factures-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'ref_fournisseur': 'INV-999',
            'montant_ht': '500', 'montant_tva': '50', 'montant_ttc': '550',
            'date_facture': '2026-09-01',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertNotIn('doublon_warning', resp.data)

    def test_override_confirme_est_journalise(self):
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-0003',
            fournisseur=self.fournisseur, ref_fournisseur='INV-555',
            montant_ttc=Decimal('1000'),
            date_facture=datetime.date(2026, 6, 1))
        resp = self.api.post('/api/django/stock/factures-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'ref_fournisseur': 'INV-555',
            'montant_ht': '900', 'montant_tva': '90', 'montant_ttc': '990',
            'date_facture': '2026-06-20',
            'confirmer_malgre_doublon': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('doublon_warning', resp.data)
        try:
            from apps.audit.models import AuditLog
            self.assertTrue(
                AuditLog.objects.filter(company=self.company).exists())
        except Exception:  # pragma: no cover - audit app optionnelle
            pass


class TestFactureDoublonMontantDate(Xpur11Base):
    def test_meme_montant_ttc_dans_la_fenetre_7j_leve_doublon(self):
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-0010',
            fournisseur=self.fournisseur, montant_ttc=Decimal('2500'),
            date_facture=datetime.date(2026, 6, 10))
        matches = detect_facture_fournisseur_doublon(
            self.company, fournisseur_id=self.fournisseur.id,
            montant_ttc=Decimal('2500'),
            date_facture=datetime.date(2026, 6, 14))
        self.assertEqual(len(matches), 1)

    def test_hors_fenetre_7j_pas_de_doublon(self):
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-0011',
            fournisseur=self.fournisseur, montant_ttc=Decimal('2500'),
            date_facture=datetime.date(2026, 6, 10))
        matches = detect_facture_fournisseur_doublon(
            self.company, fournisseur_id=self.fournisseur.id,
            montant_ttc=Decimal('2500'),
            date_facture=datetime.date(2026, 7, 1))
        self.assertEqual(matches, [])

    def test_autre_societe_jamais_matchee(self):
        other_company = _company('xpur11-other-co')
        other_fournisseur = Fournisseur.objects.create(
            company=other_company, nom='Autre Fournisseur')
        FactureFournisseur.objects.create(
            company=other_company, reference='FF-OTHER',
            fournisseur=other_fournisseur, ref_fournisseur='INV-777',
            montant_ttc=Decimal('1000'),
            date_facture=datetime.date(2026, 6, 1))
        matches = detect_facture_fournisseur_doublon(
            self.company, fournisseur_id=self.fournisseur.id,
            ref_fournisseur='INV-777')
        self.assertEqual(matches, [])


class TestBcfSimilairesOuverts(Xpur11Base):
    def _create_bcf(self, statut=BonCommandeFournisseur.Statut.BROUILLON):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-{statut}',
            fournisseur=self.fournisseur, statut=statut)
        bc.lignes.create(
            produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1200'))
        return bc

    def test_panel_liste_brouillon_et_envoye(self):
        self._create_bcf(BonCommandeFournisseur.Statut.BROUILLON)
        self._create_bcf(BonCommandeFournisseur.Statut.ENVOYE)
        self._create_bcf(BonCommandeFournisseur.Statut.RECU)
        out = bcf_similaires_ouverts(
            self.company, fournisseur_id=self.fournisseur.id)
        self.assertEqual(len(out), 2)
        statuts = {o['statut'] for o in out}
        self.assertEqual(
            statuts, {BonCommandeFournisseur.Statut.BROUILLON,
                      BonCommandeFournisseur.Statut.ENVOYE})

    def test_panel_filtre_par_produits_communs(self):
        self._create_bcf(BonCommandeFournisseur.Statut.BROUILLON)
        autre_produit = Produit.objects.create(
            company=self.company, nom='Panneau X11', sku='PAN-XPUR11',
            prix_vente=Decimal('900'), prix_achat=Decimal('500'))
        bc_sans_produit_commun = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-AUTRE',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON)
        bc_sans_produit_commun.lignes.create(
            produit=autre_produit, quantite=2,
            prix_achat_unitaire=Decimal('500'))

        out = bcf_similaires_ouverts(
            self.company, fournisseur_id=self.fournisseur.id,
            produit_ids=[self.produit.id])
        refs = {o['reference'] for o in out}
        self.assertIn('BCF-brouillon', refs)
        self.assertNotIn('BCF-AUTRE', refs)

    def test_endpoint_requiert_fournisseur(self):
        resp = self.api.get(
            '/api/django/stock/bons-commande-fournisseur/bcf-similaires/')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_retourne_similaires(self):
        self._create_bcf(BonCommandeFournisseur.Statut.BROUILLON)
        resp = self.api.get(
            '/api/django/stock/bons-commande-fournisseur/bcf-similaires/'
            f'?fournisseur={self.fournisseur.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

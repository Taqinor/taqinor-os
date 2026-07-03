"""XPUR7 — Dates de livraison prévues, accusé fournisseur & OTD réel.

Couvre :
  * un BCF confirmé au 10 reçu le 15 sort 5 j de retard dans l'OTD ;
  * l'alerte « BCF en retard » remonte via bcf_en_retard_list ;
  * la date demandée d'origine est préservée après confirmer() ;
  * date_livraison_prevue pré-calculée depuis PrixFournisseur.

Run:
    python manage.py test apps.stock.test_xpur7_otd_livraison -v 2
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
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    PrixFournisseur, Produit, ReceptionFournisseur, LigneReceptionFournisseur,
)
from apps.stock.services import bcf_en_retard, bcf_en_retard_list, otd_stats

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


class Xpur7Base(TestCase):
    def setUp(self):
        self.company = _company('xpur7-co')
        self.user = _user(
            self.company, 'xpur7-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur OTD')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur OTD', sku='OND-XPUR7',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))


class TestDateLivraisonPrevuePrecalcul(Xpur7Base):
    def test_prefill_from_prix_fournisseur_delai(self):
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('1200'),
            delai_livraison_jours=10)
        resp = self.api.post('/api/django/stock/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'date_commande': '2026-06-01',
            'lignes': [{
                'produit': self.produit.id, 'quantite': 5,
                'prix_achat_unitaire': '1200',
            }],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['date_livraison_prevue'], '2026-06-11')

    def test_no_delai_known_no_prefill(self):
        resp = self.api.post('/api/django/stock/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'date_commande': '2026-06-01',
            'lignes': [{
                'produit': self.produit.id, 'quantite': 5,
                'prix_achat_unitaire': '1200',
            }],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data['date_livraison_prevue'])

    def test_explicit_date_not_overridden(self):
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('1200'),
            delai_livraison_jours=10)
        resp = self.api.post('/api/django/stock/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'date_commande': '2026-06-01',
            'date_livraison_prevue': '2026-07-01',
            'lignes': [{
                'produit': self.produit.id, 'quantite': 5,
                'prix_achat_unitaire': '1200',
            }],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['date_livraison_prevue'], '2026-07-01')


class TestConfirmerAccuse(Xpur7Base):
    def _bcf(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-XPUR7-0001',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_livraison_prevue=datetime.date(2026, 6, 10))
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1200'))
        return bc

    def test_confirmer_sets_date_and_numero_preserves_original(self):
        bc = self._bcf()
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/confirmer/',
            {'date_confirmee_fournisseur': '2026-06-15',
             'numero_confirmation_fournisseur': 'ACK-9981'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['date_confirmee_fournisseur'], '2026-06-15')
        self.assertEqual(
            resp.data['numero_confirmation_fournisseur'], 'ACK-9981')
        # Original requested date untouched.
        self.assertEqual(resp.data['date_livraison_prevue'], '2026-06-10')

    def test_confirmer_requires_date(self):
        bc = self._bcf()
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/confirmer/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


class TestOtdAndLateAlert(Xpur7Base):
    def _bcf_confirme(self, date_confirmee):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-XPUR7-0002',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_confirmee_fournisseur=date_confirmee)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1200'), quantite_recue=5)
        return bc

    def test_otd_reports_5_days_late(self):
        bc = self._bcf_confirme(datetime.date(2026, 6, 10))
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-XPUR7-0001',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=datetime.date(2026, 6, 15))
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=bc.lignes.first(),
            produit=self.produit, quantite=5)
        stats = otd_stats(self.company, self.fournisseur)
        self.assertEqual(stats['otd_ecart_moyen_jours'], 5.0)
        self.assertEqual(stats['otd_a_lheure_pct'], 0.0)

    def test_otd_on_time_delivery(self):
        bc = self._bcf_confirme(datetime.date(2026, 6, 10))
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-XPUR7-0002',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=datetime.date(2026, 6, 8))
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=bc.lignes.first(),
            produit=self.produit, quantite=5)
        stats = otd_stats(self.company, self.fournisseur)
        self.assertEqual(stats['otd_a_lheure_pct'], 100.0)

    def test_no_confirmed_date_returns_none(self):
        stats = otd_stats(self.company, self.fournisseur)
        self.assertIsNone(stats['otd_ecart_moyen_jours'])

    def test_performance_endpoint_includes_otd_fields(self):
        resp = self.api.get(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/performance/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('otd_ecart_moyen_jours', resp.data)
        self.assertIn('otd_a_lheure_pct', resp.data)


class TestBcfEnRetard(Xpur7Base):
    def test_envoye_past_prevue_not_fully_received_is_late(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-XPUR7-0003',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_livraison_prevue=datetime.date(2026, 1, 1))
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1200'))
        self.assertTrue(
            bcf_en_retard(bc, a_la_date=datetime.date(2026, 6, 1)))
        self.assertIn(bc, bcf_en_retard_list(
            self.company, a_la_date=datetime.date(2026, 6, 1)))

    def test_brouillon_never_late(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-XPUR7-0004',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON,
            date_livraison_prevue=datetime.date(2026, 1, 1))
        self.assertFalse(
            bcf_en_retard(bc, a_la_date=datetime.date(2026, 6, 1)))

    def test_fully_received_never_late(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-XPUR7-0005',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_livraison_prevue=datetime.date(2026, 1, 1))
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1200'), quantite_recue=5)
        self.assertFalse(
            bcf_en_retard(bc, a_la_date=datetime.date(2026, 6, 1)))

    def test_en_retard_endpoint(self):
        BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-XPUR7-0006',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_livraison_prevue=datetime.date(2020, 1, 1))
        resp = self.api.get(
            '/api/django/stock/bons-commande-fournisseur/en-retard/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertGreaterEqual(len(resp.data), 1)

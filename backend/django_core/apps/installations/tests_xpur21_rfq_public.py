"""XPUR21 — réponse fournisseur en ligne à la RFQ (sans login).

Couvre :
  * le lien tokenisé public (GET) affiche la RFQ sans prix interne d'autrui ;
  * le POST crée l'offre du fournisseur (première soumission) ;
  * une re-soumission (idempotent) MET À JOUR la même offre (pas de doublon) ;
  * un token invalide/expiré/révoqué renvoie 404 ;
  * l'isolation inter-fournisseurs : jamais les offres des autres visibles ;
  * une RFQ clôturée refuse une nouvelle soumission.

Run :
    python manage.py test apps.installations.tests_xpur21_rfq_public -v2
"""
import itertools
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.installations.models import RFQ, RFQOffre, RFQConsultation

_seq = itertools.count(1)
BASE = '/api/django/public/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xpur21-co-{n}', defaults={'nom': nom or f'XPUR21 Co {n}'})
    return company


def make_fournisseur(company, nom='SolarImport'):
    from apps.stock.models import Fournisseur
    return Fournisseur.objects.create(company=company, nom=nom)


class TestPublicRFQResponse(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.company = make_company()
        self.rfq = RFQ.objects.create(
            company=self.company, reference='RFQ-XPUR21-1', objet='Panneaux',
            date_limite_reponse=timezone.localdate() + timedelta(days=7))
        self.f1 = make_fournisseur(self.company, nom='F1')
        self.f2 = make_fournisseur(self.company, nom='F2')
        self.c1 = RFQConsultation.objects.create(
            company=self.company, rfq=self.rfq, fournisseur=self.f1)
        self.c2 = RFQConsultation.objects.create(
            company=self.company, rfq=self.rfq, fournisseur=self.f2)

    def test_get_public_payload_no_login(self):
        r = self.api.get(f'{BASE}/rfq/{self.c1.token}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['reference'], self.rfq.reference)
        self.assertIsNone(r.data['offre'])

    def test_post_creates_offer(self):
        r = self.api.post(f'{BASE}/rfq/{self.c1.token}/', {
            'montant_ht': '95000', 'delai_jours': 15, 'validite_jours': 30,
            'note': 'Livraison rapide possible',
        })
        self.assertEqual(r.status_code, 200, r.data)
        self.c1.refresh_from_db()
        self.assertIsNotNone(self.c1.offre_id)
        offre = self.c1.offre
        self.assertEqual(float(offre.montant_ht), 95000.0)
        self.assertEqual(offre.fournisseur_id, self.f1.id)

    def test_resubmit_updates_same_offer_idempotent(self):
        self.api.post(f'{BASE}/rfq/{self.c1.token}/', {'montant_ht': '90000'})
        self.c1.refresh_from_db()
        first_offre_id = self.c1.offre_id
        self.api.post(f'{BASE}/rfq/{self.c1.token}/', {'montant_ht': '85000'})
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.offre_id, first_offre_id)
        self.assertEqual(float(self.c1.offre.montant_ht), 85000.0)
        self.assertEqual(
            RFQOffre.objects.filter(rfq=self.rfq, fournisseur=self.f1).count(), 1)

    def test_invalid_token_404(self):
        r = self.api.get(f'{BASE}/rfq/does-not-exist/')
        self.assertEqual(r.status_code, 404)

    def test_expired_token_404(self):
        self.rfq.date_limite_reponse = timezone.localdate() - timedelta(days=1)
        self.rfq.save(update_fields=['date_limite_reponse'])
        r = self.api.get(f'{BASE}/rfq/{self.c1.token}/')
        self.assertEqual(r.status_code, 404)

    def test_revoked_token_404(self):
        self.c1.revoque = True
        self.c1.save(update_fields=['revoque'])
        r = self.api.get(f'{BASE}/rfq/{self.c1.token}/')
        self.assertEqual(r.status_code, 404)

    def test_isolation_no_other_offers_leaked(self):
        RFQOffre.objects.create(
            company=self.company, rfq=self.rfq, fournisseur=self.f2,
            montant_ht=77777)
        r = self.api.get(f'{BASE}/rfq/{self.c1.token}/')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('77777', str(r.data))

    def test_cloturee_rejects_new_submission(self):
        self.rfq.statut = RFQ.Statut.CLOTUREE
        self.rfq.save(update_fields=['statut'])
        r = self.api.post(
            f'{BASE}/rfq/{self.c1.token}/', {'montant_ht': '1000'})
        self.assertEqual(r.status_code, 400, r.data)

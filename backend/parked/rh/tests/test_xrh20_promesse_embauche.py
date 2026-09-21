"""Tests XRH20 — Promesse d'embauche / lettre d'offre PDF + e-sign interne.

Couvre :
* le PDF d'offre se génère (mocké — pas de WeasyPrint dans les tests) ;
* le candidat signe via le lien tokenisé (signature figée, horodatée),
  journalisée dans le chatter (« Offre acceptée ») ;
* token expiré → 400 côté signature ;
* token cross-tenant / inconnu → 404 ;
* re-signature d'une promesse déjà signée → refusée.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import (
    Candidature,
    CandidatureActivity,
    OuverturePoste,
    PromesseEmbauche,
)

User = get_user_model()

PROMESSES = '/api/django/rh/promesses-embauche/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


FAKE_PDF = b'%PDF-1.4 fake promesse'


class PromesseEmbaucheTests(TestCase):
    def setUp(self):
        self.co = make_company('promesse-a', 'A')
        self.rh = make_user(self.co, 'promesse-rh')
        self.ouverture = OuverturePoste.objects.create(
            company=self.co, intitule='Chef de projet solaire')
        self.cand = Candidature.objects.create(
            company=self.co, ouverture=self.ouverture, nom='Salma Rifai',
            etape=Candidature.Etape.OFFRE)
        self.promesse = PromesseEmbauche.objects.create(
            company=self.co, candidature=self.cand,
            poste_propose='Chef de projet solaire',
            type_contrat='cdi', salaire_propose=14000)

    def test_pdf_interne_se_genere(self):
        with mock.patch(
                'apps.rh.pdf.render_promesse_embauche_pdf',
                return_value=FAKE_PDF):
            resp = auth(self.rh).get(f'{PROMESSES}{self.promesse.id}/pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_candidat_signe_via_lien_tokenise(self):
        url = f'/api/django/rh/promesses-embauche/public/{self.promesse.token}/signer/'
        resp = self.client.post(url, {'signataire_nom': 'Salma Rifai'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'signee')
        self.assertEqual(resp.data['signataire_nom'], 'Salma Rifai')

        self.promesse.refresh_from_db()
        self.assertEqual(self.promesse.statut, 'signee')
        self.assertIsNotNone(self.promesse.date_signature)

        notes = CandidatureActivity.objects.filter(candidature=self.cand)
        self.assertTrue(any('Offre acceptée' in n.message for n in notes))

    def test_detail_public_consultable_sans_session(self):
        url = f'/api/django/rh/promesses-embauche/public/{self.promesse.token}/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['candidat_nom'], 'Salma Rifai')

    def test_token_expire_refuse_signature(self):
        self.promesse.expires_at = timezone.now() - timedelta(days=1)
        self.promesse.save(update_fields=['expires_at'])
        url = f'/api/django/rh/promesses-embauche/public/{self.promesse.token}/signer/'
        resp = self.client.post(url, {'signataire_nom': 'Salma Rifai'})
        self.assertEqual(resp.status_code, 400)

    def test_token_expire_404_detail(self):
        self.promesse.expires_at = timezone.now() - timedelta(days=1)
        self.promesse.save(update_fields=['expires_at'])
        url = f'/api/django/rh/promesses-embauche/public/{self.promesse.token}/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_token_inconnu_404(self):
        url = '/api/django/rh/promesses-embauche/public/tok_inconnu/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_resignature_refusee(self):
        url = f'/api/django/rh/promesses-embauche/public/{self.promesse.token}/signer/'
        self.client.post(url, {'signataire_nom': 'Salma Rifai'})
        resp = self.client.post(url, {'signataire_nom': 'Salma Rifai'})
        self.assertEqual(resp.status_code, 400)

    def test_isolation_societe_interne(self):
        co_b = make_company('promesse-b', 'B')
        rh_b = make_user(co_b, 'promesse-rh-b')
        resp = auth(rh_b).get(f'{PROMESSES}{self.promesse.id}/')
        self.assertEqual(resp.status_code, 404)

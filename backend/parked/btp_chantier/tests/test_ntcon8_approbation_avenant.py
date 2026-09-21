"""Tests NTCON8 — Approbation client de l'avenant (e-sign, lien public).

Couvre :
* ``faire-approuver/`` génère un lien public + expiration ;
* lien public expiré → 404 (jamais de fuite) ;
* signature capturée (IP/user-agent serveur), déclenche NTCON7 (facture) ;
* idempotent : un second appel sur un avenant déjà décidé → 400, aucun
  second impact (une seule facture créée).
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.btp_chantier.models import AvenantChantier, SignatureBtp

from .helpers import auth, make_chantier, make_client_crm, make_company, make_user

BASE = '/api/django/btp-chantier/avenants-chantier/'


class ApprobationAvenantPublicTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.client_crm = make_client_crm(self.co)
        self.chantier = make_chantier(self.co, client=self.client_crm)
        self.avenant = AvenantChantier.objects.create(
            company=self.co, chantier=self.chantier,
            reference='AVC-TEST-0001', description='Test NTCON8',
            montant_ht='7500.00')
        # Client public NON authentifié (pas ``self.client`` — le client de
        # test Django par défaut ne comprend pas ``format='json'``).
        self.public = APIClient()

    def test_faire_approuver_genere_lien(self):
        api = auth(self.user)
        resp = api.post(
            f'{BASE}{self.avenant.id}/faire-approuver/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['avenant']['statut'], 'soumis_client')
        self.assertIn('lien_public', resp.data)
        self.avenant.refresh_from_db()
        self.assertIsNotNone(self.avenant.token_expires_at)

    def test_lien_public_detail(self):
        self.avenant.statut = AvenantChantier.Statut.SOUMIS_CLIENT
        self.avenant.save(update_fields=['statut'])
        resp = self.public.get(
            f'{BASE}public/{self.avenant.token}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['reference'], self.avenant.reference)
        # Jamais de coût interne / autre ID exposé publiquement.
        self.assertNotIn('facture_id', resp.data)
        self.assertNotIn('budget_projet_id', resp.data)

    def test_lien_expire_404(self):
        self.avenant.statut = AvenantChantier.Statut.SOUMIS_CLIENT
        self.avenant.token_expires_at = timezone.now() - timedelta(days=1)
        self.avenant.save(update_fields=['statut', 'token_expires_at'])
        resp = self.public.get(f'{BASE}public/{self.avenant.token}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_lien_inconnu_404(self):
        resp = self.public.get(f'{BASE}public/jeton-inconnu/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_approuver_public_capture_signature_et_declenche_facture(self):
        self.avenant.statut = AvenantChantier.Statut.SOUMIS_CLIENT
        self.avenant.save(update_fields=['statut'])
        resp = self.public.post(
            f'{BASE}public/{self.avenant.token}/approuver/',
            {'signataire_nom': 'Client Test'}, format='json',
            HTTP_USER_AGENT='TestAgent/1.0')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['statut'], 'approuve')

        self.avenant.refresh_from_db()
        self.assertEqual(self.avenant.statut, AvenantChantier.Statut.APPROUVE)
        self.assertIsNotNone(self.avenant.facture_id)

        signature = SignatureBtp.objects.get(
            contexte='approbation_avenant', object_id=self.avenant.pk)
        self.assertEqual(signature.signataire_nom, 'Client Test')
        self.assertEqual(signature.user_agent, 'TestAgent/1.0')
        self.assertIsNone(signature.signataire)

    def test_approuver_public_sans_nom_refuse(self):
        self.avenant.statut = AvenantChantier.Statut.SOUMIS_CLIENT
        self.avenant.save(update_fields=['statut'])
        resp = self.public.post(
            f'{BASE}public/{self.avenant.token}/approuver/', {},
            format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_approuver_public_idempotent(self):
        self.avenant.statut = AvenantChantier.Statut.SOUMIS_CLIENT
        self.avenant.save(update_fields=['statut'])
        resp1 = self.public.post(
            f'{BASE}public/{self.avenant.token}/approuver/',
            {'signataire_nom': 'Client Test'}, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        resp2 = self.public.post(
            f'{BASE}public/{self.avenant.token}/approuver/',
            {'signataire_nom': 'Client Test'}, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

        from apps.ventes.models import Facture
        self.assertEqual(Facture.objects.filter(
            client=self.client_crm).count(), 1)
        self.assertEqual(SignatureBtp.objects.filter(
            contexte='approbation_avenant', object_id=self.avenant.pk).count(), 1)

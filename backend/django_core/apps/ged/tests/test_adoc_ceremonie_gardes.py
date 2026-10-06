"""ADOC76 — La cérémonie d'un destinataire se ferme dès que la demande n'est
plus en attente (410) ; seuls les rôles « signataire » signent (403 pour copie
et approbateur) ; creer-multi est validé (400 nommé, jamais 500).

Sources réelles : vue publique `public_signataire`, action `creer-multi`,
services GED ; aucun mock.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    Cabinet, DemandeSignatureDocument, Document, Folder, ROLE_COPIE,
    ROLE_SIGNATAIRE, ROUTAGE_PARALLELE, SIGNATAIRE_NOTIFIE, SIGNATURE_REFUSE,
)

User = get_user_model()


class CeremonieGardesBase(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.co_a, _ = Company.objects.get_or_create(
            slug='adoc76-a', defaults={'nom': 'Adoc76 A'})
        self.admin = User.objects.create_user(
            username='adoc76-admin', password='x', company=self.co_a,
            role_legacy='admin')
        cab = Cabinet.objects.create(company=self.co_a, nom='Admin')
        folder = Folder.objects.create(
            company=self.co_a, cabinet=cab, nom='Contrats')
        self.doc = Document.objects.create(
            company=self.co_a, folder=folder, nom='Contrat ADOC76')
        self.anon = APIClient()
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _circuit_parallele(self):
        return services.creer_demande_multi_signataires(
            self.doc, destinataires=[
                {'nom': 'A', 'email': 'a@x.ma', 'role': ROLE_SIGNATAIRE},
                {'nom': 'B', 'email': 'b@x.ma', 'role': ROLE_SIGNATAIRE},
                {'nom': 'C', 'email': 'c@x.ma', 'role': ROLE_COPIE}],
            company=self.co_a, routage=ROUTAGE_PARALLELE)

    def _signer(self, signataire):
        return self.anon.post(
            f'/api/django/ged/signataire/{signataire.token}/', {
                'action': 'signer', 'consentement': True,
                'signature_texte': signataire.nom}, format='json')


class CeremonieGardesTests(CeremonieGardesBase):
    def test_signer_apres_refus_global_410(self):
        demande = self._circuit_parallele()
        a = demande.signataires.get(nom='A')
        b = demande.signataires.get(nom='B')
        resp_refus = self.anon.post(
            f'/api/django/ged/signataire/{a.token}/',
            {'action': 'refuser', 'motif': 'Montant erroné'}, format='json')
        self.assertEqual(resp_refus.status_code, 200, resp_refus.data)
        resp = self._signer(b)
        self.assertEqual(resp.status_code, 410, resp.data)
        b.refresh_from_db()
        self.assertEqual(b.statut, SIGNATAIRE_NOTIFIE)
        self.assertEqual(b.hash_contenu, '')
        demande.refresh_from_db()
        self.assertEqual(demande.statut, SIGNATURE_REFUSE)

    def test_copie_ne_signe_pas_403(self):
        demande = self._circuit_parallele()
        copie = demande.signataires.get(nom='C')
        resp = self._signer(copie)
        self.assertEqual(resp.status_code, 403, resp.data)
        copie.refresh_from_db()
        self.assertEqual(copie.statut, SIGNATAIRE_NOTIFIE)

    def test_creer_multi_role_libre_400(self):
        resp = self.api.post(
            '/api/django/ged/demandes-signature/creer-multi/', {
                'document': self.doc.pk,
                'destinataires': [{'nom': 'X', 'role': 'Client'}]},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('destinataires', resp.data)
        self.assertFalse(DemandeSignatureDocument.objects.filter(
            document=self.doc).exists())

    def test_creer_multi_date_invalide_400(self):
        resp = self.api.post(
            '/api/django/ged/demandes-signature/creer-multi/', {
                'document': self.doc.pk,
                'destinataires': [{'nom': 'X'}],
                'expires_at': 'pas-une-date'},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('expires_at', resp.data)

    def test_circuit_sans_signataire_refuse(self):
        resp = self.api.post(
            '/api/django/ged/demandes-signature/creer-multi/', {
                'document': self.doc.pk,
                'destinataires': [{'nom': 'X', 'role': ROLE_COPIE}]},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        with self.assertRaises(ValueError):
            services.creer_demande_multi_signataires(
                self.doc, destinataires=[{'nom': 'X', 'role': ROLE_COPIE}],
                company=self.co_a)

    def test_creer_multi_ordre_invalide_400(self):
        resp = self.api.post(
            '/api/django/ged/demandes-signature/creer-multi/', {
                'document': self.doc.pk,
                'destinataires': [{'nom': 'X', 'ordre': 0}]},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

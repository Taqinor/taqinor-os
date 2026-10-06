"""ADOC65 — Chaque destinataire du circuit multi signe par la MÊME routine de
preuve que le mono (consentement, tracé, IP, UA, hash de la version signée,
champs requis de son rôle), stockée par destinataire et reprise au certificat.

Sources réelles : vue publique `public_signataire`, services GED, stockage
MinIO de test réel (la version signée est réellement stockée et relue pour
son hash) ; aucun mock interne.
"""
import hashlib

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    CHAMP_TYPE_TEXTE, Cabinet, ChampSignature, Document, Folder,
    SIGNATAIRE_NOTIFIE, SIGNATAIRE_SIGNE, SIGNATURE_SIGNE,
)

User = get_user_model()

CONTENU = b'%PDF-1.4\n%adoc65\n' + b'C' * 120
TRACE = 'data:image/png;base64,AAA'


class MultiPreuvesBase(TestCase):
    def setUp(self):
        self.co_a, _ = Company.objects.get_or_create(
            slug='adoc65-a', defaults={'nom': 'Adoc65 A'})
        self.admin = User.objects.create_user(
            username='adoc65-admin', password='x', company=self.co_a,
            role_legacy='admin')
        cab = Cabinet.objects.create(company=self.co_a, nom='Admin')
        folder = Folder.objects.create(
            company=self.co_a, cabinet=cab, nom='Contrats')
        self.doc = Document.objects.create(
            company=self.co_a, folder=folder, nom='Contrat multi')
        key, meta = services._store_bytes(CONTENU, mime='application/pdf')
        services.add_version(
            self.doc, file_key=key, company=self.co_a,
            filename=meta['filename'], size=len(CONTENU),
            mime='application/pdf')
        self.demande = services.creer_demande_multi_signataires(
            self.doc, destinataires=[
                {'nom': 'A', 'email': 'a@x.ma', 'role': 'signataire'}],
            company=self.co_a, created_by=self.admin)
        self.signataire = self.demande.signataires.get()
        self.champ = ChampSignature.objects.create(
            company=self.co_a, demande=self.demande,
            type_champ=CHAMP_TYPE_TEXTE, requis=True, role='signataire')
        self.url = f'/api/django/ged/signataire/{self.signataire.token}/'
        self.anon = APIClient()
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _signer(self, avec_champs=True):
        corps = {'action': 'signer', 'consentement': True,
                 'signature_tracee': TRACE}
        if avec_champs:
            corps['valeurs_champs'] = {str(self.champ.id): 'Gérant'}
        return self.anon.post(
            self.url, corps, format='json',
            HTTP_USER_AGENT='Adoc65Agent/1.0', REMOTE_ADDR='41.77.1.5')


class SignatureMultiPreuvesTests(MultiPreuvesBase):
    def test_signature_multi_conserve_les_preuves(self):
        resp = self._signer()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.signataire.refresh_from_db()
        self.assertEqual(self.signataire.statut, SIGNATAIRE_SIGNE)
        self.assertTrue(self.signataire.consentement_explicite)
        self.assertEqual(self.signataire.signature_tracee, TRACE)
        self.assertEqual(self.signataire.user_agent, 'Adoc65Agent/1.0')
        self.assertIsNotNone(self.signataire.adresse_ip)
        self.assertEqual(
            self.signataire.hash_contenu, hashlib.sha256(CONTENU).hexdigest())
        self.champ.refresh_from_db()
        self.assertEqual(self.champ.valeur, 'Gérant')
        # Persistance relue par l'API authentifiée.
        relu = self.api.get(
            f'/api/django/ged/signataires-demande/{self.signataire.pk}/')
        self.assertEqual(relu.status_code, 200, relu.data)
        self.assertEqual(relu.data['hash_contenu'], self.signataire.hash_contenu)
        self.assertEqual(relu.data['signature_tracee'], TRACE)
        self.assertTrue(relu.data['consentement_explicite'])
        # Complétion : la demande reçoit ses preuves (hash non vide).
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.statut, SIGNATURE_SIGNE)
        self.assertEqual(
            self.demande.hash_contenu, hashlib.sha256(CONTENU).hexdigest())

    def test_champ_requis_exige_en_multi(self):
        resp = self._signer(avec_champs=False)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('champs requis', resp.data['detail'])
        self.signataire.refresh_from_db()
        self.assertEqual(self.signataire.statut, SIGNATAIRE_NOTIFIE)
        self.assertEqual(self.signataire.hash_contenu, '')

    def test_payload_public_expose_les_champs_du_signataire(self):
        resp = self.anon.get(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual([c['id'] for c in resp.data['champs']],
                         [self.champ.id])

    def test_certificat_une_ligne_par_signataire(self):
        self.assertEqual(self._signer().status_code, 200)
        self.demande.refresh_from_db()
        html = services._certificat_html(self.demande)
        self.assertIn('Adoc65Agent/1.0', html)
        self.assertIn(hashlib.sha256(CONTENU).hexdigest(), html)
        self.assertIn('Tracée', html)
        self.assertNotIn('Non calculé', html)

    def test_verifier_certificat_hash_non_vide(self):
        self.assertEqual(self._signer().status_code, 200)
        self.demande.refresh_from_db()
        empreinte = services.memoriser_empreinte_certificat(self.demande)
        resp = self.anon.get(
            f'/api/django/ged/verifier-certificat/{empreinte}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            resp.data['hash_document'], hashlib.sha256(CONTENU).hexdigest())

"""ADOC78 — « signer-client » n'accepte qu'une data-URL PNG/JPEG base64 bornée.

Constat C-ADOC-042 (C6, S3) : n'importe quelle chaîne non vide était acceptée
(200, ``signe_le`` posé) puis injectée dans ``<img src>`` du PV / du BL — une
URL http/file était récupérée par le moteur PDF, la chaîne « null »
verrouillait le chantier par une signature parasite.

(Module à la racine de l'app : ``apps/installations/tests.py`` existe déjà.)

Run :
    python manage.py test apps.installations.test_adoc_signature_client_validee -v2
"""
import itertools
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.installations.signature_validation import SIGNATURE_MAX_CARACTERES
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
PNG = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAf'
       'FcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')


# Le gel GED au geste (ADOC71) est hors sujet ici : neutralisé.
@patch('apps.documents.builders.figer_documents_signes', return_value={})
class SignatureClientValideeTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'adoc78-co-{n}', nom=f'ADOC78 Co {n}')
        self.user = User.objects.create_user(
            username=f'adoc78-resp-{n}', password='x',
            company=self.company, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(
            company=self.company, nom='Tazi', prenom='Hind',
            telephone='+212600000078')
        self.chantier = Installation.objects.create(
            company=self.company, reference=f'CH-ADOC78-{n}', client=client,
            statut=Installation.Statut.INSTALLE,
            puissance_installee_kwc=Decimal('5.00'))

    def _post(self, signature):
        return self.api.post(
            f'/api/django/installations/chantiers/{self.chantier.pk}/'
            'signer-client/',
            {'signature_client': signature, 'signataire_nom': 'Hind Tazi'},
            format='json')

    def _assert_refus(self, signature):
        r = self._post(signature)
        self.assertEqual(r.status_code, 400, getattr(r, 'data', r))
        self.assertIn('signature_client', r.data)
        self.chantier.refresh_from_db()
        self.assertIsNone(self.chantier.signe_le)
        self.assertFalse(self.chantier.signature_client)

    def test_url_http_refusee_400(self, _figer):
        self._assert_refus('http://127.0.0.1:9/x.png')
        self._assert_refus('file:///etc/passwd')

    def test_chaine_null_refusee(self, _figer):
        self._assert_refus('null')
        self._assert_refus('data:image/svg+xml;base64,PHN2Zz4=')

    def test_data_url_png_acceptee(self, _figer):
        r = self._post(PNG)
        self.assertEqual(r.status_code, 200, r.data)
        self.chantier.refresh_from_db()
        self.assertEqual(self.chantier.signature_client, PNG)
        self.assertIsNotNone(self.chantier.signe_le)

    def test_taille_maximale(self, _figer):
        prefixe = 'data:image/png;base64,'
        trop = prefixe + 'A' * (SIGNATURE_MAX_CARACTERES - len(prefixe) + 4)
        self._assert_refus(trop)

    def test_signature_intervention_meme_validation(self, _figer):
        interv = Intervention.objects.create(
            company=self.company, installation=self.chantier,
            type_intervention='pose', created_by=self.user,
            technicien=self.user)
        url = (f'/api/django/installations/interventions/{interv.pk}/'
               'signer-client/')
        r = self.api.post(url, {'signature_client': 'http://evil/x.png'},
                          format='json')
        self.assertEqual(r.status_code, 400, getattr(r, 'data', r))
        interv.refresh_from_db()
        self.assertIsNone(interv.signe_le)
        r = self.api.post(url, {'signature_client': PNG}, format='json')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))

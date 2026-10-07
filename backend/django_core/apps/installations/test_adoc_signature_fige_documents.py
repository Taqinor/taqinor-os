"""ADOC71 — PV et BL figés en GED AU GESTE « signer-client ».

Constat C-ADOC-038 (C9, S2) — sonde CHANT #69 : sans téléchargement
intermédiaire, un PV signé puis un chantier modifié imprimait la NOUVELLE
puissance au premier GET (le gel ADOC70 n'avait lieu qu'au téléchargement).

Rendu WeasyPrint réel, GED et MinIO de test réels (aucun mock de la source).
(Module à la racine de l'app : ``apps/installations/tests.py`` existe déjà,
un paquet ``tests/`` le masquerait.)

Run :
    python manage.py test apps.installations.test_adoc_signature_fige_documents -v2
"""
import hashlib
import itertools
from decimal import Decimal
from unittest.mock import patch

import fitz
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.documents import builders
from apps.ged import services as ged_services
from apps.installations.models import Installation, InstallationActivity
from apps.records.storage import fetch_attachment
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
SIG_A = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAf'
         'FcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')
SIG_B = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAf'
         'FcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg==')


def _texte(contenu):
    doc = fitz.open(stream=contenu, filetype='pdf')
    try:
        return '\n'.join(page.get_text() for page in doc)
    finally:
        doc.close()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


class SignatureFigeDocumentsTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'adoc71-co-{n}', nom=f'ADOC71 Co {n}')
        self.user = User.objects.create_user(
            username=f'adoc71-resp-{n}', password='x',
            company=self.company, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Samir',
            telephone='+212600000071')
        self.chantier = Installation.objects.create(
            company=self.company, reference=f'CH-ADOC71-{n}', client=client,
            statut=Installation.Statut.INSTALLE,
            puissance_installee_kwc=Decimal('6.60'),
            site_adresse='12 rue Ancienne', site_ville='Rabat')

    def _url(self, route):
        return f'/api/django/installations/chantiers/{self.chantier.pk}/{route}/'

    def _signer(self, signature=SIG_A, **extra):
        return self.api.post(
            self._url('signer-client'),
            {'signature_client': signature, 'signataire_nom': 'Samir Alaoui',
             **extra}, format='json')

    def _modifier_chantier(self):
        Installation.objects.filter(pk=self.chantier.pk).update(
            puissance_installee_kwc=Decimal('8.00'),
            site_adresse='99 boulevard Nouveau')

    def _document(self, source_type):
        return ged_services.find_document_by_source(
            self.company, source_type=source_type, source_id=self.chantier.pk)

    def _octets_en_vigueur(self, document):
        version = document.versions.order_by('-version').first()
        data, err = fetch_attachment(version.file_key)
        self.assertIsNone(err)
        return data

    def _get_pv(self):
        r = self.api.get(
            f'/api/django/documents/chantiers/{self.chantier.pk}/pv-reception/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        return r.content

    def test_signer_client_fige_le_pv_a_l_instant(self):
        r = self._signer()
        self.assertEqual(r.status_code, 200, r.data)
        # GED relue juste après le POST : PV et BL déjà figés.
        pv_doc = self._document(builders.SOURCE_PV_RECEPTION)
        bl_doc = self._document(builders.SOURCE_BON_LIVRAISON)
        self.assertIsNotNone(pv_doc)
        self.assertIsNotNone(bl_doc)
        fige = self._octets_en_vigueur(pv_doc)

        self._modifier_chantier()
        servi = self._get_pv()

        self.assertEqual(_sha(servi), _sha(fige))
        texte = _texte(servi)
        self.assertIn('12 rue Ancienne', texte)
        self.assertNotIn('99 boulevard Nouveau', texte)
        self.assertNotIn('8.00', texte)
        self.assertEqual(pv_doc.versions.count(), 1)

    def test_resignature_motivee_cree_une_nouvelle_version(self):
        self.assertEqual(self._signer(SIG_A).status_code, 200)
        pv_doc = self._document(builders.SOURCE_PV_RECEPTION)
        self.assertEqual(pv_doc.versions.count(), 1)
        r = self._signer(SIG_B, motif_override_signature='Signature illisible')
        self.assertEqual(r.status_code, 200, r.data)
        pv_doc.refresh_from_db()
        self.assertEqual(pv_doc.versions.count(), 2)

    def test_panne_ged_n_empeche_pas_la_signature(self):
        with patch('apps.documents.builders.figer_documents_signes',
                   side_effect=RuntimeError('MinIO indisponible')), \
                self.assertLogs('apps.installations', level='WARNING'):
            r = self._signer()
        self.assertEqual(r.status_code, 200, r.data)
        self.chantier.refresh_from_db()
        self.assertIsNotNone(self.chantier.signe_le)
        notes = list(InstallationActivity.objects.filter(
            installation=self.chantier).values_list('body', flat=True))
        self.assertTrue(any('Signature client enregistrée' in (b or '')
                            for b in notes), notes)
        self.assertTrue(any('gel' in (b or '').lower() for b in notes), notes)
        # Repli ADOC70 : le premier GET fige.
        self._get_pv()
        self.assertIsNotNone(self._document(builders.SOURCE_PV_RECEPTION))

"""ADOC70 — PV / BL signés et attestation FIGÉS en GED (D-ADOC-2).

Constat C-ADOC-038 (S2) : PV et BL étaient régénérés à chaque téléchargement
depuis l'état LIVE du chantier — un PV « Signé le … — empreinte … » imprimait
les NOUVELLES valeurs après une modification du chantier ; l'attestation
portait la date du téléchargement (deux téléchargements = deux dates).

Rendu WeasyPrint réel, GED et MinIO de test réels (aucun mock de la source).
Dépend de ``ged.services.deposit_document(versionner_si_modifie=True)``
(ADOC61) pour la nouvelle version d'une re-signature / d'une régénération.

Run :
    python manage.py test apps.documents.tests.test_adoc_documents_signes_figes -v2
"""
import hashlib
import itertools
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import fitz
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.documents import builders
from apps.ged import services as ged_services
from apps.installations.models import Installation
from apps.records.storage import fetch_attachment
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/documents/chantiers'
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


class DocumentsSignesFigesTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'adoc70-co-{n}', nom=f'ADOC70 Co {n}')
        self.user = User.objects.create_user(
            username=f'adoc70-resp-{n}', password='x',
            company=self.company, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(
            company=self.company, nom='Berrada', prenom='Yassine',
            telephone='+212600000070')
        self.chantier = Installation.objects.create(
            company=self.company, reference=f'CH-ADOC70-{n}', client=client,
            statut=Installation.Statut.INSTALLE,
            puissance_installee_kwc=Decimal('5.00'),
            site_adresse='7 avenue Ancienne', site_ville='Fès')

    def _signer(self, signature=SIG_A, signe_le=None):
        Installation.objects.filter(pk=self.chantier.pk).update(
            signature_client=signature, signataire_nom='Yassine Berrada',
            signe_le=signe_le or timezone.now())
        self.chantier.refresh_from_db()

    def _get(self, route, **params):
        r = self.api.get(f'{BASE}/{self.chantier.pk}/{route}/', params)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        return r.content

    def _document(self, source_type):
        return ged_services.find_document_by_source(
            self.company, source_type=source_type, source_id=self.chantier.pk)

    def _octets_version_en_vigueur(self, document):
        version = document.versions.order_by('-version').first()
        data, err = fetch_attachment(version.file_key)
        self.assertIsNone(err)
        return data

    def _modifier_chantier(self):
        Installation.objects.filter(pk=self.chantier.pk).update(
            puissance_installee_kwc=Decimal('9.50'),
            site_adresse='99 boulevard Nouveau')
        self.chantier.refresh_from_db()

    def test_pv_signe_identique_apres_modification_du_chantier(self):
        self._signer()
        builders.figer_documents_signes(self.chantier)
        document = self._document(builders.SOURCE_PV_RECEPTION)
        self.assertIsNotNone(document)
        fige = self._octets_version_en_vigueur(document)

        self._modifier_chantier()
        servi = self._get('pv-reception')

        self.assertEqual(_sha(servi), _sha(fige))
        texte = _texte(servi)
        self.assertIn('7 avenue Ancienne', texte)
        self.assertNotIn('99 boulevard Nouveau', texte)
        self.assertNotIn('9.50', texte)
        self.assertIn('Signé le', texte)
        self.assertEqual(document.versions.count(), 1)

    def test_bl_signe_fige(self):
        self._signer()
        premier = self._get('bon-livraison')
        document = self._document(builders.SOURCE_BON_LIVRAISON)
        self.assertIsNotNone(document)
        self.assertEqual(
            _sha(self._octets_version_en_vigueur(document)), _sha(premier))

        self._modifier_chantier()
        second = self._get('bon-livraison')

        self.assertEqual(_sha(second), _sha(premier))
        self.assertNotIn('9.50', _texte(second))
        self.assertEqual(document.versions.count(), 1)

    def test_resignature_cree_une_nouvelle_version(self):
        self._signer(SIG_A)
        v1 = self._get('pv-reception')
        document = self._document(builders.SOURCE_PV_RECEPTION)
        self.assertEqual(document.versions.count(), 1)

        # AUD305 — re-signature motivée : nouvelle empreinte.
        self._signer(SIG_B, signe_le=timezone.now() + timedelta(minutes=5))
        v2 = self._get('pv-reception')

        self.assertNotEqual(_sha(v1), _sha(v2))
        document.refresh_from_db()
        self.assertEqual(document.versions.count(), 2)
        self.assertEqual(
            _sha(self._octets_version_en_vigueur(document)), _sha(v2))
        self.assertIn(builders.empreinte_signature(self.chantier), _texte(v2))

    def test_pv_signe_avant_le_correctif_mention_de_gel_tardif(self):
        signe_le = timezone.now() - timedelta(days=2)
        self._signer(signe_le=signe_le)
        texte = _texte(self._get('pv-reception'))
        self.assertIn('Figé le', texte)
        self.assertIn('après la signature du', texte)
        self.assertNotIn('empreinte', texte)

    def test_attestation_garde_sa_date_d_emission(self):
        t0 = date(2026, 10, 6)
        with patch('apps.documents.builders._aujourdhui', return_value=t0):
            premier = self._get('attestation', type='fin_travaux')
        with patch('apps.documents.builders._aujourdhui',
                   return_value=t0 + timedelta(days=30)):
            second = self._get('attestation', type='fin_travaux')
        self.assertEqual(_sha(premier), _sha(second))
        texte = _texte(second)
        self.assertIn('06/10/2026', texte)
        self.assertNotIn('05/11/2026', texte)
        document = self._document(
            builders._source_attestation('fin_travaux'))
        self.assertIsNotNone(document)
        self.assertEqual(document.custom_data.get('type'), 'fin_travaux')
        self.assertEqual(document.custom_data.get('date_emission'),
                         '2026-10-06')

    def test_regenerer_attestation_nouvelle_version(self):
        t0 = date(2026, 10, 6)
        with patch('apps.documents.builders._aujourdhui', return_value=t0):
            self._get('attestation', type='installation')
        with patch('apps.documents.builders._aujourdhui',
                   return_value=t0 + timedelta(days=30)):
            regen = self._get('attestation', type='installation', regenerer=1)
        self.assertIn('05/11/2026', _texte(regen))
        document = self._document(
            builders._source_attestation('installation'))
        self.assertEqual(document.versions.count(), 2)
        self.assertEqual(
            _sha(self._octets_version_en_vigueur(document)), _sha(regen))
        # Les deux types d'attestation ne se versionnent pas l'un sur l'autre.
        self.assertIsNone(self._document(
            builders._source_attestation('fin_travaux')))

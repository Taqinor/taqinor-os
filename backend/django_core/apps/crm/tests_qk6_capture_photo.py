"""QK6 — Photo de facture/compteur captée par le site → pièce jointe lead + OCR.

Couvre :
  - Une photo base64 du payload webhook devient une pièce jointe (records.
    Attachment) rattachée au lead, company forcée côté serveur ;
  - Dégradation douce : OCR OFF (défaut, keyless) → simple pièce jointe,
    aucun appel réseau, champs du lead intacts ;
  - OCR ON : tranche/consommation extraites pré-remplissent le lead
    (uniquement les champs vides) ;
  - Photo absente / base64 invalide → lead créé quand même, pas de crash.

Le stockage MinIO est mocké (store_attachment) : on teste le FLUX, pas boto3.
"""

import base64
import json
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from .intake_photo import attach_capture_photo
from .models import Lead, LeadActivity

SECRET = 'test-secret-qk6'

# Un « JPEG » minimal (magic bytes corrects pour records.storage).
FAKE_JPEG = b'\xff\xd8\xff\xe0' + b'0' * 120
FAKE_JPEG_B64 = base64.b64encode(FAKE_JPEG).decode('ascii')

FAKE_META = {
    'file_key': 'attachments/qk6-test.jpg',
    'filename': 'facture.jpg',
    'size': len(FAKE_JPEG),
    'mime': 'image/jpeg',
}


def payload_site(**extra):
    base = {
        'fullName': 'Salma Idrissi',
        'phoneE164': '+212662000222',
        'whatsappOptIn': False,
        'city': 'Marrakech',
        'roofType': 'villa',
        'billRange': '1500-3000',
        'consent': True,
        'qualified': True,
        'band': {'kwcLabel': '5 à 9 kWc', 'paybackLabel': '4 à 6 ans'},
        'page': '/devis/mon-toit',
    }
    base.update(extra)
    return base


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class WebhookCapturePhotoTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QK6 Co', slug='qk6-co')
        self.url = reverse('website-lead-webhook')

    def post(self, data):
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    @mock.patch('apps.records.storage.store_attachment',
                return_value=(dict(FAKE_META), None))
    def test_photo_devient_piece_jointe_du_lead(self, mock_store):
        res = self.post(payload_site(
            photo=FAKE_JPEG_B64, photoFilename='facture.jpg'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])

        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        att = Attachment.objects.get(
            content_type=ContentType.objects.get_for_model(Lead),
            object_id=lead.pk)
        # Multi-tenant : company du lead, forcée côté serveur.
        self.assertEqual(att.company, lead.company)
        self.assertEqual(att.company, self.company)
        self.assertEqual(att.filename, 'facture.jpg')
        self.assertEqual(att.mime, 'image/jpeg')
        self.assertIsNone(att.uploaded_by)
        mock_store.assert_called_once()
        # Tracée dans le chatter.
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body__contains='Photo').exists())

    @mock.patch('apps.crm.intake_photo._run_capture_ocr')
    @mock.patch('apps.records.storage.store_attachment',
                return_value=(dict(FAKE_META), None))
    def test_sans_cle_ocr_degrade_en_simple_piece_jointe(
            self, mock_store, mock_ocr):
        """OCR OFF (défaut / keyless) : pièce jointe créée, AUCUN appel OCR,
        champs énergie du lead intacts."""
        res = self.post(payload_site(photo=FAKE_JPEG_B64))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])

        from apps.records.models import Attachment
        self.assertEqual(Attachment.objects.count(), 1)
        mock_ocr.assert_not_called()
        self.assertIsNone(lead.conso_mensuelle_kwh)
        self.assertIsNone(lead.tranche_onee)

    @mock.patch('apps.records.storage.store_attachment')
    def test_data_url_acceptee(self, mock_store):
        mock_store.return_value = (dict(FAKE_META), None)
        res = self.post(payload_site(
            photoBase64='data:image/jpeg;base64,' + FAKE_JPEG_B64))
        self.assertEqual(res.status_code, 201, res.content)
        from apps.records.models import Attachment
        self.assertEqual(Attachment.objects.count(), 1)
        # Le contenu décodé transmis au stockage est bien la photo d'origine.
        stored_file = mock_store.call_args[0][0]
        stored_file.seek(0)
        self.assertEqual(stored_file.read(), FAKE_JPEG)

    def test_base64_invalide_le_lead_survit(self):
        res = self.post(payload_site(photo='%%%pas-du-base64%%%'))
        self.assertEqual(res.status_code, 201, res.content)
        from apps.records.models import Attachment
        self.assertEqual(Attachment.objects.count(), 0)
        self.assertEqual(Lead.objects.count(), 1)

    def test_sans_photo_aucun_attachement(self):
        res = self.post(payload_site())
        self.assertEqual(res.status_code, 201, res.content)
        from apps.records.models import Attachment
        self.assertEqual(Attachment.objects.count(), 0)

    @mock.patch('apps.records.storage.store_attachment',
                side_effect=RuntimeError('MinIO en panne'))
    def test_stockage_en_panne_le_lead_survit(self, mock_store):
        res = self.post(payload_site(photo=FAKE_JPEG_B64))
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(Lead.objects.count(), 1)
        from apps.records.models import Attachment
        self.assertEqual(Attachment.objects.count(), 0)


class CaptureOcrTests(TestCase):
    """OCR ON : extraction tranche/consommation vers le lead (champs vides)."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from apps.roles.models import Role, RESPONSABLE_PERMISSIONS

        User = get_user_model()
        self.company = Company.objects.create(nom='QK6 OCR', slug='qk6-ocr')
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='Responsable',
            defaults={'permissions': RESPONSABLE_PERMISSIONS,
                      'est_systeme': True})
        self.owner = User.objects.create_user(
            username='qk6_owner', password='x',
            role=role, role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='OCR Lead', owner=self.owner)

    def _fake_ocr_response(self, payload):
        resp = mock.Mock()
        resp.status_code = 200
        resp.json.return_value = payload
        return resp

    @override_settings(CRM_CAPTURE_OCR_ENABLED=True)
    @mock.patch('apps.records.storage.store_attachment',
                return_value=(dict(FAKE_META), None))
    def test_ocr_configure_extrait_tranche_et_conso(self, mock_store):
        with mock.patch('requests.post', return_value=self._fake_ocr_response({
            'texte_brut': 'ONEE Facture — Consommation 385 kWh — Tranche: 3',
            'donnees_structurees': {},
        })) as mock_post:
            att = attach_capture_photo(self.lead, {'photo': FAKE_JPEG_B64})
        self.assertIsNotNone(att)
        mock_post.assert_called_once()
        # Auth relayée vers FastAPI (jeton du owner).
        headers = mock_post.call_args.kwargs.get('headers') or {}
        self.assertTrue(headers.get('Authorization', '').startswith('Bearer '))
        self.lead.refresh_from_db()
        self.assertEqual(float(self.lead.conso_mensuelle_kwh), 385.0)
        self.assertEqual(self.lead.tranche_onee, '3')
        # L'extraction est tracée dans le chatter.
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, body__contains='OCR').exists())

    @override_settings(CRM_CAPTURE_OCR_ENABLED=True)
    @mock.patch('apps.records.storage.store_attachment',
                return_value=(dict(FAKE_META), None))
    def test_ocr_necrase_jamais_une_valeur_existante(self, mock_store):
        self.lead.conso_mensuelle_kwh = 500
        self.lead.tranche_onee = 'Tranche 5'
        self.lead.save(update_fields=['conso_mensuelle_kwh', 'tranche_onee'])
        with mock.patch('requests.post', return_value=self._fake_ocr_response({
            'texte_brut': 'Consommation 385 kWh Tranche: 3',
            'donnees_structurees': {},
        })):
            attach_capture_photo(self.lead, {'photo': FAKE_JPEG_B64})
        self.lead.refresh_from_db()
        self.assertEqual(float(self.lead.conso_mensuelle_kwh), 500.0)
        self.assertEqual(self.lead.tranche_onee, 'Tranche 5')

    @override_settings(CRM_CAPTURE_OCR_ENABLED=True)
    @mock.patch('apps.records.storage.store_attachment',
                return_value=(dict(FAKE_META), None))
    def test_ocr_sans_owner_saute_mais_attache(self, mock_store):
        """Pas d'utilisateur pour le jeton → OCR sauté, photo quand même jointe."""
        lead = Lead.objects.create(company=self.company, nom='Sans owner')
        with mock.patch('requests.post') as mock_post:
            att = attach_capture_photo(lead, {'photo': FAKE_JPEG_B64})
        self.assertIsNotNone(att)
        mock_post.assert_not_called()

    @override_settings(CRM_CAPTURE_OCR_ENABLED=True)
    @mock.patch('apps.records.storage.store_attachment',
                return_value=(dict(FAKE_META), None))
    def test_ocr_en_panne_la_photo_reste_jointe(self, mock_store):
        with mock.patch('requests.post',
                        side_effect=RuntimeError('réseau en panne')):
            att = attach_capture_photo(self.lead, {'photo': FAKE_JPEG_B64})
        self.assertIsNotNone(att)
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.conso_mensuelle_kwh)

    @override_settings(CRM_CAPTURE_OCR_ENABLED=True)
    @mock.patch('apps.records.storage.store_attachment',
                return_value=(dict(FAKE_META), None))
    def test_donnees_structurees_prioritaires(self, mock_store):
        with mock.patch('requests.post', return_value=self._fake_ocr_response({
            'texte_brut': 'Consommation 999 kWh',
            'donnees_structurees': {'conso_kwh': '412,5',
                                    'tranche': 'Tranche 4'},
        })):
            attach_capture_photo(self.lead, {'photo': FAKE_JPEG_B64})
        self.lead.refresh_from_db()
        self.assertEqual(float(self.lead.conso_mensuelle_kwh), 412.5)
        self.assertEqual(self.lead.tranche_onee, 'Tranche 4')


class ExtractionHelpersTests(TestCase):
    """Parsing local déterministe (sans réseau)."""

    def test_extract_conso_regex(self):
        from .intake_photo import _extract_conso_kwh
        self.assertEqual(_extract_conso_kwh({}, 'Total 1 250 kWh ce mois'),
                         1250.0)
        self.assertIsNone(_extract_conso_kwh({}, 'aucune conso ici'))

    def test_extract_tranche_regex(self):
        from .intake_photo import _extract_tranche
        self.assertEqual(_extract_tranche({}, 'Tranche : 3\nSuite'), '3')
        self.assertIsNone(_extract_tranche({}, 'rien'))

    def test_conso_bornes_plausibles(self):
        from .intake_photo import _extract_conso_kwh
        # Une valeur absurde des données structurées est ignorée.
        self.assertIsNone(_extract_conso_kwh({'conso_kwh': '99999999'}, ''))
        self.assertIsNone(_extract_conso_kwh({'conso_kwh': 'abc'}, ''))

"""ACHT29 (C-ACHT-027) — le PDF « compte-rendu d'intervention » imprime la
signature recueillie (image data-URL, nom du signataire, date et heure) dans
le bloc « Le client / Bon pour accord » ; une intervention non signée garde
la case vide et le nom du client du chantier.

Rejoue CINT-3 : PDF d'une intervention signée sans image, sans nom, sans
date de signature.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_compte_rendu_signature"
"""
import base64
from datetime import datetime

import fitz
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm.models import Client
from apps.installations.intervention_pdf import compte_rendu_pdf
from apps.installations.models import Installation, Intervention

User = get_user_model()

_PNG_1x1 = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08'
    b'\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00'
    b'\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
SIGNATURE = 'data:image/png;base64,' + base64.b64encode(_PNG_1x1).decode()


def _pdf(contenu):
    doc = fitz.open(stream=contenu, filetype='pdf')
    try:
        texte = '\n'.join(page.get_text() for page in doc)
        images = sum(len(page.get_images(full=True)) for page in doc)
    finally:
        doc.close()
    return texte, images


class CompteRenduSignatureTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht29', defaults={'nom': 'Co ACHT29'})
        self.user = User.objects.create_user(
            username='resp-acht29', password='x', company=self.company,
            role_legacy='responsable')
        client = Client.objects.create(
            company=self.company, nom='Benali', prenom='Karim',
            email='acht29@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT29', client=client)

    def _intervention(self, **extra):
        return Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user, statut=Intervention.Statut.VALIDEE,
            **extra)

    def test_signature_imprimee(self):
        signe_le = timezone.make_aware(datetime(2026, 10, 1, 10, 15))
        iv = self._intervention(
            signature_client=SIGNATURE, signataire_nom='M. ProbeSignataire',
            signe_le=signe_le)
        texte, images = _pdf(compte_rendu_pdf(iv))
        self.assertIn('M. ProbeSignataire', texte)
        self.assertIn('Signé le 01/10/2026 10:15', texte)
        # Témoin : la même fiche sans signature porte une image de moins
        # (le logo éventuel de la société est commun aux deux).
        _texte, images_temoin = _pdf(compte_rendu_pdf(self._intervention()))
        self.assertEqual(images, images_temoin + 1)

    def test_non_signee_case_vide(self):
        iv = self._intervention()
        texte, _images = _pdf(compte_rendu_pdf(iv))
        self.assertIn('Benali Karim', texte)
        self.assertNotIn('Signé le', texte)

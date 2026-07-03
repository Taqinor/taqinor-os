"""XGED4 — Certificat de complétion + classement automatique des documents
signés.

Couvre :
  * `generer_certificat_completion` rend un PDF avec identités/IP/UA/
    géoloc-absente-OK/méthode/séquence d'événements/hash ;
  * `classer_signature_completee` classe le document signé + son certificat
    dans un dossier « Signés » (idempotent par source) ;
  * `marquer_signe` déclenche le classement automatiquement SANS action
    manuelle, une seule fois (pas de doublon sur un ré-appel idempotent) ;
  * `DocumentLien` existant sur le document source se propage vers les
    documents classés (best-effort) ;
  * no-op silencieux si la demande n'est pas signée ;
  * un souci de rendu (WeasyPrint absent) ne bloque JAMAIS la signature.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.ged import services
from apps.ged.models import (
    Cabinet, Document, DocumentLien, DocumentVersion, Folder,
    SIGNATURE_EN_ATTENTE,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class XGed4Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged4-a', 'Xged4 A')
        self.admin_a = make_user(self.co_a, 'xged4-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat à signer')
        self.version_a = DocumentVersion.objects.create(
            company=self.co_a, document=self.doc_a, version=1,
            file_key='ged/xged4/doc-a.pdf', filename='doc-a.pdf',
            mime='application/pdf')
        self.demande = services.demander_signature(
            self.doc_a, signataire_nom='Jean Client',
            signataire_email='jean@example.com', company=self.co_a,
            created_by=self.admin_a)


class CertificatContentTests(XGed4Base):
    def test_generer_certificat_completion_renders_pdf(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'data', None)):
            services.signer_demande_publique(
                self.demande, consentement=True, signature_texte='Jean Client',
                adresse_ip='41.140.1.2', user_agent='TestAgent/1.0')
        pdf = services.generer_certificat_completion(self.demande)
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_certificat_html_includes_proof_fields(self):
        self.demande.adresse_ip = '41.140.1.2'
        self.demande.user_agent = 'TestAgent/1.0'
        self.demande.hash_contenu = 'a' * 64
        self.demande.signature_texte = 'Jean Client'
        self.demande.save()
        html = services._certificat_html(self.demande)
        self.assertIn('41.140.1.2', html)
        self.assertIn('TestAgent/1.0', html)
        self.assertIn('a' * 64, html)
        self.assertIn('Jean Client', html)

    def test_certificat_geoloc_absent_is_ok(self):
        """Géolocalisation absente (jamais requise) → mention explicite, PAS
        d'erreur."""
        html = services._certificat_html(self.demande)
        self.assertIn('Non transmise', html)


class ClassementAutomatiqueTests(XGed4Base):
    def test_noop_when_not_signed(self):
        self.assertEqual(self.demande.statut, SIGNATURE_EN_ATTENTE)
        result = services.classer_signature_completee(self.demande)
        self.assertIsNone(result)

    def test_classement_creates_signed_folder_documents(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'%PDF data', None)):
            services.signer_demande_publique(
                self.demande, consentement=True, signature_texte='Jean')
            result = services.classer_signature_completee(self.demande)
        self.assertIsNotNone(result)
        self.assertIsNotNone(result['document_signe'])
        self.assertIsNotNone(result['certificat'])
        self.assertEqual(result['document_signe'].folder.nom, 'Signés')
        self.assertEqual(result['certificat'].folder.nom, 'Signés')

    def test_classement_idempotent_by_source(self):
        # `signer_demande_publique` déclenche déjà `marquer_signe`, qui classe
        # AUTOMATIQUEMENT la demande (XGED4) : au moment où ce test appelle
        # `classer_signature_completee` lui-même, le classement a donc déjà eu
        # lieu une fois — les deux appels explicites ci-dessous sont donc tous
        # les deux des RE-classements idempotents (created=False), et c'est
        # précisément ce que ce test vérifie : aucun doublon, même ID renvoyé.
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'%PDF data', None)):
            services.signer_demande_publique(
                self.demande, consentement=True, signature_texte='Jean')
            r1 = services.classer_signature_completee(self.demande)
            r2 = services.classer_signature_completee(self.demande)
        self.assertEqual(r1['document_signe'].id, r2['document_signe'].id)
        self.assertFalse(r1['created'])
        self.assertFalse(r2['created'])

    def test_marquer_signe_triggers_classement_automatically(self):
        """Aucune action manuelle : marquer_signe déclenche seul le
        classement."""
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'%PDF data', None)):
            services.marquer_signe(self.demande)
        signes = Document.objects.filter(
            company=self.co_a, folder__nom='Signés')
        self.assertEqual(signes.count(), 2)  # document + certificat

    def test_marquer_signe_second_call_does_not_duplicate(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'%PDF data', None)):
            services.marquer_signe(self.demande)
            services.marquer_signe(self.demande)  # idempotent (déjà signé)
        signes = Document.objects.filter(
            company=self.co_a, folder__nom='Signés')
        self.assertEqual(signes.count(), 2)

    def test_document_lien_propagates_to_classed_documents(self):
        client = Client.objects.create(company=self.co_a, nom='Client X')
        ct = ContentType.objects.get_for_model(Client)
        DocumentLien.objects.create(
            company=self.co_a, document=self.doc_a,
            content_type=ct, object_id=client.id, created_by=self.admin_a)
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'%PDF data', None)):
            services.signer_demande_publique(
                self.demande, consentement=True, signature_texte='Jean')
            result = services.classer_signature_completee(self.demande)
        lien_signe = DocumentLien.objects.filter(
            document=result['document_signe'], content_type=ct,
            object_id=client.id)
        self.assertTrue(lien_signe.exists())

    def test_render_failure_never_blocks_signature(self):
        """Un souci de rendu du certificat (WeasyPrint indisponible) ne
        bloque JAMAIS l'enregistrement de la signature elle-même."""
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'%PDF data', None)), \
             mock.patch('apps.ged.services.generer_certificat_completion',
                        side_effect=RuntimeError('WeasyPrint absent')):
            demande = services.marquer_signe(self.demande)
        self.assertEqual(demande.statut, 'signe')

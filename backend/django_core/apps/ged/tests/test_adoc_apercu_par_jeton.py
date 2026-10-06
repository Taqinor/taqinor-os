"""ADOC67 — L'aperçu du document à signer est servi PAR LE JETON (AllowAny,
noindex) : un signataire non connecté lit ce qu'il signe.

Sources réelles : vues publiques GED, stockage MinIO de test réel (les octets
servis sont ceux réellement stockés), `JournalAcces` réel ; aucun mock.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.ged import services
from apps.ged.models import ACCES_PUBLIC, Cabinet, Document, Folder, JournalAcces

User = get_user_model()

CONTENU_A = b'%PDF-1.4\n%adoc67-A\n' + b'A' * 80
CONTENU_B = b'%PDF-1.4\n%adoc67-B\n' + b'B' * 80


def _doc_avec_version(company, nom, contenu):
    cab = Cabinet.objects.create(company=company, nom=f'Cab {nom}')
    folder = Folder.objects.create(company=company, cabinet=cab, nom='D')
    doc = Document.objects.create(company=company, folder=folder, nom=nom)
    key, meta = services._store_bytes(contenu, mime='application/pdf')
    services.add_version(
        doc, file_key=key, company=company, filename='doc.pdf',
        size=len(contenu), mime='application/pdf')
    return doc


class ApercuParJetonTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.co_a, _ = Company.objects.get_or_create(
            slug='adoc67-a', defaults={'nom': 'Adoc67 A'})
        self.co_b, _ = Company.objects.get_or_create(
            slug='adoc67-b', defaults={'nom': 'Adoc67 B'})
        self.doc_a = _doc_avec_version(self.co_a, 'Doc A', CONTENU_A)
        self.doc_b = _doc_avec_version(self.co_b, 'Doc B', CONTENU_B)
        self.anon = APIClient()

    def _octets(self, resp):
        return b''.join(resp.streaming_content) if resp.streaming \
            else resp.content

    def test_apercu_anonyme_par_jeton_mono(self):
        demande = services.demander_signature(
            self.doc_a, signataire_nom='A', signataire_email='a@x.ma',
            company=self.co_a)
        resp = self.anon.get(
            f'/api/django/ged/signature/{demande.token}/document/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('noindex', resp['X-Robots-Tag'])
        self.assertEqual(self._octets(resp), CONTENU_A)
        # La consultation est tracée.
        self.assertTrue(JournalAcces.objects.filter(
            document=self.doc_a, type_acces=ACCES_PUBLIC,
            source_ref='public_signature').exists())
        # Le payload de la page fournit l'URL de cet aperçu.
        page = self.anon.get(f'/api/django/ged/signature/{demande.token}/')
        self.assertEqual(
            page.data['apercu_url'],
            f'/api/django/ged/signature/{demande.token}/document/')

    def test_apercu_anonyme_par_jeton_signataire(self):
        demande = services.creer_demande_multi_signataires(
            self.doc_b, destinataires=[{'nom': 'S', 'email': 's@x.ma'}],
            company=self.co_b)
        signataire = demande.signataires.get()
        resp = self.anon.get(
            f'/api/django/ged/signataire/{signataire.token}/document/')
        self.assertEqual(resp.status_code, 200)
        # Jamais le document d'une autre demande / société.
        self.assertEqual(self._octets(resp), CONTENU_B)
        self.assertEqual(
            self.anon.get(f'/api/django/ged/signataire/{signataire.token}/')
            .data['apercu_url'],
            f'/api/django/ged/signataire/{signataire.token}/document/')

    def test_jeton_expire_404(self):
        demande = services.demander_signature(
            self.doc_a, signataire_nom='A', signataire_email='a@x.ma',
            company=self.co_a)
        demande.expires_at = timezone.now() - datetime.timedelta(days=1)
        demande.save(update_fields=['expires_at'])
        resp = self.anon.get(
            f'/api/django/ged/signature/{demande.token}/document/')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(
            resp.data['detail'], "Ce lien de signature est introuvable.")

    def test_jeton_inconnu_ou_annule_404(self):
        self.assertEqual(self.anon.get(
            '/api/django/ged/signature/inconnu/document/').status_code, 404)
        demande = services.demander_signature(
            self.doc_a, signataire_nom='A', signataire_email='a@x.ma',
            company=self.co_a)
        services.annuler_demande(demande, user=None)
        self.assertEqual(self.anon.get(
            f'/api/django/ged/signature/{demande.token}/document/')
            .status_code, 404)

"""NTPRT13 — "Mes documents" (GED partagée avec le portail CLIENT).

Couvre :

* LECTURE — ``ged.selectors.documents_partages_client_portail`` : un document
  SANS ``AclGed`` explicite (``client=…``) pour ce client N'APPARAÎT JAMAIS
  côté portail (critère d'acceptation NTPRT13), même s'il vit dans un dossier
  par ailleurs consultable en interne. Un document partagé avec un AUTRE
  client, ou d'une autre société, reste également invisible ;
* le TÉLÉCHARGEMENT sert le contenu de la version courante d'un document
  PARTAGÉ, et 404 sur un document non partagé (jamais « trouvé puis refusé ») ;
* le DÉPÔT d'un justificatif crée un ``DocumentClientPortail`` avec
  ``client_id``/``company`` FORCÉS côté serveur (un ``client_id`` étranger
  dans le corps est ignoré) — réutilise le serializer FG231 existant, aucun
  nouveau modèle d'upload ;
* NTPRT6 — un membre d'équipe « lecture seule » ne peut PAS déposer de
  document (403), seulement consulter.

Run :
    python manage.py test apps.portail.tests.test_ntprt13_mes_documents -v2
"""
import itertools
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.ged.models import AclGed, Cabinet, Document, DocumentVersion, Folder
from apps.portail.models import DocumentClientPortail
from apps.portail.services import (
    accepter_invitation_portail, inviter_membre_portail,
    provisionner_compte_portail_client,
)
from authentication.models import Company

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client_crm(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom=f'NTPRT13-{n}',
        email=f'ntprt13-{company.id}-{n}@example.invalid')


def make_admin(company):
    """Provisionne le compte ADMIN (NTPRT2) — voir NTPRT6 pour l'explication
    du ``must_change_password=False`` (sinon AUD139 bloque toute requête)."""
    client = make_client_crm(company)
    admin, _ = provisionner_compte_portail_client(company, client.id)
    admin.must_change_password = False
    admin.save(update_fields=['must_change_password'])
    return client, admin


def make_document(company, nom='Facture fournisseur.pdf'):
    n = next(_seq)
    cabinet = Cabinet.objects.create(company=company, nom=f'Cabinet-{n}')
    folder = Folder.objects.create(
        company=company, cabinet=cabinet, nom=f'Dossier-{n}')
    document = Document.objects.create(company=company, folder=folder, nom=nom)
    DocumentVersion.objects.create(
        company=company, document=document, version=1,
        file_key=f'ged/{company.id}/{n}.pdf', filename=nom,
        size=42, mime='application/pdf')
    return document


class DocumentsPartagesClientPortailTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt13-co-a', 'NTPRT13 Société A')
        self.client_crm, self.admin = make_admin(self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.admin)

    def test_document_sans_acl_explicite_najamais_visible(self):
        make_document(self.company, "Contrat interne (pas d'ACL)")
        res = self.api.get('/api/django/portail/mes-documents/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['results'], [])

    def test_document_avec_acl_explicite_pour_ce_client_visible(self):
        document = make_document(self.company, 'Fiche technique panneau.pdf')
        AclGed.objects.create(
            company=self.company, document=document, client=self.client_crm)
        res = self.api.get('/api/django/portail/mes-documents/')
        self.assertEqual(res.status_code, 200, res.data)
        ids = [d['id'] for d in res.data['results']]
        self.assertEqual(ids, [document.id])
        self.assertEqual(res.data['results'][0]['taille'], 42)
        self.assertEqual(res.data['results'][0]['mime'], 'application/pdf')

    def test_document_partage_avec_un_autre_client_invisible(self):
        autre_client = make_client_crm(self.company)
        document = make_document(self.company)
        AclGed.objects.create(
            company=self.company, document=document, client=autre_client)
        res = self.api.get('/api/django/portail/mes-documents/')
        self.assertEqual(res.data['results'], [])

    def test_document_dune_autre_societe_invisible(self):
        autre = make_company('ntprt13-co-b', 'NTPRT13 Société B')
        autre_client, _ = make_admin(autre)
        document = make_document(autre)
        AclGed.objects.create(
            company=autre, document=document, client=autre_client)
        res = self.api.get('/api/django/portail/mes-documents/')
        self.assertEqual(res.data['results'], [])

    def test_document_dans_un_dossier_partage_sans_acl_document_invisible(self):
        """L'héritage dossier n'est PAS un canal client (hors périmètre
        NTPRT13) : partager le DOSSIER ne suffit pas."""
        document = make_document(self.company)
        AclGed.objects.create(
            company=self.company, folder=document.folder,
            client=self.client_crm)
        res = self.api.get('/api/django/portail/mes-documents/')
        self.assertEqual(res.data['results'], [])

    def test_document_supprime_najamais_visible(self):
        from django.utils import timezone
        document = make_document(self.company)
        AclGed.objects.create(
            company=self.company, document=document, client=self.client_crm)
        document.supprime_le = timezone.now()
        document.save(update_fields=['supprime_le'])
        res = self.api.get('/api/django/portail/mes-documents/')
        self.assertEqual(res.data['results'], [])


class TelechargerDocumentPortailTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt13-dl-a', 'NTPRT13 Téléchargement A')
        self.client_crm, self.admin = make_admin(self.company)
        self.document = make_document(self.company, 'Notice onduleur.pdf')
        AclGed.objects.create(
            company=self.company, document=self.document,
            client=self.client_crm)
        self.api = APIClient()
        self.api.force_authenticate(user=self.admin)

    def test_telechargement_document_partage(self):
        with patch('apps.records.storage.fetch_attachment',
                   return_value=(b'%PDF-1.4', None)):
            res = self.api.get(
                f'/api/django/portail/mes-documents/{self.document.id}/'
                'telecharger/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')

    def test_telechargement_document_non_partage_404(self):
        autre_document = make_document(self.company, 'Sans ACL.pdf')
        res = self.api.get(
            f'/api/django/portail/mes-documents/{autre_document.id}/'
            'telecharger/')
        self.assertEqual(res.status_code, 404)


class DeposerJustificatifPortailTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt13-up-a', 'NTPRT13 Upload A')
        self.client_crm, self.admin = make_admin(self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.admin)
        self.url = '/api/django/portail/mes-documents/'

    def test_depot_force_client_id_et_ignore_le_corps(self):
        autre_client = make_client_crm(self.company)
        with patch('apps.records.storage.store_attachment',
                   return_value=({
                       'file_key': f'attachments/{self.company.id}/f.pdf',
                       'filename': 'facture.pdf', 'size': 10,
                       'mime': 'application/pdf'}, None)):
            res = self.api.post(self.url, {
                'client_id': autre_client.id,  # doit être ignoré
                'type_document': 'facture_onee',
                'libelle': 'Facture ONEE janvier',
                'fichier': SimpleUploadedFile(
                    'facture.pdf', b'%PDF-1.4', 'application/pdf'),
            }, format='multipart')
        self.assertEqual(res.status_code, 201, res.data)
        doc = DocumentClientPortail.objects.get(id=res.data['id'])
        self.assertEqual(doc.client_id, self.client_crm.id)
        self.assertEqual(doc.company_id, self.company.id)

    def test_membre_lecture_ne_peut_pas_deposer(self):
        invitation = inviter_membre_portail(
            self.company, self.client_crm.id, 'lecteur@example.invalid',
            'lecture')
        lecteur = accepter_invitation_portail(
            invitation.token_invitation, 'motdepasse-lecteur-1234')
        api = APIClient()
        api.force_authenticate(user=lecteur)
        res = api.post(self.url, {
            'type_document': 'facture_onee', 'libelle': 'X',
        }, format='multipart')
        self.assertEqual(res.status_code, 403)
        self.assertFalse(
            DocumentClientPortail.objects.filter(
                company=self.company).exists())

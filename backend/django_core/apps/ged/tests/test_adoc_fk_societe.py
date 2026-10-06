"""ADOC1 — chaque FK écrite par les sérialiseurs GED est bornée à la société.

Rejoue les sondes #1 et #56 de l'audit documents (2026-10-05) : un responsable
de la société A envoyait l'id d'un dossier / version / document / tag /
utilisateur de la société B et obtenait 201 (ou 500). Désormais : 400 avec
l'erreur DRF « objet inexistant », octet-identique à celle d'un id absent.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.db.models import F
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    AnnotationDocument, Cabinet, DemandeDocument, DepotPublic, Document,
    DocumentTag, DocumentVersion, ExigenceDossier, Folder,
    PlanificationDocument, RegleDossier, RoutageDocumentaire,
)

User = get_user_model()

BASE = '/api/django/ged/'
ABSENT = 999999


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _erreur_attendue(resp_absent, champ):
    """Message d'erreur d'un id absent, avec l'id remplacé (pour comparer)."""
    return [str(m).replace(str(ABSENT), '{pk}') for m in resp_absent.data[champ]]


class FkSocieteGedTests(TestCase):
    def setUp(self):
        self.co_a = make_company('adoc1-a', 'ADOC1 A')
        self.co_b = make_company('adoc1-b', 'ADOC1 B')
        self.resp_a = make_user(self.co_a, 'adoc1-resp-a')
        self.user_b = make_user(self.co_b, 'adoc1-user-b', 'normal')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Cab A')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.cab_b = Cabinet.objects.create(company=self.co_b, nom='Cab B')
        self.folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b,
            nom='DOSSIER-SECRET-SOCIETE-B')
        self.doc_b = Document.objects.create(
            company=self.co_b, folder=self.folder_b, nom='secret-b.pdf')
        self.version_b = DocumentVersion.objects.create(
            company=self.co_b, document=self.doc_b, version=1,
            file_key='attachments/b.pdf', filename='b.pdf', size=10,
            mime='application/pdf')
        self.tag_b = DocumentTag.objects.create(company=self.co_b, nom='Tag B')
        self.api = auth(self.resp_a)

    def _assert_comme_absent(self, url, corps_etranger, corps_absent, champ,
                             methode='post'):
        envoyer = getattr(self.api, methode)
        resp = envoyer(url, corps_etranger, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn(champ, resp.data)
        absent = envoyer(url, corps_absent, format='json')
        self.assertEqual(absent.status_code, 400, absent.data)
        etranger_pk = corps_etranger[champ]
        if isinstance(etranger_pk, list):
            etranger_pk = etranger_pk[0]
        recu = [str(m).replace(str(etranger_pk), '{pk}')
                for m in resp.data[champ]]
        self.assertEqual(recu, _erreur_attendue(absent, champ))
        self.assertNotIn('DOSSIER-SECRET-SOCIETE-B', str(resp.content))
        return resp

    def test_depot_public_dossier_etranger(self):
        self._assert_comme_absent(
            BASE + 'depots-publics/', {'folder': self.folder_b.pk},
            {'folder': ABSENT}, 'folder')
        self.assertFalse(DepotPublic.objects.exists())

    def test_depot_public_cree_par_le_service(self):
        resp = self.api.post(BASE + 'depots-publics/',
                             {'folder': self.folder_a.pk}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        with mock.patch('apps.ged.services.create_depot_public',
                        side_effect=services.create_depot_public) as espion:
            resp = self.api.post(BASE + 'depots-publics/',
                                 {'folder': self.folder_a.pk}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(espion.call_count, 1)
        self.assertFalse(DepotPublic.objects.exclude(
            company_id=F('folder__company_id')).exists())

    def test_patch_folder_refuse(self):
        depot = services.create_depot_public(
            folder=self.folder_a, company=self.co_a, created_by=self.resp_a)
        url = f'{BASE}depots-publics/{depot.pk}/'
        self._assert_comme_absent(
            url, {'folder': self.folder_b.pk}, {'folder': ABSENT}, 'folder',
            methode='patch')
        autre = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Autre A')
        resp = self.api.patch(url, {'folder': autre.pk}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        depot.refresh_from_db()
        self.assertEqual(depot.folder_id, self.folder_a.pk)

    def test_depot_anonyme_reste_dans_sa_societe(self):
        # Ligne incohérente héritée (lien de A sur un dossier de B).
        depot = DepotPublic.objects.create(
            company=self.co_a, folder=self.folder_b, created_by=self.resp_a)
        statut, _ = services.resolve_depot_public(depot.token)
        self.assertEqual(statut, services.DEPOT_INTROUVABLE)
        resp = APIClient().get(f'{BASE}depot/{depot.token}/')
        self.assertEqual(resp.status_code, 404)
        with self.assertRaises(ValueError):
            services.deposer_via_lien_public(
                depot, file_key='attachments/x.pdf', filename='x.pdf',
                size=10, mime='application/pdf')
        self.assertFalse(Document.objects.filter(
            folder=self.folder_b).exclude(pk=self.doc_b.pk).exists())
        # Lien légitime : le document naît dans la société de son dossier.
        bon = services.create_depot_public(
            folder=self.folder_a, company=self.co_a)
        doc = services.deposer_via_lien_public(
            bon, file_key='attachments/y.pdf', filename='y.pdf', size=10,
            mime='application/pdf')
        self.assertEqual(doc.company_id, doc.folder.company_id)

    def test_exigence_dossier_etranger(self):
        self._assert_comme_absent(
            BASE + 'exigences-dossier/',
            {'folder': self.folder_b.pk, 'libelle': 'CIN'},
            {'folder': ABSENT, 'libelle': 'CIN'}, 'folder')
        self.assertFalse(ExigenceDossier.objects.exists())

    def test_demande_document_utilisateur_etranger(self):
        self._assert_comme_absent(
            BASE + 'demandes-document/',
            {'folder': self.folder_a.pk, 'libelle': 'RIB',
             'utilisateur': self.user_b.pk},
            {'folder': self.folder_a.pk, 'libelle': 'RIB',
             'utilisateur': ABSENT}, 'utilisateur')
        self.assertFalse(DemandeDocument.objects.exists())

    def test_demande_document_dossier_etranger_400_pas_500(self):
        self._assert_comme_absent(
            BASE + 'demandes-document/',
            {'folder': self.folder_b.pk, 'libelle': 'RIB'},
            {'folder': ABSENT, 'libelle': 'RIB'}, 'folder')
        self.assertFalse(DemandeDocument.objects.exists())

    def test_annotation_version_etrangere(self):
        self._assert_comme_absent(
            BASE + 'annotations/',
            {'version': self.version_b.pk, 'type_annotation': 'note'},
            {'version': ABSENT, 'type_annotation': 'note'}, 'version')
        self.assertFalse(AnnotationDocument.objects.exists())

    def test_regle_dossier_etranger(self):
        self._assert_comme_absent(
            BASE + 'regles-dossier/',
            {'folder': self.folder_b.pk, 'nom': 'R', 'actions': []},
            {'folder': ABSENT, 'nom': 'R', 'actions': []}, 'folder')
        self.assertFalse(RegleDossier.objects.exists())

    def test_planification_document_etranger(self):
        self._assert_comme_absent(
            BASE + 'planifications/',
            {'document': self.doc_b.pk, 'libelle': 'Relancer',
             'echeance': '2026-12-01'},
            {'document': ABSENT, 'libelle': 'Relancer',
             'echeance': '2026-12-01'}, 'document')
        self.assertFalse(PlanificationDocument.objects.exists())

    def test_planification_assigne_etranger(self):
        doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='a.pdf')
        self._assert_comme_absent(
            BASE + 'planifications/',
            {'document': doc_a.pk, 'libelle': 'Relancer',
             'echeance': '2026-12-01', 'assigne_a': self.user_b.pk},
            {'document': doc_a.pk, 'libelle': 'Relancer',
             'echeance': '2026-12-01', 'assigne_a': ABSENT}, 'assigne_a')
        self.assertFalse(PlanificationDocument.objects.exists())

    def test_routage_tags_defaut_etranger(self):
        resp = self.api.post(BASE + 'routages-documentaires/', {
            'source': 'ventes_devis', 'cabinet_cible': self.cab_a.pk,
            'tags_defaut': [self.tag_b.pk]}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('tags_defaut', resp.data)
        self.assertFalse(RoutageDocumentaire.objects.exists())

    def test_export_annote_ignore_annotation_etrangere(self):
        import fitz
        pdf = fitz.open()
        pdf.new_page()
        octets = pdf.tobytes()
        pdf.close()
        doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='a.pdf')
        version_a = DocumentVersion.objects.create(
            company=self.co_a, document=doc_a, version=1,
            file_key='attachments/a.pdf', filename='a.pdf',
            size=len(octets), mime='application/pdf')
        AnnotationDocument.objects.create(
            company=self.co_b, version=version_a, type_annotation='note',
            page=0, x=10, y=10, contenu='SECRETB')
        AnnotationDocument.objects.create(
            company=self.co_a, version=version_a, type_annotation='note',
            page=0, x=10, y=50, contenu='VISIBLEA')
        with mock.patch('apps.ged.services._fetch_version_bytes',
                        return_value=(octets, None)):
            sortie = services.exporter_pdf_annote(version_a)
        lu = fitz.open(stream=sortie, filetype='pdf')
        texte = lu[0].get_text()
        lu.close()
        self.assertIn('VISIBLEA', texte)
        self.assertNotIn('SECRETB', texte)

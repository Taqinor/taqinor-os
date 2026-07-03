"""XGED6 — Vérification périodique d'intégrité des archives légales + dossier
de preuve (loi 43-20).

Couvre :
  * un archive INTACT passe le contrôle (résultat `ok`, hash identique) ;
  * un objet ALTÉRÉ est détecté (`altere`) et les admins sont notifiés
    (best-effort, mocké) ;
  * contenu indisponible → `indisponible` (PAS accusé d'altération) ;
  * le dossier de preuve s'exporte (hash au dépôt + contrôles successifs) ;
  * `ArchivageLegal` (GED23, write-once) n'est JAMAIS modifié par un contrôle ;
  * scoping société ; endpoint gated (responsable/admin) + commande OK.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    Cabinet, CONTROLE_RESULTAT_ALTERE, CONTROLE_RESULTAT_INDISPONIBLE,
    CONTROLE_RESULTAT_OK, ControleIntegrite, Document, DocumentVersion, Folder,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XGed6Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged6-a', 'Xged6 A')
        self.co_b = make_company('xged6-b', 'Xged6 B')
        self.admin_a = make_user(self.co_a, 'xged6-admin-a', 'admin')
        self.employe_a = make_user(self.co_a, 'xged6-emp-a', 'normal')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat archivé')
        self.contenu_original = b'%PDF-1.4 contenu archive original'
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(self.contenu_original, None)):
            DocumentVersion.objects.create(
                company=self.co_a, document=self.doc_a, version=1,
                file_key='ged/xged6/doc-a.pdf', filename='doc-a.pdf',
                mime='application/pdf',
                checksum=services.compute_checksum(self.contenu_original))
            self.archivage = services.archiver_legalement(
                self.doc_a, user=self.admin_a, motif='Test XGED6')


class IntegrityCheckTests(XGed6Base):
    def test_intact_archive_passes(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(self.contenu_original, None)):
            synthese = services.verifier_integrite_archives(self.co_a)
        self.assertEqual(synthese, {
            'total': 1, 'ok': 1, 'altere': 0, 'indisponible': 0})
        controle = ControleIntegrite.objects.get(archivage=self.archivage)
        self.assertEqual(controle.resultat, CONTROLE_RESULTAT_OK)

    def test_altered_archive_detected(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'contenu MODIFIE', None)), \
             mock.patch('apps.ged.services._notifier_alteration_archives'
                        ) as mocked_notify:
            synthese = services.verifier_integrite_archives(self.co_a)
        self.assertEqual(synthese['altere'], 1)
        self.assertEqual(synthese['ok'], 0)
        controle = ControleIntegrite.objects.get(archivage=self.archivage)
        self.assertEqual(controle.resultat, CONTROLE_RESULTAT_ALTERE)
        mocked_notify.assert_called_once()

    def test_unavailable_content_is_not_accused_of_alteration(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(None, 'unreachable')):
            synthese = services.verifier_integrite_archives(self.co_a)
        self.assertEqual(synthese['indisponible'], 1)
        self.assertEqual(synthese['altere'], 0)
        controle = ControleIntegrite.objects.get(archivage=self.archivage)
        self.assertEqual(controle.resultat, CONTROLE_RESULTAT_INDISPONIBLE)

    def test_sain_case_ignored_no_false_positive(self):
        """Un archivage intact (cas SAIN, fixture construite exprès) ne doit
        JAMAIS ressortir comme altéré."""
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(self.contenu_original, None)):
            services.verifier_integrite_archives(self.co_a)
        self.assertFalse(
            ControleIntegrite.objects.filter(
                archivage=self.archivage,
                resultat=CONTROLE_RESULTAT_ALTERE).exists())

    def test_archivage_legal_never_mutated_by_control(self):
        """Write-once GED23 intact : un contrôle ne modifie JAMAIS
        l'ArchivageLegal lui-même."""
        hash_avant = self.archivage.hash_integrite
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'contenu MODIFIE', None)):
            services.verifier_integrite_archives(self.co_a)
        self.archivage.refresh_from_db()
        self.assertEqual(self.archivage.hash_integrite, hash_avant)

    def test_scoped_by_company(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(self.contenu_original, None)):
            services.verifier_integrite_archives(self.co_a)
            synthese_b = services.verifier_integrite_archives(self.co_b)
        self.assertEqual(synthese_b['total'], 0)


class DossierPreuveTests(XGed6Base):
    def test_dossier_preuve_contains_hash_and_controles(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(self.contenu_original, None)):
            services.verifier_integrite_archives(self.co_a)
        dossier = services.dossier_preuve_archivage(self.archivage)
        self.assertEqual(
            dossier['hash_integrite_au_depot'], self.archivage.hash_integrite)
        self.assertEqual(len(dossier['controles']), 1)
        self.assertEqual(dossier['controles'][0]['resultat'], CONTROLE_RESULTAT_OK)

    def test_dossier_preuve_accumulates_successive_controls(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(self.contenu_original, None)):
            services.verifier_integrite_archives(self.co_a)
            services.verifier_integrite_archives(self.co_a)
        dossier = services.dossier_preuve_archivage(self.archivage)
        self.assertEqual(len(dossier['controles']), 2)


class ApiTests(XGed6Base):
    URL = '/api/django/ged/archivages-legaux/'

    def test_dossier_preuve_endpoint(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(self.contenu_original, None)):
            services.verifier_integrite_archives(self.co_a)
        resp = auth(self.admin_a).get(
            f'{self.URL}{self.archivage.id}/dossier-preuve/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('controles', resp.data)

    def test_verifier_integrite_endpoint_gated_non_manager(self):
        resp = auth(self.employe_a).post(
            f'{self.URL}verifier-integrite/', {}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_verifier_integrite_endpoint_manager_ok(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(self.contenu_original, None)):
            resp = auth(self.admin_a).post(
                f'{self.URL}verifier-integrite/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total'], 1)

    def test_dossier_preuve_cross_company_404(self):
        admin_b = make_user(self.co_b, 'xged6-admin-b', 'admin')
        resp = auth(admin_b).get(
            f'{self.URL}{self.archivage.id}/dossier-preuve/')
        self.assertEqual(resp.status_code, 404)

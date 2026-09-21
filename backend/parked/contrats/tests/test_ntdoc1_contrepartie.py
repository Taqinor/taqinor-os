"""Tests NTDOC1 — Dépôt de la version « contrepartie » sur un Contrat.

Couvre le critère d'acceptation :
- un fichier .docx/.pdf déposé par la contrepartie apparaît LIÉ au contrat et
  HORODATÉ ;
- le contenu figé d'une ``VersionContrat`` (CONTRAT18) n'est JAMAIS écrasé ;
- aucune suppression physique : l'archivage est SOFT ;
- la société est posée côté serveur (jamais lue du corps) et l'isolation
  multi-tenant tient ;
- dépôt externe par lien tokenisé (patron ``PartageGed``/XGED7) : un lien
  révoqué/expiré renvoie 404 sans fuite d'existence ;
- un format non accepté est refusé en 400 en NOMMANT le champ fautif.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import (
    Contrat, DocumentContrepartie, LienDepotContrepartie, VersionContrat,
)

User = get_user_model()

BASE = '/api/django/contrats/contrats/'
PUBLIC = '/api/django/public/contrats/depot/'


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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


def fake_minio():
    """Contexte qui neutralise le stockage objet (aucun MinIO en test)."""
    client = mock.Mock()
    client.upload_fileobj.return_value = None
    return (
        mock.patch('apps.ventes.utils.minio_client.get_minio_client',
                   return_value=client),
        mock.patch('apps.ventes.utils.minio_client.ensure_uploads_bucket',
                   return_value=None),
        client,
    )


class DepotContrepartieApiTests(TestCase):
    """Dépôt interne via l'API authentifiée."""

    def setUp(self):
        self.co = make_company('ntdoc1-a', 'Alpha')
        self.admin = make_user(self.co, 'ntdoc1-admin')
        self.contrat = Contrat.objects.create(
            company=self.co, objet='Contrat O&M', reference='CT-001')

    def _post_fichier(self, nom='redline.docx', contenu=b'PK\x03\x04 docx'):
        api = auth(self.admin)
        p_client, p_bucket, _ = fake_minio()
        with p_client, p_bucket:
            return api.post(
                f'{BASE}{self.contrat.id}/contreparties/',
                {'fichier': SimpleUploadedFile(nom, contenu)},
                format='multipart')

    def test_depot_docx_lie_et_horodate(self):
        """Un .docx déposé apparaît lié au contrat et horodaté côté serveur."""
        resp = self._post_fichier()
        self.assertEqual(resp.status_code, 201, resp.data)
        doc = DocumentContrepartie.objects.get(id=resp.data['id'])
        self.assertEqual(doc.contrat_id, self.contrat.id)
        self.assertEqual(doc.company_id, self.co.id)
        self.assertIsNotNone(doc.date_depot)
        self.assertEqual(doc.nom_fichier, 'redline.docx')
        self.assertEqual(doc.statut, DocumentContrepartie.Statut.NOUVEAU)
        # Clé de stockage PRÉFIXÉE SOCIÉTÉ (isolation multi-tenant, ERR75).
        self.assertTrue(
            doc.fichier_key.startswith(
                f'contrats/contreparties/{self.co.id}/'),
            doc.fichier_key)

    def test_depot_pdf_accepte(self):
        """Un .pdf est également accepté (les deux formats du critère)."""
        resp = self._post_fichier(nom='contrat-signe.pdf', contenu=b'%PDF-1.4')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['mime'], 'application/pdf')

    def test_format_refuse_nomme_le_champ_fautif(self):
        """Un format non accepté renvoie 400 en NOMMANT « nom_fichier »."""
        resp = self._post_fichier(nom='virus.exe', contenu=b'MZ')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('nom_fichier', resp.data['detail'])
        self.assertFalse(DocumentContrepartie.objects.exists())

    def test_ne_touche_jamais_la_version_figee(self):
        """Le dépôt n'écrase JAMAIS le contenu figé d'une VersionContrat."""
        version = VersionContrat.objects.create(
            company=self.co, contrat=self.contrat, version=1,
            contenu='TEXTE FIGÉ', motif='signature')
        resp = self._post_fichier()
        self.assertEqual(resp.status_code, 201, resp.data)
        version.refresh_from_db()
        self.assertEqual(version.contenu, 'TEXTE FIGÉ')
        self.assertEqual(VersionContrat.objects.count(), 1)

    def test_liste_masque_les_archives_sauf_demande(self):
        """La liste masque les dépôts archivés ; ?archives=1 les rend visibles."""
        self._post_fichier(nom='a.docx')
        self._post_fichier(nom='b.docx')
        doc = DocumentContrepartie.objects.order_by('id').first()
        api = auth(self.admin)
        resp = api.post(
            f'{BASE}{self.contrat.id}/contreparties/{doc.id}/archiver/', {})
        self.assertEqual(resp.status_code, 200, resp.data)

        visibles = rows(api.get(f'{BASE}{self.contrat.id}/contreparties/'))
        self.assertEqual(len(visibles), 1)
        tous = rows(
            api.get(f'{BASE}{self.contrat.id}/contreparties/?archives=1'))
        self.assertEqual(len(tous), 2)

    def test_archivage_est_soft_jamais_physique(self):
        """Archiver ne supprime JAMAIS la ligne en base (pièce juridique)."""
        self._post_fichier()
        doc = DocumentContrepartie.objects.get()
        api = auth(self.admin)
        api.post(f'{BASE}{self.contrat.id}/contreparties/{doc.id}/archiver/',
                 {})
        doc.refresh_from_db()
        self.assertTrue(doc.archive)
        self.assertIsNotNone(doc.date_archivage)
        self.assertEqual(DocumentContrepartie.objects.count(), 1)

    def test_archiver_depot_d_un_autre_contrat_404(self):
        """Un dépôt d'un autre contrat n'est pas archivable depuis celui-ci."""
        autre = Contrat.objects.create(company=self.co, objet='Autre')
        self._post_fichier()
        doc = DocumentContrepartie.objects.get()
        api = auth(self.admin)
        resp = api.post(
            f'{BASE}{autre.id}/contreparties/{doc.id}/archiver/', {})
        self.assertEqual(resp.status_code, 404)

    def test_chatter_journalise_le_depot(self):
        """Le dépôt est journalisé au chatter du contrat (CONTRAT15)."""
        self._post_fichier()
        self.assertTrue(
            self.contrat.activites.filter(field='contrepartie').exists())


class DepotContrepartieIsolationTests(TestCase):
    """Isolation multi-société : jamais de fuite entre tenants."""

    def setUp(self):
        self.co_a = make_company('ntdoc1-iso-a', 'A')
        self.co_b = make_company('ntdoc1-iso-b', 'B')
        self.admin_b = make_user(self.co_b, 'ntdoc1-iso-b-admin')
        self.contrat_a = Contrat.objects.create(
            company=self.co_a, objet='Contrat A')

    def test_contrat_d_une_autre_societe_404(self):
        api = auth(self.admin_b)
        resp = api.get(f'{BASE}{self.contrat_a.id}/contreparties/')
        self.assertEqual(resp.status_code, 404)


class LienDepotPublicTests(TestCase):
    """Dépôt EXTERNE par lien tokenisé (patron PartageGed / XGED7)."""

    def setUp(self):
        self.co = make_company('ntdoc1-pub', 'Public')
        self.admin = make_user(self.co, 'ntdoc1-pub-admin')
        self.contrat = Contrat.objects.create(
            company=self.co, objet='Contrat cadre', reference='CT-042')

    def _creer_lien(self):
        api = auth(self.admin)
        resp = api.post(
            f'{BASE}{self.contrat.id}/creer-lien-depot/',
            {'destinataire_nom': 'Cabinet Untel',
             'destinataire_email': 'contact@cabinet.test'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data['token']

    def test_token_genere_cote_serveur(self):
        token = self._creer_lien()
        self.assertGreaterEqual(len(token), 32)
        lien = LienDepotContrepartie.objects.get(token=token)
        self.assertEqual(lien.company_id, self.co.id)
        self.assertEqual(lien.created_by_id, self.admin.id)

    def test_depot_public_cree_le_document(self):
        token = self._creer_lien()
        p_client, p_bucket, _ = fake_minio()
        with p_client, p_bucket:
            resp = APIClient().post(
                f'{PUBLIC}{token}/',
                {'fichier': SimpleUploadedFile('reponse.docx', b'PK\x03\x04')},
                format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        doc = DocumentContrepartie.objects.get()
        self.assertEqual(doc.contrat_id, self.contrat.id)
        self.assertEqual(doc.company_id, self.co.id)
        self.assertIsNone(doc.depose_par_id)
        self.assertEqual(doc.depose_par_nom, 'Cabinet Untel')

    def test_get_public_expose_le_minimum(self):
        token = self._creer_lien()
        resp = APIClient().get(f'{PUBLIC}{token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['contrat_reference'], 'CT-042')
        self.assertNotIn('montant', resp.data)
        self.assertNotIn('confidentialite', resp.data)

    def test_lien_revoque_404(self):
        token = self._creer_lien()
        LienDepotContrepartie.objects.filter(token=token).update(actif=False)
        resp = APIClient().get(f'{PUBLIC}{token}/')
        self.assertEqual(resp.status_code, 404)

    def test_lien_expire_404(self):
        token = self._creer_lien()
        LienDepotContrepartie.objects.filter(token=token).update(
            expires_at=timezone.now() - timedelta(days=1))
        resp = APIClient().get(f'{PUBLIC}{token}/')
        self.assertEqual(resp.status_code, 404)

    def test_token_inconnu_404(self):
        resp = APIClient().get(f'{PUBLIC}jeton-inexistant/')
        self.assertEqual(resp.status_code, 404)


class DepotContrepartieServiceTests(TestCase):
    """Gardes du service (indépendamment de l'API)."""

    def setUp(self):
        self.co = make_company('ntdoc1-svc', 'Service')
        self.contrat = Contrat.objects.create(company=self.co, objet='S')

    def test_nom_fichier_vide_refuse(self):
        with self.assertRaises(services.DepotContrepartieError) as ctx:
            services.deposer_document_contrepartie(
                self.contrat, nom_fichier='', fichier_key='k/1.pdf')
        self.assertIn('nom_fichier', str(ctx.exception))

    def test_fichier_vide_refuse(self):
        with self.assertRaises(services.DepotContrepartieError) as ctx:
            services.deposer_document_contrepartie(
                self.contrat, nom_fichier='vide.pdf', contenu=b'')
        self.assertIn('fichier', str(ctx.exception))

    def test_sans_contenu_ni_cle_refuse(self):
        with self.assertRaises(services.DepotContrepartieError):
            services.deposer_document_contrepartie(
                self.contrat, nom_fichier='ok.pdf')

    def test_archiver_est_idempotent(self):
        doc = services.deposer_document_contrepartie(
            self.contrat, nom_fichier='x.pdf', fichier_key='k/x.pdf')
        services.archiver_document_contrepartie(doc)
        premier = doc.date_archivage
        services.archiver_document_contrepartie(doc)
        doc.refresh_from_db()
        self.assertEqual(doc.date_archivage, premier)

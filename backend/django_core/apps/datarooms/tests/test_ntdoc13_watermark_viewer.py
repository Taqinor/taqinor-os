"""NTDOC13 — Filigrane dynamique PAR VIEWER sur les documents d'une salle.

Couvre :
  * l'étiquette de filigrane porte le NOM et l'EMAIL du viewer (jamais la
    seule identité société de GED21) — deux viewers, deux étiquettes ;
  * télécharger le MÊME document via deux liens viewer produit deux flux
    filigranés DIFFÉREMMENT ;
  * le fichier original en GED reste byte-identique ;
  * un document masqué ou hors de la salle renvoie 404 (jamais un oracle) ;
  * un lien révoqué/expiré ne sert plus rien.

Horloge FIGÉE : l'horodatage du filigrane est injecté explicitement.
"""
import datetime
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.datarooms import services

from ._base import make_admin, make_company, make_document


REFERENCE = timezone.make_aware(datetime.datetime(2026, 6, 15, 9, 30, 0))
PDF_ORIGINAL = b'%PDF-1.4 contenu original de la salle'


class NtDoc13Base(TestCase):
    def setUp(self):
        self.co_a = make_company('ntdoc13-a', 'Ntdoc13 A')
        self.admin_a = make_admin(self.co_a, 'ntdoc13-admin-a')
        self.salle = services.creer_salle(
            company=self.co_a, nom='Due diligence', created_by=self.admin_a)
        self.doc = make_document(self.co_a, 'Comptes 2025')
        services.ajouter_documents(self.salle, [self.doc])
        self.viewer_a = services.inviter_viewer(
            self.salle, nom='Alice Investisseur', email='alice@example.com')
        self.viewer_b = services.inviter_viewer(
            self.salle, nom='Bob Banquier', email='bob@example.com')

    def _url(self, acces, document=None):
        document = document or self.doc
        return (f'/api/django/datarooms/public/{acces.token}/documents/'
                f'{document.pk}/')


class EtiquetteParViewerTests(NtDoc13Base):
    def test_etiquette_porte_nom_et_email_du_viewer(self):
        etiquette = services.watermark_label_viewer(
            self.viewer_a, now=REFERENCE)
        self.assertIn('Alice Investisseur', etiquette)
        self.assertIn('alice@example.com', etiquette)
        self.assertIn('2026-06-15 09:30', etiquette)
        self.assertTrue(etiquette.startswith('CONFIDENTIEL'))

    def test_deux_viewers_deux_etiquettes(self):
        self.assertNotEqual(
            services.watermark_label_viewer(self.viewer_a, now=REFERENCE),
            services.watermark_label_viewer(self.viewer_b, now=REFERENCE))

    def test_viewer_sans_email_reste_identifiable(self):
        sans_email = services.inviter_viewer(self.salle, nom='Carl Sans Mail')
        etiquette = services.watermark_label_viewer(sans_email, now=REFERENCE)
        self.assertIn('Carl Sans Mail', etiquette)
        self.assertNotIn('—  —', etiquette)


class FluxFiligraneTests(NtDoc13Base):
    def _servir(self, acces):
        """Sert le document en simulant le stockage objet et le rendu PDF.

        Le rendu réel (PyMuPDF) n'est PAS une dépendance dure : on remplace
        `apply_watermark` par un marquage déterministe pour pouvoir assurer que
        l'étiquette INJECTÉE est bien celle du viewer."""
        def _faux_watermark(data, mime, texte):
            return data + b'||' + texte.encode('utf-8'), True

        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(PDF_ORIGINAL, None)), \
                mock.patch('apps.ged.services.apply_watermark',
                           side_effect=_faux_watermark):
            return self.client.get(self._url(acces))

    def test_deux_liens_produisent_deux_fichiers_differents(self):
        rep_a = self._servir(self.viewer_a)
        rep_b = self._servir(self.viewer_b)
        self.assertEqual(rep_a.status_code, 200)
        self.assertEqual(rep_b.status_code, 200)
        self.assertNotEqual(rep_a.content, rep_b.content)
        self.assertIn(b'Alice Investisseur', rep_a.content)
        self.assertIn(b'Bob Banquier', rep_b.content)

    def test_original_ged_reste_byte_identique(self):
        rep = self._servir(self.viewer_a)
        self.assertNotEqual(rep.content, PDF_ORIGINAL)
        # Rien n'a été réécrit côté GED : la version courante est intacte.
        from apps.ged.models import DocumentVersion
        version = DocumentVersion.objects.get(document=self.doc, version=1)
        self.assertEqual(version.file_key, f'ged/{self.co_a.pk}/'
                                           f'{self.doc.pk}.pdf')
        self.assertEqual(DocumentVersion.objects.filter(
            document=self.doc).count(), 1)

    def test_entetes_de_diffusion(self):
        rep = self._servir(self.viewer_a)
        self.assertEqual(rep['X-Content-Type-Options'], 'nosniff')
        self.assertIn('noindex', rep['X-Robots-Tag'])
        self.assertIn('inline', rep['Content-Disposition'])

    def test_sans_lib_de_rendu_l_original_est_servi_sans_erreur(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(PDF_ORIGINAL, None)), \
                mock.patch('apps.ged.services.apply_watermark',
                           return_value=(PDF_ORIGINAL, False)):
            rep = self.client.get(self._url(self.viewer_a))
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(rep.content, PDF_ORIGINAL)


class GardesAccesDocumentTests(NtDoc13Base):
    def test_document_masque_404(self):
        from apps.datarooms.models import SalleDeDonneesDocument
        SalleDeDonneesDocument.objects.filter(salle=self.salle).update(
            visible=False)
        self.assertEqual(
            self.client.get(self._url(self.viewer_a)).status_code, 404)

    def test_document_hors_salle_404(self):
        etranger = make_document(self.co_a, 'Document non partagé')
        reponse = self.client.get(self._url(self.viewer_a, document=etranger))
        self.assertEqual(reponse.status_code, 404)

    def test_lien_revoque_ne_sert_plus_rien(self):
        services.revoquer_acces(self.viewer_a)
        self.assertEqual(
            self.client.get(self._url(self.viewer_a)).status_code, 404)

    def test_lien_expire_410(self):
        self.viewer_a.expires_at = timezone.now() - datetime.timedelta(days=1)
        self.viewer_a.save(update_fields=['expires_at'])
        self.assertEqual(
            self.client.get(self._url(self.viewer_a)).status_code, 410)

"""AUD719 — coffre documents employé : dépôt et suppression tracés + confirmés.

DÉFAUT (rouge avant ce correctif) : `DocumentEmployeViewSet.create()` et
`perform_destroy()` n'écrivaient JAMAIS dans le chatter du dossier
(`DossierActivity`). Le vrai enjeu n'est pas seulement l'absence de log mais
l'IRRÉVERSIBILITÉ : un porteur `rh_gerer` détruisait le contrat de travail ou la
CIN scannée d'un salarié — la ligne ET l'objet MinIO partaient — et rien nulle
part ne montrait que le document avait existé.

Après correctif :
* le dépôt écrit une ligne `DossierActivity` (qui / quel type / quel fichier) ;
* la suppression d'un CONTRAT / CIN / RIB exige un `motif` ET un `confirmer`
  égal au type du document ; sans eux, 400 et RIEN n'est effacé ;
* la suppression écrite est tracée AVANT la destruction, sur le DOSSIER — donc
  la trace survit au document.
"""
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.records.models import Attachment
from apps.rh.models import DocumentEmploye, DossierActivity, DossierEmploye

User = get_user_model()

URL = '/api/django/rh/documents/'


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


def fake_store(file, *, company=None, audio=False):
    return ({'file_key': 'attachments/aud719/contrat.pdf',
             'filename': 'contrat-travail.pdf',
             'size': 4096, 'mime': 'application/pdf'}, None)


class CoffreDocumentsTraceTests(TestCase):
    def setUp(self):
        self.co = make_company('aud719', 'A')
        self.rh = make_user(self.co, 'aud719-rh')
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='D1', nom='Tazi', prenom='Reda')

    def _deposer(self, type_document='contrat'):
        pdf = BytesIO(b'%PDF-1.4 contrat')
        pdf.name = 'contrat-travail.pdf'
        with mock.patch('apps.rh.views.store_attachment',
                        side_effect=fake_store):
            resp = auth(self.rh).post(URL, {
                'employe': self.emp.id, 'type_document': type_document,
                'file': pdf,
            }, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        return DocumentEmploye.objects.get(pk=resp.data['id'])

    def test_depot_journalise_dans_le_chatter_du_dossier(self):
        doc = self._deposer()
        traces = DossierActivity.objects.filter(employe=self.emp)
        self.assertEqual(traces.count(), 1)
        trace = traces.first()
        self.assertEqual(trace.auteur, self.rh)          # WHO
        self.assertEqual(trace.company, self.co)
        self.assertIn('Contrat', trace.message)          # WHAT
        self.assertIn(str(doc.pk), trace.message)
        self.assertIsNotNone(trace.date_creation)        # WHEN

    def test_suppression_contrat_sans_motif_refusee(self):
        doc = self._deposer('contrat')
        resp = auth(self.rh).delete(f'{URL}{doc.pk}/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('motif', resp.data)
        self.assertTrue(DocumentEmploye.objects.filter(pk=doc.pk).exists())
        self.assertTrue(
            Attachment.objects.filter(pk=doc.attachment_id).exists())

    def test_suppression_cin_sans_confirmation_refusee(self):
        doc = self._deposer('cin')
        resp = auth(self.rh).delete(
            f'{URL}{doc.pk}/?motif=doublon')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('confirmer', resp.data)
        self.assertTrue(DocumentEmploye.objects.filter(pk=doc.pk).exists())

    def test_suppression_rib_confirmee_passe_et_laisse_une_trace(self):
        doc = self._deposer('rib')
        with mock.patch('apps.rh.views.delete_attachment') as suppr:
            resp = auth(self.rh).delete(
                f'{URL}{doc.pk}/?motif=RIB+erron%C3%A9&confirmer=rib')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(DocumentEmploye.objects.filter(pk=doc.pk).exists())
        suppr.assert_called_once()
        # La trace survit au document supprimé : elle vit sur le DOSSIER.
        trace = DossierActivity.objects.filter(
            employe=self.emp, message__contains='SUPPRIMÉ').first()
        self.assertIsNotNone(trace)
        self.assertEqual(trace.auteur, self.rh)
        self.assertIn('RIB', trace.message)
        self.assertIn('attachments/aud719/contrat.pdf', trace.message)
        self.assertIn('motif', trace.message)

    def test_document_non_sensible_supprimable_mais_toujours_trace(self):
        """Un « autre » document ne demande pas de confirmation renforcée —
        il laisse malgré tout sa trace WHO/WHAT/WHEN."""
        doc = self._deposer('autre')
        with mock.patch('apps.rh.views.delete_attachment'):
            resp = auth(self.rh).delete(f'{URL}{doc.pk}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(DocumentEmploye.objects.filter(pk=doc.pk).exists())
        self.assertTrue(DossierActivity.objects.filter(
            employe=self.emp, message__contains='SUPPRIMÉ').exists())

"""XGED27 — Envoi en masse de demandes de signature.

Couvre :
  * un CSV de N destinataires crée N documents personnalisés + N demandes de
    signature tracées sous un lot ;
  * les erreurs par ligne sont rapportées sans bloquer le lot ;
  * les compteurs se rafraîchissent depuis l'état réel des demandes ;
  * isolation société.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import DemandeSignatureDocument, LotEnvoi, ModeleDocument

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


class XGed27Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged27-a', 'Xged27 A')
        self.admin_a = make_user(self.co_a, 'xged27-admin-a', 'admin')
        self.modele = ModeleDocument.objects.create(
            company=self.co_a, nom='Renouvellement maintenance',
            corps_html='<p>Bonjour {{ nom }}, votre contrat expire.</p>')
        self._store_patch = mock.patch(
            'apps.ged.services._store_bytes',
            side_effect=self._fake_store_bytes)
        self._store_patch.start()
        self.addCleanup(self._store_patch.stop)
        self._weasy_patch = mock.patch(
            'apps.ged.services.rendre_modele',
            side_effect=self._fake_rendre_modele)
        self._weasy_patch.start()
        self.addCleanup(self._weasy_patch.stop)

    def _fake_store_bytes(self, data, *, mime='application/pdf'):
        import uuid
        key = f'attachments/{uuid.uuid4().hex}.pdf'
        return key, {'filename': key, 'size': len(data), 'mime': mime}

    def _fake_rendre_modele(self, modele, contexte):
        return b'%PDF-1.4\n%fake\n%%EOF'


class ServiceTests(XGed27Base):
    def test_csv_de_n_destinataires_cree_n_documents_et_demandes(self):
        destinataires = [
            {'nom': 'Client A', 'email': 'a@example.com'},
            {'nom': 'Client B', 'email': 'b@example.com'},
        ]
        lot = services.creer_lot_envoi_signature(
            company=self.co_a, modele=self.modele, destinataires=destinataires,
            libelle='Renouvellement 2026', created_by=self.admin_a)
        self.assertEqual(lot.total, 2)
        self.assertEqual(lot.nb_envoyes, 2)
        self.assertEqual(lot.nb_erreurs, 0)
        self.assertEqual(
            DemandeSignatureDocument.objects.filter(company=self.co_a).count(), 2)

    def test_erreur_par_ligne_ne_bloque_pas_le_lot(self):
        destinataires = [
            {'nom': 'Client A', 'email': 'a@example.com'},
            {'nom': '', 'email': ''},  # ligne invalide
            {'nom': 'Client C', 'email': 'c@example.com'},
        ]
        lot = services.creer_lot_envoi_signature(
            company=self.co_a, modele=self.modele, destinataires=destinataires,
            created_by=self.admin_a)
        self.assertEqual(lot.total, 3)
        self.assertEqual(lot.nb_envoyes, 2)
        self.assertEqual(lot.nb_erreurs, 1)
        erreurs = [r for r in lot.resultats if not r['ok']]
        self.assertEqual(len(erreurs), 1)
        self.assertEqual(erreurs[0]['ligne'], 1)

    def test_rafraichir_compteurs_depuis_etat_reel(self):
        destinataires = [
            {'nom': 'Client A', 'email': 'a@example.com'},
            {'nom': 'Client B', 'email': 'b@example.com'},
        ]
        lot = services.creer_lot_envoi_signature(
            company=self.co_a, modele=self.modele, destinataires=destinataires,
            created_by=self.admin_a)
        demande_id = lot.resultats[0]['demande_id']
        DemandeSignatureDocument.objects.filter(pk=demande_id).update(
            statut='signe')
        lot = services.rafraichir_compteurs_lot_envoi(lot)
        self.assertEqual(lot.nb_signes, 1)
        self.assertEqual(lot.nb_vus, 1)


class ViewTests(XGed27Base):
    def test_envoi_masse_via_csv_endpoint(self):
        api = auth(self.admin_a)
        csv_content = (
            'nom,email\r\n'
            'Client A,a@example.com\r\n'
            'Client B,b@example.com\r\n'
        ).encode('utf-8')
        upload = SimpleUploadedFile(
            'destinataires.csv', csv_content, content_type='text/csv')
        resp = api.post('/api/django/ged/lots-envoi/envoi-masse/', {
            'modele': self.modele.pk, 'libelle': 'Renouvellement 2026',
            'csv': upload,
        }, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['total'], 2)
        self.assertEqual(resp.data['nb_envoyes'], 2)

    def test_sans_destinataires_400(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/lots-envoi/envoi-masse/', {
            'modele': self.modele.pk,
        }, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_societe(self):
        co_b = make_company('xged27-b', 'Xged27 B')
        admin_b = make_user(co_b, 'xged27-admin-b', 'admin')
        lot = LotEnvoi.objects.create(
            company=self.co_a, modele=self.modele, libelle='Lot A')
        api_b = auth(admin_b)
        resp = api_b.get(f'/api/django/ged/lots-envoi/{lot.pk}/')
        self.assertEqual(resp.status_code, 404)

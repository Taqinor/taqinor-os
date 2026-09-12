"""NTDOC10 — Empreinte cryptographique visible sur le certificat de complétion.

Couvre :
  * l'empreinte du certificat est un SHA-256 déterministe, recalculable ;
  * le HTML du certificat imprime LISIBLEMENT le hash du document ET
    l'empreinte du certificat, plus l'URL et le QR de vérification ;
  * générer le certificat mémorise l'empreinte sur la demande (idempotent) ;
  * l'endpoint public confirme « intègre » sur la bonne empreinte et renvoie
    « non trouvé » sinon — sans jamais exposer le nom ni le contenu du
    document ;
  * une demande modifiée après émission ne se vérifie plus (l'intégrité est
    RECALCULÉE, pas relue) ;
  * sans la lib `qrcode`, le certificat se rend quand même (hash imprimé).
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, DocumentVersion, Folder

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class NtDoc10Base(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.co_a = make_company('ntdoc10-a', 'Ntdoc10 A')
        self.admin_a = make_user(self.co_a, 'ntdoc10-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a,
            nom='Contrat confidentiel Alpha')
        DocumentVersion.objects.create(
            company=self.co_a, document=self.doc_a, version=1,
            file_key='ged/ntdoc10/doc-a.pdf', filename='doc-a.pdf',
            mime='application/pdf')
        self.demande = services.demander_signature(
            self.doc_a, signataire_nom='Jean Client',
            signataire_email='jean@example.com', company=self.co_a,
            created_by=self.admin_a)
        self.demande.hash_contenu = 'a' * 64
        self.demande.save(update_fields=['hash_contenu'])
        self.api = APIClient()


class EmpreinteCertificatTests(NtDoc10Base):
    def test_empreinte_est_un_sha256_deterministe(self):
        empreinte = services.empreinte_certificat(self.demande)
        self.assertEqual(len(empreinte), 64)
        self.assertEqual(empreinte, services.empreinte_certificat(self.demande))

    def test_empreinte_change_si_la_demande_change(self):
        avant = services.empreinte_certificat(self.demande)
        self.demande.hash_contenu = 'b' * 64
        self.demande.save(update_fields=['hash_contenu'])
        self.assertNotEqual(avant, services.empreinte_certificat(self.demande))

    def test_deux_demandes_ont_des_empreintes_distinctes(self):
        autre = services.demander_signature(
            self.doc_a, signataire_nom='Autre Client',
            signataire_email='autre@example.com', company=self.co_a,
            created_by=self.admin_a)
        self.assertNotEqual(services.empreinte_certificat(self.demande),
                            services.empreinte_certificat(autre))

    def test_memorisation_idempotente(self):
        empreinte = services.memoriser_empreinte_certificat(self.demande)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.empreinte_certificat, empreinte)
        self.assertEqual(
            services.memoriser_empreinte_certificat(self.demande), empreinte)


class CertificatHtmlTests(NtDoc10Base):
    def test_html_imprime_les_deux_empreintes_et_le_qr(self):
        html = services._certificat_html(self.demande)
        self.demande.refresh_from_db()
        empreinte = self.demande.empreinte_certificat
        self.assertTrue(empreinte)
        # Hash du document signé ET empreinte du certificat, tous deux lisibles.
        self.assertIn('a' * 64, html)
        self.assertIn(empreinte, html)
        self.assertIn("Empreintes d'intégrité", html)
        self.assertIn(f'/api/django/ged/verifier-certificat/{empreinte}/', html)
        self.assertIn('data:image/png;base64,', html)

    @override_settings(PUBLIC_SITE_URL='https://erp.example.ma')
    def test_url_absolue_quand_le_site_public_est_configure(self):
        empreinte = services.empreinte_certificat(self.demande)
        self.assertEqual(
            services.url_verification_certificat(empreinte),
            f'https://erp.example.ma/api/django/ged/verifier-certificat/'
            f'{empreinte}/')

    def test_sans_qrcode_le_certificat_se_rend_quand_meme(self):
        with mock.patch.object(services, 'qr_verification_certificat',
                               return_value=None):
            html = services._certificat_html(self.demande)
        self.assertIn('a' * 64, html)
        self.assertIn('QR indisponible', html)
        self.assertNotIn('data:image/png;base64,', html)


class VerificationPubliqueTests(NtDoc10Base):
    def _url(self, empreinte):
        return f'/api/django/ged/verifier-certificat/{empreinte}/'

    def test_empreinte_valide_confirme_integre_sans_fuite(self):
        empreinte = services.memoriser_empreinte_certificat(self.demande)
        reponse = self.api.get(self._url(empreinte))
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.data['integre'])
        self.assertEqual(reponse.data['type'], 'certificat_completion')
        self.assertEqual(reponse.data['hash_document'], 'a' * 64)
        # Jamais le nom du document, jamais l'identité d'un signataire.
        corps = str(reponse.data)
        self.assertNotIn('Contrat confidentiel Alpha', corps)
        self.assertNotIn('jean@example.com', corps)
        self.assertNotIn('Jean Client', corps)

    def test_empreinte_inconnue_non_trouvee(self):
        reponse = self.api.get(self._url('f' * 64))
        self.assertEqual(reponse.status_code, 404)
        self.assertFalse(reponse.data['integre'])

    def test_empreinte_mal_formee_non_trouvee(self):
        reponse = self.api.get(self._url('pas-une-empreinte'))
        self.assertEqual(reponse.status_code, 404)
        self.assertFalse(reponse.data['integre'])

    def test_demande_modifiee_apres_emission_ne_se_verifie_plus(self):
        empreinte = services.memoriser_empreinte_certificat(self.demande)
        self.assertEqual(self.api.get(self._url(empreinte)).status_code, 200)
        # Altération du contenu couvert par le certificat : l'empreinte
        # recalculée ne correspond plus à celle mémorisée.
        self.demande.hash_contenu = 'c' * 64
        self.demande.save(update_fields=['hash_contenu'])
        self.assertEqual(self.api.get(self._url(empreinte)).status_code, 404)

    def test_endpoint_ne_demande_aucune_authentification(self):
        empreinte = services.memoriser_empreinte_certificat(self.demande)
        anonyme = APIClient()
        self.assertEqual(anonyme.get(self._url(empreinte)).status_code, 200)

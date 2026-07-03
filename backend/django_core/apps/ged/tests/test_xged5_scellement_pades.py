"""XGED5 — Scellement cryptographique des PDF signés + horodatage qualifié
(gated).

Couvre :
  * sans pyHanko installé (cas réel de cet environnement) : `sceller_pdf`
    dégrade proprement et renvoie le PDF INCHANGÉ, `scelle=False` ;
  * `tsa_url_configuree()` vide par défaut → no-op déterministe ;
  * `_certificat_societe_pour_scellement` renvoie None sans
    `GED_PADES_CERT_PATH`/`GED_PADES_KEY_PATH`, même si pyHanko est "présent"
    (mocké) ;
  * avec pyHanko simulé disponible ET un certificat configuré, le PDF est
    scellé (mocké — la vraie lib n'est pas installée dans cet environnement) ;
  * le flux XGED4 (classement automatique) reste intact que le scellement
    réussisse ou dégrade (jamais bloquant) ;
  * `sceller_pdf` ne lève jamais, quel que soit l'échec interne.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

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


class XGed5Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged5-a', 'Xged5 A')
        self.admin_a = make_user(self.co_a, 'xged5-admin-a', 'admin')


class NoOpWithoutPyHankoTests(XGed5Base):
    def test_pades_signer_disponible_false_in_this_env(self):
        """pyHanko n'est PAS installé dans cet environnement — confirme le
        chemin de dégradation réel (pas seulement mocké)."""
        self.assertFalse(services._pades_signer_disponible())

    def test_sceller_pdf_returns_original_unchanged(self):
        original = b'%PDF-1.4 contenu original'
        out, scelle = services.sceller_pdf(original, company=self.co_a)
        self.assertEqual(out, original)
        self.assertFalse(scelle)

    def test_tsa_url_configuree_empty_by_default(self):
        self.assertEqual(services.tsa_url_configuree(), '')

    def test_certificat_societe_none_without_pyhanko(self):
        self.assertIsNone(
            services._certificat_societe_pour_scellement(self.co_a))


class NoOpWithoutCertificatTests(XGed5Base):
    def test_pyhanko_present_but_no_cert_configured_returns_none(self):
        """pyHanko « disponible » (mocké) mais sans certificat configuré →
        toujours no-op (pas de génération de clé sans provisionnement)."""
        with mock.patch('apps.ged.services._pades_signer_disponible',
                        return_value=True):
            self.assertIsNone(
                services._certificat_societe_pour_scellement(self.co_a))

    def test_sceller_pdf_noop_when_pyhanko_present_but_no_signer(self):
        with mock.patch('apps.ged.services._pades_signer_disponible',
                        return_value=True):
            original = b'%PDF-1.4 x'
            out, scelle = services.sceller_pdf(original, company=self.co_a)
        self.assertEqual(out, original)
        self.assertFalse(scelle)


@override_settings(GED_TSA_URL='https://tsa.example.ma/timestamp')
class TsaGatingTests(XGed5Base):
    def test_tsa_url_configuree_reads_setting(self):
        self.assertEqual(
            services.tsa_url_configuree(), 'https://tsa.example.ma/timestamp')


class SealingWithMockedPyHankoTests(XGed5Base):
    @override_settings(GED_PADES_CERT_PATH='/tmp/cert.pem',
                       GED_PADES_KEY_PATH='/tmp/key.pem')
    def test_sceller_pdf_seals_when_signer_resolved(self):
        """Avec un signataire résolu (mocké — la vraie lib n'est pas
        installée), `sceller_pdf` produit un PDF scellé (`scelle=True`)."""
        fake_signer = object()
        fake_out = mock.Mock()
        fake_out.getvalue.return_value = b'%PDF-1.4 scelle'
        with mock.patch('apps.ged.services._pades_signer_disponible',
                        return_value=True), \
             mock.patch('apps.ged.services._certificat_societe_pour_scellement',
                        return_value=fake_signer), \
             mock.patch.dict('sys.modules', {
                 'pyhanko.pdf_utils.incremental_writer': mock.MagicMock(),
                 'pyhanko.sign': mock.MagicMock(
                     sign_pdf=mock.Mock(return_value=fake_out),
                     PdfSignatureMetadata=mock.Mock(),
                     timestamps=mock.MagicMock()),
                 'pyhanko.sign.timestamps': mock.MagicMock(),
             }):
            out, scelle = services.sceller_pdf(
                b'%PDF-1.4 original', company=self.co_a)
        self.assertTrue(scelle)
        self.assertEqual(out, b'%PDF-1.4 scelle')

    def test_sceller_pdf_never_raises_on_internal_failure(self):
        """Toute exception interne (signature, TSA, I/O) dégrade en silence —
        `sceller_pdf` ne lève JAMAIS."""
        with mock.patch('apps.ged.services._pades_signer_disponible',
                        return_value=True), \
             mock.patch('apps.ged.services._certificat_societe_pour_scellement',
                        side_effect=RuntimeError('boom')):
            out, scelle = services.sceller_pdf(
                b'%PDF-1.4 original', company=self.co_a)
        self.assertEqual(out, b'%PDF-1.4 original')
        self.assertFalse(scelle)


class Xged4FlowIntactTests(XGed5Base):
    """XGED5 ne casse JAMAIS le flux de classement automatique XGED4."""

    def setUp(self):
        super().setUp()
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat à signer')
        DocumentVersion.objects.create(
            company=self.co_a, document=self.doc_a, version=1,
            file_key='ged/xged5/doc-a.pdf', filename='doc-a.pdf',
            mime='application/pdf')
        self.demande = services.demander_signature(
            self.doc_a, signataire_nom='Jean', signataire_email='jean@x.com',
            company=self.co_a, created_by=self.admin_a)

    def test_classement_still_works_without_pyhanko(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'%PDF data', None)):
            services.marquer_signe(self.demande)
        signes = Document.objects.filter(
            company=self.co_a, folder__nom='Signés')
        self.assertEqual(signes.count(), 2)

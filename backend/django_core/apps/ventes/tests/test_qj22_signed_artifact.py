"""QJ22 — Signed-proposal artifact + "signé" surfacing in the devis list.

Tests cover:
  (a) _store_signed_pdf is called on acceptance and stores signed_pdf_key.
  (b) Idempotency — re-acceptance / re-call of _store_signed_pdf does not
      overwrite an existing signed_pdf_key.
  (c) Engine failure is best-effort — does not block acceptance.
  (d) DevisSerializer exposes est_signe=True + signature_info when signed.
  (e) est_signe=False and signature_info=None when no signature exists.
  (f) Company scoping — est_signe cannot be contaminated across companies.
  (g) No prix_achat / marge in signature_info (rule #4).
  (h) Seller notification still fires after QJ22 additions (smoke).
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, DevisSignature
from apps.ventes.serializers import DevisSerializer
from apps.ventes.services import accept_devis

User = get_user_model()

_DUMMY_KEY = 'devis/1/DEV-QJ22-0001.pdf'


def _make_company(slug='qj22-co', nom='QJ22 Co'):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return c


def _make_user(company, username='qj22u'):
    return User.objects.get_or_create(
        username=username,
        defaults={'password': 'x', 'role_legacy': 'responsable',
                  'company': company},
    )[0]


def _make_client(company, nom='Client QJ22'):
    return Client.objects.get_or_create(
        company=company, nom=nom, defaults={})[0]


def _make_devis(company, client, ref='DEV-QJ22-0001',
                statut=Devis.Statut.ENVOYE):
    return Devis.objects.create(
        company=company, reference=ref,
        client=client, statut=statut, taux_tva=Decimal('20'))


# ═══════════════════════════════════════════════════════════════════════════
# (a) signed_pdf_key stored on acceptance
# ═══════════════════════════════════════════════════════════════════════════

class TestSignedPdfKeyStored(TestCase):
    """QJ22(a) — accept_devis stores signed_pdf_key on DevisSignature."""

    def setUp(self):
        self.company = _make_company('qj22-a', 'QJ22 A')
        self.client_obj = _make_client(self.company, 'QJ22 A Client')
        self.user = _make_user(self.company, 'qj22au')

    @patch('apps.ventes.services.generate_premium_devis_pdf',
           return_value=_DUMMY_KEY)
    def test_signed_pdf_key_set_after_accept(self, mock_gen):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ22-A01')
        accept_devis(devis=devis, user=self.user, nom='M. Bennani')
        sig = DevisSignature.objects.get(devis=devis)
        self.assertEqual(sig.signed_pdf_key, _DUMMY_KEY)

    @patch('apps.ventes.services.generate_premium_devis_pdf',
           return_value=_DUMMY_KEY)
    def test_generate_premium_devis_pdf_called_with_persist_true(
            self, mock_gen):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ22-A02')
        accept_devis(devis=devis, user=self.user, nom='Test')
        mock_gen.assert_called_once()
        call_args = mock_gen.call_args
        # persist=True is required so the PDF is stored permanently.
        self.assertTrue(call_args.kwargs.get('persist', call_args.args[2]
                        if len(call_args.args) > 2 else True))


# ═══════════════════════════════════════════════════════════════════════════
# (b) Idempotency — existing signed_pdf_key never overwritten
# ═══════════════════════════════════════════════════════════════════════════

class TestSignedPdfKeyIdempotency(TestCase):
    """QJ22(b) — _store_signed_pdf does not overwrite an existing key."""

    def setUp(self):
        self.company = _make_company('qj22-b', 'QJ22 B')
        self.client_obj = _make_client(self.company, 'QJ22 B Client')
        self.user = _make_user(self.company, 'qj22bu')

    @patch('apps.ventes.services.generate_premium_devis_pdf',
           return_value='new/key.pdf')
    def test_existing_key_not_overwritten(self, mock_gen):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ22-B01')
        # Manually create the signature with an existing key.
        DevisSignature.objects.create(
            company=self.company,
            devis=devis,
            signataire_nom='Alice',
            consentement_explicite=True,
            content_hash=DevisSignature.compute_content_hash(devis),
            signed_at=timezone.now(),
            signed_pdf_key='existing/key.pdf',
        )
        # Set devis as accepte so re-acceptance via idempotent path returns early.
        devis.statut = Devis.Statut.ACCEPTE
        devis.save(update_fields=['statut'])
        # Call _store_signed_pdf directly to test idempotency.
        from apps.ventes.services import _store_signed_pdf
        _store_signed_pdf(devis=devis)
        mock_gen.assert_not_called()
        sig = DevisSignature.objects.get(devis=devis)
        self.assertEqual(sig.signed_pdf_key, 'existing/key.pdf')


# ═══════════════════════════════════════════════════════════════════════════
# (c) Best-effort — PDF engine failure does not block acceptance
# ═══════════════════════════════════════════════════════════════════════════

class TestSignedPdfKeyBestEffort(TestCase):
    """QJ22(c) — PDF engine failure is swallowed; acceptance still succeeds."""

    def setUp(self):
        self.company = _make_company('qj22-c', 'QJ22 C')
        self.client_obj = _make_client(self.company, 'QJ22 C Client')
        self.user = _make_user(self.company, 'qj22cu')

    @patch('apps.ventes.services.generate_premium_devis_pdf',
           side_effect=Exception('WeasyPrint offline'))
    def test_pdf_engine_failure_does_not_block_acceptance(self, mock_gen):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ22-C01')
        # Should NOT raise.
        accept_devis(devis=devis, user=self.user, nom='Test C')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')
        # Signature record created; signed_pdf_key is None (engine failed).
        sig = DevisSignature.objects.get(devis=devis)
        self.assertIsNone(sig.signed_pdf_key)


# ═══════════════════════════════════════════════════════════════════════════
# (d) DevisSerializer exposes est_signe + signature_info when signed
# ═══════════════════════════════════════════════════════════════════════════

class TestDevisSerializerSignedFields(TestCase):
    """QJ22(d) — est_signe=True and signature_info populated after signature."""

    def setUp(self):
        self.company = _make_company('qj22-d', 'QJ22 D')
        self.client_obj = _make_client(self.company, 'QJ22 D Client')
        self.user = _make_user(self.company, 'qj22du')

    @patch('apps.ventes.services.generate_premium_devis_pdf',
           return_value=_DUMMY_KEY)
    def test_est_signe_true_after_acceptance(self, mock_gen):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ22-D01')
        accept_devis(devis=devis, user=self.user, nom='M. Signer')
        data = DevisSerializer(devis).data
        self.assertTrue(data['est_signe'])

    @patch('apps.ventes.services.generate_premium_devis_pdf',
           return_value=_DUMMY_KEY)
    def test_signature_info_has_required_fields(self, mock_gen):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ22-D02')
        accept_devis(devis=devis, user=self.user, nom='Madame Signer')
        data = DevisSerializer(devis).data
        info = data['signature_info']
        self.assertIsNotNone(info)
        self.assertEqual(info['signataire_nom'], 'Madame Signer')
        self.assertIn('signed_at', info)
        self.assertIsNotNone(info['signed_at'])
        self.assertIn('has_pdf', info)
        self.assertTrue(info['has_pdf'])

    @patch('apps.ventes.services.generate_premium_devis_pdf',
           return_value=_DUMMY_KEY)
    def test_signature_info_has_pdf_false_when_no_key(self, mock_gen):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ22-D03')
        # Create signature without signed_pdf_key.
        DevisSignature.objects.create(
            company=self.company,
            devis=devis,
            signataire_nom='No PDF',
            consentement_explicite=True,
            content_hash=DevisSignature.compute_content_hash(devis),
            signed_at=timezone.now(),
            signed_pdf_key=None,
        )
        data = DevisSerializer(devis).data
        info = data['signature_info']
        self.assertFalse(info['has_pdf'])


# ═══════════════════════════════════════════════════════════════════════════
# (e) est_signe=False when no signature
# ═══════════════════════════════════════════════════════════════════════════

class TestDevisSerializerNotSigned(TestCase):
    """QJ22(e) — est_signe=False and signature_info=None for unsigned devis."""

    def setUp(self):
        self.company = _make_company('qj22-e', 'QJ22 E')
        self.client_obj = _make_client(self.company, 'QJ22 E Client')

    def test_est_signe_false_for_new_devis(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ22-E01',
                            statut=Devis.Statut.BROUILLON)
        data = DevisSerializer(devis).data
        self.assertFalse(data['est_signe'])
        self.assertIsNone(data['signature_info'])

    def test_est_signe_false_for_accepte_without_signature(self):
        """A devis can be accepte without a DevisSignature (in-app acceptance
        path in tests that mock _create_esign_record or skip it)."""
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ22-E02',
                            statut=Devis.Statut.ACCEPTE)
        data = DevisSerializer(devis).data
        self.assertFalse(data['est_signe'])
        self.assertIsNone(data['signature_info'])


# ═══════════════════════════════════════════════════════════════════════════
# (f) Company scoping
# ═══════════════════════════════════════════════════════════════════════════

class TestSignedPdfKeyCompanyScoping(TestCase):
    """QJ22(f) — signature_info cannot be contaminated across companies."""

    def setUp(self):
        self.co_a = _make_company('qj22-fa', 'QJ22 FA')
        self.co_b = _make_company('qj22-fb', 'QJ22 FB')
        self.cli_a = _make_client(self.co_a, 'Cli A')
        self.cli_b = _make_client(self.co_b, 'Cli B')

    @patch('apps.ventes.services.generate_premium_devis_pdf',
           return_value=_DUMMY_KEY)
    def test_signature_info_not_visible_from_other_company(self, mock_gen):
        user_a = _make_user(self.co_a, 'qj22fua')
        devis_a = _make_devis(self.co_a, self.cli_a, 'DEV-QJ22-FA01')
        devis_b = _make_devis(self.co_b, self.cli_b, 'DEV-QJ22-FB01')
        accept_devis(devis=devis_a, user=user_a, nom='A signer')
        # devis_b has no signature.
        data_b = DevisSerializer(devis_b).data
        self.assertFalse(data_b['est_signe'])
        self.assertIsNone(data_b['signature_info'])
        # devis_a has its own signature.
        data_a = DevisSerializer(devis_a).data
        self.assertTrue(data_a['est_signe'])


# ═══════════════════════════════════════════════════════════════════════════
# (g) No prix_achat / marge in signature_info (rule #4)
# ═══════════════════════════════════════════════════════════════════════════

class TestSignedPdfKeyNoPrixAchat(TestCase):
    """QJ22(g) — signature_info never exposes prix_achat/marge (rule #4)."""

    def setUp(self):
        self.company = _make_company('qj22-g', 'QJ22 G')
        self.client_obj = _make_client(self.company, 'QJ22 G Client')
        self.user = _make_user(self.company, 'qj22gu')

    @patch('apps.ventes.services.generate_premium_devis_pdf',
           return_value=_DUMMY_KEY)
    def test_no_prix_achat_in_signature_info(self, mock_gen):
        import json
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ22-G01')
        accept_devis(devis=devis, user=self.user, nom='Test G')
        data = DevisSerializer(devis).data
        raw = json.dumps(data)
        self.assertNotIn('prix_achat', raw)
        self.assertNotIn('marge', raw)


# ═══════════════════════════════════════════════════════════════════════════
# (h) Seller notification smoke — still fires after QJ22
# ═══════════════════════════════════════════════════════════════════════════

class TestQJ22SellerNotificationStillFires(TestCase):
    """QJ22(h) — adding _store_signed_pdf does not break seller notification."""

    def setUp(self):
        self.company = _make_company('qj22-h', 'QJ22 H')
        self.client_obj = _make_client(self.company, 'QJ22 H Client')
        self.seller = _make_user(self.company, 'qj22hs')

    @patch('apps.ventes.services.generate_premium_devis_pdf',
           return_value=_DUMMY_KEY)
    @patch('apps.ventes.services._notify_seller_accepted')
    def test_seller_notified_after_qj22(self, mock_notify, mock_gen):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ22-H01')
        devis.created_by = self.seller
        devis.save(update_fields=['created_by'])
        accept_devis(devis=devis, user=None, nom='Client H')
        mock_notify.assert_called_once()

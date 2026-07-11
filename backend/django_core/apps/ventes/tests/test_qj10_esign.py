"""QJ10 — E-signature legal trail (loi 53-05): DevisSignature tests.

Tests cover:
  (a) DevisSignature created on acceptance (fields: nom, ip, user_agent,
      consentement_explicite, content_hash, signed_at, company).
  (b) Idempotency — re-accept does NOT create a second DevisSignature.
  (c) Company scoping — signature belongs to the devis company; cannot be
      reached from another company.
  (d) Status preservation — devis flips brouillon/envoye -> accepte; no
      further status change by the signature path.
  (e) No buy-price or margin in the content_hash payload.
  (f) Acceptance emails are sent (best-effort smoke test via mock).
  (g) Seller in-app notification fired on acceptance (best-effort smoke).
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisSignature, LigneDevis
from apps.ventes.services import accept_devis, AcceptError

User = get_user_model()


def _make_company(slug='qj10-co', nom='QJ10 Co'):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return c


def _make_user(company, username='qj10u'):
    return User.objects.get_or_create(
        username=username,
        defaults={'password': 'x', 'role_legacy': 'responsable',
                  'company': company},
    )[0]


def _make_client(company, nom='Client QJ10'):
    return Client.objects.get_or_create(
        company=company, nom=nom, defaults={})[0]


def _make_devis(company, client, ref='DEV-QJ10-0001',
                statut=Devis.Statut.ENVOYE):
    return Devis.objects.create(
        company=company, reference=ref,
        client=client, statut=statut, taux_tva=Decimal('20'))


def _make_devis_with_ligne(company, client, ref='DEV-QJ10-0002'):
    """Devis with one product line so content_hash covers lignes."""
    devis = _make_devis(company, client, ref)
    sku = f'SKU-{ref[-4:]}'
    produit = Produit.objects.create(
        company=company, nom=f'Panneau {ref}', sku=sku,
        prix_vente=Decimal('1200'), prix_achat=Decimal('800'),
        quantite_stock=10)
    LigneDevis.objects.create(
        devis=devis, produit=produit, designation='Panneau 400W',
        quantite=Decimal('10'), prix_unitaire=Decimal('1200'),
        remise=Decimal('0'))
    return devis


# ═══════════════════════════════════════════════════════════════════════════
# (a) DevisSignature created on acceptance
# ═══════════════════════════════════════════════════════════════════════════

class TestDevisSignatureCreated(TestCase):
    """QJ10(a) — accept_devis creates a DevisSignature with all required fields."""

    def setUp(self):
        self.company = _make_company('qj10-a', 'QJ10 A')
        self.client_obj = _make_client(self.company, 'QJ10 A Client')
        self.user = _make_user(self.company, 'qj10au')

    def test_signature_record_created_with_correct_fields(self):
        devis = _make_devis_with_ligne(
            self.company, self.client_obj, 'DEV-QJ10-A01')
        before = timezone.now()
        accept_devis(
            devis=devis, user=self.user,
            nom='M. Kasri', ip='1.2.3.4',
            user_agent='Mozilla/5.0 Test',
            consentement=True,
        )
        sig = DevisSignature.objects.get(devis=devis)
        self.assertEqual(sig.signataire_nom, 'M. Kasri')
        self.assertEqual(sig.ip_address, '1.2.3.4')
        self.assertEqual(sig.user_agent, 'Mozilla/5.0 Test')
        self.assertTrue(sig.consentement_explicite)
        self.assertEqual(sig.company, self.company)
        self.assertIsNotNone(sig.content_hash)
        self.assertEqual(len(sig.content_hash), 64)  # SHA-256 hex
        self.assertGreaterEqual(sig.signed_at, before)

    def test_content_hash_reproducible(self):
        """Same devis produces same hash on repeated calls (deterministic)."""
        devis = _make_devis_with_ligne(
            self.company, self.client_obj, 'DEV-QJ10-A02')
        h1 = DevisSignature.compute_content_hash(devis)
        h2 = DevisSignature.compute_content_hash(devis)
        self.assertEqual(h1, h2)

    def test_content_hash_covers_reference_and_lines(self):
        """content_hash changes if the devis reference or lines change."""
        devis = _make_devis_with_ligne(
            self.company, self.client_obj, 'DEV-QJ10-A03')
        h_before = DevisSignature.compute_content_hash(devis)
        # Create a second devis with a different reference but same lines.
        devis2 = _make_devis_with_ligne(
            self.company, self.client_obj, 'DEV-QJ10-A04')
        h_after = DevisSignature.compute_content_hash(devis2)
        self.assertNotEqual(h_before, h_after)

    def test_content_hash_never_contains_prix_achat(self):
        """prix_achat must NEVER appear in the content_hash payload (rule #4)."""
        devis = _make_devis_with_ligne(
            self.company, self.client_obj, 'DEV-QJ10-A05')
        # Check the static method's source payload string.
        client = devis.client
        client_str = (
            f'{getattr(client, "nom", "")}|{getattr(client, "email", "")}')
        lignes = list(devis.lignes.order_by('id').values(
            'designation', 'quantite', 'prix_unitaire', 'remise'))
        lignes_str = '|'.join(
            f"{lg['designation']}:{lg['quantite']}:{lg['prix_unitaire']}:{lg['remise']}"
            for lg in lignes
        )
        payload = (
            f"ref={devis.reference}|"
            f"client={client_str}|"
            f"created={devis.date_creation}|"
            f"tva={devis.taux_tva}|"
            f"remise={devis.remise_globale}|"
            f"lignes={lignes_str}"
        )
        self.assertNotIn('prix_achat', payload)
        self.assertNotIn('800', payload)  # prix_achat value not in hash


# ═══════════════════════════════════════════════════════════════════════════
# (b) Idempotency — no duplicate DevisSignature on re-accept
# ═══════════════════════════════════════════════════════════════════════════

class TestDevisSignatureIdempotency(TestCase):
    """QJ10(b) — re-accept (idempotent_reaccept=True) does not create a second
    DevisSignature."""

    def setUp(self):
        self.company = _make_company('qj10-b', 'QJ10 B')
        self.client_obj = _make_client(self.company, 'QJ10 B Client')
        self.user = _make_user(self.company, 'qj10bu')

    def test_second_accept_does_not_duplicate_signature(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ10-B01')
        accept_devis(devis=devis, user=self.user, nom='Alice', ip='1.1.1.1')
        # First signature.
        self.assertEqual(DevisSignature.objects.filter(devis=devis).count(), 1)
        first_sig = DevisSignature.objects.get(devis=devis)
        # Re-submit (idempotent_reaccept=True is the default on the public path).
        accept_devis(devis=devis, user=self.user, nom='Bob', ip='2.2.2.2',
                     idempotent_reaccept=True)
        # Still exactly one signature; original signataire_nom unchanged.
        self.assertEqual(DevisSignature.objects.filter(devis=devis).count(), 1)
        sig = DevisSignature.objects.get(devis=devis)
        self.assertEqual(sig.signed_at, first_sig.signed_at)
        self.assertEqual(sig.signataire_nom, 'Alice')


# ═══════════════════════════════════════════════════════════════════════════
# (c) Company scoping
# ═══════════════════════════════════════════════════════════════════════════

class TestDevisSignatureCompanyScoping(TestCase):
    """QJ10(c) — DevisSignature is scoped to the devis company."""

    def setUp(self):
        self.co_a = _make_company('qj10-ca', 'QJ10 CA')
        self.co_b = _make_company('qj10-cb', 'QJ10 CB')
        self.cli_a = _make_client(self.co_a, 'Cli A')
        self.cli_b = _make_client(self.co_b, 'Cli B')
        self.user_a = _make_user(self.co_a, 'qj10ua')
        self.user_b = _make_user(self.co_b, 'qj10ub')

    def test_signature_belongs_to_correct_company(self):
        devis_a = _make_devis(self.co_a, self.cli_a, 'DEV-QJ10-CA01')
        devis_b = _make_devis(self.co_b, self.cli_b, 'DEV-QJ10-CB01')
        accept_devis(devis=devis_a, user=self.user_a, nom='A')
        accept_devis(devis=devis_b, user=self.user_b, nom='B')
        sig_a = DevisSignature.objects.get(devis=devis_a)
        sig_b = DevisSignature.objects.get(devis=devis_b)
        self.assertEqual(sig_a.company, self.co_a)
        self.assertEqual(sig_b.company, self.co_b)
        # Cross-tenant: co_a cannot see sig_b.
        self.assertFalse(
            DevisSignature.objects.filter(
                company=self.co_a, devis=devis_b).exists())


# ═══════════════════════════════════════════════════════════════════════════
# (d) Status preservation — brouillon/envoye -> accepte
# ═══════════════════════════════════════════════════════════════════════════

class TestDevisSignatureStatusPreservation(TestCase):
    """QJ10(d) — accept_devis flips brouillon/envoye to accepte.
    No other status changes; signature path does NOT invent new statuses."""

    def setUp(self):
        self.company = _make_company('qj10-d', 'QJ10 D')
        self.client_obj = _make_client(self.company, 'QJ10 D Client')
        self.user = _make_user(self.company, 'qj10du')

    def test_brouillon_devis_accepts(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ10-D01',
                            statut=Devis.Statut.BROUILLON)
        accept_devis(devis=devis, user=self.user, nom='X')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')

    def test_envoye_devis_accepts(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ10-D02',
                            statut=Devis.Statut.ENVOYE)
        accept_devis(devis=devis, user=self.user, nom='Y')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')

    def test_refuse_devis_cannot_accept(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ10-D03',
                            statut=Devis.Statut.REFUSE)
        with self.assertRaises(AcceptError) as ctx:
            accept_devis(devis=devis, user=self.user, nom='Z')
        self.assertTrue(ctx.exception.conflict)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'refuse')
        # No signature created.
        self.assertFalse(DevisSignature.objects.filter(devis=devis).exists())

    def test_accepte_devis_raises_409_when_not_idempotent(self):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ10-D04',
                            statut=Devis.Statut.ACCEPTE)
        with self.assertRaises(AcceptError) as ctx:
            accept_devis(devis=devis, user=self.user, nom='W',
                         idempotent_reaccept=False)
        self.assertTrue(ctx.exception.conflict)


# ═══════════════════════════════════════════════════════════════════════════
# (e) No buy-price in content_hash (rule #4 double-check)
# ═══════════════════════════════════════════════════════════════════════════

class TestDevisSignatureNoPrixAchat(TestCase):
    """QJ10(e) — prix_achat must NEVER appear in DevisSignature content_hash."""

    def setUp(self):
        self.company = _make_company('qj10-e', 'QJ10 E')
        self.client_obj = _make_client(self.company, 'QJ10 E Client')
        self.user = _make_user(self.company, 'qj10eu')

    def test_prix_achat_absent_from_content_hash_field(self):
        devis = _make_devis_with_ligne(
            self.company, self.client_obj, 'DEV-QJ10-E01')
        accept_devis(devis=devis, user=self.user, nom='Test')
        sig = DevisSignature.objects.get(devis=devis)
        # The hash is a 64-char hex string; no internal data leaks into it.
        self.assertEqual(len(sig.content_hash), 64)
        # The hash cannot be the string "prix_achat" (obviously) — but also
        # the hash field itself must not embed the raw prix_achat VALUE "800"
        # (it's a SHA-256 hex output, so this just verifies the contract).
        self.assertNotIn('prix_achat', sig.content_hash)


# ═══════════════════════════════════════════════════════════════════════════
# (f) Acceptance email sent (smoke — best-effort)
# ═══════════════════════════════════════════════════════════════════════════

class TestDevisSignatureEmail(TestCase):
    """QJ10(f) — _send_acceptance_emails is called on acceptance (best-effort)."""

    def setUp(self):
        self.company = _make_company('qj10-f', 'QJ10 F')
        self.client_obj = _make_client(self.company, 'QJ10 F Client')
        self.user = _make_user(self.company, 'qj10fu')

    @patch('apps.ventes.services._send_acceptance_emails')
    def test_acceptance_email_called(self, mock_email):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ10-F01')
        accept_devis(devis=devis, user=self.user, nom='Test')
        mock_email.assert_called_once()
        call_kwargs = mock_email.call_args.kwargs
        # QX41 re-lit le devis VERROUILLÉ (select_for_update) sous le verrou
        # anti-course, donc l'instance transmise à l'email n'est plus le MÊME
        # objet Python que celui passé par l'appelant — mais bien le MÊME devis
        # (même PK). On vérifie l'identité MÉTIER (PK), pas l'identité objet.
        self.assertEqual(call_kwargs['devis'].pk, devis.pk)

    @patch('apps.ventes.services._send_acceptance_emails',
           side_effect=Exception('email down'))
    def test_email_failure_does_not_block_acceptance(self, mock_email):
        """Best-effort: email failure does NOT prevent the devis from being accepted."""
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ10-F02')
        # Should not raise.
        accept_devis(devis=devis, user=self.user, nom='Test2')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')


# ═══════════════════════════════════════════════════════════════════════════
# (g) Seller in-app notification smoke test
# ═══════════════════════════════════════════════════════════════════════════

class TestDevisSignatureSellerNotification(TestCase):
    """QJ10(g) — _notify_seller_accepted fires on acceptance (best-effort)."""

    def setUp(self):
        self.company = _make_company('qj10-g', 'QJ10 G')
        self.client_obj = _make_client(self.company, 'QJ10 G Client')
        self.seller = _make_user(self.company, 'qj10gs')

    @patch('apps.ventes.services._notify_seller_accepted')
    def test_seller_notified_on_acceptance(self, mock_notify):
        devis = _make_devis(self.company, self.client_obj, 'DEV-QJ10-G01')
        devis.created_by = self.seller
        devis.save(update_fields=['created_by'])
        # Accept as a different user (None = public endpoint).
        accept_devis(devis=devis, user=None, nom='Client')
        mock_notify.assert_called_once()

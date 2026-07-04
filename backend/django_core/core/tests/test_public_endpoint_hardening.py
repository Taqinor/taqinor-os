"""YRBAC9 — durcissement des endpoints publics tokenisés.

Deux gardes :

1. **Throttle** — toute vue résolue en ``AllowAny`` doit porter un
   ``throttle_classes`` non vide (anti-brute-force jeton), sauf celles d'une
   allowlist justifiée (ratchet : elle ne peut que se réduire). Un NOUVEL
   endpoint public sans throttle fait échouer le test.
2. **Expiry** — chaque modèle de lien tokenisé (``ShareLink``, ``PaymentLink``,
   tout futur) rejette un jeton EXPIRÉ (``is_valid`` faux).
"""
from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core import public_endpoint_scan

# Endpoints AllowAny SANS throttle tolérés (justifiés). YRBAC9 fige cet état ;
# la liste ne doit que DÉCROÎTRE (chaque entrée est soit publique par nature,
# soit une dette de throttle à résorber). Un nouvel AllowAny non throttlé hors
# de cette liste fait échouer le test.
THROTTLE_EXEMPT = {
    # Clé VAPID statique (aucune surface de brute-force).
    "notifications/views.py::vapid_public_key",
    # Jetons signés / opaques — dette de throttle à ajouter (suivi YRBAC9).
    "crm/public_chat_views.py::open_chat_session",
    "gestion_projet/public_views.py::portail_avancement",
    "gestion_projet/public_views.py::evaluation_projet",
    "installations/public_views.py::RFQConsultationPublicView",
    "pos/views.py::PublicTicketPDFView",
    "reporting/calendar.py::calendar_ics",
}


class PublicEndpointThrottleGuardTests(SimpleTestCase):
    def test_no_new_unthrottled_public_endpoint(self):
        unthrottled = set(public_endpoint_scan.unthrottled_public_endpoints())
        new = unthrottled - THROTTLE_EXEMPT
        self.assertEqual(
            new, set(),
            "Endpoints AllowAny SANS throttle hors allowlist (ajoutez "
            "@throttle_classes([...]) ou justifiez dans THROTTLE_EXEMPT) :\n"
            + "\n".join(sorted(new)))

    def test_exempt_list_has_no_stale_entries(self):
        """Une exemption qui a gagné un throttle doit être retirée."""
        unthrottled = set(public_endpoint_scan.unthrottled_public_endpoints())
        stale = THROTTLE_EXEMPT - unthrottled
        self.assertEqual(
            stale, set(),
            "Entrées THROTTLE_EXEMPT obsolètes (l'endpoint a un throttle "
            "maintenant — retirez-le de l'allowlist) :\n" + "\n".join(sorted(stale)))

    def test_scan_detects_public_endpoints(self):
        endpoints = public_endpoint_scan.public_endpoints()
        self.assertGreater(
            len(endpoints), 5,
            "Le scanner ne détecte quasiment aucun endpoint AllowAny — régression ?")


class TokenLinkExpiryContractTests(TestCase):
    """Chaque type de lien tokenisé rejette un jeton expiré (is_valid faux)."""

    def _make_devis(self):
        from authentication.models import Company
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        company = Company.objects.get_or_create(
            slug="yrbac9", defaults={"nom": "YRBAC9"})[0]
        client = Client.objects.create(company=company, nom="Client YRBAC9")
        devis = Devis.objects.create(
            company=company, client=client, reference="DEV-YRBAC9")
        return company, devis

    def test_sharelink_rejects_expired_token(self):
        from apps.ventes.models import ShareLink
        company, devis = self._make_devis()
        expired = ShareLink.objects.create(
            company=company, devis=devis,
            expires_at=timezone.now() - timedelta(hours=1))
        self.assertFalse(expired.is_valid)
        valid = ShareLink.objects.create(
            company=company, devis=devis,
            expires_at=timezone.now() + timedelta(hours=1))
        self.assertTrue(valid.is_valid)

    def test_paymentlink_rejects_expired_token(self):
        from apps.ventes.models import PaymentLink
        # PaymentLink porte aussi expires_at + is_valid (même contrat).
        self.assertTrue(hasattr(PaymentLink, "is_valid"))
        fields = {f.name for f in PaymentLink._meta.get_fields()}
        self.assertIn(
            "expires_at", fields,
            "PaymentLink doit porter expires_at pour le contrat d'expiry.")

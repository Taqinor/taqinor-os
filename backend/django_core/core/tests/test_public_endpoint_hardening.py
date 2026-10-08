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
    # ASEC17 — sondes de santé : 200 immédiat sans donnée, interrogées en
    # continu par nginx/Caddy/l'orchestrateur (un throttle ferait sortir le
    # worker du pool). SEULES exemptions « sécurité » de ce fichier.
    "core/views.py::health_live",
    "core/views.py::health_ready",
    # (``crm/public_chat_views.py::open_chat_session`` a QUITTÉ cette liste :
    # il porte désormais ``@throttle_classes([PublicChatRateThrottle])`` — le
    # ratchet ne fait que décroître, une exemption résorbée se retire.)
    # (SOLMVP — ``gestion_projet/public_views.py::portail_avancement`` et
    # ``::evaluation_projet`` ainsi que ``pos/views.py::PublicTicketPDFView``
    # ont quitté cette liste : leurs apps sont sorties du MVP solaire
    # (``core.parked`` / ``docs/parked-modules.md``), les fichiers n'existent
    # plus, donc les endpoints ne sont plus servis. Le ratchet ne garde AUCUNE
    # exemption pour une surface absente ; au retour d'un module, l'exemption se
    # redéclare avec lui — ou mieux, sa dette de throttle est résorbée.)
    # (ASEC45 — ``reporting/calendar.py::calendar_ics`` a quitté la liste : il
    # porte ``@throttle_classes([CalendrierIcsThrottle])``.)
}

# C-ASEC-028 (S4, V7 SPUB-4) — vues publiques qui lisent le corps comme un
# OBJET sans le garder : un corps JSON non-objet (``[]``, ``"x"``) y donne un
# 500 générique (aucune fuite : handler DRF unique). Inventaire STATIQUE gelé le
# jour d'ASEC17 (sur-ensemble des 8 sites sondés au runtime par V7) ; il ne peut
# que DÉCROÎTRE : un NOUVEAU site fait échouer le test, un site corrigé (garde
# ``isinstance(request.data, dict)`` ou sérialiseur) doit être retiré d'ici.
CORPS_NON_GARDE_PUBLIC = {
    "adminops/views_signup.py::SignupDemandeView",
    "contact/views.py::contact",
    "crm/public_booking_views.py::public_booking_reserve",
    "crm/public_chat_views.py::post_chat_message",
    "ged/views.py::public_depot",
    "ged/views.py::public_signature",
    "ged/views.py::public_signataire",
    "identity/views.py::LoginBannerView",
    "portail/public_views.py::accepter_invitation_portail_public",
    "reporting/approbations.py::decider_approbation_via_push",
    "sav/public_views.py::ticket_public_satisfaction",
    "sav/public_views.py::equipement_public_signaler",
    "statuspage/views.py::public_abonner",
    "stock/public_views.py::portail_fournisseur_confirmer_bcf_view",
    "stock/public_views.py::portail_fournisseur_reserver_creneau_view",
    "ventes/public/lecture_views.py::proposal_engagement",
    "ventes/public/signature_views.py::proposal_contact_request",
    "ventes/public/signature_views.py::proposal_accept",
    "ventes/public/signature_views.py::proposal_activate_option",
    "authentication/views.py::RegisterCompanyView",
}

# Les vues « sécurité » que l'ancien scanner (``views.py`` d'apps/ seulement,
# ``AllowAny`` en liste nue) ne voyait pas — chacune DOIT être détectée ET
# throttlée (ASEC17).
VUES_SECURITE_ATTENDUES = {
    "identity/views.py::LoginBannerView",
    "identity/scim.py::ScimUsersView",
    "identity/scim.py::ScimUserDetailView",
    "identity/scim.py::ScimGroupsView",
    "identity/scim.py::ScimGroupDetailView",
    "authentication/views.py::CookieTokenRefreshView",
    "core/dashboard_partage.py::dashboard_public",
    "core/degraded_mode.py::degraded_mode_status_view",
    "core/export_registry.py::telecharger_export_reversibilite",
    "core/trust_center.py::trust_center_public",
    "core/views.py::trust_center_export_pdf",
    "core/views.py::metrics_view",
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


class PublicEndpointHardeningTests(TestCase):
    """ASEC17 — scanner complet, throttle, bannière agrégée, PDF en cache."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)

    def test_scanner_voit_toutes_formes_allowany(self):
        source = (
            "from rest_framework import permissions\n"
            "from rest_framework.permissions import AllowAny\n"
            "class A(APIView):\n    permission_classes = [AllowAny]\n"
            "class B(APIView):\n    permission_classes = (AllowAny,)\n"
            "class C(APIView):\n"
            "    permission_classes = [permissions.AllowAny]\n"
            "class D(APIView):\n"
            "    permission_classes: list = [AllowAny]\n"
            "class E(APIView):\n"
            "    def get_permissions(self):\n        return [AllowAny()]\n"
            "@api_view(['GET'])\n@permission_classes([permissions.AllowAny])\n"
            "def f(request):\n    pass\n"
            "@api_view(['GET'])\n@permission_classes((AllowAny,))\n"
            "def g(request):\n    pass\n"
            "class V(viewsets.ViewSet):\n"
            "    @action(detail=False, permission_classes=[AllowAny])\n"
            "    def pub(self, request):\n        pass\n"
            "class Throttled(APIView):\n    permission_classes = [AllowAny]\n"
            "    throttle_classes = [X]\n"
        )
        trouves = {e["id"]: e
                   for e in public_endpoint_scan.endpoints_of_source(
                       source, "x.py")}
        attendus = {"x.py::" + n for n in (
            "A", "B", "C", "D", "E", "f", "g", "V.pub", "Throttled")}
        self.assertEqual(set(trouves), attendus)
        self.assertTrue(trouves["x.py::Throttled"]["throttled"])
        self.assertFalse(trouves["x.py::A"]["throttled"])

    def test_scanner_couvre_core_authentication_et_tout_fichier(self):
        ids = {e["id"] for e in public_endpoint_scan.public_endpoints()}
        manquantes = VUES_SECURITE_ATTENDUES - ids
        self.assertEqual(manquantes, set(),
                         "Vues publiques « sécurité » invisibles du scanner")

    def test_vues_publiques_throttlees(self):
        par_id = {e["id"]: e for e in public_endpoint_scan.public_endpoints()}
        for vue in sorted(VUES_SECURITE_ATTENDUES):
            self.assertTrue(
                par_id[vue]["throttled"],
                f"{vue} : vue publique « sécurité » sans throttle anonyme")
        sans_throttle = {i for i, e in par_id.items() if not e["throttled"]}
        self.assertEqual(sans_throttle - THROTTLE_EXEMPT, set())

    def test_banniere_post_alerte_agregee(self):
        from django.test import override_settings
        from rest_framework.test import APIClient

        from apps.audit.models import AuditLog
        from apps.parametres.models_company import CompanyProfile
        from authentication.models import Company
        from core.models import TenantTheme

        hote = "asec17-banner.example"
        company = Company.objects.create(nom="ASEC17 Co", slug="asec17-co")
        TenantTheme.objects.create(company=company, domaine=hote)
        CompanyProfile.objects.update_or_create(
            company=company, defaults={"login_banner_text": "Accès restreint."})
        api = APIClient(HTTP_HOST=hote)
        url = "/api/django/identity/login-banner/"
        avant = AuditLog.objects.filter(
            action=AuditLog.Action.SECURITY_ALERT).count()
        with override_settings(ALLOWED_HOSTS=[hote, "testserver"]):
            codes = [api.post(url, {"username": "x"}, format="json").status_code
                     for _ in range(40)]
        # CLAUSE PERSISTANCE : EXACTEMENT une alerte agrégée pour la rafale.
        apres = AuditLog.objects.filter(
            action=AuditLog.Action.SECURITY_ALERT).count()
        self.assertEqual(apres - avant, 1)
        self.assertIn(429, codes)
        self.assertEqual(codes[0], 200)

    def test_trust_center_pdf_cache(self):
        from unittest import mock

        from rest_framework.test import APIClient

        api = APIClient()
        with mock.patch(
                "core.pdf_trust_center.generer_pdf_trust_center",
                return_value=b"%PDF-1.4 asec17") as rendu:
            r1 = api.get("/api/django/core/trust-center/export-pdf/")
            r2 = api.get("/api/django/core/trust-center/export-pdf/")
        self.assertEqual((r1.status_code, r2.status_code), (200, 200))
        self.assertEqual(r1.content, r2.content)
        self.assertEqual(rendu.call_count, 1)

    def test_inventaire_500_publics_decroissant(self):
        reel = set(public_endpoint_scan.body_unguarded_public_endpoints())
        nouveaux = reel - CORPS_NON_GARDE_PUBLIC
        self.assertEqual(
            nouveaux, set(),
            "Nouvelle vue publique qui lit le corps JSON comme un objet sans "
            "garde (isinstance(request.data, dict) ou sérialiseur) — un corps "
            "non-objet y donnerait un 500 :\n" + "\n".join(sorted(nouveaux)))
        obsoletes = CORPS_NON_GARDE_PUBLIC - reel
        self.assertEqual(
            obsoletes, set(),
            "Entrées CORPS_NON_GARDE_PUBLIC obsolètes (site corrigé ou "
            "supprimé — retirez-les, la liste ne fait que décroître) :\n"
            + "\n".join(sorted(obsoletes)))


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

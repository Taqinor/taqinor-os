"""ARC5 — « proposition publique toujours accessible » (garde du sweep TenantMixin).

Le sweep ARC5 convertit les ViewSets de ``apps/ventes/views/*.py`` vers la base
transverse ``core.viewsets.CompanyScopedModelViewSet`` (TenantMixin +
ModelViewSet), qui scope tout au ``request.user.company``. Ce sweep EXCLUT
explicitement les endpoints PUBLICS tokenisés (``/proposal`` client, ShareLink,
liens de paiement) : ils vivent dans ``apps/ventes/public_views.py`` (``AllowAny``,
hors périmètre du sweep) et n'ont PAS de ``request.user.company``. Les router par
le scoping société CASSERAIT les liens envoyés aux clients.

Ce module est la garde de non-régression demandée par le Done d'ARC5 : il prouve
qu'après le sweep, l'accès CLIENT à la proposition reste possible

  * SANS authentification (aucune session, aucun JWT) — 200 + PDF servi ;
  * PAR LE JETON, jamais par la société de session — un utilisateur d'une AUTRE
    société (ou aucun utilisateur) ouvre le lien via son token, le résultat ne
    dépend QUE du token ShareLink (long, imprévisible, expirant) ;
  * un token inconnu/expiré → 404 amical, jamais une fuite d'une autre société.

Deux couches de tests :
  (1) couche routing/auth (légère, PDF mocké) : c'est là que se joue le risque du
      sweep — vérifier qu'aucun ``request.user.company`` ne s'est glissé dans le
      chemin public ;
  (2) UN rendu PDF complet ``@tag('pdf')`` : prouve que le chemin public rend
      réellement le PDF client de bout en bout après le sweep.

Règle #4 : le chemin ``/proposal`` ne fait que RENDRE — aucun statut de devis
n'est touché ici (le sweep ne change ni statut ni sérialisation).
"""
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.ventes.models import Devis, ShareLink

User = get_user_model()


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_company(slug, nom):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def _make_user(company, username):
    return User.objects.get_or_create(
        username=username,
        defaults={
            'password': 'x',
            'role_legacy': 'responsable',
            'company': company,
        },
    )[0]


def _make_client(company, nom):
    return Client.objects.get_or_create(company=company, nom=nom, defaults={})[0]


def _make_devis(company, client, ref):
    return Devis.objects.get_or_create(
        company=company, reference=ref,
        defaults={'client': client, 'taux_tva': Decimal('20')},
    )[0]


# Le rendu PDF réel est mocké dans la couche routing (léger) : on teste l'AUTH
# et le routage tokenisé, pas le moteur (couvert par test_quote_engine.py).
_PATCH_GEN = patch(
    'apps.ventes.public_views.generate_premium_devis_pdf',
    return_value='devis/1/DEV-ARC5.pdf',
)
_PATCH_DL = patch(
    'apps.ventes.public_views.download_pdf',
    return_value=b'%PDF-1.4 stub arc5',
)


# ═════════════════════════════════════════════════════════════════════════════
# (1) Couche routing/auth — le chemin public NE passe PAS par request.user.company
# ═════════════════════════════════════════════════════════════════════════════

class TestProposalPublicAlwaysAccessible(TestCase):
    """ARC5 — la proposition publique reste servie sans authentification et
    UNIQUEMENT par le token ShareLink, jamais par la société de session."""

    def setUp(self):
        self.company = _make_company('arc5-co', 'ARC5 Co')
        self.client_obj = _make_client(self.company, 'ARC5 Client')
        self.devis = _make_devis(self.company, self.client_obj, 'DEV-ARC5-01')
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis)

    @_PATCH_GEN
    @_PATCH_DL
    def test_unauthenticated_get_document_returns_200_pdf(self, m_dl, m_gen):
        """GET public ``/document/<token>/`` SANS aucune session → 200 + PDF."""
        resp = APIClient().get(
            f'/api/django/public/document/{self.link.token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        # Le corps est bien le flux PDF servi par token (pas un JSON 401/403).
        self.assertEqual(resp.content, b'%PDF-1.4 stub arc5')

    @_PATCH_GEN
    @_PATCH_DL
    def test_unauthenticated_get_proposal_pdf_returns_200_pdf(
            self, m_dl, m_gen):
        """GET public ``/proposal/<token>/pdf/`` (chemin client W116) SANS
        session → 200 + PDF servi par token."""
        resp = APIClient().get(
            f'/api/django/public/proposal/{self.link.token}/pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_unauthenticated_get_proposal_data_returns_200(self):
        """GET public ``/proposal/<token>/data/`` (JSON de la proposition) SANS
        session → 200. Le rendu de données ne dépend que du token."""
        # Le mock fournit les clés que la vue indexe directement
        # (ref/date/client_name) ; le reste est lu via ``.get()``.
        with patch('apps.ventes.quote_engine.builder.build_quote_data',
                   return_value={
                       'ref': 'DEV-ARC5-01',
                       'date': '2026-07-10',
                       'client_name': 'ARC5 Client',
                   }):
            resp = APIClient().get(
                f'/api/django/public/proposal/{self.link.token}/data/')
        self.assertEqual(resp.status_code, 200)

    @_PATCH_GEN
    @_PATCH_DL
    def test_access_is_by_token_not_by_session_company(self, m_dl, m_gen):
        """Le cœur de la garde ARC5 : un utilisateur authentifié d'une AUTRE
        société ouvre le lien public par TOKEN et obtient 200 — la société de
        session ne doit JAMAIS filtrer le chemin public (sinon le sweep aurait
        cassé les liens clients)."""
        autre_co = _make_company('arc5-autre', 'ARC5 Autre')
        etranger = _make_user(autre_co, 'arc5-etranger')

        api = APIClient()
        api.force_authenticate(user=etranger)
        resp = api.get(f'/api/django/public/document/{self.link.token}/')

        # Servi par token, INDÉPENDAMMENT de la société de l'utilisateur connecté.
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_unknown_token_returns_404_without_leak(self):
        """Token inconnu → 404 amical, jamais une fuite d'une autre société."""
        resp = APIClient().get(
            '/api/django/public/document/token-inexistant-arc5/')
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn('devis', str(resp.data.get('detail', '')).lower())

    def test_expired_token_returns_404(self):
        """Token expiré → 404 (l'expiration, pas la société, borne l'accès)."""
        self.link.expires_at = timezone.now() - timedelta(days=1)
        self.link.save(update_fields=['expires_at'])
        resp = APIClient().get(
            f'/api/django/public/document/{self.link.token}/')
        self.assertEqual(resp.status_code, 404)


class TestProposalPublicCrossCompanyToken(TestCase):
    """ARC5 — un token de la société A sert la proposition de A, jamais celle de
    B : l'accès est indexé par TOKEN, l'isolation multi-tenant est préservée sans
    dépendre d'aucune session."""

    def setUp(self):
        self.co_a = _make_company('arc5-a', 'ARC5 A')
        self.co_b = _make_company('arc5-b', 'ARC5 B')
        cli_a = _make_client(self.co_a, 'ClientA')
        cli_b = _make_client(self.co_b, 'ClientB')
        self.devis_a = _make_devis(self.co_a, cli_a, 'DEV-ARC5-A1')
        self.devis_b = _make_devis(self.co_b, cli_b, 'DEV-ARC5-B1')
        self.link_a = ShareLink.objects.create(
            company=self.co_a, devis=self.devis_a)
        self.link_b = ShareLink.objects.create(
            company=self.co_b, devis=self.devis_b)

    @_PATCH_GEN
    @_PATCH_DL
    def test_token_a_serves_devis_a(self, m_dl, m_gen):
        APIClient().get(
            f'/api/django/public/document/{self.link_a.token}/')
        # Le rendu a été demandé pour le devis de A, jamais celui de B.
        called_ids = {c.args[0] for c in m_gen.call_args_list}
        self.assertIn(self.devis_a.id, called_ids)
        self.assertNotIn(self.devis_b.id, called_ids)


# ═════════════════════════════════════════════════════════════════════════════
# (2) UN rendu PDF complet — le chemin public rend réellement après le sweep
# ═════════════════════════════════════════════════════════════════════════════

@tag('pdf')  # rendu PDF premium réel — lourd → palier release-verify
class TestProposalPublicRealRender(TestCase):
    """ARC5 — bout en bout : le PDF CLIENT servi derrière le token public est un
    vrai PDF, sans authentification (MinIO mocké, moteur réel)."""

    def setUp(self):
        from apps.ventes.tests.test_quote_engine import (
            make_company, make_user, make_client, make_devis,
        )
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '12', '1500'),
            ('Onduleur hybride', '1', '12000'),
            ('Structures acier', '12', '450'),
        ], reference='DEV-ARC5-RENDER')
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis)

    @patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket')
    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.public_views.download_pdf')
    def test_public_proposal_pdf_renders_real_pdf_unauthenticated(
            self, m_dl, m_upload, m_bucket):
        # download_pdf renvoie les octets réellement rendus + uploadés par le
        # moteur (persist=False : le moteur rend sans persister sur le modèle).
        captured = {}

        def _capture_upload(pdf_bytes, key, *a, **k):
            captured['bytes'] = pdf_bytes
            return key
        m_upload.side_effect = _capture_upload
        m_dl.side_effect = lambda key: captured.get('bytes', b'')

        resp = APIClient().get(
            f'/api/django/public/proposal/{self.link.token}/pdf/')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        body = resp.content
        self.assertTrue(body[:4] == b'%PDF',
                        'le chemin public doit servir un vrai PDF')
        self.assertGreater(len(body), 5000)

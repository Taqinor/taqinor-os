"""
Tests for QJ15 — Quote variants / multi-option comparison.

Covers:
  - POST /ventes/devis/{id}/dupliquer-variante/ creates 3 brouillon sibling
    devis with scaled line quantities (default scales: 0.8 / 1.0 / 1.25).
  - Custom scales body param creates the requested number of variants (≤ 3).
  - All variants share version_parent = source (or source's root), is_active=True.
  - RULE #4: dupliquer_variante never changes Devis.statut.
  - Company scoping: another company's devis → 404.
  - GET /ventes/devis/{id}/variantes/ lists siblings with the same version_parent.
  - proposal_data (public endpoint) includes a 'variants' key.
  - _variant_summaries returns [] when the devis is isolated (no siblings).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qj15_variants -v 2
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.public_views import _variant_summaries

User = get_user_model()


# ─── Helpers ───────────────────────────────────────────────────────────────────

def make_company(slug='qj15-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': 'QJ15 Co'})[0]


def make_user(company, username=None):
    uname = username or f'u_{company.slug}'
    try:
        return User.objects.get(username=uname)
    except User.DoesNotExist:
        return User.objects.create_user(
            username=uname, password='x',
            role_legacy='responsable', company=company)


def make_client(company):
    return Client.objects.create(
        company=company, nom='Benali', prenom='Tariq',
        email='tariq@qj15.ma', telephone='+212611000010')


def make_produit(company, nom, sku, prix_vente):
    return Produit.objects.create(
        company=company, nom=nom, sku=sku,
        prix_vente=Decimal(str(prix_vente)),
        prix_achat=Decimal('1'),
        quantite_stock=50)


def make_devis(company, user, client, ref='DEV-QJ15-001', statut='brouillon'):
    return Devis.objects.create(
        company=company, reference=ref, client=client,
        statut=statut, created_by=user)


def add_ligne(devis, produit, qty='6', pu='2000'):
    return LigneDevis.objects.create(
        devis=devis, produit=produit, designation=produit.nom,
        quantite=Decimal(str(qty)), prix_unitaire=Decimal(str(pu)),
        remise=Decimal('0'))


def make_api(user):
    cli = APIClient()
    cli.force_authenticate(user=user)
    return cli


def url_variante(devis_id):
    return f'/api/django/ventes/devis/{devis_id}/dupliquer-variante/'


def url_variantes(devis_id):
    return f'/api/django/ventes/devis/{devis_id}/variantes/'


# ─── Tests ─────────────────────────────────────────────────────────────────────

class TestDupliquerVariante(TestCase):
    """POST dupliquer-variante/ — creates size variants."""

    def setUp(self):
        self.company = make_company('qj15-main')
        self.user = make_user(self.company)
        self.api = make_api(self.user)
        self.client_obj = make_client(self.company)
        self.produit = make_produit(self.company, 'Panneau 550W', 'P550-QJ15', '2000')

    def test_creates_three_variants_by_default(self):
        """Default call creates 3 brouillon variants (scales 0.8/1.0/1.25)."""
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ15-V1')
        add_ligne(d, self.produit, qty='10')

        resp = self.api.post(url_variante(d.id), {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data), 3)

    def test_all_variants_are_brouillon(self):
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ15-V2')
        add_ligne(d, self.produit, qty='8')

        resp = self.api.post(url_variante(d.id), {}, format='json')
        self.assertEqual(resp.status_code, 201)
        for v in resp.data:
            self.assertEqual(v['statut'], 'brouillon')

    def test_quantities_are_scaled(self):
        """Variant with scale 0.8 has qty = original × 0.8 (rounded)."""
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ15-V3')
        add_ligne(d, self.produit, qty='10')

        resp = self.api.post(url_variante(d.id), {'scales': [0.8]}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data), 1)

        variant_id = resp.data[0]['id']
        ligne = LigneDevis.objects.filter(devis_id=variant_id).first()
        self.assertIsNotNone(ligne)
        # 10 × 0.8 = 8.00
        self.assertEqual(ligne.quantite, Decimal('8.00'))

    def test_variants_share_version_parent_with_source(self):
        """All variants have version_parent pointing to the source devis."""
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ15-V4')
        add_ligne(d, self.produit, qty='6')

        resp = self.api.post(url_variante(d.id), {}, format='json')
        self.assertEqual(resp.status_code, 201)

        for v_data in resp.data:
            variant = Devis.objects.get(pk=v_data['id'])
            self.assertIsNotNone(variant.version_parent,
                                 'variant must have version_parent set')
            # Root is either source itself or source.version_parent.
            root = d.version_parent or d
            self.assertEqual(variant.version_parent_id, root.pk)

    def test_variants_are_all_active(self):
        """is_active=True on all variants (they're alternatives, not replacements)."""
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ15-V5')
        add_ligne(d, self.produit, qty='8')

        resp = self.api.post(url_variante(d.id), {}, format='json')
        self.assertEqual(resp.status_code, 201)
        for v_data in resp.data:
            v = Devis.objects.get(pk=v_data['id'])
            self.assertTrue(v.is_active)

    def test_rule4_source_statut_unchanged(self):
        """RULE #4: dupliquer_variante never changes the source Devis.statut."""
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ15-V6')
        add_ligne(d, self.produit, qty='6')
        original_statut = d.statut

        self.api.post(url_variante(d.id), {}, format='json')

        d.refresh_from_db()
        self.assertEqual(d.statut, original_statut)

    def test_custom_scales_respected(self):
        """Passing custom scales=[0.5, 2.0] creates 2 variants only."""
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ15-V7')
        add_ligne(d, self.produit, qty='4')

        resp = self.api.post(url_variante(d.id), {'scales': [0.5, 2.0]}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data), 2)

    def test_scales_capped_at_three(self):
        """More than 3 scales are silently truncated to the first 3."""
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ15-V8')
        add_ligne(d, self.produit, qty='4')

        resp = self.api.post(url_variante(d.id),
                             {'scales': [0.5, 1.0, 1.5, 2.0, 3.0]}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data), 3)

    def test_variants_scoped_to_company(self):
        """All created variants belong to the source devis's company."""
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ15-V9')
        add_ligne(d, self.produit, qty='6')

        resp = self.api.post(url_variante(d.id), {}, format='json')
        self.assertEqual(resp.status_code, 201)
        for v_data in resp.data:
            v = Devis.objects.get(pk=v_data['id'])
            self.assertEqual(v.company, self.company)


class TestGetVariantes(TestCase):
    """GET variantes/ — lists siblings with the same version_parent."""

    def setUp(self):
        self.company = make_company('qj15-get')
        self.user = make_user(self.company)
        self.api = make_api(self.user)
        self.client_obj = make_client(self.company)
        self.produit = make_produit(self.company, 'Panneau 400W', 'P400-QJ15', '1800')

    def test_variantes_returns_siblings(self):
        """GET /variantes/ on a variant returns all active siblings."""
        source = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ15-G1')
        add_ligne(source, self.produit, qty='6')

        # Create variants
        resp = self.api.post(url_variante(source.id), {}, format='json')
        self.assertEqual(resp.status_code, 201)
        first_variant_id = resp.data[0]['id']

        # GET variantes/ on one of the variants
        resp2 = self.api.get(url_variantes(first_variant_id))
        self.assertEqual(resp2.status_code, 200, resp2.data)
        ids = [v['id'] for v in resp2.data]
        # Should include the source devis and the other 2 variants
        self.assertIn(source.id, ids)

    def test_isolated_devis_returns_empty(self):
        """A devis with no siblings returns [] from the variantes endpoint."""
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ15-G2')
        resp = self.api.get(url_variantes(d.id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [])

    def test_cross_company_variantes_404(self):
        """User from company A cannot list variantes of a devis from company B."""
        company_b = make_company('qj15-b')
        user_b = make_user(company_b, 'u_qj15b')
        client_b = make_client(company_b)
        devis_b = make_devis(company_b, user_b, client_b, 'DEV-QJ15-B1')

        resp = self.api.get(url_variantes(devis_b.id))
        self.assertEqual(resp.status_code, 404)


class TestVariantSummaries(TestCase):
    """_variant_summaries helper — used by proposal_data for QJ15 side-by-side."""

    def setUp(self):
        self.company = make_company('qj15-vs')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.produit = make_produit(self.company, 'Panneau 600W', 'P600-QJ15', '2200')

    def test_isolated_devis_returns_empty(self):
        """An isolated devis (no version_parent, no siblings) → []."""
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ15-S1')
        self.assertEqual(_variant_summaries(d), [])

    def test_returns_summaries_for_siblings(self):
        """Returns non-empty list when active siblings share version_parent."""
        source = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ15-S2')
        add_ligne(source, self.produit, qty='8')

        # Create a sibling manually
        sibling = Devis.objects.create(
            company=self.company, reference='DEV-QJ15-S2b',
            client=self.client_obj, statut='brouillon',
            version_parent=source, version=2, is_active=True,
            created_by=self.user)
        add_ligne(sibling, self.produit, qty='10')

        # source should see sibling in summaries
        summaries = _variant_summaries(source)
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]['id'], sibling.id)

    def test_summary_contains_expected_fields(self):
        """Each summary has id, reference, version, note, total_ttc."""
        source = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ15-S3')
        add_ligne(source, self.produit, qty='6')

        sibling = Devis.objects.create(
            company=self.company, reference='DEV-QJ15-S3b',
            client=self.client_obj, statut='brouillon',
            version_parent=source, version=2, is_active=True,
            created_by=self.user)
        add_ligne(sibling, self.produit, qty='8')

        summaries = _variant_summaries(source)
        s = summaries[0]
        for key in ('id', 'reference', 'version', 'note', 'total_ttc'):
            self.assertIn(key, s, f"Missing key: {key}")

    def test_no_buy_price_in_summary(self):
        """total_ttc must be > 0 and never expose prix_achat."""
        source = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ15-S4')
        add_ligne(source, self.produit, qty='6', pu='2200')
        sibling = Devis.objects.create(
            company=self.company, reference='DEV-QJ15-S4b',
            client=self.client_obj, statut='brouillon',
            version_parent=source, version=2, is_active=True,
            created_by=self.user)
        add_ligne(sibling, self.produit, qty='8', pu='2200')

        summaries = _variant_summaries(source)
        self.assertEqual(len(summaries), 1)
        # total_ttc = 8 × 2200 × 1.20 = 21120.0
        self.assertAlmostEqual(summaries[0]['total_ttc'], 21120.0, places=0)
        # prix_achat must not appear
        self.assertNotIn('prix_achat', summaries[0])

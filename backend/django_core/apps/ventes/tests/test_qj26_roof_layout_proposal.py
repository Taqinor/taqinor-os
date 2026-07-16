"""QJ26 — Expose the roof layout in the public proposal payload.

proposal_data exposed only roof_image_url. QJ26 adds a SANITIZED roof_layout
(geometry + per-pan panel count/orientation/tilt/kWc ONLY — NEVER any price,
prix_achat, margin, or internal field), only when present; the PNG stays the
poster/fallback. No-leak, layout-less, and company-scoping covered.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qj26_roof_layout_proposal -v 2
"""
import json
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient, TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink

User = get_user_model()


def make_company(slug):
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return c


def make_user(company):
    return User.objects.create_user(
        username=f'qj26_{company.slug}', password='x',
        role_legacy='responsable', company=company)


def make_client(company):
    return Client.objects.create(
        company=company, nom='Roof', prenom='Test',
        email=f'r_{company.slug}@ex.com', telephone='+212600000008')


def make_devis(company, user, client, reference, roof_layout=None):
    devis = Devis.objects.create(
        company=company, reference=reference, client=client,
        statut='envoye', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'), created_by=user, roof_layout=roof_layout)
    for desig, qty, pu in [('Onduleur réseau 8kW', '1', '14000'),
                           ('Panneau mono 550W', '10', '1400')]:
        produit = Produit.objects.create(
            company=company, nom=desig, sku=f'{reference[-6:]}-{desig[:10]}',
            prix_vente=Decimal(pu), prix_achat=Decimal('9999'),
            quantite_stock=50)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=desig,
            quantite=Decimal(qty), prix_unitaire=Decimal(pu),
            remise=Decimal('0'))
    return devis


def sample_layout():
    return {
        'version': 1,
        'scenario': 'reseau',
        'result': {'panels': 16, 'kwc': 8.8, 'annualKwh': 14000,
                   'savings': 11000},
        'zones': [{
            'id': 'z1', 'label': 'Pan Sud',
            'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
            'obstacles': [], 'roofType': 'pitched', 'pitchDeg': 30,
            'facingAzimuthDeg': 0, 'neededPanels': 12,
        }],
        '_pans_geometry': [{
            'label': 'Pan Sud', 'orientation': 'Sud', 'azimut_deg': 0,
            'inclinaison_deg': 30, 'nb_panneaux': 12, 'kwc': 6.6,
            'roof_type': 'pitched',
            # These MUST be stripped by the sanitizer:
            'prix_achat': 9999, 'marge': 0.3, 'prix_vente': 1400,
        }],
        # top-level internal field that must not leak:
        'prix_achat_total': 123456,
    }


class TestSafeRoofLayoutSanitizer(TestCase):
    def setUp(self):
        self.company = make_company('qj26-san')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_sanitized_layout_geometry_only(self):
        from apps.ventes.public_views import _safe_roof_layout
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-QJ26-1', roof_layout=sample_layout())
        safe = _safe_roof_layout(devis)
        self.assertIsNotNone(safe)
        pan = safe['pans'][0]
        self.assertEqual(pan['orientation'], 'Sud')
        self.assertEqual(pan['azimut_deg'], 0)
        self.assertEqual(pan['inclinaison_deg'], 30)
        self.assertEqual(pan['nb_panneaux'], 12)
        self.assertEqual(pan['kwc'], 6.6)
        # geometry totals present, but savings/price absent
        self.assertIn('kwc', safe['result'])
        self.assertNotIn('savings', safe['result'])
        # NO price / margin / internal key anywhere in the JSON
        blob = json.dumps(safe)
        for leak in ('prix_achat', 'marge', 'prix_vente', '9999', '123456',
                     'savings'):
            self.assertNotIn(leak, blob)

    def test_no_layout_returns_none(self):
        from apps.ventes.public_views import _safe_roof_layout
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-QJ26-NONE', roof_layout=None)
        self.assertIsNone(_safe_roof_layout(devis))


class TestProposalRoofLayoutPayload(TestCase):
    def setUp(self):
        self.company = make_company('qj26-ep')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _get_payload(self, devis):
        token = str(uuid.uuid4())
        ShareLink.objects.create(
            company=self.company, devis=devis, token=token)
        c = DjangoClient()
        return c.get(f'/api/django/public/proposal/{token}/data/')

    def test_payload_has_sanitized_roof_layout(self):
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-QJ26-EP', roof_layout=sample_layout())
        resp = self._get_payload(devis)
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn('roof_layout', payload)
        self.assertIsNotNone(payload['roof_layout'])
        blob = json.dumps(payload['roof_layout'])
        for leak in ('prix_achat', 'marge', '9999', '123456'):
            self.assertNotIn(leak, blob)

    def test_layoutless_proposal_omits_roof_layout(self):
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-QJ26-EP2', roof_layout=None)
        resp = self._get_payload(devis)
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIsNone(payload['roof_layout'])

    def test_full_payload_never_leaks_buy_price(self):
        """The whole proposal payload must never contain the reseller buy price
        (9999) that is set on the products' prix_achat."""
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-QJ26-LEAK', roof_layout=sample_layout())
        resp = self._get_payload(devis)
        raw = json.dumps(resp.json())
        # Le prix d'achat (9999) ne doit jamais apparaître comme VALEUR AUTONOME.
        # On borne le motif (aucun chiffre/point adjacent) : « 9999 » en
        # sous-chaîne d'un montant client LÉGITIME — ex. un cashflow 25 ans
        # « 399991 » (QX39) — n'est PAS une fuite du prix d'achat.
        self.assertNotRegex(
            raw, r'(?<![\d.])9999(?![\d.])',
            "prix d'achat 9999 fuité comme valeur autonome dans la charge utile")
        self.assertNotIn('prix_achat', raw)


class TestRoofLayoutCompanyScoping(TestCase):
    def test_token_only_reads_its_own_company_layout(self):
        """A token bound to company A's devis returns A's layout; company B's
        devis+layout are unreachable through it (token is single-devis-scoped)."""
        co_a = make_company('qj26-a')
        co_b = make_company('qj26-b')
        ua, ub = make_user(co_a), make_user(co_b)
        ca, cb = make_client(co_a), make_client(co_b)
        da = make_devis(co_a, ua, ca, 'DEV-QJ26-A', roof_layout=sample_layout())
        make_devis(co_b, ub, cb, 'DEV-QJ26-B', roof_layout=sample_layout())
        token = str(uuid.uuid4())
        ShareLink.objects.create(company=co_a, devis=da, token=token)
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{token}/data/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['reference'], 'DEV-QJ26-A')

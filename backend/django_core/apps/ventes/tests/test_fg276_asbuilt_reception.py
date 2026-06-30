"""FG276/FG277/FG278/FG287 — packs as-built, attestation de conformité, PR de
réception et attestation d'énergie renouvelable.

Couvre : calculs purs (PR de réception, CO₂ évité), création (company forcée
serveur, jamais du corps), valeurs dérivées serveur (pr/ecart/verdict pour le PR ;
facteur/CO₂ pour l'attestation RE), isolation par société, filtres, et que rien ne
change le statut d'un devis (RULE #4).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_fg276_asbuilt_reception -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase
from rest_framework.test import APIClient

from apps.ventes.models import (
    Devis, AsBuiltPack, AttestationConformite, TestPerformanceReception,
    AttestationRE)
from apps.ventes.commissioning import (
    compute_reception_pr, compute_co2_evite, DEFAULT_GRID_CO2_KG_PER_KWH,
    DEFAULT_PR_ACCEPTANCE)
from apps.crm.models import Client
from authentication.models import Company

User = get_user_model()


def make_company(slug):
    return Company.objects.create(nom=f'Co {slug}', slug=slug)


def make_user(company, name):
    return User.objects.create_user(
        username=name, password='x',
        role_legacy='responsable', company=company)


def make_devis(company, user, ref='DEV-FG276-1'):
    client = Client.objects.create(
        company=company, nom='Alaoui', prenom='Nadia',
        email=f'n_{ref}@example.com', telephone='+212666777888')
    return Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='accepte', created_by=user)


# ───────────────────────── calculs purs ─────────────────────────

class ComputeReceptionPrTest(SimpleTestCase):
    def test_pr_derived_from_energies(self):
        # pr_attendu 0.80, énergie réalisée 90% de l'attendu → pr ≈ 0.72.
        pr_m, ecart, verdict = compute_reception_pr(
            energie_mesuree_kwh=900, energie_attendue_kwh=1000,
            pr_attendu='0.80')
        self.assertAlmostEqual(pr_m, 0.72, places=4)
        self.assertAlmostEqual(ecart, -10.0, places=2)
        # 0.72 < seuil par défaut 0.75 → refusé.
        self.assertEqual(verdict, 'refuse')

    def test_explicit_pr_above_threshold_accepted(self):
        pr_m, ecart, verdict = compute_reception_pr(
            pr_mesure='0.82', pr_attendu='0.80')
        self.assertAlmostEqual(pr_m, 0.82, places=4)
        self.assertAlmostEqual(ecart, 2.5, places=2)
        self.assertEqual(verdict, 'accepte')

    def test_custom_threshold_used(self):
        _, _, verdict = compute_reception_pr(
            pr_mesure='0.73', pr_attendu='0.80', pr_seuil_acceptation='0.70')
        self.assertEqual(verdict, 'accepte')

    def test_default_threshold_constant(self):
        self.assertEqual(DEFAULT_PR_ACCEPTANCE, 0.75)

    def test_no_data_is_en_attente(self):
        pr_m, ecart, verdict = compute_reception_pr()
        self.assertIsNone(pr_m)
        self.assertIsNone(ecart)
        self.assertEqual(verdict, 'en_attente')


class ComputeCo2Test(SimpleTestCase):
    def test_default_factor_applied(self):
        facteur, co2 = compute_co2_evite(energie_kwh=10000)
        self.assertEqual(facteur, DEFAULT_GRID_CO2_KG_PER_KWH)
        # 10000 kWh × 0.72 / 1000 = 7.2 t.
        self.assertAlmostEqual(co2, 7.2, places=3)

    def test_no_energy_returns_none_co2(self):
        facteur, co2 = compute_co2_evite(energie_kwh=None)
        self.assertEqual(facteur, DEFAULT_GRID_CO2_KG_PER_KWH)
        self.assertIsNone(co2)


# ───────────────────────── API : as-built ─────────────────────────

class AsBuiltApiTest(TestCase):
    def setUp(self):
        self.company = make_company('ab-acme')
        self.other = make_company('ab-other')
        self.user = make_user(self.company, 'ab_user')
        self.devis = make_devis(self.company, self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/django/ventes/packs-asbuilt/'

    def test_create_forces_company_from_devis(self):
        resp = self.api.post(self.url, {
            'devis': self.devis.id, 'titre': 'Dossier as-built',
            'pieces': [{'type': 'schema', 'libelle': 'Unifilaire',
                        'reference': 'SLD-1'}],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        pack = AsBuiltPack.objects.get(id=resp.data['id'])
        self.assertEqual(pack.company_id, self.company.id)
        self.assertEqual(len(pack.pieces), 1)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'accepte')

    def test_other_company_devis_refused(self):
        ou = make_user(self.other, 'ab_o')
        od = make_devis(self.other, ou, ref='DEV-AB-OTHER')
        resp = self.api.post(self.url, {'devis': od.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_list_scoped(self):
        AsBuiltPack.objects.create(company=self.company, devis=self.devis)
        AsBuiltPack.objects.create(company=self.other)
        resp = self.api.get(self.url)
        rows = resp.data['results'] if isinstance(
            resp.data, dict) and 'results' in resp.data else resp.data
        self.assertEqual(len(rows), 1)


# ─────────────────── API : attestation conformité ───────────────────

class AttestationConformiteApiTest(TestCase):
    def setUp(self):
        self.company = make_company('ac-acme')
        self.user = make_user(self.company, 'ac_user')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/django/ventes/attestations-conformite/'

    def test_create_and_filter_statut(self):
        resp = self.api.post(self.url, {
            'reference': 'ATT-1', 'referentiel': 'NF C 15-100',
            'signataire_nom': 'M. Tazi', 'statut': 'emise',
            'mesures': [{'libelle': 'Isolement', 'valeur': '5.5',
                         'unite': 'MΩ', 'conforme': True}],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        att = AttestationConformite.objects.get(id=resp.data['id'])
        self.assertEqual(att.company_id, self.company.id)
        resp2 = self.api.get(self.url, {'statut': 'emise'})
        rows = resp2.data['results'] if isinstance(
            resp2.data, dict) and 'results' in resp2.data else resp2.data
        self.assertEqual(len(rows), 1)


# ─────────────────────── API : PR de réception ───────────────────────

class TestPerformanceReceptionApiTest(TestCase):
    def setUp(self):
        self.company = make_company('pr-acme')
        self.user = make_user(self.company, 'pr_user')
        self.devis = make_devis(self.company, self.user, ref='DEV-PR-1')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/django/ventes/tests-pr-reception/'

    def test_verdict_and_ecart_derived_server_side(self):
        # Le corps tente d'imposer verdict=accepte ; serveur recalcule refuse.
        resp = self.api.post(self.url, {
            'pr_mesure': '0.70', 'pr_attendu': '0.80',
            'verdict': 'accepte',  # ignoré
            'ecart_pct': '999',    # ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        obj = TestPerformanceReception.objects.get(id=resp.data['id'])
        self.assertEqual(obj.verdict, 'refuse')
        self.assertAlmostEqual(float(obj.ecart_pct), -12.5, places=2)
        self.assertEqual(obj.company_id, self.company.id)

    def test_pr_derived_from_energies(self):
        resp = self.api.post(self.url, {
            'energie_mesuree_kwh': '950', 'energie_attendue_kwh': '1000',
            'pr_attendu': '0.80',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        obj = TestPerformanceReception.objects.get(id=resp.data['id'])
        # 0.80 × 0.95 = 0.76 ≥ 0.75 → accepté.
        self.assertAlmostEqual(float(obj.pr_mesure), 0.76, places=4)
        self.assertEqual(obj.verdict, 'accepte')


# ─────────────────────── API : attestation RE ───────────────────────

class AttestationREApiTest(TestCase):
    def setUp(self):
        self.company = make_company('re-acme')
        self.user = make_user(self.company, 're_user')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/django/ventes/attestations-re/'

    def test_co2_derived_server_side(self):
        # Le corps tente d'imposer co2_evite_t ; serveur recalcule.
        resp = self.api.post(self.url, {
            'reference': 'RE-1', 'energie_kwh': '10000',
            'co2_evite_t': '9999',  # ignoré
            'facteur_co2_kg_kwh': '9',  # ignoré (read-only)
            'signataire_nom': 'Mme Idrissi', 'statut': 'emise',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        att = AttestationRE.objects.get(id=resp.data['id'])
        self.assertEqual(att.company_id, self.company.id)
        self.assertAlmostEqual(float(att.co2_evite_t), 7.2, places=3)
        self.assertAlmostEqual(
            float(att.facteur_co2_kg_kwh), DEFAULT_GRID_CO2_KG_PER_KWH,
            places=4)

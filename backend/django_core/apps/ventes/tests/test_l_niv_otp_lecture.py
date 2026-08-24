"""L-NIV chantier 5 — otp_lecture : gate OTP sur la LECTURE de la proposition
publique (distinct de l'OTP de SIGNATURE QJ11/QX10, gouverné par un toggle
société ; ici c'est un booléen PAR LIEN posé par le commercial).

Covered:
  (a) services.request_otp_lecture / validate_otp_lecture / otp_lecture_verified
      — même mécanique que QJ11 (cache 6 chiffres, anti-brute-force), sous un
      espace de clés séparé, pas de dépendance à ESIGN_OTP_ENABLED.
  (b) proposal_data / proposal_pdf — off (default) → servi comme aujourd'hui ;
      on → 403 jusqu'à vérification, puis servi normalement pendant la
      fenêtre de vérification (1 h).
  (c) endpoints publics demander/vérifier.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_l_niv_otp_lecture -v 2
"""
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client as DjangoClient, TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, ShareLink
from apps.ventes.services import (
    request_otp_lecture,
    validate_otp_lecture,
    otp_lecture_verified,
    _otp_lecture_cache_key,
)

User = get_user_model()


def make_company(slug):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return c


def make_client_obj(company, phone='', email=''):
    return Client.objects.create(
        company=company, nom='OtpLecture', prenom='Test',
        email=email, telephone=phone)


def make_devis(company, client_obj, ref):
    devis = Devis.objects.create(
        company=company, reference=ref, client=client_obj,
        statut='envoye', taux_tva=Decimal('20'))
    # Un devis SANS onduleur classifiable (vocabulaire réseau/hybride du
    # builder) fait refuser build_quote_data → 404 public : lignes minimales.
    from apps.stock.models import Produit
    from apps.ventes.models import LigneDevis
    for desig, qty, pu in [('Onduleur réseau Deye 8kW', '1', '14000'),
                           ('Panneau Canadian Solar 550W', '10', '1400')]:
        produit = Produit.objects.create(
            company=company, nom=desig, sku=f'{ref[-6:]}-{desig[:8]}',
            prix_vente=Decimal(pu), quantite_stock=50)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=desig,
            quantite=Decimal(qty), prix_unitaire=Decimal(pu),
            remise=Decimal('0'))
    return devis


def make_link(devis, otp_lecture=False, niveau=ShareLink.NIVEAU_CONFIANCE):
    return ShareLink.objects.create(
        company=devis.company, devis=devis, token=str(uuid.uuid4()),
        otp_lecture=otp_lecture, niveau=niveau)


# ═══════════════════════════════════════════════════════════════════════════
# (a) services — mechanics
# ═══════════════════════════════════════════════════════════════════════════

class TestOtpLectureServices(TestCase):
    def setUp(self):
        self.company = make_company('lniv-otpl-svc')
        self.client_obj = make_client_obj(
            self.company, phone='+212600000099', email='otpl@test.com')

    def test_otp_lecture_verified_true_when_flag_off(self):
        """Founder rule: off (default) -> served as today, i.e. always
        'verified' (nothing to unlock)."""
        devis = make_devis(self.company, self.client_obj, 'DEV-OTPL-1')
        link = make_link(devis, otp_lecture=False)
        self.assertTrue(otp_lecture_verified(link))

    def test_otp_lecture_verified_false_until_validated(self):
        devis = make_devis(self.company, self.client_obj, 'DEV-OTPL-2')
        link = make_link(devis, otp_lecture=True)
        self.assertFalse(otp_lecture_verified(link))

    def test_request_stores_code_in_separate_cache_namespace(self):
        devis = make_devis(self.company, self.client_obj, 'DEV-OTPL-3')
        link = make_link(devis, otp_lecture=True)
        request_otp_lecture(link)
        stored = cache.get(_otp_lecture_cache_key(link.token))
        self.assertIsNotNone(stored)
        self.assertEqual(len(stored), 6)

    def test_validate_correct_code_unlocks_reading(self):
        devis = make_devis(self.company, self.client_obj, 'DEV-OTPL-4')
        link = make_link(devis, otp_lecture=True)
        cache.set(_otp_lecture_cache_key(link.token), '424242', 600)
        err = validate_otp_lecture(link, '424242')
        self.assertIsNone(err)
        self.assertTrue(otp_lecture_verified(link))

    def test_validate_wrong_code_keeps_it_locked(self):
        devis = make_devis(self.company, self.client_obj, 'DEV-OTPL-5')
        link = make_link(devis, otp_lecture=True)
        cache.set(_otp_lecture_cache_key(link.token), '111111', 600)
        err = validate_otp_lecture(link, '000000')
        self.assertIsNotNone(err)
        self.assertFalse(otp_lecture_verified(link))

    def test_validate_missing_code_returns_error(self):
        devis = make_devis(self.company, self.client_obj, 'DEV-OTPL-6')
        link = make_link(devis, otp_lecture=True)
        err = validate_otp_lecture(link, '')
        self.assertIsNotNone(err)


# ═══════════════════════════════════════════════════════════════════════════
# (b) proposal_data / proposal_pdf gate
# ═══════════════════════════════════════════════════════════════════════════

class TestProposalDataOtpLectureGate(TestCase):
    def setUp(self):
        self.company = make_company('lniv-otpl-data')
        self.client_obj = make_client_obj(self.company)

    def test_off_served_as_today(self):
        devis = make_devis(self.company, self.client_obj, 'DEV-OTPL-D1')
        link = make_link(devis, otp_lecture=False)
        resp = DjangoClient().get(f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 200)

    def test_on_unverified_returns_403(self):
        devis = make_devis(self.company, self.client_obj, 'DEV-OTPL-D2')
        link = make_link(devis, otp_lecture=True)
        resp = DjangoClient().get(f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get('detail'), 'otp_required')

    def test_on_verified_is_served(self):
        devis = make_devis(self.company, self.client_obj, 'DEV-OTPL-D3')
        link = make_link(devis, otp_lecture=True)
        cache.set(_otp_lecture_cache_key(link.token), '555555', 600)
        validate_otp_lecture(link, '555555')
        resp = DjangoClient().get(f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 200)

    def test_invalid_token_still_404s_before_otp_gate(self):
        resp = DjangoClient().get('/api/django/public/proposal/bogus-token/data/')
        self.assertEqual(resp.status_code, 404)


class TestProposalPdfOtpLectureGate(TestCase):
    def setUp(self):
        self.company = make_company('lniv-otpl-pdf')
        self.client_obj = make_client_obj(self.company)

    def test_on_unverified_pdf_returns_403(self):
        devis = make_devis(self.company, self.client_obj, 'DEV-OTPL-P1')
        link = make_link(devis, otp_lecture=True)
        resp = DjangoClient().get(f'/api/django/public/proposal/{link.token}/pdf/')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get('detail'), 'otp_required')


# ═══════════════════════════════════════════════════════════════════════════
# (c) public endpoints — demander / vérifier
# ═══════════════════════════════════════════════════════════════════════════

class TestOtpLecturePublicEndpoints(TestCase):
    def setUp(self):
        self.company = make_company('lniv-otpl-ep')
        self.client_obj = make_client_obj(
            self.company, email='otpl-ep@test.com')
        self.api = DjangoClient()

    def test_demander_noop_when_flag_off(self):
        devis = make_devis(self.company, self.client_obj, 'DEV-OTPL-E1')
        link = make_link(devis, otp_lecture=False)
        resp = self.api.post(
            f'/api/django/public/proposal/{link.token}/otp-lecture/demander/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(cache.get(_otp_lecture_cache_key(link.token)))

    def test_demander_sends_code_when_flag_on(self):
        devis = make_devis(self.company, self.client_obj, 'DEV-OTPL-E2')
        link = make_link(devis, otp_lecture=True)
        resp = self.api.post(
            f'/api/django/public/proposal/{link.token}/otp-lecture/demander/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(cache.get(_otp_lecture_cache_key(link.token)))

    def test_verifier_then_data_is_unlocked(self):
        devis = make_devis(self.company, self.client_obj, 'DEV-OTPL-E3')
        link = make_link(devis, otp_lecture=True)
        self.api.post(
            f'/api/django/public/proposal/{link.token}/otp-lecture/demander/')
        code = cache.get(_otp_lecture_cache_key(link.token))
        resp = self.api.post(
            f'/api/django/public/proposal/{link.token}/otp-lecture/verifier/',
            {'otp_code': code}, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data_resp = self.api.get(
            f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(data_resp.status_code, 200)

    def test_invalid_token_returns_404(self):
        resp = self.api.post(
            '/api/django/public/proposal/bogus-token/otp-lecture/demander/')
        self.assertEqual(resp.status_code, 404)

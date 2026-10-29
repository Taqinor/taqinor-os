"""L-NIV chantier 5 — otp_lecture : gate OTP sur la LECTURE de la proposition
publique (distinct de l'OTP de SIGNATURE QJ11/QX10, gouverné par un toggle
société ; ici c'est un booléen PAR LIEN posé par le commercial).

Covered:
  (a) services.request_otp_lecture / validate_otp_lecture / preuve de lecture
      (ASEC23 : preuve PAR NAVIGATEUR, plus de drapeau global au jeton)
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
import json
import uuid
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client as DjangoClient, TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.domain import cycle_vie
from apps.ventes.models import Devis, DevisSignature, ShareLink
from apps.ventes.services import (
    request_otp_lecture,
    validate_otp_lecture,
    emettre_preuve_lecture,
    preuve_lecture_valide_pour_lien,
)
from apps.ventes.domain.cycle_vie import _otp_lecture_cache_key

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
        self.assertTrue(preuve_lecture_valide_pour_lien(link, ''))

    def test_otp_lecture_verified_false_until_validated(self):
        devis = make_devis(self.company, self.client_obj, 'DEV-OTPL-2')
        link = make_link(devis, otp_lecture=True)
        self.assertFalse(preuve_lecture_valide_pour_lien(link, ''))

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
        # ASEC23 — le code valide ne déverrouille RIEN globalement : seule la
        # preuve émise pour le navigateur vérifié ouvre la lecture.
        self.assertFalse(preuve_lecture_valide_pour_lien(link, ''))
        preuve = emettre_preuve_lecture(link)
        self.assertTrue(preuve_lecture_valide_pour_lien(link, preuve))

    def test_validate_wrong_code_keeps_it_locked(self):
        devis = make_devis(self.company, self.client_obj, 'DEV-OTPL-5')
        link = make_link(devis, otp_lecture=True)
        cache.set(_otp_lecture_cache_key(link.token), '111111', 600)
        err = validate_otp_lecture(link, '000000')
        self.assertIsNotNone(err)
        self.assertFalse(preuve_lecture_valide_pour_lien(link, ''))

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
        self.assertIsNone(validate_otp_lecture(link, '555555'))
        preuve = emettre_preuve_lecture(link)
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{link.token}/data/',
            HTTP_X_PROPOSITION_PREUVE=preuve)
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
        # ASEC23 — la preuve du navigateur vérifié, relayée en en-tête.
        preuve = resp.json()['preuve']
        data_resp = self.api.get(
            f'/api/django/public/proposal/{link.token}/data/',
            HTTP_X_PROPOSITION_PREUVE=preuve)
        self.assertEqual(data_resp.status_code, 200)

    def test_invalid_token_returns_404(self):
        resp = self.api.post(
            '/api/django/public/proposal/bogus-token/otp-lecture/demander/')
        self.assertEqual(resp.status_code, 404)


# ── ASEC23 (C-ASEC-025, D-ASEC-3) — le déverrouillage vaut pour UN navigateur ──
#
# Avant : la vérification posait un drapeau GLOBAL au jeton
# (``otp_lecture_verified:<token>``, TTL 1 h) — un SECOND navigateur, sans
# code, lisait la proposition puis la SIGNAIT pendant l'heure du premier
# (sonde V7 : tiers 200 puis signe, DevisSignature 0→1).
# Après : la vérification rend une PREUVE opaque (contrat ASEC1
# ``apps/ventes/contract_samples/proposition_otp_preuve.json``, CHARGÉ ici —
# jamais un mock écrit à la main) ; le serveur n'en garde que l'empreinte,
# rattachée au jeton ; chaque lecture / action exige ``X-Proposition-Preuve``.
# Chaîne réelle : endpoints publics demander → vérifier → lire / signer, cache
# réel, aucun mock de la garde. Test-du-test : remplacer la garde par la clé
# globale ⇒ ``test_second_navigateur_ne_signe_pas`` rougit.

CONTRAT_PREUVE = (Path(__file__).resolve().parents[1] / 'contract_samples'
                  / 'proposition_otp_preuve.json')
BASE_PUBLIQUE = '/api/django/public/proposal'


def _contrat_preuve():
    return json.loads(CONTRAT_PREUVE.read_text(encoding='utf-8'))


class OtpParNavigateurTests(TestCase):

    def setUp(self):
        cache.clear()
        self.company = make_company('asec23')
        self.client_obj = make_client_obj(
            self.company, email='asec23@example.com')
        self.devis = make_devis(self.company, self.client_obj, 'DV-ASEC23-1')
        from apps.ventes.models import LigneDevis
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, designation='Batterie supplémentaire 5 kWh',
            quantite=Decimal('1'), prix_unitaire=Decimal('12000'),
            remise=Decimal('0'), optionnelle=True)
        self.link = make_link(self.devis, otp_lecture=True)
        self.n1 = APIClient()   # navigateur qui VÉRIFIE
        self.n2 = APIClient()   # second navigateur, sans preuve

    def tearDown(self):
        cache.clear()

    def _corps_signature(self):
        from apps.ventes.public.signature_views import empreinte_contenu
        return {'nom': 'M. Client', 'consent_esign': True,
                'empreinte_contenu': empreinte_contenu(
                    self.devis, link=self.link)}

    def _verifier(self, navigateur, link=None):
        """Parcours réel : demander le code, le saisir, recevoir la preuve,
        et la relayer en en-tête (ce que fait ``apps/web``)."""
        link = link or self.link
        with mock.patch('apps.ventes.domain.cycle_vie._send_otp_email',
                        return_value=True):
            navigateur.post(
                f'{BASE_PUBLIQUE}/{link.token}/otp-lecture/demander/')
        code = cache.get(_otp_lecture_cache_key(link.token))
        self.assertIsNotNone(code)
        resp = navigateur.post(
            f'{BASE_PUBLIQUE}/{link.token}/otp-lecture/verifier/',
            {'otp_code': code}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        navigateur.credentials(HTTP_X_PROPOSITION_PREUVE=resp.data['preuve'])
        return resp

    def _assert_refus(self, resp):
        self.assertEqual(resp.status_code, 403, getattr(resp, 'data', resp))
        self.assertEqual(resp.data,
                         _contrat_preuve()['exemple_refus_sans_preuve'])

    def test_la_reponse_de_verification_suit_le_contrat(self):
        resp = self._verifier(self.n1)
        exemple = _contrat_preuve()['exemple']
        self.assertEqual(set(resp.data), set(exemple))
        self.assertIs(resp.data['verifie'], True)
        self.assertEqual(resp.data['expire_dans'], exemple['expire_dans'])
        # ≥ 32 octets aléatoires en base64 url-safe sans remplissage.
        self.assertGreaterEqual(len(resp.data['preuve']), 43)
        self.assertNotIn('=', resp.data['preuve'])

    def test_la_preuve_est_stockee_hachee(self):
        preuve = self._verifier(self.n1).data['preuve']
        cle = cycle_vie._otp_lecture_preuve_key(
            self.link.token, cycle_vie._empreinte_preuve_lecture(preuve))
        stockee = cache.get(cle)
        self.assertIsNotNone(stockee)
        self.assertNotIn(preuve, json.dumps(stockee))
        self.assertNotIn(preuve, cle)

    def test_second_navigateur_ne_lit_pas(self):
        self._verifier(self.n1)
        self._assert_refus(
            self.n2.get(f'{BASE_PUBLIQUE}/{self.link.token}/data/'))
        self._assert_refus(self.n2.get(
            f'/api/django/public/suivi/{self.link.token}/'))

    def test_second_navigateur_ne_signe_pas(self):
        self._verifier(self.n1)
        avant = DevisSignature.objects.filter(devis=self.devis).count()
        self._assert_refus(self.n2.post(
            f'{BASE_PUBLIQUE}/{self.link.token}/accept/',
            self._corps_signature(), format='json'))
        self.assertEqual(
            DevisSignature.objects.filter(devis=self.devis).count(), avant)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)

    def test_second_navigateur_n_active_pas_d_option(self):
        self._verifier(self.n1)
        self._assert_refus(self.n2.post(
            f'{BASE_PUBLIQUE}/{self.link.token}/activer-option/',
            {'ligne_id': self.ligne.id}, format='json'))
        self.ligne.refresh_from_db()
        self.assertTrue(self.ligne.optionnelle)

    def test_second_navigateur_ni_contact_ni_engagement(self):
        self._verifier(self.n1)
        self._assert_refus(self.n2.post(
            f'{BASE_PUBLIQUE}/{self.link.token}/contact/',
            {'channel': 'rappel'}, format='json'))
        self._assert_refus(self.n2.post(
            f'{BASE_PUBLIQUE}/{self.link.token}/engagement/',
            {'section': 'prix', 'seconds': 12}, format='json'))
        self.link.refresh_from_db()
        self.assertFalse(self.link.engagement)

    def test_navigateur_verifie_signe(self):
        self._verifier(self.n1)
        lecture = self.n1.get(f'/api/django/public/suivi/{self.link.token}/')
        self.assertEqual(lecture.status_code, 200, lecture.data)
        resp = self.n1.post(f'{BASE_PUBLIQUE}/{self.link.token}/accept/',
                            self._corps_signature(), format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(
            DevisSignature.objects.filter(devis=self.devis).count(), 1)
        # La signature de N1 ne déverrouille RIEN pour N2 (ADEV97 : plus de
        # drapeau global posé après une acceptation fraîche).
        self._assert_refus(self.n2.get(
            f'/api/django/public/suivi/{self.link.token}/'))

    def test_preuve_autre_jeton_refusee(self):
        autre_devis = make_devis(self.company, self.client_obj, 'DV-ASEC23-2')
        autre = make_link(autre_devis, otp_lecture=True)
        # N2 a vérifié l'AUTRE lien : sa preuve ne vaut rien ici.
        self._verifier(self.n2, link=autre)
        self._assert_refus(self.n2.post(
            f'{BASE_PUBLIQUE}/{self.link.token}/accept/',
            self._corps_signature(), format='json'))
        self.assertFalse(
            DevisSignature.objects.filter(devis=self.devis).exists())

    def test_preuve_expiree_refusee(self):
        self._verifier(self.n1)
        horloge = mock.Mock()
        horloge.time.return_value = (
            cycle_vie.time.time() + cycle_vie.OTP_LECTURE_VERIFIED_TTL + 1)
        with mock.patch.object(cycle_vie, 'time', horloge):
            self._assert_refus(self.n1.post(
                f'{BASE_PUBLIQUE}/{self.link.token}/accept/',
                self._corps_signature(), format='json'))
        self.assertFalse(
            DevisSignature.objects.filter(devis=self.devis).exists())

    def test_preuve_inventee_refusee(self):
        self._verifier(self.n1)
        self.n2.credentials(
            HTTP_X_PROPOSITION_PREUVE=_contrat_preuve()['exemple']['preuve'])
        self._assert_refus(
            self.n2.get(f'{BASE_PUBLIQUE}/{self.link.token}/data/'))

    def test_deux_navigateurs_verifies_gardent_chacun_leur_preuve(self):
        """Une nouvelle vérification n'invalide pas la preuve précédente
        (plusieurs appareils du même client — contrat ASEC1)."""
        self._verifier(self.n1)
        self._verifier(self.n2)
        for navigateur in (self.n1, self.n2):
            resp = navigateur.get(
                f'/api/django/public/suivi/{self.link.token}/')
            self.assertEqual(resp.status_code, 200, resp.data)

    def test_lien_sans_otp_lecture_inchange(self):
        self.link.otp_lecture = False
        self.link.save(update_fields=['otp_lecture'])
        resp = self.n2.post(f'{BASE_PUBLIQUE}/{self.link.token}/accept/',
                            self._corps_signature(), format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_aucune_cle_globale_au_jeton(self):
        """Jumeau supprimé : l'ancien drapeau global n'existe plus."""
        self._verifier(self.n1)
        self.assertIsNone(
            cache.get(f'otp_lecture_verified:{self.link.token}'))
        self.assertFalse(hasattr(cycle_vie, 'otp_lecture_verified'))
        self.assertFalse(hasattr(cycle_vie, '_otp_lecture_verified_key'))

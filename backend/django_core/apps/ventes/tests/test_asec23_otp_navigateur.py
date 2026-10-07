"""ASEC23 (C-ASEC-025, D-ASEC-3) — le déverrouillage OTP de LECTURE de la
proposition vaut pour UN NAVIGATEUR, jamais pour le jeton entier.

Avant : la vérification posait un drapeau GLOBAL au jeton
(``otp_lecture_verified:<token>``, TTL 1 h) — un SECOND navigateur, sans
code, lisait la proposition puis la SIGNAIT pendant l'heure du premier
(sonde V7 : tiers 200 puis signe, DevisSignature 0→1).

Après : la vérification rend une PREUVE opaque (contrat ASEC1
``apps/ventes/contract_samples/proposition_otp_preuve.json``, CHARGÉ ici —
jamais un mock écrit à la main) ; le serveur n'en garde que l'empreinte,
rattachée au jeton ; chaque lecture / action exige l'en-tête
``X-Proposition-Preuve``.

Chaîne réelle : endpoints publics demander → vérifier → lire / signer, cache
réel, aucun mock de la garde.
"""
import json
import uuid
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.ventes.domain import cycle_vie
from apps.ventes.domain.cycle_vie import _otp_lecture_cache_key
from apps.ventes.models import Devis, DevisSignature, LigneDevis, ShareLink
from authentication.models import Company

CONTRAT = (Path(__file__).resolve().parents[1] / 'contract_samples'
           / 'proposition_otp_preuve.json')
BASE = '/api/django/public/proposal'
CORPS_SIGNATURE = {'nom': 'M. Client', 'consent_esign': True}


def _contrat():
    return json.loads(CONTRAT.read_text(encoding='utf-8'))


class _Base(TestCase):

    def setUp(self):
        cache.clear()
        self.company = Company.objects.get_or_create(
            slug='asec23', defaults={'nom': 'ASEC23'})[0]
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASEC23',
            email='asec23@example.com', telephone='')
        self.devis = Devis.objects.create(
            company=self.company, reference='DV-ASEC23-1',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, designation='Batterie supplémentaire 5 kWh',
            quantite=Decimal('1'), prix_unitaire=Decimal('12000'),
            remise=Decimal('0'), optionnelle=True)
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis, token=str(uuid.uuid4()),
            otp_lecture=True)
        self.n1 = APIClient()   # navigateur qui VÉRIFIE
        self.n2 = APIClient()   # second navigateur, sans preuve

    def tearDown(self):
        cache.clear()

    def _verifier(self, navigateur, link=None):
        """Parcours réel : demander le code, le saisir, recevoir la preuve,
        et la relayer en en-tête (ce que fait ``apps/web``)."""
        link = link or self.link
        navigateur.post(f'{BASE}/{link.token}/otp-lecture/demander/')
        code = cache.get(_otp_lecture_cache_key(link.token))
        self.assertIsNotNone(code)
        resp = navigateur.post(
            f'{BASE}/{link.token}/otp-lecture/verifier/',
            {'otp_code': code}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        preuve = resp.data['preuve']
        navigateur.credentials(HTTP_X_PROPOSITION_PREUVE=preuve)
        return resp

    def _assert_refus(self, resp):
        self.assertEqual(resp.status_code, 403, getattr(resp, 'data', resp))
        self.assertEqual(resp.data, _contrat()['exemple_refus_sans_preuve'])


class OtpParNavigateurTests(_Base):

    def test_la_reponse_de_verification_suit_le_contrat(self):
        resp = self._verifier(self.n1)
        exemple = _contrat()['exemple']
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
        self._assert_refus(self.n2.get(f'{BASE}/{self.link.token}/data/'))
        self._assert_refus(self.n2.get(
            f'/api/django/public/suivi/{self.link.token}/'))

    def test_second_navigateur_ne_signe_pas(self):
        self._verifier(self.n1)
        avant = DevisSignature.objects.filter(devis=self.devis).count()
        self._assert_refus(self.n2.post(
            f'{BASE}/{self.link.token}/accept/', CORPS_SIGNATURE,
            format='json'))
        self.assertEqual(
            DevisSignature.objects.filter(devis=self.devis).count(), avant)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)

    def test_second_navigateur_n_active_pas_d_option(self):
        self._verifier(self.n1)
        self._assert_refus(self.n2.post(
            f'{BASE}/{self.link.token}/activer-option/',
            {'ligne_id': self.ligne.id}, format='json'))
        self.ligne.refresh_from_db()
        self.assertTrue(self.ligne.optionnelle)

    def test_second_navigateur_ni_contact_ni_engagement(self):
        self._verifier(self.n1)
        self._assert_refus(self.n2.post(
            f'{BASE}/{self.link.token}/contact/',
            {'channel': 'rappel'}, format='json'))
        self._assert_refus(self.n2.post(
            f'{BASE}/{self.link.token}/engagement/',
            {'section': 'prix', 'seconds': 12}, format='json'))
        self.link.refresh_from_db()
        self.assertFalse(self.link.engagement)

    def test_navigateur_verifie_signe(self):
        self._verifier(self.n1)
        lecture = self.n1.get(f'/api/django/public/suivi/{self.link.token}/')
        self.assertEqual(lecture.status_code, 200, lecture.data)
        resp = self.n1.post(f'{BASE}/{self.link.token}/accept/',
                            CORPS_SIGNATURE, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(
            DevisSignature.objects.filter(devis=self.devis).count(), 1)

    def test_preuve_autre_jeton_refusee(self):
        autre_devis = Devis.objects.create(
            company=self.company, reference='DV-ASEC23-2',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        autre = ShareLink.objects.create(
            company=self.company, devis=autre_devis,
            token=str(uuid.uuid4()), otp_lecture=True)
        # N2 a vérifié l'AUTRE lien : sa preuve ne vaut rien ici.
        self._verifier(self.n2, link=autre)
        self._assert_refus(self.n2.post(
            f'{BASE}/{self.link.token}/accept/', CORPS_SIGNATURE,
            format='json'))
        self.assertFalse(
            DevisSignature.objects.filter(devis=self.devis).exists())

    def test_preuve_expiree_refusee(self):
        self._verifier(self.n1)
        horloge = mock.Mock()
        horloge.time.return_value = (
            cycle_vie.time.time() + cycle_vie.OTP_LECTURE_VERIFIED_TTL + 1)
        with mock.patch.object(cycle_vie, 'time', horloge):
            self._assert_refus(self.n1.post(
                f'{BASE}/{self.link.token}/accept/', CORPS_SIGNATURE,
                format='json'))
        self.assertFalse(
            DevisSignature.objects.filter(devis=self.devis).exists())

    def test_preuve_inventee_refusee(self):
        self._verifier(self.n1)
        self.n2.credentials(
            HTTP_X_PROPOSITION_PREUVE=_contrat()['exemple']['preuve'])
        self._assert_refus(self.n2.get(f'{BASE}/{self.link.token}/data/'))

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
        resp = self.n2.post(f'{BASE}/{self.link.token}/accept/',
                            CORPS_SIGNATURE, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_aucune_cle_globale_au_jeton(self):
        """Jumeau supprimé : l'ancien drapeau global n'existe plus."""
        self._verifier(self.n1)
        self.assertIsNone(cache.get(f'otp_lecture_verified:{self.link.token}'))
        self.assertFalse(hasattr(cycle_vie, 'otp_lecture_verified'))
        self.assertFalse(hasattr(cycle_vie, '_otp_lecture_verified_key'))

"""QJR147 — plafond cumulatif sur les demandes d'OTP publiques.

Constat ES5 de l'audit du 30/08/2026, vérifié en code : les deux endpoints de
DEMANDE d'OTP sont ``AllowAny`` et leur seul frein était
``PublicLinkRateThrottle`` (30/minute par IP + jeton) — ni plafond journalier,
ni plafond PAR JETON toutes IP confondues. Et chaque demande faisait
``cache.delete(_otp_attempts_key(...))`` : le verrouillage à cinq tentatives
n'était donc qu'un ralentisseur (cinq essais, on redemande un code, cinq essais
de plus, indéfiniment).

LE DOMMAGE LE PLUS DÉMONTRABLE n'est pas le brute-force : **chaque demande
envoie un vrai email au contact du devis**. Un porteur de jeton pouvait
bombarder le client de son propre fournisseur.

ES7 est traité dans le même lot : le jeton Meta CAPI passait en QUERY STRING
alors que l'API l'accepte dans le corps (risque environnemental — journaux
d'accès, proxys ; vérifié : ce code ne le journalise pas lui-même).

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr147_otp_plafond -v 2
"""
import json
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.crm.models import Client
from apps.ventes.models import Devis, ShareLink
from apps.ventes.services import (
    OTP_MAX_ATTEMPTS, _otp_lecture_attempts_key, _otp_lecture_cache_key,
    request_esign_otp, request_otp_lecture, validate_otp_lecture,
)
from apps.ventes.domain.cycle_vie import (
    OTP_DEMANDES_MAX_PAR_JOUR, OTP_PLAFOND_MESSAGE,
)
from authentication.models import Company


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class _BaseOtp(TestCase):
    slug = 'qjr147'

    def setUp(self):
        cache.clear()
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR147',
            email='qjr147-%s@example.com' % self.slug,
            telephone='+212600000147')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR147-%s' % self.slug[-3:],
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        self.link = self._lien()

    def _lien(self):
        return ShareLink.objects.create(
            company=self.company, devis=self.devis, token=str(uuid.uuid4()),
            otp_lecture=True)

    def _sans_reseau(self):
        """Neutralise les deux canaux d'envoi et compte les emails."""
        return patch('apps.ventes.domain.cycle_vie._send_otp_email',
                     return_value=True)


class LePlafondJournalierParJeton(_BaseOtp):
    """ES5 — un porteur de jeton ne peut plus bombarder le client d'emails."""

    slug = 'qjr147-plafond'

    def test_les_demandes_de_lecture_sont_plafonnees(self):
        with self._sans_reseau() as envoi:
            for rang in range(OTP_DEMANDES_MAX_PAR_JOUR):
                self.assertIsNone(
                    request_otp_lecture(self.link),
                    'la demande n° %d devait passer' % (rang + 1))
            refus = request_otp_lecture(self.link)

        self.assertEqual(refus, OTP_PLAFOND_MESSAGE)
        self.assertEqual(envoi.call_count, OTP_DEMANDES_MAX_PAR_JOUR,
                         "la demande refusée ne doit envoyer AUCUN email")

    def test_le_refus_ne_regenere_meme_pas_de_code(self):
        """Le plafond est compté AVANT toute génération : un refus ne remplace
        pas le code déjà en cache."""
        with self._sans_reseau():
            for _ in range(OTP_DEMANDES_MAX_PAR_JOUR):
                request_otp_lecture(self.link)
            code_avant = cache.get(_otp_lecture_cache_key(self.link.token))
            request_otp_lecture(self.link)
        self.assertEqual(
            cache.get(_otp_lecture_cache_key(self.link.token)), code_avant)

    def test_les_demandes_de_signature_sont_plafonnees_aussi(self):
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            with self._sans_reseau():
                for _ in range(OTP_DEMANDES_MAX_PAR_JOUR):
                    self.assertIsNone(request_esign_otp(self.link))
                refus = request_esign_otp(self.link)
        self.assertEqual(refus, OTP_PLAFOND_MESSAGE)

    def test_le_plafond_est_PAR_JETON_pas_global(self):
        """Un client dont le lien est saturé ne bloque pas les autres."""
        autre = self._lien()
        with self._sans_reseau():
            for _ in range(OTP_DEMANDES_MAX_PAR_JOUR):
                request_otp_lecture(self.link)
            self.assertEqual(request_otp_lecture(self.link),
                             OTP_PLAFOND_MESSAGE)
            self.assertIsNone(request_otp_lecture(autre))

    def test_le_compteur_de_demandes_n_est_jamais_remis_a_zero(self):
        """C'est TOUT l'intérêt : contrairement au compteur d'échecs d'hier,
        une nouvelle demande ne l'efface pas — sinon le plafond serait
        inatteignable."""
        with self._sans_reseau():
            for _ in range(OTP_DEMANDES_MAX_PAR_JOUR + 3):
                request_otp_lecture(self.link)
            # Après dépassement, TOUTES les suivantes restent refusées.
            self.assertEqual(request_otp_lecture(self.link),
                             OTP_PLAFOND_MESSAGE)

    def test_un_cache_illisible_echoue_FERME(self):
        """Même discipline que les autres chemins OTP du module : sans
        compteur lisible, on refuse d'envoyer plutôt que d'ouvrir un robinet."""
        with patch('django.core.cache.backends.locmem.LocMemCache.incr',
                   side_effect=RuntimeError('cache HS')):
            with self._sans_reseau() as envoi:
                refus = request_otp_lecture(self.link)
        self.assertEqual(refus, OTP_PLAFOND_MESSAGE)
        self.assertEqual(envoi.call_count, 0)


class LeVerrouDEchecsSurvitALaRegeneration(_BaseOtp):
    """ES5, seconde moitié — le verrouillage n'est plus annulable d'un clic."""

    slug = 'qjr147-verrou'

    def test_le_compteur_d_echecs_de_lecture_n_est_plus_efface(self):
        cache.set(_otp_lecture_attempts_key(self.link.token),
                  OTP_MAX_ATTEMPTS, 600)
        with self._sans_reseau():
            request_otp_lecture(self.link)
        self.assertEqual(
            cache.get(_otp_lecture_attempts_key(self.link.token)),
            OTP_MAX_ATTEMPTS)

    def test_le_verrou_de_lecture_tient_apres_un_nouveau_code(self):
        cache.set(_otp_lecture_attempts_key(self.link.token),
                  OTP_MAX_ATTEMPTS, 600)
        with self._sans_reseau():
            request_otp_lecture(self.link)
        code = cache.get(_otp_lecture_cache_key(self.link.token))
        self.assertIsNotNone(code)
        # MÊME avec le bon code : le lien est gelé le temps de la fenêtre.
        err = validate_otp_lecture(self.link, code)
        self.assertIn('Trop de tentatives', err)

    def test_le_message_ne_promet_plus_qu_un_nouveau_code_debloque(self):
        cache.set(_otp_lecture_attempts_key(self.link.token),
                  OTP_MAX_ATTEMPTS, 600)
        err = validate_otp_lecture(self.link, '000000')
        self.assertIn('gelé', err)
        self.assertNotIn('Redemandez un nouveau code de confirmation', err)


@override_settings(META_CAPI_ACCESS_TOKEN='jeton-secret-capi',
                   META_CAPI_PIXEL_ID='1234567890')
class LeJetonMetaVoyageDansLeCorps(_BaseOtp):
    """ES7 — plus d'``access_token`` en query string (journaux, proxys)."""

    slug = 'qjr147-capi'

    def test_l_url_ne_porte_plus_le_jeton_et_le_corps_le_porte(self):
        from apps.ventes.domain.cycle_vie import _fire_capi_signed_quote

        captures = []

        def _faux(req, timeout=None):
            captures.append(req)
            reponse = MagicMock()
            reponse.read.return_value = b'{"events_received":1}'
            reponse.status = 200
            reponse.__enter__.return_value = reponse
            reponse.__exit__.return_value = False
            return reponse

        with patch('urllib.request.urlopen', side_effect=_faux):
            _fire_capi_signed_quote(devis=self.devis)

        self.assertEqual(len(captures), 1)
        req = captures[0]
        self.assertNotIn('access_token', req.full_url)
        corps = json.loads(req.data.decode('utf-8'))
        self.assertEqual(corps['access_token'], 'jeton-secret-capi')
        # L'événement lui-même n'a pas bougé de place.
        self.assertEqual(corps['data'][0]['event_name'], 'SignedQuote')

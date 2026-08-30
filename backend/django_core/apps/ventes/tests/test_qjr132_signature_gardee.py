"""QJR132 — la SIGNATURE d'un devis est au moins aussi gardée que sa LECTURE.

Constat ES1 de l'audit du 30/08/2026, vérifié en code : ``proposal_accept``
n'appelait JAMAIS ``otp_lecture_verified(link)``, contrairement aux TROIS
routes de LECTURE de la même proposition (``proposal_data``, la page publique
et ``proposal_pdf``). Sur un lien où le commercial a activé l'OTP de lecture,
quiconque détenait le jeton pouvait donc **engager le client** sans jamais
fournir de code : le geste le plus lourd du parcours était le moins gardé.

INDÉPENDANT DU TOGGLE DE SIGNATURE. L'OTP de SIGNATURE (``validate_esign_otp``)
est gouverné par ``ESIGN_OTP_ENABLED``, dont l'audit a vérifié qu'il n'apparaît
dans AUCUN ``.env.example``, settings ou ``docker-compose`` : il vaut donc '0'
en production, et ce contrôle-là est un no-op. La garde posée ici ne dépend
d'aucun réglage — elle suit ce que LE LIEN porte (``ShareLink.otp_lecture``).

LES DEUX SENS SONT ÉPINGLÉS : refus quand le lien porte l'OTP de lecture et
qu'il n'est pas vérifié ; comportement STRICTEMENT INCHANGÉ sinon (aucun lien
d'aujourd'hui ne porte ce booléen par défaut).

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr132_signature_gardee -v 2
"""
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.ventes.models import Devis, ShareLink
from apps.ventes.services import (
    _otp_lecture_cache_key, validate_otp_lecture,
)
from authentication.models import Company


def _url_accept(token):
    return f'/api/django/public/proposal/{token}/accept/'


CORPS_SIGNATURE = {'nom': 'M. Client', 'consent_esign': True}


class _BaseSignature(TestCase):
    slug = 'qjr132'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR132',
            email='qjr132-%s@example.com' % self.slug, telephone='')
        self.api = APIClient()

    def _devis(self, ref):
        return Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'))

    def _lien(self, devis, *, otp_lecture=False):
        return ShareLink.objects.create(
            company=devis.company, devis=devis, token=str(uuid.uuid4()),
            otp_lecture=otp_lecture)

    def _verifier_le_lien(self, link):
        """Le client a fourni son code : la lecture est déverrouillée."""
        cache.set(_otp_lecture_cache_key(link.token), '424242', 600)
        self.assertIsNone(validate_otp_lecture(link, '424242'))

    def _assert_pas_signe(self, devis, reponse):
        devis.refresh_from_db()
        self.assertNotEqual(devis.statut, Devis.Statut.ACCEPTE, reponse.data)
        self.assertEqual(devis.accepte_par_nom or '', '')
        self.assertIsNone(devis.date_acceptation)


class LeLienSansOtpDeLectureSigneCommeAvant(_BaseSignature):
    """LE TÉMOIN — le sens « inchangé ». ``otp_lecture`` vaut False par défaut
    sur tous les liens existants : leur signature ne bouge pas d'un octet."""

    slug = 'qjr132-temoin'

    def test_la_signature_passe(self):
        devis = self._devis('DEV-QJR132-T1')
        link = self._lien(devis, otp_lecture=False)
        resp = self.api.post(_url_accept(link.token), CORPS_SIGNATURE,
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(devis.accepte_par_nom, 'M. Client')


class LeLienAOtpDeLectureExigeLeCodePourSigner(_BaseSignature):
    """ES1 — le trou refermé."""

    slug = 'qjr132-public'

    def test_non_verifie_la_signature_est_refusee(self):
        devis = self._devis('DEV-QJR132-P1')
        link = self._lien(devis, otp_lecture=True)
        resp = self.api.post(_url_accept(link.token), CORPS_SIGNATURE,
                             format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(resp.data.get('detail'), 'otp_required')
        self._assert_pas_signe(devis, resp)

    def test_verifie_la_signature_passe(self):
        devis = self._devis('DEV-QJR132-P2')
        link = self._lien(devis, otp_lecture=True)
        self._verifier_le_lien(link)
        resp = self.api.post(_url_accept(link.token), CORPS_SIGNATURE,
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)

    def test_la_garde_ne_depend_pas_du_toggle_de_signature(self):
        """``ESIGN_OTP_ENABLED`` vaut '0' en production (il n'est déclaré nulle
        part) : c'est PRÉCISÉMENT dans cet état que le jeton seul suffisait à
        engager le client."""
        devis = self._devis('DEV-QJR132-P3')
        link = self._lien(devis, otp_lecture=True)
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '0'}):
            resp = self.api.post(_url_accept(link.token), CORPS_SIGNATURE,
                                 format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        self._assert_pas_signe(devis, resp)

    def test_le_refus_precede_toute_lecture_du_corps(self):
        """Un corps VIDE (ni nom ni consentement) reçoit quand même le 403 de
        l'OTP, pas un 400 de validation : la garde est bien la première."""
        devis = self._devis('DEV-QJR132-P4')
        link = self._lien(devis, otp_lecture=True)
        resp = self.api.post(_url_accept(link.token), {}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(resp.data.get('detail'), 'otp_required')


class LeJetonInterneNeSigneJamais(_BaseSignature):
    """L-INTPREV, préservé : l'aperçu commercial ne peut pas engager le client,
    avec ou sans OTP de lecture — et le refus reste le 404 générique (jamais un
    message qui distinguerait le jeton interne d'un jeton invalide)."""

    slug = 'qjr132-interne'

    def test_sans_otp_de_lecture(self):
        devis = self._devis('DEV-QJR132-I1')
        link = self._lien(devis, otp_lecture=False)
        resp = self.api.post(
            _url_accept(link.jeton_interne_effectif()), CORPS_SIGNATURE,
            format='json')
        self.assertEqual(resp.status_code, 404, resp.data)
        self._assert_pas_signe(devis, resp)

    def test_avec_otp_de_lecture(self):
        devis = self._devis('DEV-QJR132-I2')
        link = self._lien(devis, otp_lecture=True)
        resp = self.api.post(
            _url_accept(link.jeton_interne_effectif()), CORPS_SIGNATURE,
            format='json')
        self.assertEqual(resp.status_code, 404, resp.data)
        self._assert_pas_signe(devis, resp)

"""NTAPI6 — quota FG398 réellement APPLIQUÉ + en-têtes `X-RateLimit-*`.

Critère d'acceptation :
  * dépasser le quota MENSUEL du plan renvoie 429 + `Retry-After` ;
  * les en-têtes `X-RateLimit-Limit/Remaining/Reset` reflètent le compteur RÉEL
    (pas une constante de configuration).

Vérifie aussi les deux non-régressions qui comptent : sans plan enregistré le
comportement reste l'historique (aucun en-tête, aucune borne de volume), et un
appel NON authentifié ne consomme jamais le quota d'une société.
"""
import datetime

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from core import api_usage
from core.models import ApiUsagePlan, ApiUsageRecord
from testkit.time import frozen

from .constants import SCOPE_READ_LEADS
from .models import ApiKey
from .public_response import (
    RATE_LIMIT_LIMIT_HEADER, RATE_LIMIT_REMAINING_HEADER,
    RATE_LIMIT_RESET_HEADER, RETRY_AFTER_HEADER,
)


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


class Ntapi6QuotaEnforcementTests(TestCase):
    def setUp(self):
        # Le throttle DRF de débit s'appuie sur le cache : le vider isole ce
        # test des fenêtres glissantes laissées par les suites voisines.
        cache.clear()
        self.co = _company('ntapi6', 'NTAPI6')
        self.key, self.raw = ApiKey.issue(
            company=self.co, label='quota', scopes=[SCOPE_READ_LEADS])

    def _plan(self, **kwargs):
        champs = {'quota_par_minute': 0, 'quota_par_jour': 0,
                  'quota_par_mois': 0}
        champs.update(kwargs)
        plan, _ = ApiUsagePlan.objects.update_or_create(
            company=self.co, defaults=champs)
        return plan

    def _consommer(self, nb, *, jour=None):
        """Pré-remplit le compteur d'usage sans passer par HTTP."""
        jour = jour or timezone.now().date()
        ApiUsageRecord.objects.update_or_create(
            api_key=self.key, jour=jour,
            defaults={'company': self.co, 'nb_requetes': nb})

    # ── Le cœur du critère ────────────────────────────────────────────────
    def test_quota_mensuel_depasse_renvoie_429_et_retry_after(self):
        self._plan(quota_par_mois=10)
        self._consommer(10)  # quota mensuel atteint
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 429)
        self.assertIn(RETRY_AFTER_HEADER, resp)
        self.assertGreater(int(resp[RETRY_AFTER_HEADER]), 0)
        self.assertEqual(resp.json()['error']['code'], 'throttled')

    def test_entetes_refletent_le_compteur_reel(self):
        self._plan(quota_par_mois=100)
        self._consommer(40)
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp[RATE_LIMIT_LIMIT_HEADER], '100')
        # 40 déjà consommés + CET appel = 41 → il en reste 59.
        self.assertEqual(resp[RATE_LIMIT_REMAINING_HEADER], '59')
        self.assertGreater(int(resp[RATE_LIMIT_RESET_HEADER]),
                           int(timezone.now().timestamp()))

    def test_remaining_decroit_appel_apres_appel(self):
        self._plan(quota_par_mois=50)
        client = _key_client(self.raw)
        premier = client.get('/api/public/v1/leads/')
        second = client.get('/api/public/v1/leads/')
        self.assertEqual(premier.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            int(premier[RATE_LIMIT_REMAINING_HEADER])
            - int(second[RATE_LIMIT_REMAINING_HEADER]), 1)

    def test_quota_journalier_aussi_applique(self):
        self._plan(quota_par_jour=5)
        self._consommer(5)
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 429)

    def test_fenetre_la_plus_contraignante_est_exposee(self):
        # Jour (10, dont 8 consommés → 2 restants) plus serré que le mois
        # (1000, 8 consommés → 992 restants) : c'est le jour qu'on annonce.
        self._plan(quota_par_jour=10, quota_par_mois=1000)
        self._consommer(8)
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp[RATE_LIMIT_LIMIT_HEADER], '10')
        self.assertEqual(resp[RATE_LIMIT_REMAINING_HEADER], '1')

    # ── Non-régressions ───────────────────────────────────────────────────
    def test_sans_plan_aucun_entete_et_aucune_borne(self):
        self.assertFalse(ApiUsagePlan.objects.filter(company=self.co).exists())
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(RATE_LIMIT_LIMIT_HEADER, resp)
        self.assertNotIn(RATE_LIMIT_REMAINING_HEADER, resp)

    def test_plan_inactif_ne_borne_rien(self):
        self._plan(quota_par_mois=1, actif=False)
        self._consommer(500)
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(RATE_LIMIT_LIMIT_HEADER, resp)

    def test_quota_zero_signifie_illimite(self):
        self._plan(quota_par_mois=0, quota_par_jour=0)
        self._consommer(10_000)
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(RATE_LIMIT_LIMIT_HEADER, resp)

    def test_appel_non_authentifie_ne_consomme_aucun_quota(self):
        self._plan(quota_par_mois=100)
        avant = api_usage.usage_mois(self.co)
        resp = APIClient().get('/api/public/v1/leads/')
        self.assertIn(resp.status_code, (401, 403))
        self.assertEqual(api_usage.usage_mois(self.co), avant)

    def test_appel_compte_dans_lusage_de_la_societe(self):
        self._plan(quota_par_mois=100)
        avant = api_usage.usage_mois(self.co)
        _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertEqual(api_usage.usage_mois(self.co), avant + 1)

    def test_quota_dune_societe_ne_borne_jamais_une_autre(self):
        autre = _company('ntapi6-autre', 'NTAPI6 autre')
        _autre_key, autre_raw = ApiKey.issue(
            company=autre, label='autre', scopes=[SCOPE_READ_LEADS])
        self._plan(quota_par_mois=1)
        self._consommer(5)  # société A saturée
        self.assertEqual(
            _key_client(self.raw).get('/api/public/v1/leads/').status_code, 429)
        self.assertEqual(
            _key_client(autre_raw).get('/api/public/v1/leads/').status_code, 200)

    # ── Sélecteur de fondation ────────────────────────────────────────────
    def test_etat_quota_retourne_none_sans_borne(self):
        self._plan()
        self.assertIsNone(api_usage.etat_quota(self.key))

    def test_limite_par_minute_ajoute_la_marge_de_rafale(self):
        self._plan(quota_par_minute=60, quota_burst=20)
        self.assertEqual(api_usage.limite_par_minute(self.key), 80)

    def test_reset_mensuel_pointe_le_mois_suivant(self):
        self._plan(quota_par_mois=100)
        # Temps GELÉ : sans cela, l'assertion « le reset est dans le futur »
        # se compare à une horloge vivante et deviendrait une bascule de
        # minuit (et un fin-de-mois) intermittente en CI.
        with frozen('2026-12-15T10:00:00Z'):
            etat = api_usage.etat_quota(self.key)
        # Les compteurs d'usage sont agrégés sur la date UTC (`enregistrer_usage`
        # utilise `timezone.now().date()`) : la borne de réinitialisation se lit
        # donc en UTC, jamais dans le fuseau d'affichage.
        reset = datetime.datetime.fromtimestamp(
            etat['reset'], tz=datetime.timezone.utc)
        self.assertEqual((reset.year, reset.month, reset.day), (2027, 1, 1))
        self.assertEqual(reset.hour, 0)

    def test_record_call_est_bien_lalias_de_enregistrer_usage(self):
        self.assertIs(api_usage.record_call, api_usage.enregistrer_usage)

"""NTAPI38 — journal d'appels de l'API publique (`publicapi.ApiCallLog`).

Critère d'acceptation, les deux volets :
  * chaque appel public crée une entrée AVEC latence et `request_id` ;
  * la purge respecte la rétention DU PLAN de la société (NTAPI7).

Le middleware est éprouvé BRANCHÉ (`override_settings(MIDDLEWARE=…)`) et non
appelé à la main : c'est la seule façon de prouver que `request.request_id`
(posé par `core.middleware.RequestIdMiddleware`, plus haut dans la pile) et le
statut réel de la réponse arrivent bien dans la ligne.

Le middleware n'est PAS encore inscrit dans `erp_agentique/settings/base.py`
(hors périmètre de cette lane) : sans cette inscription, la journalisation est
inerte en production — le modèle, la purge et le middleware sont prêts.
"""
from datetime import timedelta

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Lead
from core.models import ApiUsagePlan

from . import call_log
from .constants import SCOPE_READ_LEADS
from .models import ApiCallLog, ApiKey

# La pile RÉELLE du projet + le middleware de journalisation en dernier : il
# doit voir le statut final de la réponse ET le `request_id` posé en tête de
# pile par `RequestIdMiddleware` (YAPIC4).
MIDDLEWARE_AVEC_JOURNAL = list(settings.MIDDLEWARE) + [
    'apps.publicapi.middleware.PublicApiCallLogMiddleware',
]


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


@override_settings(MIDDLEWARE=MIDDLEWARE_AVEC_JOURNAL)
class Ntapi38JournalisationTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi38', 'NTAPI38')
        Lead.objects.create(company=self.co, nom='Lead journalisé')
        _key, self.raw = ApiKey.issue(
            company=self.co, label='journal', scopes=[SCOPE_READ_LEADS])

    # ── Le cœur du critère ────────────────────────────────────────────────
    def test_un_appel_public_cree_une_entree_avec_latence_et_request_id(self):
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 200, resp.content)
        entree = ApiCallLog.objects.get()
        self.assertEqual(entree.company_id, self.co.id)
        self.assertEqual(entree.methode, 'GET')
        self.assertEqual(entree.chemin, '/api/public/v1/leads/')
        self.assertEqual(entree.statut, 200)
        self.assertFalse(entree.est_erreur)
        self.assertGreaterEqual(entree.latence_ms, 0)
        self.assertTrue(entree.taille_payload > 0)
        # Le MÊME identifiant que l'en-tête de réponse : c'est le seul point de
        # recoupement entre une plainte client et les logs serveur.
        self.assertTrue(entree.request_id)
        self.assertEqual(entree.request_id, resp['X-Request-Id'])

    def test_la_cle_emettrice_est_tracee(self):
        cle, raw = ApiKey.issue(
            company=self.co, label='tracee', scopes=[SCOPE_READ_LEADS])
        _key_client(raw).get('/api/public/v1/leads/')
        entree = ApiCallLog.objects.get()
        self.assertEqual(entree.api_key_id, cle.pk)

    def test_un_appel_en_erreur_est_journalise_aussi(self):
        """Un 403 (scope manquant) est EXACTEMENT ce qu'un admin cherche quand
        son intégration « ne marche plus »."""
        _key, raw = ApiKey.issue(
            company=self.co, label='sans-scope', scopes=[])
        resp = _key_client(raw).get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 403)
        entree = ApiCallLog.objects.get()
        self.assertEqual(entree.statut, 403)
        self.assertTrue(entree.est_erreur)

    def test_un_appel_non_authentifie_ne_cree_aucune_ligne(self):
        """Aucune société propriétaire : l'inscrire exigerait d'en inventer une."""
        resp = APIClient().get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(ApiCallLog.objects.count(), 0)

    def test_les_autres_chemins_de_lerp_ne_sont_pas_journalises(self):
        """Le middleware est LÉGER : hors `/api/public/`, il ne fait qu'un test
        de préfixe — aucune écriture, aucune requête SQL ajoutée."""
        APIClient().get('/api/django/publicapi/catalogue/')
        self.assertEqual(ApiCallLog.objects.count(), 0)

    def test_le_chemin_journalise_ne_porte_jamais_le_token_en_clair(self):
        """Pull CSV NTAPI30 : `?token=<clé>` est une clé EN CLAIR. La query
        string ne doit jamais atterrir dans une table lisible depuis l'écran
        Paramètres."""
        _key, raw = ApiKey.issue(
            company=self.co, label='pull', scopes=[SCOPE_READ_LEADS])
        resp = APIClient().get(
            f'/api/public/v1/exports/leads.csv?token={raw}')
        self.assertEqual(resp.status_code, 200, resp.content)
        entree = ApiCallLog.objects.get()
        self.assertEqual(entree.chemin, '/api/public/v1/exports/leads.csv')
        self.assertNotIn('token', entree.chemin)
        self.assertNotIn(raw, entree.chemin)

    def test_une_entree_est_creee_par_appel(self):
        api = _key_client(self.raw)
        for _ in range(3):
            api.get('/api/public/v1/leads/')
        self.assertEqual(ApiCallLog.objects.count(), 3)


class Ntapi38RetentionTests(TestCase):
    """Second volet : la purge suit la rétention DU PLAN, société par société."""

    def setUp(self):
        self.maintenant = timezone.now()
        self.co_plan = _company('ntapi38-plan', 'NTAPI38 plan')
        self.co_sans = _company('ntapi38-sans', 'NTAPI38 sans plan')
        ApiUsagePlan.objects.create(
            company=self.co_plan, retention_livraisons_jours=7)

    def _appel(self, company, *, il_y_a_jours):
        entree = call_log.enregistrer(
            company_id=company.id, methode='GET', chemin='/api/public/v1/leads/',
            statut=200, latence_ms=12, request_id='abc', taille_payload=100)
        ApiCallLog.objects.filter(pk=entree.pk).update(
            created_at=self.maintenant - timedelta(days=il_y_a_jours))
        return entree

    def test_la_purge_respecte_la_retention_du_plan(self):
        vieux = self._appel(self.co_plan, il_y_a_jours=10)
        recent = self._appel(self.co_plan, il_y_a_jours=2)
        supprimes = call_log.purger_appels(self.maintenant, apply_=True)
        self.assertEqual(supprimes, 1)
        self.assertFalse(ApiCallLog.objects.filter(pk=vieux.pk).exists())
        self.assertTrue(ApiCallLog.objects.filter(pk=recent.pk).exists())

    def test_dry_run_compte_sans_supprimer(self):
        self._appel(self.co_plan, il_y_a_jours=30)
        self.assertEqual(call_log.purger_appels(self.maintenant, apply_=False), 1)
        self.assertEqual(ApiCallLog.objects.count(), 1)

    def test_une_societe_sans_plan_nest_jamais_purgee_par_defaut(self):
        """Défaut 0 = OFF : on ne supprime pas la trace d'une société qui n'a
        jamais choisi de plafond."""
        self._appel(self.co_sans, il_y_a_jours=400)
        self.assertEqual(call_log.purger_appels(self.maintenant, apply_=True), 0)
        self.assertEqual(ApiCallLog.objects.count(), 1)

    @override_settings(API_CALL_LOG_RETENTION_DAYS=30)
    def test_le_defaut_de_reglage_sapplique_aux_societes_sans_plan(self):
        vieux = self._appel(self.co_sans, il_y_a_jours=40)
        self._appel(self.co_sans, il_y_a_jours=10)
        self.assertEqual(call_log.purger_appels(self.maintenant, apply_=True), 1)
        self.assertFalse(ApiCallLog.objects.filter(pk=vieux.pk).exists())

    @override_settings(API_CALL_LOG_RETENTION_DAYS=30)
    def test_le_plan_dune_societe_prime_sur_le_reglage_global(self):
        vieux = self._appel(self.co_plan, il_y_a_jours=10)  # > 7 j du plan
        call_log.purger_appels(self.maintenant, apply_=True)
        self.assertFalse(ApiCallLog.objects.filter(pk=vieux.pk).exists())

    def test_la_politique_est_enregistree_au_registre_de_retention(self):
        from core.retention import list_retention_policies

        self.assertIn('publicapi_api_call_log_retention',
                      list_retention_policies())


class Ntapi38EnregistrementTests(TestCase):
    """L'écriture est BEST-EFFORT : jamais une exception qui casse la requête."""

    def test_sans_societe_rien_nest_ecrit(self):
        self.assertIsNone(call_log.enregistrer(company_id=None, statut=200))
        self.assertEqual(ApiCallLog.objects.count(), 0)

    def test_un_chemin_trop_long_est_tronque_pas_une_dataerror(self):
        co = _company('ntapi38-trunc', 'NTAPI38 trunc')
        entree = call_log.enregistrer(
            company_id=co.id, methode='GET', chemin='/x' * 600, statut=200)
        self.assertIsNotNone(entree)
        self.assertEqual(len(entree.chemin), call_log.MAX_CHEMIN)

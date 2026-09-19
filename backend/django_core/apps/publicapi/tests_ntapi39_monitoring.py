"""NTAPI39 — tableau de bord de monitoring des intégrations (admin tenant).

Critère d'acceptation : « l'admin voit son taux d'erreur et sa latence p95 sur
7 j, tout scopé société ». Les deux moitiés sont vérifiées — les CHIFFRES (sur
des latences choisies pour que p50 et p95 soient calculables à la main) ET
l'isolation (les appels, livraisons et jobs d'une autre société n'entrent jamais
dans le tableau de bord).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from . import monitoring
from .models import ApiCallLog, ApiKey, BulkJob, Webhook, WebhookDelivery

User = get_user_model()

URL = '/api/django/publicapi/monitoring/'


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _admin(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy='admin')


def _session_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntapi39MonitoringTests(TestCase):
    def setUp(self):
        self.maintenant = timezone.now()
        self.co = _company('ntapi39', 'NTAPI39')
        self.autre = _company('ntapi39-autre', 'NTAPI39 autre')
        self.admin = _admin(self.co, 'admin-ntapi39')
        self.cle, _raw = ApiKey.issue(
            company=self.co, label='mon', scopes=[])

    def _appel(self, company, *, statut=200, latence=10, chemin='/api/public/v1/leads/',
               il_y_a_jours=0):
        entree = ApiCallLog.objects.create(
            company=company, api_key=None, methode='GET', chemin=chemin,
            statut=statut, latence_ms=latence, request_id='r',
            taille_payload=50)
        if il_y_a_jours:
            ApiCallLog.objects.filter(pk=entree.pk).update(
                created_at=self.maintenant - timedelta(days=il_y_a_jours))
        return entree

    # ── Le cœur du critère : taux d'erreur + p95 sur 7 j ──────────────────
    def test_taux_derreur_et_percentiles_sur_sept_jours(self):
        # 20 appels, latences 10..200 par pas de 10 ; 2 erreurs (4xx + 5xx).
        for i in range(1, 21):
            statut = 200
            if i == 19:
                statut = 404
            elif i == 20:
                statut = 500
            self._appel(self.co, statut=statut, latence=i * 10)

        agregat = monitoring.tableau_de_bord(
            self.co, jours=7, maintenant=self.maintenant)
        appels = agregat['appels']
        self.assertEqual(agregat['fenetre_jours'], 7)
        self.assertEqual(appels['total'], 20)
        self.assertEqual(appels['erreurs'], 2)
        self.assertEqual(appels['erreurs_4xx'], 1)
        self.assertEqual(appels['erreurs_5xx'], 1)
        self.assertEqual(appels['taux_erreur_pct'], 10.0)
        # Rang « nearest-rank » sur n-1 : p50 → rang 10 (110 ms),
        # p95 → rang 18 (190 ms). Calculable à la main, donc vérifiable.
        self.assertEqual(appels['latence_p50_ms'], 110)
        self.assertEqual(appels['latence_p95_ms'], 190)
        self.assertEqual(appels['latence_moyenne_ms'], 105)

    def test_un_seul_appel_donne_sa_propre_latence_en_p50_et_p95(self):
        self._appel(self.co, latence=42)
        appels = monitoring.appels(
            self.co, depuis=self.maintenant - timedelta(days=7))
        self.assertEqual(appels['latence_p50_ms'], 42)
        self.assertEqual(appels['latence_p95_ms'], 42)

    def test_aucun_appel_ne_fabrique_aucun_chiffre(self):
        """Zéro appel → percentiles à `None`, jamais un 0 qui se lirait
        « réponses instantanées »."""
        appels = monitoring.appels(
            self.co, depuis=self.maintenant - timedelta(days=7))
        self.assertEqual(appels['total'], 0)
        self.assertEqual(appels['taux_erreur_pct'], 0.0)
        self.assertIsNone(appels['latence_p50_ms'])
        self.assertIsNone(appels['latence_p95_ms'])
        self.assertIsNone(appels['latence_moyenne_ms'])

    def test_la_fenetre_exclut_les_appels_plus_anciens(self):
        self._appel(self.co, latence=10, il_y_a_jours=0)
        self._appel(self.co, latence=999, il_y_a_jours=30)
        appels = monitoring.tableau_de_bord(
            self.co, jours=7, maintenant=self.maintenant)['appels']
        self.assertEqual(appels['total'], 1)
        self.assertEqual(appels['latence_p95_ms'], 10)

    # ── Isolation société ────────────────────────────────────────────────
    def test_les_appels_dune_autre_societe_nentrent_jamais(self):
        self._appel(self.co, latence=10)
        for _ in range(50):
            self._appel(self.autre, statut=500, latence=900)
        appels = monitoring.tableau_de_bord(
            self.co, jours=7, maintenant=self.maintenant)['appels']
        self.assertEqual(appels['total'], 1)
        self.assertEqual(appels['erreurs'], 0)

    # ── Top endpoints ────────────────────────────────────────────────────
    def test_top_endpoints_porte_son_propre_taux_derreur(self):
        for _ in range(5):
            self._appel(self.co, chemin='/api/public/v1/leads/')
        self._appel(self.co, chemin='/api/public/v1/devis/', statut=403)
        top = monitoring.tableau_de_bord(
            self.co, jours=7, maintenant=self.maintenant)['top_endpoints']
        self.assertEqual(top[0]['chemin'], '/api/public/v1/leads/')
        self.assertEqual(top[0]['appels'], 5)
        self.assertEqual(top[0]['taux_erreur_pct'], 0.0)
        casse = [ligne for ligne in top
                 if ligne['chemin'] == '/api/public/v1/devis/'][0]
        self.assertEqual(casse['taux_erreur_pct'], 100.0)

    # ── Santé webhooks ───────────────────────────────────────────────────
    def test_sante_webhooks_distingue_echec_et_echec_definitif(self):
        webhook = Webhook.objects.create(
            company=self.co, target_url='https://exemple.test/hook',
            secret=Webhook.generate_secret(), events=[])
        Webhook.objects.create(
            company=self.co, target_url='https://exemple.test/mort',
            secret=Webhook.generate_secret(), events=[], enabled=False)
        for statut in (WebhookDelivery.Statut.SUCCESS,
                       WebhookDelivery.Statut.SUCCESS,
                       WebhookDelivery.Statut.FAILED,
                       WebhookDelivery.Statut.EN_ECHEC):
            WebhookDelivery.objects.create(
                company=self.co, webhook=webhook, event='lead.created',
                status=statut)
        sante = monitoring.tableau_de_bord(
            self.co, jours=7, maintenant=self.maintenant)['webhooks']
        self.assertEqual(sante['livraisons_24h'], 4)
        self.assertEqual(sante['succes_24h'], 2)
        self.assertEqual(sante['echecs_24h'], 1)
        self.assertEqual(sante['echecs_definitifs_24h'], 1)
        self.assertEqual(sante['taux_echec_pct'], 50.0)
        self.assertEqual(sante['webhooks_actifs'], 1)
        self.assertEqual(sante['webhooks_desactives'], 1)

    def test_la_sante_webhooks_est_bornee_a_24h(self):
        webhook = Webhook.objects.create(
            company=self.co, target_url='https://exemple.test/hook',
            secret=Webhook.generate_secret(), events=[])
        vieille = WebhookDelivery.objects.create(
            company=self.co, webhook=webhook, event='lead.created',
            status=WebhookDelivery.Statut.FAILED)
        WebhookDelivery.objects.filter(pk=vieille.pk).update(
            created_at=self.maintenant - timedelta(days=3))
        sante = monitoring.tableau_de_bord(
            self.co, jours=7, maintenant=self.maintenant)['webhooks']
        self.assertEqual(sante['livraisons_24h'], 0)
        self.assertEqual(sante['taux_echec_pct'], 0.0)

    # ── Jobs bulk ────────────────────────────────────────────────────────
    def test_les_jobs_en_cours_sont_visibles_hors_fenetre(self):
        """Un import lancé il y a dix jours et toujours `en_cours` est
        exactement ce qu'un admin doit voir — la fenêtre ne le cache pas."""
        job = BulkJob.objects.create(
            company=self.co, api_key=self.cle, type=BulkJob.TYPE_IMPORT,
            entite='leads', statut=BulkJob.STATUT_EN_COURS, total=100,
            traites=30)
        BulkJob.objects.filter(pk=job.pk).update(
            created_at=self.maintenant - timedelta(days=10))
        BulkJob.objects.create(
            company=self.co, api_key=self.cle, type=BulkJob.TYPE_EXPORT,
            entite='devis', statut=BulkJob.STATUT_ECHEC)
        BulkJob.objects.create(
            company=self.autre, api_key=None, type=BulkJob.TYPE_EXPORT,
            entite='devis', statut=BulkJob.STATUT_ECHEC)
        jobs = monitoring.tableau_de_bord(
            self.co, jours=7, maintenant=self.maintenant)['jobs']
        self.assertEqual(jobs['en_cours'], 1)
        self.assertEqual(jobs['en_echec'], 1)
        self.assertEqual(len(jobs['derniers']), 2)
        ancien = [lig for lig in jobs['derniers'] if lig['id'] == job.pk][0]
        self.assertEqual(ancien['progression_pct'], 30)


class Ntapi39EndpointTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi39-ep', 'NTAPI39 endpoint')
        self.autre = _company('ntapi39-ep-autre', 'NTAPI39 endpoint autre')
        self.admin = _admin(self.co, 'admin-ntapi39-ep')

    def test_ladmin_recoit_son_tableau_de_bord(self):
        ApiCallLog.objects.create(
            company=self.co, methode='GET', chemin='/api/public/v1/leads/',
            statut=500, latence_ms=250, request_id='r', taille_payload=10)
        resp = _session_client(self.admin).get(URL)
        self.assertEqual(resp.status_code, 200, resp.content)
        corps = resp.json()
        self.assertEqual(corps['fenetre_jours'], 7)
        self.assertEqual(corps['appels']['total'], 1)
        self.assertEqual(corps['appels']['taux_erreur_pct'], 100.0)
        self.assertEqual(corps['appels']['latence_p95_ms'], 250)
        for cle in ('top_endpoints', 'webhooks', 'jobs'):
            self.assertIn(cle, corps)

    def test_le_tableau_de_bord_est_scope_a_la_societe_connectee(self):
        ApiCallLog.objects.create(
            company=self.autre, methode='GET', chemin='/api/public/v1/leads/',
            statut=500, latence_ms=900, request_id='r', taille_payload=10)
        corps = _session_client(self.admin).get(URL).json()
        self.assertEqual(corps['appels']['total'], 0)

    def test_la_fenetre_est_parametrable(self):
        corps = _session_client(self.admin).get(URL, {'jours': 30}).json()
        self.assertEqual(corps['fenetre_jours'], 30)

    def test_une_fenetre_non_numerique_est_un_400(self):
        resp = _session_client(self.admin).get(URL, {'jours': 'sept'})
        self.assertEqual(resp.status_code, 400)

    def test_une_fenetre_hors_bornes_est_un_400(self):
        self.assertEqual(
            _session_client(self.admin).get(URL, {'jours': 0}).status_code, 400)
        self.assertEqual(
            _session_client(self.admin).get(URL, {'jours': 9999}).status_code,
            400)

    def test_reserve_au_palier_admin(self):
        limite = User.objects.create_user(
            username='limite-ntapi39', password='x', company=self.co,
            role_legacy='normal')
        self.assertEqual(
            _session_client(limite).get(URL).status_code, 403)

    def test_anonyme_refuse(self):
        self.assertIn(APIClient().get(URL).status_code, (401, 403))

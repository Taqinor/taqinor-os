"""NTOBS27 — API publique lecture seule « Fiabilité » (scope fiabilite:lecture).

Critère de la tâche : une clé portant le scope récupère ses 3 ressources
SCOPÉES À SA SOCIÉTÉ ; une clé sans le scope reçoit 403.

Couvre aussi : le format NTOBS5 rendu tel quel (mêmes clés que l'écran
self-service interne), 400 sur période mal formée, 404 sur période sans
rapport, et l'ISOLATION multi-société du rapport SLA (la clé de la société A ne
voit jamais le SLA de la société B).
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from core.models import BackupRun
from core.sla import SlaSnapshot

from .constants import SCOPE_READ_FIABILITE, SCOPE_READ_LEADS
from .models import ApiKey

URL_SAUVEGARDES = '/api/public/v1/fiabilite/sauvegardes/'
URL_USAGE = '/api/public/v1/fiabilite/usage/'


def url_sla(periode):
    return f'/api/public/v1/fiabilite/sla/{periode}/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    return company


def key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


class FiabilitePubliqueTests(TestCase):
    def setUp(self):
        self.company = make_company('ntobs27-a', 'NTOBS27 A')
        self.autre = make_company('ntobs27-b', 'NTOBS27 B')
        _, self.raw = ApiKey.issue(
            company=self.company, label='fiabilite',
            scopes=[SCOPE_READ_FIABILITE])
        _, self.raw_sans_scope = ApiKey.issue(
            company=self.company, label='sans-scope',
            scopes=[SCOPE_READ_LEADS])

    # ── Sauvegardes (NTOBS5) ────────────────────────────────────────────────
    def test_sauvegardes_rend_le_format_ntobs5(self):
        resp = key_client(self.raw).get(URL_SAUVEGARDES)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            set(resp.data.keys()),
            {'derniere_sauvegarde', 'dernier_drill', 'rpo_planifie',
             'rto_annonce_heures'})

    def test_sauvegardes_sans_run_rend_null_jamais_un_faux_defaut(self):
        resp = key_client(self.raw).get(URL_SAUVEGARDES)
        self.assertIsNone(resp.data['derniere_sauvegarde'])
        self.assertIsNone(resp.data['dernier_drill'])

    def test_sauvegardes_expose_date_et_statut_uniquement(self):
        BackupRun.objects.create(
            company=self.company, kind=BackupRun.KIND_EXPORT,
            statut=BackupRun.STATUT_TERMINE,
            object_key='erp-backups/interne.dump', bytes_taille=4242,
            manifest={'datasets': ['leads'], 'lignes': 12})
        resp = key_client(self.raw).get(URL_SAUVEGARDES)
        resume = resp.data['derniere_sauvegarde']
        self.assertIsNotNone(resume)
        # Date + statut UNIQUEMENT : l'ensemble de clés exact prouve déjà
        # qu'aucun interne d'infrastructure (clé d'objet, taille, manifeste)
        # ne peut fuir.
        self.assertEqual(set(resume.keys()), {'date', 'statut'})
        self.assertNotIn('erp-backups', str(resp.data))
        self.assertNotIn('datasets', str(resp.data))

    # ── SLA (NTOBS3) ────────────────────────────────────────────────────────
    def test_sla_rend_le_rapport_du_mois(self):
        SlaSnapshot.objects.create(
            company=self.company, periode=date(2026, 8, 1),
            uptime_pct=Decimal('99.9500'), latence_p95_ms=180)
        resp = key_client(self.raw).get(url_sla('2026-08'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['periode'], '2026-08-01')
        self.assertEqual(str(resp.data['uptime_pct']), '99.9500')
        self.assertEqual(resp.data['latence_p95_ms'], 180)

    def test_sla_latence_non_mesuree_reste_null(self):
        SlaSnapshot.objects.create(
            company=self.company, periode=date(2026, 7, 1),
            uptime_pct=Decimal('100.0000'))
        resp = key_client(self.raw).get(url_sla('2026-07'))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['latence_p95_ms'])

    def test_sla_periode_invalide_400(self):
        resp = key_client(self.raw).get(url_sla('aout-2026'))
        self.assertEqual(resp.status_code, 400)

    def test_sla_mois_hors_bornes_400(self):
        resp = key_client(self.raw).get(url_sla('2026-13'))
        self.assertEqual(resp.status_code, 400)

    def test_sla_periode_sans_rapport_404(self):
        resp = key_client(self.raw).get(url_sla('2026-01'))
        self.assertEqual(resp.status_code, 404)

    def test_sla_scope_a_la_societe_de_la_cle(self):
        SlaSnapshot.objects.create(
            company=self.autre, periode=date(2026, 8, 1),
            uptime_pct=Decimal('90.0000'))
        resp = key_client(self.raw).get(url_sla('2026-08'))
        self.assertEqual(resp.status_code, 404)

    # ── Usage (NTOBS8) ──────────────────────────────────────────────────────
    def test_usage_rend_ressources_et_horodatage(self):
        resp = key_client(self.raw).get(URL_USAGE)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('ressources', resp.data)
        self.assertIn('genere_le', resp.data)
        self.assertIsInstance(resp.data['ressources'], list)

    # ── Contrôle d'accès ────────────────────────────────────────────────────
    def test_cle_sans_le_scope_403_sur_les_trois(self):
        api = key_client(self.raw_sans_scope)
        for url in (URL_SAUVEGARDES, url_sla('2026-08'), URL_USAGE):
            self.assertEqual(api.get(url).status_code, 403, url)

    def test_cle_invalide_401(self):
        api = key_client('tqk_does_not_exist')
        for url in (URL_SAUVEGARDES, url_sla('2026-08'), URL_USAGE):
            self.assertEqual(api.get(url).status_code, 401, url)

    def test_sans_cle_401_ou_403(self):
        api = APIClient()
        for url in (URL_SAUVEGARDES, url_sla('2026-08'), URL_USAGE):
            self.assertIn(api.get(url).status_code, (401, 403), url)

    def test_scope_declare_au_catalogue(self):
        from .constants import ALL_SCOPES
        self.assertIn(SCOPE_READ_FIABILITE, ALL_SCOPES)

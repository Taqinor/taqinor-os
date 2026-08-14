"""NTMFG29 — Écran de paramètres MRP par société (`ParametresMRP`).

Critère : chaque société a ses propres réglages isolés, changer
`horizon_mrp_jours` modifie effectivement la fenêtre du calcul NTMFG5 sur un
test, cross-tenant refusé."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import ParametresMRP
from apps.mrp.services import parametres_mrp
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ParametresMrpServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ntmfg29-1', 'MRP NTMFG29 1')

    def test_lazy_create_valeurs_par_defaut(self):
        self.assertEqual(ParametresMRP.objects.filter(company=self.company).count(), 0)
        obj = parametres_mrp(self.company)
        self.assertEqual(obj.horizon_mrp_jours, 30)
        self.assertEqual(obj.stock_securite_pct_defaut, 0)
        self.assertTrue(obj.blocage_qc_force_motif_obligatoire)
        self.assertFalse(obj.activer_kanban_production)
        self.assertEqual(ParametresMRP.objects.filter(company=self.company).count(), 1)

    def test_lazy_create_idempotent(self):
        first = parametres_mrp(self.company)
        second = parametres_mrp(self.company)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ParametresMRP.objects.filter(company=self.company).count(), 1)

    def test_isolation_par_societe(self):
        autre = make_company('mrp-ntmfg29-2', 'MRP NTMFG29 2')
        mine = parametres_mrp(self.company)
        mine.horizon_mrp_jours = 7
        mine.save(update_fields=['horizon_mrp_jours'])
        theirs = parametres_mrp(autre)
        self.assertEqual(theirs.horizon_mrp_jours, 30)  # défaut inchangé.


class ParametresMrpApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ntmfg29-api-1', 'MRP NTMFG29 API 1')
        self.admin = make_user(self.company, 'mrp-ntmfg29-admin', role='admin')
        self.responsable = make_user(self.company, 'mrp-ntmfg29-resp', role='responsable')
        self.technicien = make_user(self.company, 'mrp-ntmfg29-tech', role='normal')

    def test_technicien_refuse_lecture(self):
        resp = auth(self.technicien).get('/api/django/mrp/parametres/')
        self.assertEqual(resp.status_code, 403)

    def test_responsable_refuse_lecture_et_ecriture(self):
        # Un Responsable peut planifier (NTMFG3) mais pas voir/modifier les
        # paramètres société — Admin uniquement.
        resp = auth(self.responsable).get('/api/django/mrp/parametres/')
        self.assertEqual(resp.status_code, 403)
        resp = auth(self.responsable).put(
            '/api/django/mrp/parametres/update/',
            {'horizon_mrp_jours': 10}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_admin_lecture_et_ecriture(self):
        resp = auth(self.admin).get('/api/django/mrp/parametres/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['horizon_mrp_jours'], 30)

        resp = auth(self.admin).put(
            '/api/django/mrp/parametres/update/',
            {'horizon_mrp_jours': 10}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['horizon_mrp_jours'], 10)

        obj = parametres_mrp(self.company)
        self.assertEqual(obj.horizon_mrp_jours, 10)

    def test_cross_tenant_refuse(self):
        autre_company = make_company('mrp-ntmfg29-api-2', 'MRP NTMFG29 API 2')
        autre_admin = make_user(autre_company, 'mrp-ntmfg29-autre-admin', role='admin')
        parametres_mrp(self.company).horizon_mrp_jours
        resp = auth(autre_admin).get('/api/django/mrp/parametres/')
        self.assertEqual(resp.status_code, 200)
        # La société de `autre_admin` a ses PROPRES paramètres (défaut), jamais
        # ceux de `self.company` — server-side scoping, aucun paramètre id/URL.
        self.assertEqual(resp.data['horizon_mrp_jours'], 30)


class ParametresMrpHorizonMrpRunTests(TestCase):
    """`horizon_mrp_jours` alimente la fenêtre du calcul NTMFG5 quand
    l'appelant ne fournit pas `horizon_jours` explicitement."""

    def setUp(self):
        self.company = make_company('mrp-ntmfg29-run-1', 'MRP NTMFG29 RUN 1')
        self.admin = make_user(self.company, 'mrp-ntmfg29-run-admin', role='admin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Produit rupture', prix_vente=0, tva=20,
            quantite_stock=0)

    def test_horizon_mrp_jours_pilote_date_besoin(self):
        today = timezone.localdate()
        api = auth(self.admin)

        resp = api.post('/api/django/mrp/mrp-run/', {
            'demande_independante': {str(self.produit.id): 5},
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne = next(r for r in resp.data if r['produit_id'] == self.produit.id)
        self.assertEqual(ligne['date_besoin'], (today + timedelta(days=30)).isoformat())

        api.put('/api/django/mrp/parametres/update/',
                {'horizon_mrp_jours': 7}, format='json')

        resp = api.post('/api/django/mrp/mrp-run/', {
            'demande_independante': {str(self.produit.id): 5},
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne = next(r for r in resp.data if r['produit_id'] == self.produit.id)
        self.assertEqual(ligne['date_besoin'], (today + timedelta(days=7)).isoformat())

    def test_horizon_jours_explicite_prime_sur_les_parametres(self):
        api = auth(self.admin)
        today = timezone.localdate()
        resp = api.post('/api/django/mrp/mrp-run/', {
            'demande_independante': {str(self.produit.id): 5},
            'horizon_jours': 3,
        }, format='json')
        ligne = next(r for r in resp.data if r['produit_id'] == self.produit.id)
        self.assertEqual(ligne['date_besoin'], (today + timedelta(days=3)).isoformat())

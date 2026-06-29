"""Tests du tableau de bord litiges (LITIGE6).

Couvre le sélecteur ``selectors.tableau_bord_litiges`` et l'endpoint
``reclamations/tableau-bord/`` :
  - comptage par statut (ouvertes / en_traitement / résolues / rejetées) ;
  - total du montant contesté ;
  - délai de résolution moyen (à partir des logs chatter → 'resolue') ;
  - garde anti-division par zéro (aucune résolue → délai None) ;
  - fenêtre de dates (debut / fin inclusives) ;
  - isolation multi-société ;
  - endpoint 200 pour un rôle lecture, 403 pour un rôle limité,
    et paramètre d'export DRF ``?export=`` qui ne casse pas la réponse.
"""
import datetime as _dt
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.litiges import selectors
from apps.litiges.models import Reclamation, ReclamationActivity

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _set_creation(reclamation, when):
    """Force ``date_creation`` (auto_now_add) via un UPDATE direct."""
    Reclamation.objects.filter(pk=reclamation.pk).update(date_creation=when)
    reclamation.refresh_from_db()
    return reclamation


def _log_resolue(reclamation, company, when):
    """Crée un log chatter 'resolue' avec un horodatage forcé."""
    act = ReclamationActivity.objects.create(
        company=company,
        reclamation=reclamation,
        type=ReclamationActivity.Kind.LOG,
        old_value=Reclamation.Statut.EN_TRAITEMENT,
        new_value=Reclamation.Statut.RESOLUE,
    )
    ReclamationActivity.objects.filter(pk=act.pk).update(date_creation=when)
    return act


class TableauBordSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company('litiges-tb-a', 'A')
        self.co_b = make_company('litiges-tb-b', 'B')

    def _make(self, company, **kw):
        defaults = {'objet': 'Litige'}
        defaults.update(kw)
        return Reclamation.objects.create(company=company, **defaults)

    # ── Comptage par statut ──────────────────────────────────────────────────
    def test_counts_by_statut(self):
        self._make(self.co_a, statut=Reclamation.Statut.OUVERTE)
        self._make(self.co_a, statut=Reclamation.Statut.OUVERTE)
        self._make(self.co_a, statut=Reclamation.Statut.EN_TRAITEMENT)
        self._make(self.co_a, statut=Reclamation.Statut.RESOLUE)
        self._make(self.co_a, statut=Reclamation.Statut.REJETEE)

        tb = selectors.tableau_bord_litiges(self.co_a)
        self.assertEqual(tb['ouvertes'], 2)
        self.assertEqual(tb['en_traitement'], 1)
        self.assertEqual(tb['resolues'], 1)
        self.assertEqual(tb['rejetees'], 1)
        self.assertEqual(tb['total'], 5)

    def test_empty_company_all_zero_no_crash(self):
        tb = selectors.tableau_bord_litiges(self.co_a)
        self.assertEqual(tb['total'], 0)
        self.assertEqual(tb['ouvertes'], 0)
        self.assertEqual(tb['montant_conteste_total'], '0')
        self.assertIsNone(tb['delai_resolution_moyen_jours'])
        self.assertEqual(tb['nb_resolues_avec_delai'], 0)

    # ── Montant contesté ─────────────────────────────────────────────────────
    def test_montant_conteste_total(self):
        self._make(self.co_a, montant_conteste=Decimal('1000.50'))
        self._make(self.co_a, montant_conteste=Decimal('250.25'))
        self._make(self.co_a, montant_conteste=Decimal('0'))
        tb = selectors.tableau_bord_litiges(self.co_a)
        self.assertEqual(Decimal(tb['montant_conteste_total']),
                         Decimal('1250.75'))

    # ── Délai de résolution moyen ────────────────────────────────────────────
    def test_avg_resolution_delay(self):
        now = timezone.now()
        # Réclamation A : créée il y a 4 j, résolue il y a 2 j → délai 2 j.
        r1 = self._make(self.co_a, statut=Reclamation.Statut.RESOLUE)
        _set_creation(r1, now - _dt.timedelta(days=4))
        _log_resolue(r1, self.co_a, now - _dt.timedelta(days=2))
        # Réclamation B : créée il y a 6 j, résolue il y a 2 j → délai 4 j.
        r2 = self._make(self.co_a, statut=Reclamation.Statut.RESOLUE)
        _set_creation(r2, now - _dt.timedelta(days=6))
        _log_resolue(r2, self.co_a, now - _dt.timedelta(days=2))

        tb = selectors.tableau_bord_litiges(self.co_a)
        self.assertEqual(tb['nb_resolues_avec_delai'], 2)
        # Moyenne (2 j + 4 j) / 2 = 3 j.
        self.assertAlmostEqual(tb['delai_resolution_moyen_jours'], 3.0,
                               places=1)
        self.assertAlmostEqual(tb['delai_resolution_moyen_heures'], 72.0,
                               places=0)

    def test_no_resolved_delay_is_none_not_crash(self):
        # Que des ouvertes : aucune résolue → moyenne None (pas de /0).
        self._make(self.co_a, statut=Reclamation.Statut.OUVERTE)
        self._make(self.co_a, statut=Reclamation.Statut.OUVERTE)
        tb = selectors.tableau_bord_litiges(self.co_a)
        self.assertIsNone(tb['delai_resolution_moyen_jours'])
        self.assertIsNone(tb['delai_resolution_moyen_heures'])
        self.assertEqual(tb['nb_resolues_avec_delai'], 0)

    def test_resolved_without_log_excluded_from_delay(self):
        # Résolue mais SANS log 'resolue' exploitable → exclue de la moyenne,
        # comptée dans 'resolues'. Pas de crash, moyenne None.
        self._make(self.co_a, statut=Reclamation.Statut.RESOLUE)
        tb = selectors.tableau_bord_litiges(self.co_a)
        self.assertEqual(tb['resolues'], 1)
        self.assertEqual(tb['nb_resolues_avec_delai'], 0)
        self.assertIsNone(tb['delai_resolution_moyen_jours'])

    # ── Fenêtre de dates ─────────────────────────────────────────────────────
    def test_date_window_filters(self):
        now = timezone.now()
        old = self._make(self.co_a, statut=Reclamation.Statut.OUVERTE)
        _set_creation(old, now - _dt.timedelta(days=30))
        recent = self._make(self.co_a, statut=Reclamation.Statut.OUVERTE)
        _set_creation(recent, now - _dt.timedelta(days=1))

        debut = (now - _dt.timedelta(days=7)).date().isoformat()
        tb = selectors.tableau_bord_litiges(self.co_a, debut=debut)
        # Seule la récente entre dans la fenêtre.
        self.assertEqual(tb['total'], 1)
        self.assertEqual(tb['debut'], debut)

    def test_date_window_fin_inclusive(self):
        now = timezone.now()
        r = self._make(self.co_a, statut=Reclamation.Statut.OUVERTE)
        target = now - _dt.timedelta(days=2)
        _set_creation(r, target)
        # fin == jour de création → inclus (borne haute inclusive).
        fin = target.date().isoformat()
        tb = selectors.tableau_bord_litiges(self.co_a, fin=fin)
        self.assertEqual(tb['total'], 1)
        # fin la veille → exclu.
        fin_avant = (target - _dt.timedelta(days=1)).date().isoformat()
        tb2 = selectors.tableau_bord_litiges(self.co_a, fin=fin_avant)
        self.assertEqual(tb2['total'], 0)

    def test_invalid_date_string_ignored(self):
        self._make(self.co_a, statut=Reclamation.Statut.OUVERTE)
        # Chaîne invalide → borne ignorée (parse_date renvoie None).
        tb = selectors.tableau_bord_litiges(self.co_a, debut='pas-une-date')
        self.assertEqual(tb['total'], 1)
        self.assertIsNone(tb['debut'])

    # ── Isolation multi-société ──────────────────────────────────────────────
    def test_scoping_per_company(self):
        self._make(self.co_a, statut=Reclamation.Statut.OUVERTE)
        self._make(self.co_b, statut=Reclamation.Statut.OUVERTE)
        self._make(self.co_b, statut=Reclamation.Statut.OUVERTE)
        tb_a = selectors.tableau_bord_litiges(self.co_a)
        tb_b = selectors.tableau_bord_litiges(self.co_b)
        self.assertEqual(tb_a['total'], 1)
        self.assertEqual(tb_b['total'], 2)


class TableauBordEndpointTests(TestCase):
    BASE = '/api/django/litiges/reclamations/tableau-bord/'

    def setUp(self):
        self.co_a = make_company('litiges-tbe-a', 'A')
        self.co_b = make_company('litiges-tbe-b', 'B')
        self.user_a = make_user(self.co_a, 'litiges-tbe-a')

    def _make(self, company, **kw):
        defaults = {'objet': 'Litige'}
        defaults.update(kw)
        return Reclamation.objects.create(company=company, **defaults)

    def test_endpoint_200_read_role(self):
        self._make(self.co_a, statut=Reclamation.Statut.OUVERTE)
        self._make(self.co_a, statut=Reclamation.Statut.RESOLUE)
        resp = auth(self.user_a).get(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['ouvertes'], 1)
        self.assertEqual(resp.data['resolues'], 1)
        self.assertIn('montant_conteste_total', resp.data)
        self.assertIn('delai_resolution_moyen_jours', resp.data)

    def test_endpoint_scoped_to_company(self):
        self._make(self.co_b, statut=Reclamation.Statut.OUVERTE)
        resp = auth(self.user_a).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total'], 0)

    def test_endpoint_date_params(self):
        now = timezone.now()
        old = self._make(self.co_a, statut=Reclamation.Statut.OUVERTE)
        _set_creation(old, now - _dt.timedelta(days=30))
        self._make(self.co_a, statut=Reclamation.Statut.OUVERTE)
        debut = (now - _dt.timedelta(days=7)).date().isoformat()
        resp = auth(self.user_a).get(self.BASE, {'debut': debut})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total'], 1)

    def test_endpoint_export_param_does_not_break(self):
        # ``?export=`` (et non ``?format=`` qui force un suffixe DRF → 404).
        self._make(self.co_a, statut=Reclamation.Statut.OUVERTE)
        resp = auth(self.user_a).get(self.BASE, {'export': 'csv'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['ouvertes'], 1)

    def test_endpoint_role_normal_refused(self):
        normal = make_user(self.co_a, 'litiges-tbe-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)

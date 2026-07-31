"""NTAI36 — Tests du brouillon de rapport d'activité périodique.

Le test central est celui du GARDE-FOU : les chiffres viennent du serveur, et
un narratif qui en invente un est REFUSÉ (jamais rendu à l'utilisateur).
"""
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.ai import AIResult, LLMProvider, register_provider
from core.ai import registry

from ..services import (RAPPORT_MODULES, build_rapport_prompt,
                        metriques_periode, nombres_hors_source)

User = get_user_model()

URL = '/api/django/ai/rapport-periode/'
PERIODE = '2026-03'


class FakeRapportLLM(LLMProvider):
    """Reformule fidèlement : ne cite que des chiffres du prompt."""

    key = 'fake_ntai36_ok'
    last_prompt = None

    def is_configured(self):
        return True

    def complete(self, *, prompt, system='', max_tokens=512):
        FakeRapportLLM.last_prompt = prompt
        return AIResult(
            ok=True, configured=True, provider=self.key,
            data={'text': 'En mars 2026, 2 leads ont été créés, dont 0 signé.'})


class FakeHallucinantLLM(LLMProvider):
    """Invente un chiffre absent des métriques — doit être REFUSÉ."""

    key = 'fake_ntai36_ko'

    def is_configured(self):
        return True

    def complete(self, *, prompt, system='', max_tokens=512):
        return AIResult(
            ok=True, configured=True, provider=self.key,
            data={'text': 'Excellente période : 2 leads créés et 47 chantiers '
                          'réceptionnés, en hausse de 312 % sur un an.'})


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntai36RapportPeriodeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.crm.models import Lead

        cls.company = make_company('ntai36-co', 'NTAI36 Co')
        # Garde CI : la seconde société porte un slug distinct explicite.
        cls.autre = make_company('ntai36-autre', 'NTAI36 Autre')
        cls.user = User.objects.create_user(
            username='ntai36-user', password='x', company=cls.company,
            role_legacy='normal')
        cls.user_autre = User.objects.create_user(
            username='ntai36-autre-user', password='x', company=cls.autre,
            role_legacy='normal')

        dans_periode = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)
        hors_periode = datetime(2026, 5, 15, 10, 0, tzinfo=timezone.utc)
        for nom, quand, societe in (
            ('Lead A', dans_periode, cls.company),
            ('Lead B', dans_periode, cls.company),
            ('Lead hors periode', hors_periode, cls.company),
            ('Lead autre societe', dans_periode, cls.autre),
        ):
            lead = Lead.objects.create(company=societe, nom=nom)
            # `date_creation` est auto_now_add : on la recale par UPDATE.
            Lead.objects.filter(pk=lead.pk).update(date_creation=quand)

    def _with_llm(self, provider_cls):
        register_provider(provider_cls)
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop(provider_cls.key, None))
        return override_settings(AI_PROVIDERS={'llm': provider_cls.key})

    def _post(self, **body):
        payload = {'module': 'commercial', 'periode': PERIODE}
        payload.update(body)
        return auth(self.user).post(URL, payload, format='json')

    # ── Métriques SERVEUR ───────────────────────────────────────────────────
    def test_metriques_calculees_serveur(self):
        metriques = metriques_periode(
            company=self.company, module='commercial', periode=PERIODE)
        par_cle = {m['cle']: m['valeur'] for m in metriques}
        self.assertEqual(par_cle['nb_leads'], 2)
        self.assertEqual(par_cle['nb_signes'], 0)

    def test_metriques_scopees_societe(self):
        metriques = metriques_periode(
            company=self.autre, module='commercial', periode=PERIODE)
        par_cle = {m['cle']: m['valeur'] for m in metriques}
        self.assertEqual(par_cle['nb_leads'], 1)

    def test_module_facturation_disponible(self):
        metriques = metriques_periode(
            company=self.company, module='facturation', periode=PERIODE)
        self.assertIn('nb_factures', {m['cle'] for m in metriques})

    def test_modules_couverts(self):
        self.assertEqual(set(RAPPORT_MODULES), {'commercial', 'facturation'})

    # ── Validation d'entrée ─────────────────────────────────────────────────
    def test_module_inconnu_400(self):
        resp = self._post(module='astrologie')
        self.assertEqual(resp.status_code, 400)

    def test_periode_invalide_400(self):
        with self._with_llm(FakeRapportLLM):
            resp = self._post(periode='mars')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('AAAA-MM', resp.data['detail'])

    def test_sans_cle_llm_degrade_en_503(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 503)

    def test_anonyme_refuse(self):
        resp = APIClient().post(URL, {'module': 'commercial',
                                      'periode': PERIODE}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    # ── Narratif adossé aux vrais chiffres ──────────────────────────────────
    def test_narratif_adosse_aux_chiffres_serveur(self):
        with self._with_llm(FakeRapportLLM):
            resp = self._post()
        self.assertEqual(resp.status_code, 200)
        self.assertIn('2 leads', resp.data['narratif'])
        self.assertFalse(resp.data['envoye'])
        # Les métriques accompagnent le narratif (l'utilisateur peut vérifier).
        par_cle = {m['cle']: m['valeur'] for m in resp.data['metriques']}
        self.assertEqual(par_cle['nb_leads'], '2')
        # Le prompt ne contient QUE les métriques calculées.
        self.assertIn('Leads créés : 2', FakeRapportLLM.last_prompt or '')

    # ── GARDE « aucun nombre inventé » (le test qui compte) ─────────────────
    def test_narratif_qui_invente_un_chiffre_est_refuse(self):
        with self._with_llm(FakeHallucinantLLM):
            resp = self._post()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('47', resp.data['detail'])
        # Le narratif inventé n'est JAMAIS rendu à l'utilisateur.
        self.assertNotIn('narratif', resp.data)

    def test_detecteur_de_nombres_hors_source(self):
        self.assertEqual(nombres_hors_source('12 leads et 3 devis', [12, 3]), [])
        self.assertEqual(
            nombres_hors_source('12 leads et 999 devis', [12, 3]), ['999'])
        # Séparateur de milliers et virgule décimale FR reconnus.
        self.assertEqual(
            nombres_hors_source('CA de 1 234,50 MAD', ['1234.50']), [])
        # Un arrondi raisonnable d'une vraie métrique reste accepté.
        self.assertEqual(nombres_hors_source('environ 1234 MAD', ['1234.56']),
                         [])

    def test_prompt_ne_contient_que_les_metriques(self):
        metriques = metriques_periode(
            company=self.company, module='commercial', periode=PERIODE)
        prompt = build_rapport_prompt('commercial', PERIODE, metriques)
        self.assertIn('2026-03', prompt)
        self.assertIn('Leads créés', prompt)

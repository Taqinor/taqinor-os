"""NTAI35 — Tests de l'assistant de configuration (« Setup Copilot »).

Le test central : AUCUN LIEN INVENTÉ — chaque lien profond de l'index doit
exister dans le routeur RÉEL de la SPA (`module.config.jsx`). Couvre aussi le
repli FAQ sans clé LLM, le filtrage par rôle et l'absence totale d'écriture.
"""
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.ai import AIResult, LLMProvider, register_provider
from core.ai import registry

from ..config_index import CONFIG_ENTRIES, rechercher_ecrans
from ..services import assistant_config

User = get_user_model()

URL = '/api/django/ai/assistant-config/'

#: Routeur RÉEL de la SPA — source de vérité des chemins Paramètres.
#: (``parents[5]`` = racine du dépôt depuis ``…/apps/ai_governance/tests/``.)
ROUTER_SPA = (Path(__file__).resolve().parents[5] / 'frontend' / 'src'
              / 'features' / 'parametres' / 'module.config.jsx')


class FakeConfigLLM(LLMProvider):
    key = 'fake_ntai35'
    last_prompt = None

    def is_configured(self):
        return True

    def complete(self, *, prompt, system='', max_tokens=512):
        FakeConfigLLM.last_prompt = prompt
        return AIResult(
            ok=True, configured=True, provider=self.key,
            data={'text': 'Rendez-vous dans Paramètres → Entreprise.'})


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntai35IndexTests(TestCase):
    """L'index lui-même — pur, sans base, sans clé."""

    def test_aucun_lien_invente(self):
        """CHAQUE lien profond doit exister dans le routeur RÉEL de la SPA.

        Se saute proprement quand ``frontend/`` n'est pas monté (le conteneur
        de test ne monte que ``backend/django_core``) — la garde reste pleine
        en local et partout où l'arbre complet est présent.
        """
        if not ROUTER_SPA.exists():
            self.skipTest(f'frontend non monté ({ROUTER_SPA})')
        source = ROUTER_SPA.read_text(encoding='utf-8')
        for entry in CONFIG_ENTRIES:
            with self.subTest(lien=entry['lien']):
                self.assertIn(f"'{entry['lien']}'", source)

    def test_cles_uniques(self):
        cles = [e['cle'] for e in CONFIG_ENTRIES]
        self.assertEqual(len(cles), len(set(cles)))

    def test_chaque_entree_est_complete(self):
        for entry in CONFIG_ENTRIES:
            with self.subTest(cle=entry['cle']):
                self.assertTrue(entry['titre'])
                self.assertTrue(entry['resume'])
                self.assertTrue(entry['mots_cles'])
                self.assertTrue(entry['lien'].startswith('/'))

    def test_recherche_trouve_lecran_attendu(self):
        for question, cle_attendue in (
            ('où régler la TVA ?', 'entreprise'),
            ('comment activer les relances par email ?', 'notifications'),
            ("comment créer une alerte de seuil sur un KPI ?", 'alertes_kpi'),
            ('comment exporter mes données ?', 'export'),
            ('où voir qui a modifié un devis ?', 'journal'),
        ):
            with self.subTest(question=question):
                ecrans = rechercher_ecrans(question)
                self.assertTrue(ecrans, f'aucun écran pour « {question} »')
                self.assertEqual(ecrans[0]['cle'], cle_attendue)

    def test_recherche_insensible_aux_accents(self):
        self.assertEqual(rechercher_ecrans('ou regler la tva')[0]['cle'],
                         'entreprise')

    def test_question_hors_sujet_ne_renvoie_rien(self):
        self.assertEqual(rechercher_ecrans('quelle est la météo demain'), [])

    def test_filtrage_par_role(self):
        # `/parametres/ia` est réservé aux admins : jamais proposé à un
        # commercial (on ne renvoie pas un lien qui répondrait 403).
        cles_normal = {e['cle'] for e in
                       rechercher_ecrans('diagnostic ia ocr', role='normal')}
        cles_admin = {e['cle'] for e in
                      rechercher_ecrans('diagnostic ia ocr', role='admin')}
        self.assertNotIn('ia', cles_normal)
        self.assertIn('ia', cles_admin)


class Ntai35AssistantTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntai35-co', 'NTAI35 Co')
        # Garde CI : la seconde société porte un slug distinct explicite.
        cls.autre = make_company('ntai35-autre', 'NTAI35 Autre')
        cls.admin = User.objects.create_user(
            username='ntai35-admin', password='x', company=cls.company,
            role_legacy='admin')

    def _with_llm(self):
        register_provider(FakeConfigLLM)
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_ntai35', None))
        return override_settings(AI_PROVIDERS={'llm': 'fake_ntai35'})

    # ── Repli FAQ sans clé ──────────────────────────────────────────────────
    def test_sans_cle_degrade_sur_la_faq_statique(self):
        resp = auth(self.admin).post(URL, {'question': 'où régler la TVA ?'},
                                     format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['source'], 'faq')
        self.assertIn('TVA', resp.data['reponse'])
        self.assertEqual(resp.data['ecrans'][0]['lien'], '/parametres')
        self.assertFalse(resp.data['modifie'])

    # ── Chemin LLM ──────────────────────────────────────────────────────────
    def test_avec_llm_reponse_redigee_et_liens(self):
        with self._with_llm():
            resp = auth(self.admin).post(
                URL, {'question': 'où régler la TVA ?'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['source'], 'llm')
        self.assertIn('Paramètres', resp.data['reponse'])
        self.assertEqual(resp.data['ecrans'][0]['lien'], '/parametres')
        # Le prompt ne contient QUE les écrans retenus (pas d'écran inventable).
        self.assertIn('/parametres', FakeConfigLLM.last_prompt or '')

    # ── Validation & garanties ──────────────────────────────────────────────
    def test_question_vide_400(self):
        resp = auth(self.admin).post(URL, {'question': '  '}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_question_hors_sujet_repond_sans_lien(self):
        resp = auth(self.admin).post(
            URL, {'question': 'quelle est la météo demain'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['ecrans'], [])
        self.assertIn('Reformulez', resp.data['reponse'])

    def test_anonyme_refuse(self):
        resp = APIClient().post(URL, {'question': 'tva'}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_aucune_ecriture(self):
        """Guidage seul : l'assistant ne touche à aucun paramètre."""
        from apps.parametres.models import CompanyProfile

        avant = CompanyProfile.objects.count()
        with self._with_llm():
            auth(self.admin).post(URL, {'question': 'où régler la TVA ?'},
                                  format='json')
        self.assertEqual(CompanyProfile.objects.count(), avant)

    def test_service_filtre_par_role_transmis(self):
        resultat = assistant_config(question='diagnostic ia ocr', role='normal')
        liens = {e['lien'] for e in resultat['ecrans']}
        self.assertNotIn('/parametres/ia', liens)
        self.assertFalse(resultat['modifie'])

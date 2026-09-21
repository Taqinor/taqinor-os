"""NTAI13 — Tests du brouillon de description produit.

Couvre : dégradation propre sans clé LLM (503, aucun appel réseau), génération
avec un faux fournisseur, ABSENCE TOTALE de ``prix_achat`` dans le prompt
(garde de confidentialité), non-écriture du produit, et scoping société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.ai import AIResult, LLMProvider, register_provider
from core.ai import registry

from ..services import (
    PRODUIT_DESCRIPTION_ALLOWED_FIELDS,
    build_description_produit_prompt,
    produit_description_facts,
)

User = get_user_model()

URL = '/api/django/ai/description-produit/'


class FakeDescriptionLLM(LLMProvider):
    key = 'fake_ntai13'
    #: Dernier prompt reçu — sert à PROUVER ce qui est réellement transmis.
    last_prompt = None

    def is_configured(self):
        return True

    def complete(self, *, prompt, system='', max_tokens=512):
        FakeDescriptionLLM.last_prompt = prompt
        return AIResult(
            ok=True, configured=True, provider=self.key,
            data={'text': "Onduleur hybride robuste.\nCOURT : Onduleur hybride."})


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntai13DescriptionProduitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.stock.models import Categorie, Produit

        cls.company = make_company('ntai13-co', 'NTAI13 Co')
        # Garde CI : une SECONDE société doit porter un slug distinct explicite.
        cls.autre = make_company('ntai13-autre', 'NTAI13 Autre')
        cls.user = User.objects.create_user(
            username='ntai13-user', password='x', company=cls.company,
            role_legacy='normal')
        cls.categorie = Categorie.objects.create(
            company=cls.company, nom='Onduleurs')
        cls.produit = Produit.objects.create(
            company=cls.company, nom='Onduleur Deye 8 kW', marque='Deye',
            categorie=cls.categorie, garantie='10 ans constructeur',
            # Donnée INTERNE : ne doit JAMAIS atteindre le prompt.
            prix_achat='7777.77', prix_vente='12345.67')
        cls.produit_autre = Produit.objects.create(
            company=cls.autre, nom='Produit autre société', prix_vente='10')

    def setUp(self):
        FakeDescriptionLLM.last_prompt = None

    def _with_fake_llm(self):
        register_provider(FakeDescriptionLLM)
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_ntai13', None))
        return override_settings(AI_PROVIDERS={'llm': 'fake_ntai13'})

    # ── Dégradation sans clé ────────────────────────────────────────────────
    def test_sans_cle_llm_degrade_en_503(self):
        resp = auth(self.user).post(URL, {'produit_id': self.produit.id},
                                    format='json')
        self.assertEqual(resp.status_code, 503)
        self.assertIn('configuré', resp.data['detail'])

    def test_produit_id_manquant_400(self):
        resp = auth(self.user).post(URL, {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_anonyme_refuse(self):
        resp = APIClient().post(URL, {'produit_id': self.produit.id},
                                format='json')
        self.assertIn(resp.status_code, (401, 403))

    # ── Chemin câblé ────────────────────────────────────────────────────────
    def test_genere_description_et_variante_courte(self):
        with self._with_fake_llm():
            resp = auth(self.user).post(URL, {'produit_id': self.produit.id},
                                        format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['description'], 'Onduleur hybride robuste.')
        self.assertEqual(resp.data['description_courte'], 'Onduleur hybride.')
        self.assertFalse(resp.data['applique'])

    def test_ne_modifie_pas_le_produit(self):
        avant = self.produit.description
        with self._with_fake_llm():
            auth(self.user).post(URL, {'produit_id': self.produit.id},
                                 format='json')
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.description, avant)

    # ── Scoping société ─────────────────────────────────────────────────────
    def test_produit_autre_societe_invisible(self):
        with self._with_fake_llm():
            resp = auth(self.user).post(
                URL, {'produit_id': self.produit_autre.id}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('introuvable', resp.data['detail'])

    def test_produit_id_non_numerique_400(self):
        resp = auth(self.user).post(URL, {'produit_id': 'abc'}, format='json')
        self.assertEqual(resp.status_code, 400)

    # ── GARDE prix_achat (le test qui compte) ───────────────────────────────
    def test_prix_achat_jamais_dans_le_prompt(self):
        with self._with_fake_llm():
            resp = auth(self.user).post(URL, {'produit_id': self.produit.id},
                                        format='json')
        self.assertEqual(resp.status_code, 200)
        prompt = FakeDescriptionLLM.last_prompt or ''
        self.assertTrue(prompt, 'le faux fournisseur devait recevoir un prompt')
        lowered = prompt.lower()
        for interdit in ('prix_achat', "prix d'achat", 'marge', '7777'):
            self.assertNotIn(interdit, lowered)
        # Le prix de VENTE non plus n'a rien à faire dans un texte marketing.
        self.assertNotIn('12345', prompt)
        # …et les faits légitimes, eux, y sont bien.
        self.assertIn('Deye', prompt)

    def test_facts_limites_a_lallowlist(self):
        facts = produit_description_facts(self.produit)
        self.assertEqual(set(facts), set(PRODUIT_DESCRIPTION_ALLOWED_FIELDS))
        self.assertNotIn('prix_achat', facts)

    def test_prompt_refuse_un_terme_interdit(self):
        # Simule une régression qui élargirait l'allowlist : la garde de
        # dernier recours doit lever plutôt que de laisser fuiter.
        facts = produit_description_facts(self.produit)
        facts['marque'] = 'Deye (prix_achat 7777)'
        with self.assertRaises(ValueError):
            build_description_produit_prompt(facts)

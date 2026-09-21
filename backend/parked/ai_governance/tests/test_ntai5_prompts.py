"""NTAI5 — Tests de la bibliothèque de prompts éditables.

Couvre : le rendu avec placeholders, le REPLI sur le défaut code, la surcharge
société effectivement utilisée par un copilote, l'immutabilité des versions,
le scoping société et le CRUD admin-only.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.ai import AIResult, LLMProvider, register_provider
from core.ai import registry
from core.ai import prompts as core_prompts
from core.ai.prompts import (default_prompt, effective_prompt, placeholders,
                             register_default_prompt, render_prompt)

from ..models import PromptTemplate, PromptTemplateVersion

User = get_user_model()

URL = '/api/django/ai-governance/prompt-templates/'
DESCRIPTION_URL = '/api/django/ai/description-produit/'


class FakePromptLLM(LLMProvider):
    key = 'fake_ntai5'
    dernier_system = None

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        FakePromptLLM.dernier_system = system
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': 'Description.\nCOURT : Description.'})


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntai5PromptsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.stock.models import Produit

        cls.company = make_company('ntai5-co', 'NTAI5 Co')
        cls.autre = make_company('ntai5-autre', 'NTAI5 Autre')
        cls.admin = User.objects.create_user(
            username='ntai5-admin', password='x', company=cls.company,
            role_legacy='admin')
        cls.simple = User.objects.create_user(
            username='ntai5-simple', password='x', company=cls.company,
            role_legacy='normal')
        cls.produit = Produit.objects.create(
            company=cls.company, nom='Onduleur Deye 8 kW', marque='Deye',
            prix_vente='10000')

    def setUp(self):
        FakePromptLLM.dernier_system = None
        register_default_prompt('test.ntai5', 'Bonjour {{nom}}, ton {{canal}}.')
        self.addCleanup(
            lambda: core_prompts._DEFAULTS.pop('test.ntai5', None))

    def _with_fake_llm(self):
        register_provider(FakePromptLLM)
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_ntai5', None))

    # --- Rendu --------------------------------------------------------------

    def test_rendu_du_defaut_code_avec_placeholders(self):
        rendu = render_prompt(self.company, 'test.ntai5',
                              {'nom': 'Reda', 'canal': 'e-mail'})
        self.assertEqual(rendu, 'Bonjour Reda, ton e-mail.')

    def test_placeholder_absent_ne_laisse_pas_de_marqueur(self):
        rendu = render_prompt(self.company, 'test.ntai5', {'nom': 'Reda'})
        self.assertNotIn('{{', rendu)
        self.assertEqual(rendu, 'Bonjour Reda, ton .')

    def test_cle_inconnue_leve(self):
        with self.assertRaises(KeyError):
            render_prompt(self.company, 'test.inexistant', {})

    def test_placeholders_declares(self):
        self.assertEqual(placeholders(default_prompt('test.ntai5')),
                         ['nom', 'canal'])

    # --- Surcharge société --------------------------------------------------

    def test_surcharge_active_utilisee_puis_repli_si_inactive(self):
        gabarit = PromptTemplate.objects.create(
            company=self.company, cle='test.ntai5',
            corps='Salut {{nom}} !', label='Test')
        corps, origine = effective_prompt(self.company, 'test.ntai5')
        self.assertEqual(origine, 'societe')
        self.assertEqual(corps, 'Salut {{nom}} !')

        gabarit.actif = False
        gabarit.save(update_fields=['actif'])
        corps, origine = effective_prompt(self.company, 'test.ntai5')
        self.assertEqual(origine, 'code')

    def test_surcharge_d_une_societe_invisible_pour_l_autre(self):
        PromptTemplate.objects.create(
            company=self.autre, cle='test.ntai5', corps='Autre société.')
        corps, origine = effective_prompt(self.company, 'test.ntai5')
        self.assertEqual(origine, 'code')
        self.assertNotIn('Autre société', corps)

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai5'})
    def test_un_copilote_utilise_la_surcharge(self):
        from ..services import generer_description_produit

        self._with_fake_llm()
        PromptTemplate.objects.create(
            company=self.company, cle='ai.description_produit.system',
            corps='Rédige en trois mots, sans adjectif.')

        generer_description_produit(company=self.company,
                                    produit_id=self.produit.id)
        self.assertEqual(FakePromptLLM.dernier_system,
                         'Rédige en trois mots, sans adjectif.')

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai5'})
    def test_sans_surcharge_le_prompt_est_celui_du_code(self):
        from ..services import (PRODUIT_DESCRIPTION_SYSTEM,
                                generer_description_produit)

        self._with_fake_llm()
        generer_description_produit(company=self.company,
                                    produit_id=self.produit.id)
        self.assertEqual(FakePromptLLM.dernier_system,
                         PRODUIT_DESCRIPTION_SYSTEM)

    # --- Versions -----------------------------------------------------------

    def test_chaque_changement_fige_une_version(self):
        api = auth(self.admin)
        reponse = api.post(URL, {'cle': 'test.ntai5', 'corps': 'V1 {{nom}}'},
                           format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        gabarit_id = reponse.json()['id']
        self.assertEqual(
            PromptTemplateVersion.objects.filter(
                template_id=gabarit_id).count(), 1)

        api.patch(f'{URL}{gabarit_id}/', {'corps': 'V2 {{nom}}'},
                  format='json')
        versions = list(PromptTemplateVersion.objects.filter(
            template_id=gabarit_id).order_by('numero'))
        self.assertEqual([v.numero for v in versions], [1, 2])
        # La version 1 garde son texte : immuable.
        self.assertEqual(versions[0].corps, 'V1 {{nom}}')

    def test_enregistrement_sans_changement_ne_duplique_pas(self):
        api = auth(self.admin)
        gabarit_id = api.post(
            URL, {'cle': 'test.ntai5', 'corps': 'V1'},
            format='json').json()['id']
        api.patch(f'{URL}{gabarit_id}/', {'label': 'Renommé'}, format='json')
        self.assertEqual(
            PromptTemplateVersion.objects.filter(
                template_id=gabarit_id).count(), 1)

    # --- CRUD ---------------------------------------------------------------

    def test_crud_admin_seulement(self):
        self.assertEqual(auth(self.simple).get(URL).status_code, 403)

    def test_creation_force_la_societe(self):
        reponse = auth(self.admin).post(
            URL, {'cle': 'test.ntai5', 'corps': 'X', 'company': self.autre.id},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        self.assertEqual(PromptTemplate.objects.get().company_id,
                         self.company.id)

    def test_cle_en_double_refusee(self):
        PromptTemplate.objects.create(company=self.company, cle='test.ntai5',
                                      corps='X')
        reponse = auth(self.admin).post(
            URL, {'cle': 'test.ntai5', 'corps': 'Y'}, format='json')
        self.assertEqual(reponse.status_code, 400)

    def test_effective_liste_le_code_et_la_surcharge(self):
        PromptTemplate.objects.create(
            company=self.company, cle='test.ntai5', corps='Surchargé')
        lignes = auth(self.admin).get(URL + 'effective/').json()
        par_cle = {ligne['cle']: ligne for ligne in lignes}
        self.assertEqual(par_cle['test.ntai5']['origine'], 'societe')
        self.assertEqual(par_cle['test.ntai5']['corps'], 'Surchargé')

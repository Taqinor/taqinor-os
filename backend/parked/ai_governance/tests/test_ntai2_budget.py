"""NTAI2 — Tests du budget IA mensuel et de son coupe-circuit.

Couvre : le calcul du statut (dépensé du mois vs plafond), le COUPE-CIRCUIT
au-delà de 100 % (fournisseur NO-OP « budget épuisé », jamais d'exception),
l'alerte au seuil (une seule fois par mois), le scoping société et le CRUD
admin-only.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.ai import AIResult, LLMProvider, register_provider
from core.ai import registry
from core.ai.registry import get_provider
from core.ai.usage import budget_status, usage_context

from ..models import LlmBudget, LlmUsageRecord

User = get_user_model()

URL = '/api/django/ai-governance/budgets/'


class FakeBudgetLLM(LLMProvider):
    key = 'fake_ntai2'

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': 'Réponse.'})


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntai2BudgetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntai2-co', 'NTAI2 Co')
        cls.autre = make_company('ntai2-autre', 'NTAI2 Autre')
        cls.admin = User.objects.create_user(
            username='ntai2-admin', password='x', company=cls.company,
            role_legacy='admin')
        cls.simple = User.objects.create_user(
            username='ntai2-simple', password='x', company=cls.company,
            role_legacy='normal')

    def _with_fake_llm(self):
        register_provider(FakeBudgetLLM)
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_ntai2', None))

    def _depenser(self, company, mad):
        """Journalise une dépense IA (en MAD) sur le mois courant."""
        LlmUsageRecord.objects.create(
            company=company, capability='llm', provider='fake_ntai2',
            feature_key='ai.test', prompt_tokens=1, completion_tokens=1,
            cost_estimated_micro_mad=int(Decimal(mad) * 1000000),
            cout_tarife=True, success=True)

    # --- Calcul -------------------------------------------------------------

    def test_sans_budget_rien_n_est_configure_ni_bride(self):
        statut = budget_status(self.company)
        self.assertFalse(statut.configured)
        self.assertFalse(statut.depasse)

    def test_statut_calcule_le_depense_du_mois(self):
        LlmBudget.objects.create(company=self.company,
                                 montant_mensuel_mad=Decimal('100.00'))
        self._depenser(self.company, '25')
        self._depenser(self.company, '15')
        # Dépense d'une AUTRE société : ne doit jamais compter ici.
        self._depenser(self.autre, '500')

        statut = budget_status(self.company)
        self.assertTrue(statut.configured)
        self.assertEqual(statut.depense, Decimal('40.000000'))
        self.assertAlmostEqual(statut.pourcentage, 40.0, places=3)
        self.assertFalse(statut.depasse)
        self.assertFalse(statut.alerte)

    def test_budget_inactif_ne_bride_rien(self):
        LlmBudget.objects.create(company=self.company, actif=False,
                                 montant_mensuel_mad=Decimal('10.00'))
        self._depenser(self.company, '999')
        self.assertFalse(budget_status(self.company).configured)

    # --- Coupe-circuit ------------------------------------------------------

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai2'})
    def test_au_dela_du_plafond_le_fournisseur_devient_noop(self):
        self._with_fake_llm()
        LlmBudget.objects.create(company=self.company,
                                 montant_mensuel_mad=Decimal('10.00'))
        self._depenser(self.company, '12')

        with usage_context(company_id=self.company.id, feature_key='ai.test'):
            provider = get_provider('llm')
            resultat = provider.complete(prompt='Bonjour')

        # Même chemin de dégradation qu'une clé absente : key == 'noop'.
        self.assertEqual(provider.key, 'noop')
        self.assertEqual(getattr(provider, 'raison', ''), 'budget_epuise')
        self.assertFalse(resultat.configured)
        self.assertFalse(resultat.ok)
        self.assertIn('Budget IA', resultat.error)

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai2'})
    def test_sous_le_plafond_le_vrai_fournisseur_repond(self):
        self._with_fake_llm()
        LlmBudget.objects.create(company=self.company,
                                 montant_mensuel_mad=Decimal('100.00'))
        self._depenser(self.company, '1')

        with usage_context(company_id=self.company.id):
            provider = get_provider('llm')
        self.assertEqual(provider.key, 'fake_ntai2')

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai2'})
    def test_le_budget_d_une_societe_ne_bride_pas_l_autre(self):
        self._with_fake_llm()
        LlmBudget.objects.create(company=self.company,
                                 montant_mensuel_mad=Decimal('10.00'))
        self._depenser(self.company, '50')

        with usage_context(company_id=self.autre.id):
            self.assertEqual(get_provider('llm').key, 'fake_ntai2')

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai2'})
    def test_hors_contexte_societe_aucun_bridage(self):
        """On ne bride jamais sur une société devinée."""
        self._with_fake_llm()
        LlmBudget.objects.create(company=self.company,
                                 montant_mensuel_mad=Decimal('1.00'))
        self._depenser(self.company, '50')
        self.assertEqual(get_provider('llm').key, 'fake_ntai2')

    # --- Alerte -------------------------------------------------------------

    def test_alerte_au_seuil_une_seule_fois_par_mois(self):
        from apps.notifications.models import Notification

        budget = LlmBudget.objects.create(
            company=self.company, montant_mensuel_mad=Decimal('100.00'),
            seuil_alerte_pct=80)
        self._depenser(self.company, '85')

        avant = Notification.objects.count()
        statut = budget_status(self.company)
        self.assertTrue(statut.alerte)
        budget.refresh_from_db()
        self.assertEqual(budget.alerte_periode,
                         timezone.localdate().strftime('%Y-%m'))
        premier_lot = Notification.objects.count()
        self.assertGreater(premier_lot, avant)

        # Deuxième consultation le même mois : aucune notification de plus.
        budget_status(self.company)
        self.assertEqual(Notification.objects.count(), premier_lot)

    # --- CRUD ---------------------------------------------------------------

    def test_crud_admin_seulement(self):
        reponse = auth(self.simple).get(URL)
        self.assertEqual(reponse.status_code, 403)

    def test_creation_force_la_societe_du_serveur(self):
        reponse = auth(self.admin).post(URL, {
            'montant_mensuel_mad': '250.00',
            'seuil_alerte_pct': 75,
            # Tentative d'injection : la société du corps est IGNORÉE.
            'company': self.autre.id,
        }, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        budget = LlmBudget.objects.get()
        self.assertEqual(budget.company_id, self.company.id)

    def test_second_budget_refuse_proprement(self):
        LlmBudget.objects.create(company=self.company,
                                 montant_mensuel_mad=Decimal('10.00'))
        reponse = auth(self.admin).post(
            URL, {'montant_mensuel_mad': '20.00'}, format='json')
        self.assertEqual(reponse.status_code, 400)

    def test_seuil_hors_bornes_refuse_en_francais(self):
        reponse = auth(self.admin).post(
            URL, {'montant_mensuel_mad': '20.00', 'seuil_alerte_pct': 150},
            format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('seuil', str(reponse.json()).lower())

    def test_statut_expose_le_mois_courant(self):
        LlmBudget.objects.create(company=self.company,
                                 montant_mensuel_mad=Decimal('100.00'))
        self._depenser(self.company, '10')
        corps = auth(self.admin).get(URL + 'statut/').json()
        self.assertTrue(corps['configure'])
        self.assertEqual(Decimal(corps['depense_mad']), Decimal('10'))
        self.assertFalse(corps['depasse'])

    def test_liste_scopee_societe(self):
        LlmBudget.objects.create(company=self.autre,
                                 montant_mensuel_mad=Decimal('99.00'))
        corps = auth(self.admin).get(URL).json()
        resultats = corps['results'] if isinstance(corps, dict) else corps
        self.assertEqual(len(resultats), 0)

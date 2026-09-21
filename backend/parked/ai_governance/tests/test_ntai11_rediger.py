"""NTAI11 — Tests de la rédaction assistée de réponse/relance.

Couvre : un brouillon par CANAL (email/whatsapp/sms), contextualisation par
l'historique de la fiche, dégradation propre sans clé LLM, refus d'un canal
inconnu, scoping société, et surtout la GARANTIE que rien n'est jamais envoyé.
"""
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.ai import AIResult, LLMProvider, register_provider
from core.ai import registry

from ..services import aplatir_fil

User = get_user_model()

URL = '/api/django/ai/rediger/'


class FakeRedactionLLM(LLMProvider):
    key = 'fake_ntai11'
    last_prompt = None
    last_system = None

    def is_configured(self):
        return True

    def complete(self, *, prompt, system='', max_tokens=512):
        FakeRedactionLLM.last_prompt = prompt
        FakeRedactionLLM.last_system = system
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': 'Bonjour, je reviens vers vous.'})


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntai11RedigerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.contenttypes.models import ContentType
        from apps.crm.models import Lead
        from apps.records.models import Activity

        cls.company = make_company('ntai11-co', 'NTAI11 Co')
        # Garde CI : la seconde société porte un slug distinct explicite.
        cls.autre = make_company('ntai11-autre', 'NTAI11 Autre')
        cls.user = User.objects.create_user(
            username='ntai11-user', password='x', company=cls.company,
            role_legacy='normal')
        cls.lead = Lead.objects.create(company=cls.company, nom='Benali')
        cls.lead_autre = Lead.objects.create(company=cls.autre, nom='Etranger')

        ct = ContentType.objects.get_for_model(Lead)
        Activity.objects.create(
            company=cls.company, content_type=ct, object_id=cls.lead.id,
            kind='note', body='Le client demande un devis pour 6 kWc.',
            created_by=cls.user)
        Activity.objects.create(
            company=cls.company, content_type=ct, object_id=cls.lead.id,
            kind='note', body='Relancé par téléphone, sans réponse.',
            created_by=cls.user)
        # Bruit d'une AUTRE société sur le même id de cible : ne doit jamais
        # apparaître dans le fil aplati.
        Activity.objects.create(
            company=cls.autre, content_type=ct, object_id=cls.lead.id,
            kind='note', body='NOTE CONFIDENTIELLE AUTRE SOCIETE',
            created_by=None)
        cls.ct = ct

    def setUp(self):
        FakeRedactionLLM.last_prompt = None
        mail.outbox = []

    def _with_fake_llm(self):
        register_provider(FakeRedactionLLM)
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_ntai11', None))
        return override_settings(AI_PROVIDERS={'llm': 'fake_ntai11'})

    def _post(self, **body):
        payload = {'content_type': 'crm.lead', 'object_id': self.lead.id}
        payload.update(body)
        return auth(self.user).post(URL, payload, format='json')

    # ── Dégradation / validation ────────────────────────────────────────────
    def test_sans_cle_llm_degrade_en_503(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 503)

    def test_champs_requis(self):
        resp = auth(self.user).post(URL, {'canal': 'email'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_canal_inconnu_refuse(self):
        with self._with_fake_llm():
            resp = self._post(canal='pigeon')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Canal inconnu', resp.data['detail'])

    def test_cible_non_autorisee_refuse(self):
        with self._with_fake_llm():
            resp = auth(self.user).post(
                URL, {'content_type': 'auth.user', 'object_id': self.user.id},
                format='json')
        self.assertEqual(resp.status_code, 400)

    def test_anonyme_refuse(self):
        resp = APIClient().post(URL, {'content_type': 'crm.lead',
                                      'object_id': self.lead.id}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    # ── Un brouillon par canal ──────────────────────────────────────────────
    def test_brouillon_par_canal(self):
        for canal in ('email', 'whatsapp', 'sms'):
            with self.subTest(canal=canal):
                with self._with_fake_llm():
                    resp = self._post(canal=canal, intention='Relancer le devis')
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.data['canal'], canal)
                self.assertTrue(resp.data['brouillon'])
                self.assertFalse(resp.data['envoye'])

    def test_brouillon_contextualise_par_lhistorique(self):
        with self._with_fake_llm():
            resp = self._post(canal='whatsapp', intention='Relancer le devis')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['entrees_fil'], 2)
        prompt = FakeRedactionLLM.last_prompt or ''
        self.assertIn('6 kWc', prompt)
        self.assertIn('Relancer le devis', prompt)
        # Le ton WhatsApp est bien passé au fournisseur.
        self.assertIn('WhatsApp', FakeRedactionLLM.last_system or '')

    def test_fil_scope_societe(self):
        fil = aplatir_fil(company=self.company, content_type=self.ct,
                          object_id=self.lead.id)
        textes = ' '.join(e['texte'] for e in fil)
        self.assertNotIn('AUTRE SOCIETE', textes)
        # Ordre chronologique : la note la plus ancienne en premier.
        self.assertIn('6 kWc', fil[0]['texte'])

    # ── GARANTIE : jamais d'envoi ───────────────────────────────────────────
    def test_aucun_envoi(self):
        with self._with_fake_llm():
            resp = self._post(canal='email')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['envoye'])
        self.assertEqual(len(mail.outbox), 0)

    def test_aucune_activite_creee(self):
        from apps.records.models import Activity

        avant = Activity.objects.count()
        with self._with_fake_llm():
            self._post(canal='email')
        self.assertEqual(Activity.objects.count(), avant)

    # ── Scoping société ─────────────────────────────────────────────────────
    def test_lead_autre_societe_refuse(self):
        with self._with_fake_llm():
            resp = auth(self.user).post(
                URL, {'content_type': 'crm.lead',
                      'object_id': self.lead_autre.id}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_intention_bornee(self):
        with self._with_fake_llm():
            resp = self._post(canal='sms', intention='A' * 5000)
        self.assertEqual(resp.status_code, 200)
        self.assertLess((FakeRedactionLLM.last_prompt or '').count('A'), 1000)

"""ARC33 — auto-découverte des actions agent depuis les manifestes plateforme.

Couvre : (1) l'app pilote (adsengine) est découverte au démarrage via son
``agent_actions_module`` (AUCUN câblage dans sa propre ``AppConfig.ready()``)
et ses actions sont LECTURE seule ; (2) le gatage ``ModuleToggle`` (ODX23) —
module OFF pour la société ⇒ ses actions découvertes ABSENTES du catalogue
``for_user`` (même pour un superuser de cette société) ; (3) non-régression —
les builtins et les enregistrements historiques hors manifeste (crm, ventes…)
ne sont JAMAIS gatés par ce mécanisme (comportement d'avant ARC33 préservé) ;
(4) idempotence de la découverte (ré-appel sans doublon ni perte
d'attribution).

SOLMVP-sweep (2026-09-21) — les 2 pilotes d'origine (rh, compta) sont sortis
du MVP solaire (Groupe SOLMVP, en cours de mise en coquille par la lane
SOLMVP30b) : leurs ``agent_actions.py``/``platform.py`` disparaissent avec le
reste du module, donc plus rien ne les découvre. Remplacés par ``adsengine``
(app KEPT, seule app — avec ``crm`` — à déclarer ``agent_actions_module`` dans
son manifeste ; ``crm`` expose ``register_crm_actions`` et non la convention
``register_actions``, donc elle reste le cas « legacy non attribué » ci-dessous
plutôt qu'un second pilote). adsengine porte à elle seule 3 actions LECTURE,
ce qui suffit à couvrir découverte/attribution/idempotence ; la gating
« un module OFF ne touche PAS un AUTRE module » est prouvée contre les
actions crm legacy (non attribuées), qui restent le seul second exemple réel
disponible après la sortie de rh/compta/contrats/ao du MVP.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.agent import registry
from authentication.models import Company
from core.models import ModuleToggle

User = get_user_model()

PILOT_KEYS = {
    'adsengine.spend.week',
    'adsengine.ads.top',
    'adsengine.campaigns.list',
}

PILOT_MODULES = {
    'apps.adsengine.agent_actions',
}


class TestAutodiscovery(SimpleTestCase):
    """La découverte au démarrage a bien enregistré et attribué les pilotes."""

    def test_pilot_actions_discovered_at_startup(self):
        keys = {a.key for a in registry.all_actions()}
        for key in PILOT_KEYS:
            self.assertIn(key, keys, f'Action pilote « {key} » non découverte.')

    def test_pilot_actions_are_read_only(self):
        """Pilotes ARC33 = LECTURE seule : GET + risk internal, jamais
        d'écriture sensible."""
        by_key = {a.key: a for a in registry.all_actions()}
        for key in PILOT_KEYS:
            action = by_key[key]
            self.assertEqual(action.method.upper(), 'GET', key)
            self.assertEqual(action.risk, registry.RISK_INTERNAL, key)

    def test_discovery_attributes_keys_to_their_modules(self):
        """Chaque clé pilote est attribuée à son module dotted (base du
        gatage ModuleToggle)."""
        for dotted in PILOT_MODULES:
            self.assertIn(dotted, registry._DISCOVERED, dotted)
        for key in PILOT_KEYS:
            self.assertIn(key,
                          registry._DISCOVERED['apps.adsengine.agent_actions'])

    def test_autodiscovery_is_idempotent(self):
        """Un ré-appel (ready() ré-exécuté) n'ajoute aucun doublon et ne perd
        aucune attribution."""
        avant_actions = {a.key for a in registry.all_actions()}
        avant_attribution = {
            d: set(k) for d, k in registry._DISCOVERED.items()}
        registry.autodiscover_from_platform_manifests()
        self.assertEqual({a.key for a in registry.all_actions()},
                         avant_actions)
        for dotted, keys in avant_attribution.items():
            self.assertTrue(
                keys.issubset(registry._DISCOVERED.get(dotted, set())),
                f'Attribution perdue pour {dotted}.')

    def test_legacy_apps_not_attributed(self):
        """Les 5 apps historiques (convention de nom propre, câblées par leur
        propre ready()) ne sont PAS attribuées — leurs actions ne seront
        jamais gatées par ce mécanisme (non-régression). crm est déclaré au
        manifeste mais expose register_crm_actions, pas register_actions."""
        attributed = set()
        for keys in registry._DISCOVERED.values():
            attributed |= keys
        for legacy_key in ('crm.lead.create', 'crm.lead.list',
                           'ventes.devis.proposal_pdf'):
            self.assertNotIn(legacy_key, attributed)


class TestModuleToggleGating(TestCase):
    """Module OFF ⇒ ses actions découvertes disparaissent du catalogue."""

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='arc33-gating', defaults={'nom': 'ARC33 Gating Co'})[0]
        # Superuser AVEC société : passe tous les filtres de permission —
        # ne reste que le gatage par société (l'objet du test).
        self.su = User.objects.create_superuser(
            username='arc33_su', password='x', email='arc33@example.com')
        self.su.company = self.company
        self.su.save(update_fields=['company'])

    def test_all_pilots_visible_by_default(self):
        keys = {a.key for a in registry.for_user(self.su)}
        for key in PILOT_KEYS:
            self.assertIn(key, keys, key)

    def test_adsengine_off_hides_adsengine_actions_only(self):
        ModuleToggle.objects.create(
            company=self.company, module='adsengine', actif=False)
        keys = {a.key for a in registry.for_user(self.su)}
        for key in PILOT_KEYS:
            self.assertNotIn(key, keys, key)
        # Une action LEGACY non attribuée (crm, hors manifeste) reste
        # visible : le gatage ne porte QUE sur le module adsengine désactivé,
        # jamais globalement.
        self.assertIn('crm.lead.create', keys)

    def test_module_off_does_not_hide_legacy_actions(self):
        """Non-régression : crm OFF ne retire PAS les actions crm historiques
        (enregistrées hors manifeste — comportement d'avant ARC33 préservé)."""
        ModuleToggle.objects.create(
            company=self.company, module='crm', actif=False)
        keys = {a.key for a in registry.for_user(self.su)}
        self.assertIn('crm.lead.create', keys)
        self.assertIn('crm.lead.list', keys)

    def test_user_without_company_sees_everything(self):
        su_global = User.objects.create_superuser(
            username='arc33_su_global', password='x',
            email='arc33g@example.com')
        keys = {a.key for a in registry.for_user(su_global)}
        for key in PILOT_KEYS:
            self.assertIn(key, keys, key)


class TestCatalogueEndpointGating(TestCase):
    """Le gatage traverse jusqu'à l'endpoint catalogue AG1."""

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='arc33-endpoint', defaults={'nom': 'ARC33 Endpoint Co'})[0]
        self.user = User.objects.create_user(
            username='arc33_endpoint_user', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_pilot_visible_then_hidden_when_module_off(self):
        resp = self.api.get('/api/django/agent/actions/')
        self.assertEqual(resp.status_code, 200)
        keys = {a['key'] for a in resp.data['actions']}
        # required_permission='adsengine_view' ⇒ distribuée à TOUS les rôles
        # (ENG19, y compris « responsable »), donc visible pour cet utilisateur.
        self.assertIn('adsengine.campaigns.list', keys)

        ModuleToggle.objects.create(
            company=self.company, module='adsengine', actif=False)
        resp = self.api.get('/api/django/agent/actions/')
        keys = {a['key'] for a in resp.data['actions']}
        self.assertNotIn('adsengine.campaigns.list', keys)

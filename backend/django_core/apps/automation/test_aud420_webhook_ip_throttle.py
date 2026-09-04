"""AUD420 — le webhook entrant est throttlé AVANT de résoudre son token.

`incoming_webhook()` exécutait d'abord
`IncomingWebhookTrigger.objects.filter(token=token, enabled=True).first()`
— une requête base NON throttlée — et n'appliquait `_throttled(token)` qu'APRÈS
avoir trouvé un trigger existant. Toute requête vers un token INEXISTANT ou
DÉSACTIVÉ déclenchait donc une lecture base à chaque appel, sans aucune limite
de débit : un scan automatisé n'était jamais ralenti (toutes 404, aucune 429).
Le token fait 256 bits, ce n'est pas un vecteur de force brute réaliste — c'est
un coût base non borné.

Le dépôt porte déjà le bon patron sur ses deux autres surfaces publiques
(`sav.SavPublicThrottle`, `stock.QuaiCheckinThrottle`) : throttle par IP appliqué
AVANT le corps de la vue.

Ces tests sont ROUGES avant le correctif (aucune 429 sur des tokens inconnus) et
VERTS après. Cache locmem DÉDIÉ + vidé : le compteur de débit ne doit ni fuiter
vers les autres tests, ni être pollué par eux.
"""
import json

from django.core.cache import cache
from django.test import TestCase, override_settings

from authentication.models import Company
from apps.automation.models import (
    ActionType, AutomationRule, IncomingWebhookTrigger, TriggerType,
)
from apps.automation.public_views import _WebhookIpThrottle

_LOCMEM_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'aud420',
    }
}


@override_settings(CACHES=_LOCMEM_CACHE)
class Aud420ThrottleAvantResolutionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(
            nom='AUD420 Co', slug='aud420-co')
        self.rule = AutomationRule.objects.create(
            company=self.company, nom='Webhook AUD420',
            trigger_type=TriggerType.WEBHOOK_INBOUND, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'reçu'}, enabled=True)
        self.trigger = IncomingWebhookTrigger.objects.create(
            company=self.company, rule=self.rule)

    def _post(self, token):
        return self.client.post(
            f'/api/django/public/hooks/{token}/',
            data=json.dumps({}), content_type='application/json')

    @property
    def _plafond(self):
        return _WebhookIpThrottle().num_requests

    def test_un_scan_de_tokens_inconnus_finit_par_etre_throttle(self):
        plafond = self._plafond
        statuts = [self._post(f'token-inexistant-{i}').status_code
                   for i in range(plafond + 3)]
        # Les premières restent des 404 (le token n'existe pas)…
        self.assertEqual(statuts[0], 404)
        # …mais la limite PAR IP finit par tomber, indépendamment de la
        # validité du token (avant AUD420 : que des 404, jamais de 429).
        self.assertIn(429, statuts)

    def test_un_token_valide_est_aussi_borne_par_lip(self):
        """La garde vit AVANT la résolution : elle couvre les deux cas."""
        plafond = self._plafond
        for _ in range(plafond):
            self._post('token-inexistant-x')
        self.assertEqual(self._post(self.trigger.token).status_code, 429)

    def test_le_plafond_ip_est_plus_haut_que_le_plafond_par_token(self):
        """Un intégrateur légitime alimentant plusieurs webhooks depuis la même
        IP ne doit pas être gêné : chaque token est déjà borné à 60/min."""
        from apps.automation.public_views import _WebhookTokenThrottle
        par_token = _WebhookTokenThrottle('x').num_requests
        self.assertGreater(self._plafond, par_token)

    # ── Non-régression : le trafic normal passe toujours ──────────────────
    def test_un_appel_legitime_reste_accepte(self):
        self.assertEqual(self._post(self.trigger.token).status_code, 202)

    def test_un_token_inconnu_reste_un_404_sous_le_plafond(self):
        self.assertEqual(self._post('token-inexistant').status_code, 404)

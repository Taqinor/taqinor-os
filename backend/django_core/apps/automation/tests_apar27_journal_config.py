"""APAR27 — chaque écriture de configuration des automatisations est journalisée.

Constat C-APAR-035 : seul le CRUD des règles écrivait dans ``SettingsAuditLog``
(section ``automatisations``) ; installer une recette, créer/modifier/tourner
un webhook entrant, restaurer une version ou gérer un type de demande
d'approbation ne laissaient AUCUNE trace « qui/quand/avant-après ». Un jeton
ou un secret n'y apparaît jamais en clair.

Test-du-test : retirer l'appel ``services.journaliser_config`` d'une route ⇒
le sous-test de CETTE route (nommée) est rouge.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.automation.models import (
    ActionType, AutomationRule, AutomationRuleVersion, IncomingWebhookTrigger,
    TriggerType, creer_version_automation_rule,
)
from apps.parametres.models import SettingsAuditLog
from authentication.models import Company

BASE = '/api/django/automation/'
SECRET = 'secret-hmac-tres-long-123'


class JournalConfigTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='apar27-co', defaults={'nom': 'APAR27'})
        self.admin = get_user_model().objects.create_user(
            username='apar27-admin', password='x', company=self.co,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.regle_webhook = AutomationRule.objects.create(
            company=self.co, nom='Webhook', enabled=True,
            trigger_type=TriggerType.WEBHOOK_INBOUND, trigger_config={},
            action_type=ActionType.WAIT, action_config={})

    def _lignes(self):
        return SettingsAuditLog.objects.filter(
            company=self.co, section='automatisations')

    def _geste(self, nom, appel, attendu_status):
        avant = self._lignes().count()
        res = appel()
        self.assertEqual(res.status_code, attendu_status,
                         f'{nom} : {getattr(res, "data", res)}')
        self.assertEqual(self._lignes().count(), avant + 1,
                         f'route non journalisée : {nom}')
        ligne = self._lignes().order_by('-id').first()
        self.assertEqual(ligne.user_id, self.admin.pk, nom)
        return res

    def test_chaque_route_d_ecriture_de_configuration_journalise(self):
        api = self.api
        self._geste('modeles-catalogue/installer', lambda: api.post(
            f'{BASE}modeles-catalogue/installer/relance_j3_devis_sans_reponse/',
            {}, format='json'), 201)

        res = self._geste('incoming-webhooks (création)', lambda: api.post(
            f'{BASE}incoming-webhooks/',
            {'rule': self.regle_webhook.pk, 'hmac_secret': SECRET},
            format='json'), 201)
        pk = res.data['id']
        self._geste('incoming-webhooks (modification)', lambda: api.patch(
            f'{BASE}incoming-webhooks/{pk}/', {'enabled': False},
            format='json'), 200)
        jeton_avant = IncomingWebhookTrigger.objects.get(pk=pk).token
        self._geste('incoming-webhooks/rotate', lambda: api.post(
            f'{BASE}incoming-webhooks/{pk}/rotate/', {}, format='json'), 200)
        jeton_apres = IncomingWebhookTrigger.objects.get(pk=pk).token
        self._geste('incoming-webhooks (suppression)', lambda: api.delete(
            f'{BASE}incoming-webhooks/{pk}/'), 204)

        creer_version_automation_rule(self.regle_webhook, auteur=self.admin)
        version = AutomationRuleVersion.objects.filter(
            rule=self.regle_webhook).order_by('-id').first()
        self._geste('rule-versions/restaurer', lambda: api.post(
            f'{BASE}rule-versions/{version.pk}/restaurer/', {},
            format='json'), 200)

        res = self._geste('approval-request-types (création)', lambda: api.post(
            f'{BASE}approval-request-types/', {'nom': 'Achat'},
            format='json'), 201)
        tid = res.data['id']
        self._geste('approval-request-types (modification)', lambda: api.patch(
            f'{BASE}approval-request-types/{tid}/', {'nom': 'Achat > 5k'},
            format='json'), 200)
        self._geste('approval-request-types (suppression)', lambda: api.delete(
            f'{BASE}approval-request-types/{tid}/'), 204)

        # Jamais le secret ni le jeton en clair dans le journal.
        for ligne in self._lignes():
            texte = f'{ligne.old_value} {ligne.new_value}'
            self.assertNotIn(SECRET, texte)
            self.assertNotIn(jeton_avant, texte)
            self.assertNotIn(jeton_apres, texte)
        rotation = self._lignes().get(
            field_label='Jeton du webhook entrant régénéré')
        self.assertTrue(rotation.old_value.startswith('••••'))
        self.assertTrue(rotation.new_value.startswith('••••'))

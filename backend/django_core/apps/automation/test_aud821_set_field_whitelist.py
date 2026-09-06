"""AUD821 — registre FERMÉ des champs assignables par l'action ``SET_FIELD``.

Défaut corrigé : ``actions._set_field`` n'excluait QUE ``company``/
``company_id``/``prix_achat`` en dur, puis faisait ``setattr`` +
``save(update_fields=[…])`` sur N'IMPORTE QUEL champ du modèle déclencheur — en
contournant ``full_clean`` ET la machine à états. ``serializers.validate()`` ne
validait QUE ``trigger_config``, jamais ``action_config``. Un Admin pouvait donc
configurer ``{"field": "statut", "value": "accepte"}`` sur un Devis : le champ
basculait en base sans passer par ``DevisWriteSerializer``/``machine_etats`` et
sans émettre ``devis_accepted`` — le Chantier n'était jamais créé, mais tout
l'aval croyait la transition faite. La LECTURE avait pourtant déjà son registre
fermé (``list_sources.SOURCES``) ; l'ÉCRITURE n'en avait aucun.

Test ROUGE d'abord — sur l'arbre d'avant AUD821 :
  * ``POST /api/django/automation/rules/`` avec
    ``action_config={'field': 'statut'}`` renvoyait 201 ;
  * la règle exécutée écrivait réellement le champ.

Après : refus à la CRÉATION (400, message français) et refus DÉFENSIF à
l'exécution (statut ``skipped``, aucune écriture) pour les règles héritées.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.automation import engine
from apps.automation.actions import (
    SET_FIELD_TARGETS, set_field_autorise, set_field_champs_autorises,
    set_field_targets,
)
from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, TriggerType,
)
from apps.crm.models import Lead
from authentication.models import Company

User = get_user_model()

URL_RULES = '/api/django/automation/rules/'

# Champs interdits par CONSTRUCTION : machine à états et argent.
CHAMPS_INTERDITS = ('statut', 'stage', 'perdu', 'is_archived', 'annule',
                    'montant_estime', 'prix_achat', 'company')


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RegistreFermeTests(SimpleTestCase):
    """Le registre est FERMÉ et n'admet aucun champ dangereux."""

    def test_aucun_champ_de_machine_a_etats_ni_financier(self):
        for cle, champs in SET_FIELD_TARGETS.items():
            for interdit in CHAMPS_INTERDITS:
                self.assertNotIn(
                    interdit, champs,
                    f'{cle} : « {interdit} » ne peut jamais être assignable '
                    'par une automatisation.')
            for champ in champs:
                self.assertFalse(
                    champ.startswith(('montant', 'prix', 'total', 'remise',
                                      'taux', 'acompte', 'cout')),
                    f'{cle}.{champ} ressemble à un champ financier.')

    def test_registre_renvoie_une_copie_defensive(self):
        copie = set_field_targets()
        copie.setdefault('crm.lead', set()).add('statut')
        self.assertFalse(set_field_autorise('crm.lead', 'statut'))

    def test_autorisation_par_couple_modele_champ(self):
        self.assertTrue(set_field_autorise('crm.lead', 'priorite'))
        self.assertTrue(set_field_autorise('CRM.Lead', 'priorite'))
        # Un champ sûr sur un modèle ne l'est pas sur un autre.
        self.assertFalse(set_field_autorise('ventes.devis', 'priorite'))
        self.assertFalse(set_field_autorise('inconnu.modele', 'priorite'))

    def test_union_des_champs_declares(self):
        union = set_field_champs_autorises()
        self.assertIn('priorite', union)
        for interdit in CHAMPS_INTERDITS:
            self.assertNotIn(interdit, union)


class ValidationCreationTests(TestCase):
    """Refus à la CRÉATION de la règle (API)."""

    def setUp(self):
        self.co = make_company('aud821-co', 'AUD821')
        self.admin = make_user(self.co, 'aud821-admin')
        self.api = auth(self.admin)

    def _payload(self, action_config):
        return {
            'nom': 'Règle AUD821',
            'trigger_type': TriggerType.LEAD_STAGE_CHANGE,
            'trigger_config': {},
            'action_type': ActionType.SET_FIELD,
            'action_config': action_config,
        }

    def test_champ_de_machine_a_etats_refuse(self):
        resp = self.api.post(
            URL_RULES, self._payload({'field': 'statut', 'value': 'accepte'}),
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('action_config', resp.data)

    def test_champ_financier_refuse(self):
        resp = self.api.post(
            URL_RULES,
            self._payload({'field': 'montant_ttc', 'value': 0}),
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_champ_manquant_refuse(self):
        resp = self.api.post(
            URL_RULES, self._payload({'value': 'x'}), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_action_config_malforme_donne_400_pas_500(self):
        """`action_config` est du JSON libre : un `field` non-textuel est un 400."""
        for config in ({'field': 42, 'value': 'x'}, {'field': ['a'], 'value': 1}):
            resp = self.api.post(
                URL_RULES, self._payload(config), format='json')
            self.assertEqual(resp.status_code, 400, resp.data)

    def test_couple_modele_champ_explicite_refuse(self):
        """`priorite` est sûr sur crm.lead, pas sur ventes.devis."""
        resp = self.api.post(
            URL_RULES,
            self._payload({'model': 'ventes.devis', 'field': 'priorite',
                           'value': 'haute'}),
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_champ_declare_accepte(self):
        resp = self.api.post(
            URL_RULES,
            self._payload({'field': 'priorite', 'value': 'haute'}),
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_une_regle_heritee_dangereuse_reste_desactivable(self):
        """Un PATCH partiel ne revalide pas l'action : on peut couper la règle.

        Refuser ce PATCH empêcherait de DÉSACTIVER une règle héritée au champ
        interdit — exactement l'inverse du but d'AUD821.
        """
        regle = AutomationRule.objects.create(
            company=self.co, nom='Héritée dangereuse',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.SET_FIELD,
            action_config={'field': 'stage', 'value': 'SIGNED'}, enabled=True)
        resp = self.api.patch(
            f'{URL_RULES}{regle.pk}/', {'enabled': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        regle.refresh_from_db()
        self.assertFalse(regle.enabled)

    def test_modifier_laction_dune_regle_heritee_revalide(self):
        regle = AutomationRule.objects.create(
            company=self.co, nom='Héritée dangereuse 2',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.SET_FIELD,
            action_config={'field': 'stage', 'value': 'SIGNED'}, enabled=True)
        resp = self.api.patch(
            f'{URL_RULES}{regle.pk}/',
            {'action_config': {'field': 'statut', 'value': 'accepte'}},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_les_autres_actions_restent_inchangees(self):
        payload = self._payload({})
        payload['action_type'] = ActionType.CREATE_ACTIVITY
        payload['action_config'] = {'body': 'Rappeler le client'}
        resp = self.api.post(URL_RULES, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)


class RefusDefensifExecutionTests(TestCase):
    """Refus à l'EXÉCUTION pour une règle héritée (créée hors API)."""

    def setUp(self):
        self.co = make_company('aud821-exec', 'AUD821 exec')

    def _regle(self, action_config):
        return AutomationRule.objects.create(
            company=self.co, nom='Héritée',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.SET_FIELD, action_config=action_config)

    def test_champ_hors_registre_refuse_sans_ecriture(self):
        regle = self._regle({'field': 'stage', 'value': 'CONTACTED'})
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        status, message = engine.run_action(regle, lead, self.co)
        self.assertEqual(status, AutomationRun.Status.SKIPPED)
        self.assertIn('hors du registre', message)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'NEW')

    def test_champ_financier_refuse_sans_ecriture(self):
        regle = self._regle({'field': 'montant_estime', 'value': 1})
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        avant = lead.montant_estime
        status, _ = engine.run_action(regle, lead, self.co)
        self.assertEqual(status, AutomationRun.Status.SKIPPED)
        lead.refresh_from_db()
        self.assertEqual(lead.montant_estime, avant)

    def test_champ_declare_ecrit_toujours(self):
        regle = self._regle({'field': 'priorite', 'value': 'haute'})
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        status, _ = engine.run_action(regle, lead, self.co)
        self.assertEqual(status, AutomationRun.Status.SUCCESS)
        lead.refresh_from_db()
        self.assertEqual(lead.priorite, 'haute')

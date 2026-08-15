"""NTEXT36 — audit des changements de plateforme (section='plateforme').

Créer/modifier/supprimer un objet personnalisé, une règle d'automatisation ou
une définition de rapport laisse une trace horodatée (qui/quoi/quand) dans le
Journal d'audit des paramètres.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.automation.models import ActionType, AutomationRule, TriggerType
from apps.customfields.audit_plateforme import SECTION_PLATEFORME
from apps.parametres.models import SettingsAuditLog
from apps.reporting.models import RapportDefinition

User = get_user_model()


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AuditPlateformeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT36 Co')
        self.admin = User.objects.create_user(
            username='ntext36_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = _auth(self.admin)

    def _lignes(self, cible=None):
        qs = SettingsAuditLog.objects.filter(
            company=self.company, section=SECTION_PLATEFORME)
        if cible:
            qs = qs.filter(field__startswith=f'{cible}:')
        return list(qs)

    # ── Objets personnalisés ───────────────────────────────────────────────

    def test_objet_custom_cree_modifie_supprime_est_audite(self):
        res = self.api.post(
            '/api/django/custom-fields/objects/',
            {'code': 'visiteurs', 'libelle': 'Visiteurs'}, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        objet_id = res.data['id']

        res = self.api.patch(
            f'/api/django/custom-fields/objects/{objet_id}/',
            {'libelle': 'Visiteurs du site'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)

        res = self.api.delete(
            f'/api/django/custom-fields/objects/{objet_id}/')
        self.assertEqual(res.status_code, 204)

        lignes = self._lignes('objet')
        self.assertEqual(len(lignes), 3)
        labels = [ligne.field_label for ligne in lignes]
        self.assertIn('Objet personnalisé créé', labels)
        self.assertIn('Objet personnalisé modifié', labels)
        self.assertIn('Objet personnalisé supprimé', labels)
        for ligne in lignes:
            # qui / quoi / quand.
            self.assertEqual(ligne.user, self.admin)
            self.assertEqual(ligne.field, 'objet:visiteurs')
            self.assertIsNotNone(ligne.timestamp)
        modif = next(x for x in lignes
                     if x.field_label == 'Objet personnalisé modifié')
        self.assertEqual(modif.old_value, 'Visiteurs')
        self.assertEqual(modif.new_value, 'Visiteurs du site')

    # ── Règles d'automatisation (critère de la tâche) ──────────────────────

    def test_modifier_une_regle_laisse_une_trace_plateforme(self):
        regle = AutomationRule.objects.create(
            company=self.company, nom='Relance J+3',
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.SET_FIELD,
            action_config={'field': 'priorite', 'value': 'haute'})

        res = self.api.patch(
            f'/api/django/automation/rules/{regle.pk}/',
            {'nom': 'Relance J+5'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)

        lignes = self._lignes('regle')
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0].field_label,
                         "Règle d'automatisation modifiée")
        self.assertEqual(lignes[0].user, self.admin)
        self.assertIn('Relance J+3', lignes[0].old_value)
        self.assertIn('Relance J+5', lignes[0].new_value)

        # L'audit HISTORIQUE (section='automatisations') reste intact.
        self.assertTrue(SettingsAuditLog.objects.filter(
            company=self.company, section='automatisations').exists())

    # ── Définitions de rapport ─────────────────────────────────────────────

    def test_rapport_supprime_est_audite(self):
        rapport = RapportDefinition.objects.create(
            company=self.company, owner=self.admin, titre='CA mensuel',
            dataset='vitals', spec={})
        res = self.api.delete(
            f'/api/django/reporting/rapport-definitions/{rapport.pk}/')
        self.assertEqual(res.status_code, 204)

        lignes = self._lignes('rapport')
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0].field_label,
                         'Définition de rapport supprimée')
        self.assertEqual(lignes[0].old_value, 'CA mensuel')

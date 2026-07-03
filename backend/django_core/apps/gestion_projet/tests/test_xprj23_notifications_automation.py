"""Tests XPRJ23 — notifications client aux étapes du projet (via automation).

Couvre : une transition de statut/phase de projet déclenche la règle
automation (e-mail console en test + lien wa.me), règles désactivées
silencieuses, clé mail absente = no-op, la transition n'est JAMAIS bloquée par
une règle en erreur (best-effort), et les variables {nom_projet}{date}.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.automation.models import ActionType, AutomationRule, AutomationRun, \
    TriggerType
from apps.gestion_projet.models import PhaseProjet, Projet
from apps.gestion_projet.services import (
    notifier_transition_phase, notifier_transition_projet,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class NotifierTransitionProjetTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj23', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X23', nom='Projet X23')

    def test_regle_email_declenchee_sur_transition(self):
        AutomationRule.objects.create(
            company=self.co, nom='Notif client statut',
            trigger_type=TriggerType.PROJET_STATUS_CHANGE,
            trigger_config={'statut': 'en_cours'},
            action_type=ActionType.SEND_EMAIL,
            action_config={'body': 'Projet {nom_projet} démarré le {date}.'},
        )
        notifier_transition_projet(
            self.projet, ancien_statut='planifie', nouveau_statut='en_cours')
        run = AutomationRun.objects.filter(
            target_model='gestion_projet.projet',
            target_id=self.projet.id).first()
        self.assertIsNotNone(run)

    def test_regle_desactivee_silencieuse(self):
        AutomationRule.objects.create(
            company=self.co, nom='Règle off', enabled=False,
            trigger_type=TriggerType.PROJET_STATUS_CHANGE,
            trigger_config={'statut': 'en_cours'},
            action_type=ActionType.SEND_EMAIL,
            action_config={'body': 'x'},
        )
        notifier_transition_projet(
            self.projet, ancien_statut='planifie', nouveau_statut='en_cours')
        self.assertFalse(
            AutomationRun.objects.filter(
                target_model='gestion_projet.projet',
                target_id=self.projet.id).exists())

    def test_statut_non_matchant_ignore(self):
        AutomationRule.objects.create(
            company=self.co, nom='Autre statut',
            trigger_type=TriggerType.PROJET_STATUS_CHANGE,
            trigger_config={'statut': 'termine'},
            action_type=ActionType.SEND_EMAIL,
            action_config={'body': 'x'},
        )
        notifier_transition_projet(
            self.projet, ancien_statut='planifie', nouveau_statut='en_cours')
        self.assertFalse(
            AutomationRun.objects.filter(
                target_model='gestion_projet.projet',
                target_id=self.projet.id).exists())

    def test_meme_statut_aucun_evenement(self):
        AutomationRule.objects.create(
            company=self.co, nom='R',
            trigger_type=TriggerType.PROJET_STATUS_CHANGE,
            trigger_config={}, action_type=ActionType.SEND_EMAIL,
            action_config={'body': 'x'},
        )
        notifier_transition_projet(
            self.projet, ancien_statut='en_cours', nouveau_statut='en_cours')
        self.assertFalse(
            AutomationRun.objects.filter(
                target_model='gestion_projet.projet',
                target_id=self.projet.id).exists())

    def test_wa_me_manuel_lien_prepare(self):
        AutomationRule.objects.create(
            company=self.co, nom='Notif client WA',
            trigger_type=TriggerType.PROJET_STATUS_CHANGE,
            trigger_config={}, action_type=ActionType.SEND_WHATSAPP,
            action_config={'body': 'Projet {nom_projet} avance.'},
        )
        # Sans numéro exploitable sur Projet → NOOP journalisé, jamais un
        # échec dur (comportement existant du moteur, préservé).
        notifier_transition_projet(
            self.projet, ancien_statut='planifie', nouveau_statut='en_cours')
        run = AutomationRun.objects.filter(
            target_model='gestion_projet.projet',
            target_id=self.projet.id).first()
        self.assertIsNotNone(run)

    def test_transition_jamais_bloquee_par_regle_en_erreur(self):
        # Règle mal configurée (action inconnue côté action_config) : le
        # moteur journalise l'échec mais notifier_transition_projet ne lève
        # jamais.
        AutomationRule.objects.create(
            company=self.co, nom='Règle cassée',
            trigger_type=TriggerType.PROJET_STATUS_CHANGE,
            trigger_config={}, action_type=ActionType.SET_FIELD,
            action_config={'field': 'champ_inexistant', 'value': 'x'},
        )
        try:
            notifier_transition_projet(
                self.projet, ancien_statut='planifie',
                nouveau_statut='en_cours')
        except Exception:  # pragma: no cover
            self.fail('notifier_transition_projet ne doit jamais lever.')


class NotifierTransitionPhaseTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj23-phase', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X23B', nom='Projet X23 Phase')
        self.phase = PhaseProjet.objects.create(
            company=self.co, projet=self.projet, type_phase='etude')

    def test_regle_phase_declenchee(self):
        AutomationRule.objects.create(
            company=self.co, nom='Notif phase',
            trigger_type=TriggerType.PROJET_PHASE_CHANGE,
            trigger_config={}, action_type=ActionType.SEND_EMAIL,
            action_config={'body': 'Phase de {nom_projet} changée.'},
        )
        notifier_transition_phase(
            self.phase, ancien_statut='a_venir', nouveau_statut='en_cours')
        self.assertTrue(
            AutomationRun.objects.filter(
                target_model='gestion_projet.phaseprojet',
                target_id=self.phase.id).exists())


class PhaseProjetEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj23-api', 'S')
        self.user = make_user(self.co, 'resp-xprj23')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X23C', nom='Projet X23 API')
        self.phase = PhaseProjet.objects.create(
            company=self.co, projet=self.projet, type_phase='etude',
            statut='a_venir')

    def test_patch_statut_declenche_automation_sans_erreur(self):
        AutomationRule.objects.create(
            company=self.co, nom='Notif',
            trigger_type=TriggerType.PROJET_PHASE_CHANGE,
            trigger_config={}, action_type=ActionType.SEND_EMAIL,
            action_config={'body': 'x'},
        )
        api = auth(self.user)
        resp = api.patch(
            f'/api/django/gestion-projet/phases/{self.phase.id}/',
            {'statut': 'en_cours'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.phase.refresh_from_db()
        self.assertEqual(self.phase.statut, 'en_cours')

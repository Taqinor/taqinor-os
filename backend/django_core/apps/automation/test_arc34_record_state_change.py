"""ARC34 — Déclencheur automation générique ``RECORD_STATE_CHANGE``.

Couvre :
- la whitelist PILOTÉE PAR LE REGISTRE (``record_state_change_targets()`` lit
  les ``automation_state_fields`` des manifestes plateforme — pilotes
  ``contrats.contrat:statut`` et ``sav.ticket:statut``) ;
- la VALIDATION à la création de règle (couple non whitelisté → 400 FR ;
  modèle/champ manquant → 400 ; arbre de conditions invalide → 400 ; les
  autres types de déclencheurs restent créables sans validation ajoutée) ;
- le PILOTE Contrat : règle no-code → transition de statut via
  ``apps.contrats.services.changer_statut`` → action notifier (email)
  réellement exécutée (mail.outbox + run SUCCESS) ;
- le PILOTE Ticket SAV : règle no-code → transition gardée via l'action de vue
  ``demarrer`` (chemin de PRODUCTION complet) → action notifier exécutée ;
- les CONDITIONS du trigger réutilisent l'évaluateur d'arbre FG367
  (``core.rules``) sur le contexte plat ;
- le catalogue EXISTANT reste intouché (``DATE_TRIGGER_TARGETS`` littéral, tous
  les TriggerType antérieurs présents) et l'isolation par société tient.
"""
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, DATE_TRIGGER_TARGETS,
    TriggerType, record_state_change_targets,
)

User = get_user_model()

URL_RULES = '/api/django/automation/rules/'


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


class WhitelistRegistreTests(TestCase):
    """La whitelist du trigger générique vient du REGISTRE plateforme."""

    def test_pilotes_declares(self):
        targets = record_state_change_targets()
        self.assertIn('statut', targets.get('contrats.contrat', set()))
        self.assertIn('statut', targets.get('sav.ticket', set()))

    def test_couple_non_declare_absent(self):
        targets = record_state_change_targets()
        self.assertNotIn('statut', targets.get('ventes.devis', set()))


class CreationRegleValidationTests(TestCase):
    """Serializer : couple (modèle, champ) hors whitelist → 400 FR."""

    def setUp(self):
        self.co = make_company('arc34-val', 'ARC34 Val')
        self.api = auth(make_user(self.co, 'arc34-val-admin'))

    def _post_rule(self, trigger_config):
        return self.api.post(URL_RULES, {
            'nom': 'Règle ARC34',
            'trigger_type': TriggerType.RECORD_STATE_CHANGE,
            'trigger_config': trigger_config,
            'action_type': ActionType.SEND_EMAIL,
            'action_config': {'body': 'Statut changé.'},
        }, format='json')

    def test_couple_whiteliste_accepte(self):
        resp = self._post_rule({'model': 'contrats.contrat', 'field': 'statut'})
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_couple_non_whiteliste_refuse(self):
        resp = self._post_rule({'model': 'ventes.devis', 'field': 'statut'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('non autorisé', str(resp.data))

    def test_modele_ou_champ_manquant_refuse(self):
        self.assertEqual(self._post_rule({}).status_code, 400)
        self.assertEqual(
            self._post_rule({'model': 'contrats.contrat'}).status_code, 400)
        self.assertEqual(
            self._post_rule({'field': 'statut'}).status_code, 400)

    def test_conditions_invalides_refusees(self):
        resp = self._post_rule({
            'model': 'sav.ticket', 'field': 'statut',
            'conditions': {'op': 'bidon', 'conditions': []},
        })
        self.assertEqual(resp.status_code, 400)

    def test_conditions_valides_acceptees(self):
        resp = self._post_rule({
            'model': 'sav.ticket', 'field': 'statut',
            'conditions': {'field': 'new_value', 'operator': 'eq',
                           'value': 'en_cours'},
        })
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_autres_triggers_inchanges(self):
        # Non-régression : la validation ARC34 ne touche pas les types
        # existants (aucune whitelist exigée pour LEAD_STAGE_CHANGE).
        resp = self.api.post(URL_RULES, {
            'nom': 'Règle lead',
            'trigger_type': TriggerType.LEAD_STAGE_CHANGE,
            'trigger_config': {'stage': 'SIGNED'},
            'action_type': ActionType.CREATE_ACTIVITY,
            'action_config': {'body': 'ok'},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)


class PiloteContratTests(TestCase):
    """Pilote 1 : statut Contrat déclenchable par une règle no-code."""

    def setUp(self):
        self.co = make_company('arc34-ctr', 'ARC34 Ctr')
        self.user = make_user(self.co, 'arc34-ctr-admin')

    def _make_contrat(self, statut):
        from apps.contrats.models import Contrat
        return Contrat.objects.create(
            company=self.co, objet='Maintenance PV', reference='ARC34-CTR-1',
            statut=statut)

    def test_regle_notifier_executee_sur_transition(self):
        from apps.contrats.models import Contrat
        from apps.contrats.services import changer_statut

        AutomationRule.objects.create(
            company=self.co, nom='Notifier suspension',
            trigger_type=TriggerType.RECORD_STATE_CHANGE,
            trigger_config={'model': 'contrats.contrat', 'field': 'statut',
                            'value': Contrat.Statut.SUSPENDU},
            action_type=ActionType.SEND_EMAIL,
            action_config={'body': 'Contrat suspendu.',
                           'subject': 'Alerte contrat'})
        contrat = self._make_contrat(Contrat.Statut.ACTIF)
        # Le Contrat n'expose pas d'email (client_id découplé) : on pose
        # l'attribut d'instance pour prouver le CANAL notifier de bout en bout
        # (résolution _resolve_email → send_mail → outbox), via le vrai chemin
        # service → engine → action.
        contrat.email = 'client-arc34@test.ma'

        changer_statut(contrat, Contrat.Statut.SUSPENDU, user=self.user)

        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.SUSPENDU)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['client-arc34@test.ma'])
        run = AutomationRun.objects.filter(company=self.co).first()
        self.assertIsNotNone(run)
        self.assertEqual(run.status, AutomationRun.Status.SUCCESS)
        self.assertEqual(run.target_model, 'contrats.contrat')

    def test_valeur_differente_ne_declenche_pas(self):
        from apps.contrats.models import Contrat
        from apps.contrats.services import changer_statut

        AutomationRule.objects.create(
            company=self.co, nom='Notifier suspension seulement',
            trigger_type=TriggerType.RECORD_STATE_CHANGE,
            trigger_config={'model': 'contrats.contrat', 'field': 'statut',
                            'value': Contrat.Statut.SUSPENDU},
            action_type=ActionType.SEND_EMAIL,
            action_config={'body': 'x'})
        contrat = self._make_contrat(Contrat.Statut.ACTIF)
        contrat.email = 'x@test.ma'

        changer_statut(contrat, Contrat.Statut.EXPIRE, user=self.user)

        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(AutomationRun.objects.filter(company=self.co).exists())

    def test_conditions_fg367_sur_contexte(self):
        # L'arbre de conditions (core.rules, FG367) filtre sur le contexte
        # plat : ne déclenche que si l'ANCIEN statut était « actif ».
        from apps.contrats.models import Contrat
        from apps.contrats.services import changer_statut

        AutomationRule.objects.create(
            company=self.co, nom='Suspension depuis actif seulement',
            trigger_type=TriggerType.RECORD_STATE_CHANGE,
            trigger_config={
                'model': 'contrats.contrat', 'field': 'statut',
                'conditions': {'op': 'and', 'conditions': [
                    {'field': 'old_value', 'operator': 'eq',
                     'value': Contrat.Statut.ACTIF},
                    {'field': 'new_value', 'operator': 'eq',
                     'value': Contrat.Statut.SUSPENDU},
                ]},
            },
            action_type=ActionType.SEND_EMAIL,
            action_config={'body': 'Suspendu depuis actif.'})

        # Cas non matché : brouillon → résilié (conditions False).
        c1 = self._make_contrat(Contrat.Statut.BROUILLON)
        c1.email = 'c1@test.ma'
        changer_statut(c1, Contrat.Statut.RESILIE, user=self.user)
        self.assertEqual(len(mail.outbox), 0)

        # Cas matché : actif → suspendu.
        from apps.contrats.models import Contrat as C
        c2 = C.objects.create(
            company=self.co, objet='2e contrat', reference='ARC34-CTR-2',
            statut=C.Statut.ACTIF)
        c2.email = 'c2@test.ma'
        changer_statut(c2, C.Statut.SUSPENDU, user=self.user)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['c2@test.ma'])

    def test_isolation_societe(self):
        # Une règle d'une AUTRE société ne se déclenche jamais.
        from apps.contrats.models import Contrat
        from apps.contrats.services import changer_statut

        autre = make_company('arc34-autre', 'ARC34 Autre')
        AutomationRule.objects.create(
            company=autre, nom='Règle autre société',
            trigger_type=TriggerType.RECORD_STATE_CHANGE,
            trigger_config={'model': 'contrats.contrat', 'field': 'statut'},
            action_type=ActionType.SEND_EMAIL, action_config={'body': 'x'})
        contrat = self._make_contrat(Contrat.Statut.ACTIF)
        contrat.email = 'iso@test.ma'
        changer_statut(contrat, Contrat.Statut.SUSPENDU, user=self.user)
        self.assertEqual(len(mail.outbox), 0)


class PiloteTicketSavTests(TestCase):
    """Pilote 2 : statut Ticket SAV déclenchable — chemin de PRODUCTION
    complet (action de vue gardée ``demarrer`` → machine d'états →
    ``services.emettre_changement_statut_ticket`` → moteur → notifier)."""

    def setUp(self):
        self.co = make_company('arc34-sav', 'ARC34 Sav')
        self.user = make_user(self.co, 'arc34-sav-admin')
        self.api = auth(self.user)

    def test_regle_notifier_executee_sur_demarrer(self):
        from apps.crm.models import Client
        from apps.sav.models import Ticket

        AutomationRule.objects.create(
            company=self.co, nom='Notifier démarrage ticket',
            trigger_type=TriggerType.RECORD_STATE_CHANGE,
            trigger_config={'model': 'sav.ticket', 'field': 'statut',
                            'value': Ticket.Statut.EN_COURS},
            action_type=ActionType.SEND_EMAIL,
            action_config={'body': 'Intervention démarrée.'})
        client = Client.objects.create(
            company=self.co, nom='Client SAV', email='sav-arc34@test.ma')
        ticket = Ticket.objects.create(
            company=self.co, reference='ARC34-SAV-1', client=client,
            statut=Ticket.Statut.NOUVEAU, description='Panne onduleur')

        resp = self.api.post(
            f'/api/django/sav/tickets/{ticket.pk}/demarrer/')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))

        ticket.refresh_from_db()
        self.assertEqual(ticket.statut, Ticket.Statut.EN_COURS)
        emails_regle = [m for m in mail.outbox
                        if m.to == ['sav-arc34@test.ma']]
        self.assertEqual(len(emails_regle), 1)
        run = AutomationRun.objects.filter(
            company=self.co, target_model='sav.ticket').first()
        self.assertIsNotNone(run)
        self.assertEqual(run.status, AutomationRun.Status.SUCCESS)


class CatalogueExistantIntoucheTests(SimpleTestCase):
    """Le catalogue FERMÉ existant reste intouché par ARC34."""

    def test_date_trigger_targets_litteral_inchange(self):
        self.assertEqual(set(DATE_TRIGGER_TARGETS), {
            ('ventes', 'devis'), ('crm', 'lead'),
        })
        self.assertEqual(
            set(DATE_TRIGGER_TARGETS[('ventes', 'devis')]), {'date_validite'})
        self.assertEqual(
            set(DATE_TRIGGER_TARGETS[('crm', 'lead')]), {'relance_date'})

    def test_trigger_types_anterieurs_presents(self):
        valeurs = set(TriggerType.values)
        for ancien in ('lead_stage_change', 'devis_accepted',
                       'chantier_status', 'facture_overdue',
                       'warranty_expiring', 'maintenance_due',
                       'stock_below_threshold', 'date_echeance_champ',
                       'webhook_inbound', 'projet_status_change',
                       'projet_phase_change'):
            self.assertIn(ancien, valeurs, ancien)
        self.assertIn('record_state_change', valeurs)

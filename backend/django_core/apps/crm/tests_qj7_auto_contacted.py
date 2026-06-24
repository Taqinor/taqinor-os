"""QJ7 — Avance automatique NEW → CONTACTED au premier contact.

Tests :
  - la première activité NOTE/APPEL/EMAIL sur un lead NEW avance l'étape
    vers CONTACTED (une seule fois) ;
  - une deuxième activité de contact ne rechange plus l'étape ;
  - un lead déjà à QUOTE_SENT n'est pas régressé ;
  - un lead perdu n'est jamais touché ;
  - une activité CREATION ou MODIFICATION ne déclenche pas l'avancée ;
  - périmètre multi-tenant : deux sociétés restent indépendantes.

Les clés d'étape suivent la convention des tests existants : clés canoniques
depuis STAGES.py (NEW, CONTACTED, QUOTE_SENT) — jamais hardcodées.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Lead, LeadActivity
from apps.crm.services import avancer_stage_new_vers_contacted

# Clés canoniques importées depuis le module CRM (re-exports STAGES.py).
from apps.crm.stages import NEW, STAGE_LABELS

User = get_user_model()

# Clés non re-exportées par stages.py : on les déclare ici à partir des valeurs
# STAGES.py (identiques aux constantes dans STAGES.py).
_CONTACTED = 'CONTACTED'
_QUOTE_SENT = 'QUOTE_SENT'


def _make_company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _make_user(company, username):
    return User.objects.create_user(
        username=username, password='x',
        role_legacy='responsable', company=company)


def _make_lead(company, stage=None, perdu=False):
    return Lead.objects.create(
        company=company,
        nom='Test Lead',
        stage=stage or NEW,
        perdu=perdu,
    )


class TestAvancerStageNewVersContactedService(TestCase):
    """Tests unitaires du service ``avancer_stage_new_vers_contacted``."""

    def setUp(self):
        self.company = _make_company('qj7-svc')
        self.user = _make_user(self.company, 'qj7u')

    def test_new_lead_avances_to_contacted(self):
        lead = _make_lead(self.company, stage=NEW)
        result = avancer_stage_new_vers_contacted(lead, self.user)
        self.assertTrue(result)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, _CONTACTED)

    def test_historique_automatique_ecrit(self):
        lead = _make_lead(self.company, stage=NEW)
        avancer_stage_new_vers_contacted(lead, self.user)
        auto = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.MODIFICATION,
            field='stage').first()
        self.assertIsNotNone(auto)
        self.assertEqual(auto.old_value, STAGE_LABELS[NEW])
        self.assertEqual(auto.new_value, STAGE_LABELS[_CONTACTED])
        self.assertIn('premier contact', auto.body)

    def test_lead_already_contacted_idempotent(self):
        lead = _make_lead(self.company, stage=_CONTACTED)
        result = avancer_stage_new_vers_contacted(lead, self.user)
        self.assertFalse(result)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, _CONTACTED)

    def test_lead_quote_sent_not_regressed(self):
        lead = _make_lead(self.company, stage=_QUOTE_SENT)
        result = avancer_stage_new_vers_contacted(lead, self.user)
        self.assertFalse(result)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, _QUOTE_SENT)

    def test_perdu_lead_untouched(self):
        lead = _make_lead(self.company, stage=NEW, perdu=True)
        result = avancer_stage_new_vers_contacted(lead, self.user)
        self.assertFalse(result)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, NEW)


class TestQJ7ReceiverOnLeadActivity(TestCase):
    """Tests d'intégration : post_save sur LeadActivity déclenche l'avancée."""

    def setUp(self):
        self.company = _make_company('qj7-rcv')
        self.user = _make_user(self.company, 'qj7rcv')

    def test_first_note_advances_new_to_contacted(self):
        lead = _make_lead(self.company, stage=NEW)
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.user,
            kind=LeadActivity.Kind.NOTE,
            body='Premier appel passé',
        )
        lead.refresh_from_db()
        self.assertEqual(lead.stage, _CONTACTED)

    def test_first_appel_advances_new_to_contacted(self):
        lead = _make_lead(self.company, stage=NEW)
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.user,
            kind=LeadActivity.Kind.APPEL,
            body='Appel commercial',
        )
        lead.refresh_from_db()
        self.assertEqual(lead.stage, _CONTACTED)

    def test_first_email_advances_new_to_contacted(self):
        lead = _make_lead(self.company, stage=NEW)
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.user,
            kind=LeadActivity.Kind.EMAIL,
            body='Email envoyé',
        )
        lead.refresh_from_db()
        self.assertEqual(lead.stage, _CONTACTED)

    def test_second_contact_activity_does_not_change_stage(self):
        lead = _make_lead(self.company, stage=NEW)
        # Premier contact → avance vers CONTACTED
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.user,
            kind=LeadActivity.Kind.NOTE,
            body='Premier contact',
        )
        lead.refresh_from_db()
        self.assertEqual(lead.stage, _CONTACTED)
        stage_before = lead.stage
        # Deuxième contact → rien ne change
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.user,
            kind=LeadActivity.Kind.NOTE,
            body='Deuxième contact',
        )
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stage_before)

    def test_creation_activity_does_not_advance_stage(self):
        lead = _make_lead(self.company, stage=NEW)
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.user,
            kind=LeadActivity.Kind.CREATION,
            body='Lead créé',
        )
        lead.refresh_from_db()
        self.assertEqual(lead.stage, NEW)

    def test_modification_activity_does_not_advance_stage(self):
        lead = _make_lead(self.company, stage=NEW)
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.user,
            kind=LeadActivity.Kind.MODIFICATION,
            field='nom',
            body='Modification',
        )
        lead.refresh_from_db()
        self.assertEqual(lead.stage, NEW)

    def test_quote_sent_lead_not_regressed(self):
        lead = _make_lead(self.company, stage=_QUOTE_SENT)
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.user,
            kind=LeadActivity.Kind.NOTE,
            body='Note sur lead déjà avancé',
        )
        lead.refresh_from_db()
        self.assertEqual(lead.stage, _QUOTE_SENT)

    def test_perdu_lead_untouched_by_activity(self):
        lead = _make_lead(self.company, stage=NEW, perdu=True)
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.user,
            kind=LeadActivity.Kind.NOTE,
            body='Note sur lead perdu',
        )
        lead.refresh_from_db()
        self.assertEqual(lead.stage, NEW)
        self.assertTrue(lead.perdu)

    def test_company_scoping_other_company_lead_unaffected(self):
        """Deux sociétés : une activité dans la société A n'affecte pas la société B."""
        company_b = _make_company('qj7-co-b')
        lead_a = _make_lead(self.company, stage=NEW)
        lead_b = _make_lead(company_b, stage=NEW)
        # Activité dans la société A
        LeadActivity.objects.create(
            company=self.company, lead=lead_a, user=self.user,
            kind=LeadActivity.Kind.NOTE,
            body='Contact société A',
        )
        lead_a.refresh_from_db()
        lead_b.refresh_from_db()
        # A avancé, B intact
        self.assertEqual(lead_a.stage, _CONTACTED)
        self.assertEqual(lead_b.stage, NEW)

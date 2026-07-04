"""YLEAD10 — Fast-lane comportemental : FOLLOW_UP à l'ouverture du devis.

Couvre :
  - un lead à QUOTE_SENT dont le devis est ouvert avance à FOLLOW_UP ;
  - une seconde ouverture n'avance rien de plus (idempotent) ;
  - un lead déjà ≥ FOLLOW_UP (ex. SIGNED) ne bouge pas ;
  - un lead PERDU ne bouge pas ;
  - un lead COLD est réactivé à FOLLOW_UP (cohérent avec le comportement
    existant de avancer_stage_pour_devis — COLD est un état de parking, pas
    une régression) ;
  - seule une clé STAGES.py est écrite (jamais de valeur hors catalogue).
"""
from django.test import TestCase

from authentication.models import Company

from apps.crm import stages
from apps.crm.models import Lead, LeadActivity
from apps.crm.services import (
    avancer_stage_sur_ouverture_devis, noter_devis_ouvert,
)


def _make_lead(company, stage=stages.QUOTE_SENT, perdu=False):
    return Lead.objects.create(
        company=company, nom='Prospect Test', stage=stage, perdu=perdu)


class FastLaneOpenTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor YLEAD10', slug='taqinor-ylead10')

    def test_quote_sent_advances_to_follow_up(self):
        lead = _make_lead(self.company, stage=stages.QUOTE_SENT)
        advanced = avancer_stage_sur_ouverture_devis(lead)
        self.assertTrue(advanced)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP)
        self.assertIn(lead.stage, stages.STAGES)

    def test_second_open_is_idempotent(self):
        lead = _make_lead(self.company, stage=stages.QUOTE_SENT)
        avancer_stage_sur_ouverture_devis(lead)
        lead.refresh_from_db()
        second = avancer_stage_sur_ouverture_devis(lead)
        self.assertFalse(second)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP)

    def test_signed_lead_does_not_move(self):
        lead = _make_lead(self.company, stage=stages.SIGNED)
        advanced = avancer_stage_sur_ouverture_devis(lead)
        self.assertFalse(advanced)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.SIGNED)

    def test_lost_lead_does_not_move(self):
        lead = _make_lead(self.company, stage=stages.QUOTE_SENT, perdu=True)
        advanced = avancer_stage_sur_ouverture_devis(lead)
        self.assertFalse(advanced)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.QUOTE_SENT)

    def test_cold_lead_is_reactivated_to_follow_up(self):
        """COLD est un état de parking (pas 'plus avancé') — cohérent avec
        avancer_stage_pour_devis, l'ouverture réactive vers FOLLOW_UP."""
        lead = _make_lead(self.company, stage=stages.COLD)
        advanced = avancer_stage_sur_ouverture_devis(lead)
        self.assertTrue(advanced)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP)

    def test_noter_devis_ouvert_calls_fastlane_and_logs_note(self):
        lead = _make_lead(self.company, stage=stages.QUOTE_SENT)
        noter_devis_ouvert('DEV-2026-001', lead)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP)
        notes = LeadActivity.objects.filter(lead=lead)
        self.assertTrue(
            any('ouvert le devis DEV-2026-001' in (n.body or '')
                for n in notes))
        self.assertTrue(
            any('auto — devis ouvert' in (n.body or '') for n in notes))

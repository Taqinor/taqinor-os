"""XMKT21 — Passage MQL automatique sur seuil de score.

Couvre :
  - seuil non configuré (0/NULL) → aucune assignation (comportement actuel) ;
  - franchissement du seuil → assignation round-robin (owner absent) +
    notification + note chatter avec le contexte marketing ;
  - idempotence : un second recalcul du score (même ≥ seuil) ne ré-assigne
    pas / ne renotifie pas une deuxième fois ;
  - un lead qui a déjà un owner n'est pas réassigné (mais l'idempotence /
    notification jouent quand même) ;
  - multi-tenant : le round-robin ne pioche jamais un commercial d'une autre
    société.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from authentication.models import Company
from apps.roles.models import Role
from apps.crm.models import Lead, LeadActivity
from apps.crm.services import maybe_assign_mql, recompute_lead_score
from apps.parametres.models import CompanyProfile
from apps.notifications.models import Notification

User = get_user_model()


def _make_company(slug='mql-co'):
    return Company.objects.create(nom=slug, slug=slug)


def _make_commercial_role(company):
    # get_or_create : (company, nom) est unique — un test appelant ce helper
    # deux fois pour la même société (ou oubliant de réutiliser un rôle déjà
    # créé) ne doit jamais lever d'IntegrityError.
    role, _ = Role.objects.get_or_create(
        company=company, nom='Commercial',
        defaults={'permissions': ['crm_voir', 'crm_creer', 'crm_modifier']})
    return role


def _make_commercial(company, username, role=None):
    role = role or _make_commercial_role(company)
    return User.objects.create_user(
        username=username, password='x', company=company, role=role)


def _make_lead(company, owner=None, score=None, nom='Prospect Test'):
    return Lead.objects.create(
        company=company, nom=nom, owner=owner, score=score)


class MqlThresholdDisabledTests(TestCase):
    def setUp(self):
        self.company = _make_company('mql-off')

    def test_no_threshold_configured_is_noop(self):
        """CompanyProfile.seuil_mql vide (défaut) → aucune assignation, même
        avec un score élevé — comportement actuel inchangé."""
        lead = _make_lead(self.company, score=95)
        assigned = maybe_assign_mql(lead)
        self.assertFalse(assigned)
        lead.refresh_from_db()
        self.assertIsNone(lead.mql_assigned_at)
        self.assertIsNone(lead.owner)


class MqlThresholdCrossingTests(TestCase):
    def setUp(self):
        self.company = _make_company('mql-on')
        CompanyProfile.objects.create(company=self.company, seuil_mql=70)
        self.role = _make_commercial_role(self.company)
        self.commercial = _make_commercial(
            self.company, 'com1', role=self.role)

    def test_below_threshold_is_noop(self):
        lead = _make_lead(self.company, score=40)
        assigned = maybe_assign_mql(lead)
        self.assertFalse(assigned)
        lead.refresh_from_db()
        self.assertIsNone(lead.mql_assigned_at)

    def test_crossing_threshold_assigns_and_notifies_once(self):
        """Franchir le seuil assigne (round-robin), notifie, journalise le
        contexte marketing — et ne le refait pas une deuxième fois (idempotent)."""
        lead = _make_lead(self.company, score=85)
        lead.utm_source = 'facebook'
        lead.utm_campaign = 'campagne-ete'
        lead.save(update_fields=['utm_source', 'utm_campaign'])

        assigned = maybe_assign_mql(lead)
        self.assertTrue(assigned)
        lead.refresh_from_db()
        self.assertIsNotNone(lead.mql_assigned_at)
        self.assertEqual(lead.owner_id, self.commercial.id)

        notes = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE)
        self.assertTrue(
            any('MQL' in (n.body or '') for n in notes))
        self.assertTrue(
            any('facebook' in (n.body or '') for n in notes))

        self.assertEqual(
            Notification.objects.filter(recipient=self.commercial).count(), 1)

        first_assigned_at = lead.mql_assigned_at

        # Second appel (ex. re-sauvegarde du lead) → idempotent : pas de
        # deuxième assignation ni de deuxième notification.
        assigned_again = maybe_assign_mql(lead)
        self.assertFalse(assigned_again)
        lead.refresh_from_db()
        self.assertEqual(lead.mql_assigned_at, first_assigned_at)
        self.assertEqual(
            Notification.objects.filter(recipient=self.commercial).count(), 1)

    def test_existing_owner_is_not_reassigned(self):
        """Un lead qui a déjà un responsable n'est pas réassigné par le
        round-robin — seul le marqueur MQL + la notification jouent."""
        other = _make_commercial(
            self.company, 'owner_deja_present', role=self.role)
        lead = _make_lead(self.company, owner=other, score=90)
        assigned = maybe_assign_mql(lead)
        self.assertTrue(assigned)
        lead.refresh_from_db()
        self.assertEqual(lead.owner_id, other.id)

    def test_round_robin_prefers_least_loaded_commercial(self):
        """Round-robin : le commercial avec le moins de leads MQL déjà
        assignés est choisi en premier."""
        other = _make_commercial(self.company, 'com2', role=self.role)
        # Charge com1 avec un lead déjà MQL-assigné.
        loaded = _make_lead(self.company, score=90)
        maybe_assign_mql(loaded)
        self.assertEqual(loaded.owner_id, self.commercial.id)

        # Le prochain lead doit aller au commercial le moins chargé (other).
        lead2 = _make_lead(self.company, score=90)
        maybe_assign_mql(lead2)
        lead2.refresh_from_db()
        self.assertEqual(lead2.owner_id, other.id)

    def test_recompute_lead_score_triggers_mql_assignment(self):
        """recompute_lead_score (appelé à la création/mise à jour du lead)
        déclenche bien le passage MQL quand le score calculé franchit le seuil."""
        lead = Lead.objects.create(
            company=self.company, nom='Client scoré',
            email='client@example.com', telephone='0612345678',
            ville='Casablanca')
        recompute_lead_score(lead)
        lead.refresh_from_db()
        # Le score réel dépend de scoring.py — on ne fige pas sa valeur, on
        # vérifie seulement la cohérence : si ≥ seuil, MQL est posé.
        if (lead.score or 0) >= 70:
            self.assertIsNotNone(lead.mql_assigned_at)
        else:
            self.assertIsNone(lead.mql_assigned_at)


class MqlMultiTenantTests(TestCase):
    def test_round_robin_never_picks_another_company_commercial(self):
        co_a = _make_company('mql-a')
        co_b = _make_company('mql-b')
        CompanyProfile.objects.create(company=co_a, seuil_mql=50)
        role_b = _make_commercial_role(co_b)
        _make_commercial(co_b, 'com_b', role=role_b)
        # Aucun commercial dans co_a.
        lead = _make_lead(co_a, score=80)
        assigned = maybe_assign_mql(lead)
        self.assertTrue(assigned)  # marqueur MQL posé même sans assignee
        lead.refresh_from_db()
        self.assertIsNotNone(lead.mql_assigned_at)
        self.assertIsNone(lead.owner)

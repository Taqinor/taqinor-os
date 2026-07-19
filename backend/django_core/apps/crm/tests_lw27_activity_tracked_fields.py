"""LW27 — +11 champs métier journalisés dans le chatter (TRACKED_FIELDS).

``apps/crm/activity.py`` ignorait des champs de pilotage réel (forecast
pondéré, qualification site QK1, champs site pro QW2). Ce test vérifie
qu'un PATCH sur l'un des 11 nouveaux champs crée bien UNE ``LeadActivity``
'modification' avec un libellé français propre, et que les champs
d'attribution marketing (utm_*) restent NON journalisés (bruit système)."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity

User = get_user_model()


def _company(slug='lw27-co', nom='LW27 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TrackedFieldsTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.user = User.objects.create_user(
            username='lw27_user', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(company=self.company, nom='LW27 Lead')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _patch(self, **body):
        return self.api.patch(
            f'/api/django/crm/leads/{self.lead.id}/', body, format='json')

    def _modifications(self, field):
        return LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.MODIFICATION, field=field)

    # ── Les 11 nouveaux champs sont maintenant journalisés ──────────────────

    def test_patch_montant_estime_logs_one_modification(self):
        resp = self._patch(montant_estime='250000.00')
        self.assertEqual(resp.status_code, 200, resp.data)
        acts = self._modifications('montant_estime')
        self.assertEqual(acts.count(), 1)
        act = acts.first()
        self.assertEqual(act.field_label, 'Montant estimé (MAD)')
        self.assertEqual(act.new_value, str(Decimal('250000.00')))

    def test_patch_date_cloture_prevue_logs_one_modification(self):
        resp = self._patch(date_cloture_prevue='2026-09-01')
        self.assertEqual(resp.status_code, 200, resp.data)
        acts = self._modifications('date_cloture_prevue')
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().field_label, 'Date de clôture prévue')
        self.assertEqual(acts.first().new_value, str(date(2026, 9, 1)))

    def test_patch_distributeur_logs_choice_label(self):
        choices = dict(Lead._meta.get_field('distributeur').choices or [])
        key = next(iter(choices))
        resp = self._patch(distributeur=key)
        self.assertEqual(resp.status_code, 200, resp.data)
        acts = self._modifications('distributeur')
        self.assertEqual(acts.count(), 1)
        act = acts.first()
        self.assertEqual(act.field_label, "Distributeur d'électricité")
        # Valeur humaine (choices), pas la clé brute.
        self.assertEqual(act.new_value, choices[key])

    def test_patch_roof_age_logs_one_modification(self):
        resp = self._patch(roof_age=12)
        self.assertEqual(resp.status_code, 200, resp.data)
        acts = self._modifications('roof_age')
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().field_label, 'Âge de la toiture (ans)')
        self.assertEqual(acts.first().new_value, '12')

    def test_patch_ownership_logs_choice_label(self):
        choices = dict(Lead._meta.get_field('ownership').choices or [])
        key = next(iter(choices))
        resp = self._patch(ownership=key)
        self.assertEqual(resp.status_code, 200, resp.data)
        acts = self._modifications('ownership')
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().field_label, "Statut d'occupation")
        self.assertEqual(acts.first().new_value, choices[key])

    def test_patch_project_timeline_logs_one_modification(self):
        choices = dict(Lead._meta.get_field('project_timeline').choices or [])
        key = next(iter(choices))
        resp = self._patch(project_timeline=key)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._modifications('project_timeline').count(), 1)

    def test_patch_financing_intent_logs_one_modification(self):
        choices = dict(Lead._meta.get_field('financing_intent').choices or [])
        key = next(iter(choices))
        resp = self._patch(financing_intent=key)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._modifications('financing_intent').count(), 1)

    def test_patch_facility_type_logs_one_modification(self):
        choices = dict(Lead._meta.get_field('facility_type').choices or [])
        key = next(iter(choices))
        resp = self._patch(facility_type=key)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._modifications('facility_type').count(), 1)

    def test_patch_site_count_logs_one_modification(self):
        choices = dict(Lead._meta.get_field('site_count').choices or [])
        key = next(iter(choices))
        resp = self._patch(site_count=key)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._modifications('site_count').count(), 1)

    def test_patch_visit_window_part_logs_one_modification(self):
        choices = dict(Lead._meta.get_field('visit_window_part').choices or [])
        key = next(iter(choices))
        resp = self._patch(visit_window_part=key)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._modifications('visit_window_part').count(), 1)

    def test_patch_visit_window_week_logs_one_modification(self):
        choices = dict(Lead._meta.get_field('visit_window_week').choices or [])
        key = next(iter(choices))
        resp = self._patch(visit_window_week=key)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._modifications('visit_window_week').count(), 1)

    # ── Bruit système JAMAIS journalisé (utm/meta_ad/custom_data) ───────────

    def test_patch_utm_source_logs_nothing(self):
        resp = self._patch(utm_source='google')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._modifications('utm_source').count(), 0)
        # Aucune LeadActivity de modification du tout pour ce PATCH.
        self.assertEqual(
            LeadActivity.objects.filter(
                lead=self.lead, kind=LeadActivity.Kind.MODIFICATION).count(),
            0)

    def test_patch_meta_ad_id_logs_nothing(self):
        resp = self._patch(meta_ad_id='123456')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._modifications('meta_ad_id').count(), 0)

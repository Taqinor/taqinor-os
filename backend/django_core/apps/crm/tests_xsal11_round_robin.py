"""XSAL11 — Affectation round-robin équilibrée des leads entrants.

Couvre :
  - OFF (défaut) : comportement byte-identique — responsable par défaut
    explicite prime, QW6 round-robin simple sinon ;
  - ON : deux leads successifs vont à deux commerciaux DIFFÉRENTS ;
  - ON : un commercial au plafond de leads OUVERTS est sauté ;
  - ON : tous saturés → fallback sur ``responsable_defaut_leads`` ;
  - ON, aucun commercial actif et pas de responsable par défaut → None (no-op) ;
  - appliqué au webhook site (pas seulement à la création manuelle) ;
  - company-scopé (jamais de fuite cross-tenant dans le pool de rotation).
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from apps.crm import stages
from apps.crm.models import Lead
from apps.crm.services import default_responsable_for
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role

User = get_user_model()

SECRET = 'xsal11-test-secret'


def make_commercial(company, username, role):
    return User.objects.create_user(
        username=username, password='x', company=company, role=role)


class RoundRobinOffByDefaultTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor XSAL11 Off', slug='taqinor-xsal11-off')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_voir'])

    def test_off_responsable_explicite_prime_octet_identique(self):
        explicite = make_commercial(self.company, 'explicite_off', self.role)
        make_commercial(self.company, 'autre_commercial_off', self.role)
        CompanyProfile.objects.create(
            company=self.company, responsable_defaut_leads=explicite,
            round_robin_leads_actif=False)
        self.assertEqual(default_responsable_for(self.company), explicite)

    def test_off_sans_reglage_retombe_sur_round_robin_simple_qw6(self):
        # round_robin_leads_actif=False (défaut du champ) : QW6 s'applique.
        commercial = make_commercial(self.company, 'seul_commercial_off', self.role)
        CompanyProfile.objects.create(company=self.company)
        self.assertEqual(default_responsable_for(self.company), commercial)


class RoundRobinOnBalancedTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor XSAL11 On', slug='taqinor-xsal11-on')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_voir'])
        self.profile = CompanyProfile.objects.create(
            company=self.company, round_robin_leads_actif=True,
            round_robin_plafond_leads_ouverts=2)

    def test_deux_leads_successifs_vont_a_deux_commerciaux_differents(self):
        com_a = make_commercial(self.company, 'com_a_on', self.role)
        com_b = make_commercial(self.company, 'com_b_on', self.role)

        first = default_responsable_for(self.company)
        self.assertIn(first, (com_a, com_b))
        Lead.objects.create(
            company=self.company, nom='Lead 1', owner=first, stage=stages.NEW)

        second = default_responsable_for(self.company)
        self.assertNotEqual(second, first)

    def test_commercial_au_plafond_est_saute(self):
        com_a = make_commercial(self.company, 'com_a_plafond', self.role)
        com_b = make_commercial(self.company, 'com_b_plafond', self.role)
        # com_a a déjà 2 leads OUVERTS (== plafond) → doit être sauté.
        Lead.objects.create(
            company=self.company, nom='L1', owner=com_a, stage=stages.NEW)
        Lead.objects.create(
            company=self.company, nom='L2', owner=com_a, stage=stages.CONTACTED)
        chosen = default_responsable_for(self.company)
        self.assertEqual(chosen, com_b)

    def test_leads_signed_ou_cold_ne_comptent_pas_dans_le_plafond(self):
        com_a = make_commercial(self.company, 'com_a_signed', self.role)
        com_b = make_commercial(self.company, 'com_b_signed', self.role)
        # 2 leads SIGNED/COLD sur com_a : ne comptent PAS comme "ouverts".
        Lead.objects.create(
            company=self.company, nom='L1', owner=com_a, stage=stages.SIGNED)
        Lead.objects.create(
            company=self.company, nom='L2', owner=com_a, stage=stages.COLD)
        chosen = default_responsable_for(self.company)
        self.assertIn(chosen, (com_a, com_b))

    def test_lead_perdu_ne_compte_pas_dans_le_plafond(self):
        com_a = make_commercial(self.company, 'com_a_perdu', self.role)
        com_b = make_commercial(self.company, 'com_b_perdu', self.role)
        Lead.objects.create(
            company=self.company, nom='L1', owner=com_a, stage=stages.NEW,
            perdu=True)
        Lead.objects.create(
            company=self.company, nom='L2', owner=com_a, stage=stages.NEW,
            perdu=True)
        chosen = default_responsable_for(self.company)
        self.assertIn(chosen, (com_a, com_b))

    def test_tous_satures_fallback_responsable_defaut(self):
        explicite = make_commercial(self.company, 'explicite_satures', self.role)
        com_a = make_commercial(self.company, 'com_a_satures', self.role)
        self.profile.responsable_defaut_leads = explicite
        self.profile.save(update_fields=['responsable_defaut_leads'])
        Lead.objects.create(
            company=self.company, nom='L1', owner=com_a, stage=stages.NEW)
        Lead.objects.create(
            company=self.company, nom='L2', owner=com_a, stage=stages.NEW)
        chosen = default_responsable_for(self.company)
        self.assertEqual(chosen, explicite)

    def test_tous_satures_sans_fallback_none(self):
        com_a = make_commercial(self.company, 'com_a_sans_fallback', self.role)
        Lead.objects.create(
            company=self.company, nom='L1', owner=com_a, stage=stages.NEW)
        Lead.objects.create(
            company=self.company, nom='L2', owner=com_a, stage=stages.NEW)
        self.assertIsNone(default_responsable_for(self.company))

    def test_aucun_commercial_actif_none(self):
        self.assertIsNone(default_responsable_for(self.company))

    def test_company_scope(self):
        other = Company.objects.create(nom='Autre XSAL11', slug='xsal11-autre')
        other_role = Role.objects.create(
            company=other, nom='Commercial', permissions=['crm_voir'])
        make_commercial(other, 'commercial_autre_societe', other_role)
        # Aucun commercial DANS self.company → None, jamais le pool de l'autre.
        self.assertIsNone(default_responsable_for(self.company))


def payload_site(**extra):
    base = {'fullName': 'Lead XSAL11', 'phoneE164': '+212611112222', 'qualified': True}
    base.update(extra)
    return base


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class RoundRobinAppliedToWebhookTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor XSAL11 Webhook', slug='taqinor-xsal11-webhook')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_voir'])
        CompanyProfile.objects.create(
            company=self.company, round_robin_leads_actif=True,
            round_robin_plafond_leads_ouverts=10)
        self.url = reverse('website-lead-webhook')

    def post(self, phone):
        return self.client.post(
            self.url, data=json.dumps(payload_site(phoneE164=phone)),
            content_type='application/json', HTTP_X_WEBHOOK_SECRET=SECRET)

    def test_deux_leads_du_site_vont_a_deux_commerciaux_differents(self):
        make_commercial(self.company, 'wh_com_a', self.role)
        make_commercial(self.company, 'wh_com_b', self.role)
        r1 = self.post('+212611110001')
        r2 = self.post('+212611110002')
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        lead1 = Lead.objects.get(pk=r1.json()['lead_id'])
        lead2 = Lead.objects.get(pk=r2.json()['lead_id'])
        self.assertIsNotNone(lead1.owner_id)
        self.assertIsNotNone(lead2.owner_id)
        self.assertNotEqual(lead1.owner_id, lead2.owner_id)

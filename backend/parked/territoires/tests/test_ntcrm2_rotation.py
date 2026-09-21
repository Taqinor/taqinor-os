"""NTCRM2 — Rotation équitable inter-territoires (race-safe, quotas)."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity
from apps.roles.models import Role
from apps.territoires.models import Territoire, TerritoireMembre, TerritoireRegle
from apps.territoires.services import assigner_lead_territoire

User = get_user_model()


class RotationEquitableTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM2', slug='taqinor-ntcrm2')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_voir'])
        self.territoire = Territoire.objects.create(
            company=self.company, nom='Centre')
        TerritoireRegle.objects.create(
            territoire=self.territoire, ordre=1,
            condition={'field': 'ville', 'operator': 'eq', 'value': 'Casablanca'})
        self.membres = []
        for i in range(3):
            user = User.objects.create_user(
                username=f'com_rot_{i}', password='x',
                company=self.company, role=self.role)
            TerritoireMembre.objects.create(territoire=self.territoire, utilisateur=user)
            self.membres.append(user)

    def test_100_leads_repartis_a_deux_pres(self):
        compte = {u.pk: 0 for u in self.membres}
        for i in range(100):
            lead = Lead.objects.create(
                company=self.company, nom=f'Lead {i}', ville='Casablanca')
            territoire, owner = assigner_lead_territoire(lead)
            self.assertEqual(territoire, self.territoire)
            self.assertIsNotNone(owner)
            compte[owner.pk] += 1

        total = sum(compte.values())
        self.assertEqual(total, 100)
        moyenne = total / len(self.membres)
        for pk, nb in compte.items():
            self.assertLessEqual(abs(nb - moyenne), 2 + 1e-9)

    def test_assignation_journalisee_dans_leadactivity(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead chatter', ville='Casablanca')
        territoire, owner = assigner_lead_territoire(lead)
        lead.refresh_from_db()
        self.assertEqual(lead.owner, owner)
        entry = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.MODIFICATION, field='owner').first()
        self.assertIsNotNone(entry)
        self.assertIn(self.territoire.nom, entry.body)

    def test_aucun_match_repli_none_none(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead ailleurs', ville='Fès')
        territoire, owner = assigner_lead_territoire(lead)
        self.assertIsNone(territoire)
        self.assertIsNone(owner)


class QuotaRotationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM2 Quota', slug='taqinor-ntcrm2-quota')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_voir'])
        self.territoire = Territoire.objects.create(
            company=self.company, nom='Quota')
        TerritoireRegle.objects.create(
            territoire=self.territoire, ordre=1,
            condition={'field': 'ville', 'operator': 'eq', 'value': 'Rabat'})
        self.gros = User.objects.create_user(
            username='quota_gros', password='x', company=self.company, role=self.role)
        self.petit = User.objects.create_user(
            username='quota_petit', password='x', company=self.company, role=self.role)
        TerritoireMembre.objects.create(
            territoire=self.territoire, utilisateur=self.gros, quota_pct=80)
        TerritoireMembre.objects.create(
            territoire=self.territoire, utilisateur=self.petit, quota_pct=20)

    def test_quota_respecte_environ_80_20_sur_10_leads(self):
        compte = {self.gros.pk: 0, self.petit.pk: 0}
        for i in range(10):
            lead = Lead.objects.create(
                company=self.company, nom=f'Lead quota {i}', ville='Rabat')
            _territoire, owner = assigner_lead_territoire(lead)
            compte[owner.pk] += 1
        self.assertGreaterEqual(compte[self.gros.pk], 7)
        self.assertLessEqual(compte[self.petit.pk], 3)

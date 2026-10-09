"""ACRM31 — UN prédicat « lead signé » (étape SIGNED, non perdu, non
archivé) partagé par les sept lectures qui comptent des signés.

Jeu : une campagne portant un lead SIGNED perdu, un SIGNED archivé et un
SIGNED normal → chaque lecture compte UN signé (rejoue la sonde LSEL-6).
Test-du-test : retirer ``perdu=False`` du prédicat ⇒ les lectures ORM
comptent 2 et ce test échoue.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import selectors, stages
from apps.crm.models import Lead

User = get_user_model()
CAMPAGNE = 'acrm31-campagne'


class SigneUniqueTests(TestCase):

    def setUp(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import ADMIN_PERMISSIONS
        self.company = Company.objects.create(
            nom='ACRM31 Solaire', slug='acrm31-signe')
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='Administrateur',
            defaults={'permissions': ADMIN_PERMISSIONS, 'est_systeme': True})
        self.user = User.objects.create_user(
            username='acrm31-admin', password='x', company=self.company,
            role=role, role_legacy='admin')
        base = dict(company=self.company, stage=stages.SIGNED,
                    utm_campaign=CAMPAGNE, canal='meta_ads',
                    ville='Rabat', owner=self.user)
        self.normal = Lead.objects.create(
            nom='Normal', telephone='0611000001', **base)
        self.perdu = Lead.objects.create(
            nom='Perdu', telephone='0611000002', perdu=True,
            motif_perte='Prix', **base)
        self.archive = Lead.objects.create(
            nom='Archive', telephone='0611000003', is_archived=True, **base)

    def _comptes(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = api.get('/api/django/crm/leads/roi-sources/')
        self.assertEqual(resp.status_code, 200, resp.data)
        roi = sum(r['signed_count'] for r in resp.data
                  if r['utm_campaign'] == CAMPAGNE)
        attribution = selectors.attribution_leads(self.company)
        return {
            'attribution_leads': sum(
                r['nb_signes'] for r in attribution['par_source']),
            'attribution_lead_rows': sum(
                1 for r in selectors.attribution_lead_rows(self.company)
                if r['signed']),
            'signed_leads_for_campaigns': selectors.signed_leads_for_campaigns(
                self.company, [CAMPAGNE])[CAMPAGNE]['signed_count'],
            'signed_lead_phone_keys': len(
                selectors.signed_lead_phone_keys(self.company)),
            'leads_ville_rows': sum(
                1 for r in selectors.leads_ville_rows(self.company)
                if r['signed']),
            'leads_signes_sans_devis_accepte': len(
                selectors.leads_signes_sans_devis_accepte(self.company)),
            'roi_sources': roi,
        }

    def test_sept_lectures_comptent_un_signe(self):
        comptes = self._comptes()
        self.assertEqual(len(comptes), 7)
        for lecteur, valeur in comptes.items():
            with self.subTest(lecteur=lecteur):
                self.assertEqual(valeur, 1, lecteur)

    def test_signed_leads_for_campaigns_liste_le_seul_signe(self):
        res = selectors.signed_leads_for_campaigns(self.company, [CAMPAGNE])
        self.assertEqual(res[CAMPAGNE]['signed_lead_ids'], [self.normal.pk])

    def test_predicat_python_et_orm_concordent(self):
        orm = set(Lead.objects.filter(
            selectors.lead_signe_q(), company=self.company)
            .values_list('pk', flat=True))
        py = {lead.pk for lead in Lead.objects.filter(company=self.company)
              if selectors.est_lead_signe(lead)}
        self.assertEqual(orm, {self.normal.pk})
        self.assertEqual(py, orm)

    def test_revenu_campagne_ignore_perdu(self):
        self.assertEqual(
            selectors.revenu_attribue_campagne(
                self.company, CAMPAGNE)['nb_signes'], 0)

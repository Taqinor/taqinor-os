"""ACRM28 (C-ACRM-023) — UNE définition des leads visibles
(``selectors.leads_visibles`` : portée propriétaire ET périmètre d'entités)
lue par toutes les files.

Sonde V_VA LSEL-3 : un rôle borné à l'entité A, propriétaire d'un lead de
l'entité B en retard : ``GET`` du lead → 404, mais le lead sortait dans la
file « en retard » et dans « Ma file ». Désormais il est absent partout ; un
rôle sans entités visibles garde le comportement actuel.

Aucun mock : rôle, entités, leads et touches réels.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.dates import aujourd_hui_local

from apps.crm import selectors, stages
from apps.crm.models import Lead, RelanceEtape
from apps.entites.models import Entite
from apps.roles.models import Role
from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS

User = get_user_model()


class PerimetreEntiteFilesTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM28 Solaire', slug='acrm28-entites')
        self.ent_a = Entite.objects.create(
            company=self.company, nom='Agence A', code='A')
        self.ent_b = Entite.objects.create(
            company=self.company, nom='Agence B', code='B')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial A',
            permissions=list(COMMERCIAL_PERMISSIONS))
        self.role.entites_visibles.set([self.ent_a])
        self.moi = User.objects.create_user(
            username='acrm28-moi', password='x', company=self.company,
            role=self.role)
        self.today = aujourd_hui_local()
        hier = self.today - datetime.timedelta(days=10)
        commun = dict(company=self.company, owner=self.moi,
                      stage=stages.CONTACTED, relance_date=hier, score=90,
                      contact_preference='phone_ok')
        self.lead_a = Lead.objects.create(nom='LeadA', entite=self.ent_a,
                                          **commun)
        self.lead_b = Lead.objects.create(nom='LeadB', entite=self.ent_b,
                                          **commun)
        # Valeurs posées SANS passer par save() (score recalculé, premier
        # contact horodaté) : le test fixe lui-même l'état observé.
        Lead.objects.filter(pk__in=[self.lead_a.pk, self.lead_b.pk]).update(
            score=90, first_contacted_at=None, relance_date=hier,
            contact_preference='phone_ok')
        RelanceEtape.objects.filter(company=self.company).delete()
        for lead in (self.lead_a, self.lead_b):
            RelanceEtape.objects.create(
                company=self.company, lead=lead, cadence='contact', ordre=1,
                canal=RelanceEtape.Canal.APPEL, libelle='Appeler',
                due_date=hier)

    def _ids_par_lecteur(self):
        today = self.today
        etapes, _resume = selectors.relance_etapes_periode(
            self.company, self.moi,
            date_debut=today - datetime.timedelta(days=30), date_fin=today)
        return {
            'relances_du_jour': {
                le.pk for le in selectors.relances_du_jour(
                    self.company, self.moi, scope='overdue', today=today)},
            'relance_etapes_dues': {
                e.lead_id for e in selectors.relance_etapes_dues(
                    self.company, self.moi, scope='all', today=today)},
            'relance_etapes_periode': {e.lead_id for e in etapes},
            'leads_chauds_non_contactes': {
                le.pk for le in selectors.leads_chauds_non_contactes(
                    self.company, self.moi)},
            'leads_rappel_demande': {
                le.pk for le in selectors.leads_rappel_demande(
                    self.company, self.moi)},
            'ma_file_commercial_items': {
                int(item['link'].rsplit('=', 1)[1])
                for item in selectors.ma_file_commercial_items(
                    self.company, self.moi, today=today)},
            'cadences_echues_a_clore': {
                ligne['lead_id'] for ligne in selectors.cadences_echues_a_clore(
                    self.company, self.moi, jours=1, today=today)},
        }

    def test_lead_hors_perimetre_absent_de_chaque_file(self):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.moi)}'))
        self.assertEqual(
            api.get(f'/api/django/crm/leads/{self.lead_b.pk}/').status_code,
            404)
        for lecteur, ids in self._ids_par_lecteur().items():
            self.assertNotIn(self.lead_b.pk, ids, lecteur)
            self.assertIn(self.lead_a.pk, ids, lecteur)
        cockpit = selectors.file_du_cockpit(self.company, self.moi,
                                            today=self.today)
        self.assertEqual(cockpit['maintenant'], 1)
        resp = api.get('/api/django/crm/leads/relances/?scope=overdue')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('LeadB', resp.content.decode())
        resp = api.get('/api/django/crm/relance-etapes/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('LeadB', resp.content.decode())

    def test_role_sans_entites_inchange(self):
        self.role.entites_visibles.clear()
        for lecteur, ids in self._ids_par_lecteur().items():
            self.assertIn(self.lead_b.pk, ids, lecteur)
            self.assertIn(self.lead_a.pk, ids, lecteur)

"""MRY19 — La première prise de contact, posée UNE fois, mesurée juste.

Quatre endroits écrivaient `first_contacted_at` à la main, avec quatre
conditions LÉGÈREMENT différentes — dont deux qui exigeaient l'étape NEW. Un
lead saisi à la main, déjà CONTACTED, ne recevait donc JAMAIS d'horodatage et
sortait silencieusement du KPI. `services.marquer_premier_contact` est
désormais la seule règle : si le champ est vide, on le pose.

Le KPI, lui, ne vaut quelque chose que parce qu'il compte en minutes OUVRÉES :
un lead arrivé vendredi 21 h et rappelé lundi 08:32 vaut 2 minutes, pas
60 heures. Et il renvoie `null` partout sur zéro lead — jamais un 0 % qui
laisserait croire à un échec.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity
from apps.crm.selectors import kpi_premier_contact
from apps.crm.services import (
    avancer_stage_new_vers_contacted, marquer_premier_contact,
    maybe_set_first_contacted_at)
from apps.parametres.models import CompanyProfile

User = get_user_model()

CASA = horaires.CASABLANCA
KPI_URL = '/api/django/crm/leads/kpi-premier-contact/'


def _company(slug, objectif=5):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    profil, _ = CompanyProfile.objects.get_or_create(company=company)
    profil.premier_contact_objectif_min = objectif
    profil.save(update_fields=['premier_contact_objectif_min'])
    return company


class MarquerPremierContactTests(TestCase):
    def setUp(self):
        self.company = _company('mry19-pose')
        self.acteur = User.objects.create_user(
            username='mry19-u', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def test_pose_une_seule_fois(self):
        self.assertTrue(marquer_premier_contact(self.lead))
        premier = self.lead.first_contacted_at
        self.assertFalse(marquer_premier_contact(self.lead))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.first_contacted_at, premier)

    def test_pose_meme_hors_de_letape_NEW(self):
        """LE trou fermé : un lead saisi à la main, déjà CONTACTED, ne
        recevait jamais d'horodatage — donc n'entrait jamais dans le KPI."""
        self.lead.stage = stages.CONTACTED
        self.lead.save(update_fields=['stage'])
        self.assertTrue(marquer_premier_contact(self.lead))
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.first_contacted_at)

    def test_chemin_noter(self):
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/noter/',
            {'body': 'Appelé, pas de réponse'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.first_contacted_at)

    def test_chemin_log_interaction(self):
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/log-interaction/',
            {'kind': 'appel'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.first_contacted_at)

    def test_chemin_avancer_stage_new_vers_contacted(self):
        avancer_stage_new_vers_contacted(self.lead, self.acteur)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)
        self.assertIsNotNone(self.lead.first_contacted_at)

    def test_chemin_maybe_set_first_contacted_at(self):
        ancien = Lead.objects.get(pk=self.lead.pk)
        self.lead.stage = stages.CONTACTED
        self.lead.save(update_fields=['stage'])
        maybe_set_first_contacted_at(ancien, self.lead)
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.first_contacted_at)

    def test_aucun_chemin_necrase_un_horodatage_existant(self):
        pose = timezone.now() - datetime.timedelta(days=3)
        Lead.objects.filter(pk=self.lead.pk).update(first_contacted_at=pose)
        self.lead.refresh_from_db()
        self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/noter/',
            {'body': 'Deuxième appel'}, format='json')
        avancer_stage_new_vers_contacted(self.lead, self.acteur)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.first_contacted_at, pose)

    def test_ne_leve_jamais(self):
        self.assertFalse(marquer_premier_contact(None))


class KpiPremierContactTests(TestCase):
    def setUp(self):
        self.company = _company('mry19-kpi')
        self.acteur = User.objects.create_user(
            username='mry19-kpi-u', password='x', role_legacy='responsable',
            company=self.company)

    def _lead(self, cree_le, contacte_le=None, **kw):
        champs = {'company': self.company, 'nom': 'Prospect',
                  'owner': self.acteur, 'source': Lead.Source.OS_NATIVE}
        champs.update(kw)
        lead = Lead.objects.create(**champs)
        maj = {'date_creation': cree_le}
        if contacte_le is not None:
            maj['first_contacted_at'] = contacte_le
        Lead.objects.filter(pk=lead.pk).update(**maj)
        return Lead.objects.get(pk=lead.pk)

    def test_null_partout_sur_zero_lead(self):
        kpi = kpi_premier_contact(self.company)
        self.assertEqual(kpi['nb_leads'], 0)
        for cle in ('nb_sous_objectif', 'pct_sous_objectif',
                    'mediane_minutes_ouvrees', 'nb_nuit_rappeles_avant_930'):
            self.assertIsNone(kpi[cle], cle)

    def test_deux_minutes_ouvrees_par_dessus_un_week_end(self):
        """Le cas qui rendrait un KPI calendaire faux à charge : vendredi
        21 h → lundi 08:32 = 2 minutes ouvrées, pas 60 heures."""
        self._lead(datetime.datetime(2026, 9, 4, 21, 0, tzinfo=CASA),
                   datetime.datetime(2026, 9, 7, 8, 32, tzinfo=CASA))
        kpi = kpi_premier_contact(self.company, jours=3650)
        self.assertEqual(kpi['mediane_minutes_ouvrees'], 2)
        self.assertEqual(kpi['nb_sous_objectif'], 1)
        self.assertEqual(kpi['pct_sous_objectif'], 100.0)

    def test_un_lead_lent_sort_de_lobjectif(self):
        self._lead(datetime.datetime(2026, 9, 2, 9, 0, tzinfo=CASA),
                   datetime.datetime(2026, 9, 2, 11, 0, tzinfo=CASA))
        kpi = kpi_premier_contact(self.company, jours=3650)
        self.assertEqual(kpi['nb_sous_objectif'], 0)
        self.assertEqual(kpi['mediane_minutes_ouvrees'], 120)

    def test_leads_de_nuit_comptes_et_rappeles_avant_930(self):
        # Arrivé mercredi 23 h (hors fenêtre), rappelé jeudi 09:00.
        self._lead(datetime.datetime(2026, 9, 2, 23, 0, tzinfo=CASA),
                   datetime.datetime(2026, 9, 3, 9, 0, tzinfo=CASA))
        # Arrivé mercredi 23 h, rappelé jeudi 14:00 — trop tard.
        self._lead(datetime.datetime(2026, 9, 2, 23, 0, tzinfo=CASA),
                   datetime.datetime(2026, 9, 3, 14, 0, tzinfo=CASA))
        kpi = kpi_premier_contact(self.company, jours=3650)
        self.assertEqual(kpi['nb_nuit'], 2)
        self.assertEqual(kpi['nb_nuit_rappeles_avant_930'], 1)

    def test_un_lead_jamais_contacte_compte_au_denominateur(self):
        """Il compte comme lead, pas comme délai : l'oublier gonflerait le
        pourcentage de réussite en cachant les leads jamais rappelés."""
        self._lead(datetime.datetime(2026, 9, 2, 9, 0, tzinfo=CASA))
        self._lead(datetime.datetime(2026, 9, 2, 9, 0, tzinfo=CASA),
                   datetime.datetime(2026, 9, 2, 9, 2, tzinfo=CASA))
        kpi = kpi_premier_contact(self.company, jours=3650)
        self.assertEqual(kpi['nb_leads'], 2)
        self.assertEqual(kpi['nb_sous_objectif'], 1)
        self.assertEqual(kpi['pct_sous_objectif'], 50.0)

    def test_les_leads_du_miroir_odoo_sont_exclus(self):
        self._lead(datetime.datetime(2026, 9, 2, 9, 0, tzinfo=CASA),
                   source=Lead.Source.ODOO_IMPORT_TEST)
        self.assertEqual(
            kpi_premier_contact(self.company, jours=3650)['nb_leads'], 0)

    def test_lobjectif_vient_du_profil_societe(self):
        autre = _company('mry19-kpi-obj', objectif=15)
        self.assertEqual(
            kpi_premier_contact(autre)['objectif_minutes'], 15)

    def test_isolation_entre_societes(self):
        voisine = _company('mry19-kpi-voisine')
        self._lead(datetime.datetime(2026, 9, 2, 9, 0, tzinfo=CASA),
                   datetime.datetime(2026, 9, 2, 9, 2, tzinfo=CASA))
        self.assertEqual(kpi_premier_contact(voisine)['nb_leads'], 0)


class KpiApiTests(TestCase):
    def setUp(self):
        self.company = _company('mry19-api')
        self.normal = User.objects.create_user(
            username='mry19-api-u', password='x', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.normal)}')

    def test_lecture_ouverte_a_tout_role(self):
        resp = self.api.get(KPI_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        for cle in ('objectif_minutes', 'nb_leads', 'nb_sous_objectif',
                    'pct_sous_objectif', 'mediane_minutes_ouvrees',
                    'nb_nuit_rappeles_avant_930', 'nb_nuit'):
            self.assertIn(cle, resp.data)

    def test_parametre_jours_invalide_retombe_sur_le_defaut(self):
        resp = self.api.get(KPI_URL, {'jours': 'beaucoup'})
        self.assertEqual(resp.status_code, 200)

    def test_le_chatter_reste_intact(self):
        """Garde négative : le KPI est une LECTURE — il n'écrit rien."""
        avant = LeadActivity.objects.count()
        self.api.get(KPI_URL)
        self.assertEqual(LeadActivity.objects.count(), avant)

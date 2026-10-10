"""ALEA30 — PATCH lead atomique (C-ALEA-018, sondes V3 LFICHE-5 et LCAD-6).

L'écriture du lead, son chatter et le report de la prochaine touche
(``reporter_prochaine_touche``) forment UNE transaction : un report en panne
n'écrit RIEN (plus de ``relance_date`` divergente de la touche). Les effets
secondaires (score, premier contact, émission d'étape) sont best-effort : leur
panne est journalisée et n'échoue jamais le PATCH (plus de 500 après écriture).

La panne est INJECTÉE (doublure de panne déclarée) sur la SEULE dépendance en
panne ; ``perform_update``, ``log_changes`` et l'écriture restent réels.
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mercredi 07/10/2026, 10 h à Casablanca : la touche ouverte est due ce jour.
J = datetime.datetime(2026, 10, 7, 10, 0, tzinfo=horaires.CASABLANCA)


class PatchAtomiqueTests(TestCase):

    def setUp(self):
        gel = frozen(J)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(nom='ALEA30 Solaire',
                                              slug='alea30')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='alea30-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Karim',
            stage=stages.CONTACTED, owner=self.acteur, ville='Casablanca',
            telephone='+212661300030', relance_date=J.date())
        self.etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=2,
            canal=RelanceEtape.Canal.APPEL, libelle='Appel 1',
            due_at=J, due_date=J.date(), cadence_depart=J)
        self.api = APIClient()
        self.api.force_authenticate(self.acteur)
        self.url = f'/api/django/crm/leads/{self.lead.pk}/'

    def _etat_touche(self):
        e = RelanceEtape.objects.get(pk=self.etape.pk)
        return (e.due_at, e.due_date, e.statut, e.nb_reports)

    def _nb_chatter(self):
        return LeadActivity.objects.filter(lead=self.lead).count()

    def test_panne_score_n_echoue_pas_le_patch(self):
        touche_avant = self._etat_touche()
        chatter_avant = self._nb_chatter()
        with mock.patch('apps.crm.leads_score.recompute_lead_score',
                        side_effect=RuntimeError('score en panne')):
            with self.assertLogs('apps.crm.views', level='WARNING') as logs:
                resp = self.api.patch(self.url, {'ville': 'Fès'},
                                      format='json')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', None))
        self.assertTrue(any('score' in ligne.lower() for ligne in logs.output),
                        logs.output)
        # Persistance : relire le lead et la touche.
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.ville, 'Fès')
        self.assertEqual(self._nb_chatter(), chatter_avant + 1)
        self.assertEqual(self._etat_touche(), touche_avant)

    def test_panne_report_annule_tout(self):
        touche_avant = self._etat_touche()
        chatter_avant = self._nb_chatter()
        relance_avant = Lead.objects.get(pk=self.lead.pk).relance_date
        j9 = (J + datetime.timedelta(days=9)).date().isoformat()
        with mock.patch('apps.crm.cadence_plan.reporter_prochaine_touche',
                        side_effect=RuntimeError('report en panne')):
            resp = self.api.patch(self.url, {'relance_date': j9},
                                  format='json')
        self.assertGreaterEqual(resp.status_code, 400)
        self.assertNotEqual(resp.status_code, 200)
        # Persistance : RIEN n'est écrit.
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.relance_date, relance_avant)
        self.assertEqual(self._etat_touche(), touche_avant)
        self.assertEqual(self._nb_chatter(), chatter_avant)

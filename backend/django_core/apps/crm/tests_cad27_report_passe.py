"""CAD27 — une date de report dans le PASSÉ est refusée, le champ NOMMÉ.

Avant : le champ date n'avait pas de ``min``, ``_parse_rappel`` ne vérifiait
que le format et le delta s'appliquait sans contrôle de signe — une faute de
frappe sur l'année tirait tout le plan en arrière, et plusieurs touches
apparaissaient d'un coup « en retard ».

Done : report à hier → 400 nommant le champ (``reporter`` comme « À rappeler
le… » de ``fait``) ; aujourd'hui reste accepté (avancer une touche à
aujourd'hui est un geste utile) ; rien n'est écrit sur un refus.

Au passage (garde-fou de la tâche) : la reprise après visite ne s'appuyait
sur AUCUN delta négatif — ``suspendre_plan_jusqu_apres_visite`` ne tire
jamais une touche EN AVANT, et aucune fonction de reprise après visite
annulée n'existe. Le contrôle vit à la frontière de la saisie humaine (les
vues) : les recalages internes du moteur ne sont pas touchés.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mercredi 23 septembre 2026, 10 h à Casablanca.
MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
HIER = '2026-09-22'
AUJOURDHUI = '2026-09-23'


class _Base(TestCase):
    slug = 'cad27'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD27 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', stage=stages.CONTACTED,
            owner=self.acteur, telephone='+212661002701')
        quand = MERCREDI + datetime.timedelta(days=2)
        self.etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=6,
            canal=RelanceEtape.Canal.APPEL, libelle='Appel 4 (répondeur)',
            due_at=quand,
            due_date=quand.astimezone(horaires.CASABLANCA).date(),
            cadence_depart=MERCREDI - datetime.timedelta(days=2))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _reporter(self, **corps):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{self.etape.pk}/reporter/',
            corps, format='json')


class ReporterTests(_Base):
    slug = 'cad27-reporter'

    def test_report_a_hier_refuse_en_nommant_le_champ(self):
        avant = self.etape.due_at
        resp = self._reporter(rappel_le=HIER, rappel_heure='11:00')
        self.assertEqual(resp.status_code, 400)
        message = resp.data['erreurs']['rappel_le']
        self.assertIn('« Reporter au »', message)
        self.assertIn('22/09/2026', message)
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.due_at, avant)
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead, body__startswith='Rappel demandé').exists())

    def test_la_forme_iso_est_refusee_sous_son_propre_champ(self):
        hier = (MERCREDI - datetime.timedelta(days=1)).isoformat()
        resp = self._reporter(due_at=hier)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('due_at', resp.data['erreurs'])

    def test_la_mise_en_veille_refuse_aussi_le_passe(self):
        resp = self._reporter(rappel_le=HIER, mode='veille')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('rappel_le', resp.data['erreurs'])

    def test_aujourd_hui_reste_accepte(self):
        # Avancer une touche à aujourd'hui : la liberté utile est intacte.
        resp = self._reporter(rappel_le=AUJOURDHUI, rappel_heure='15:00')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.due_date,
                         datetime.date.fromisoformat(AUJOURDHUI))


class RappelDepuisLeFaitTests(_Base):
    slug = 'cad27-fait'

    def test_rappel_a_hier_refuse_en_nommant_le_champ(self):
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{self.etape.pk}/fait/',
            {'outcome': 'rappel', 'rappel_le': HIER}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('« Rappeler le »', resp.data['erreurs']['rappel_le'])
        # Rien n'est écrit : la touche reste à faire.
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.statut, RelanceEtape.Statut.A_FAIRE)

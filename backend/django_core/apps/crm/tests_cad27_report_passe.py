"""CAD27 — une date de report dans le PASSÉ est refusée, le champ NOMMÉ.

Avant : le champ date n'avait pas de ``min``, ``_parse_rappel`` ne vérifiait
que le format et le delta s'appliquait sans contrôle de signe — une faute de
frappe sur l'année tirait tout le plan en arrière, et plusieurs touches
apparaissaient d'un coup « en retard ».

Done : report à hier → refus nommant le champ (409 d'état pour ``reporter``,
400 pour « À rappeler le… » de ``fait``) ; aujourd'hui reste accepté (avancer une touche à
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
        # ENF11 (api-fuzz-full 24/10) : refus d'ÉTAT (horloge serveur) = 409,
        # même corps ``erreurs`` qu'avant.
        self.assertEqual(resp.status_code, 409)
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
        self.assertEqual(resp.status_code, 409)
        self.assertIn('due_at', resp.data['erreurs'])
        # Une date-heure ISO ancienne est conforme au schéma : jamais un 400.
        resp = self._reporter(due_at='2000-01-01T00:00:00Z')
        self.assertEqual(resp.status_code, 409)
        self.assertIn('due_at', resp.data['erreurs'])

    def test_la_mise_en_veille_refuse_aussi_le_passe(self):
        resp = self._reporter(rappel_le=HIER, mode='veille')
        self.assertEqual(resp.status_code, 409)
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


class InstantHorsPlageTests(_Base):
    """api-fuzz 24/10 — un décalage ``-17:25`` (hors plage Postgres) mettait
    le réveil en 500 ; les bords an 1 / an 9999 ne lèvent plus d'overflow."""
    slug = 'cad27-hors-plage'

    def test_decalage_hors_plage_postgres_ramene_en_utc(self):
        resp = self._reporter(due_at='2030-12-09T15:35:00-17:25',
                              mode='veille')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_bords_du_calendrier(self):
        resp = self._reporter(due_at='0001-01-01T00:00:00+14:00')
        self.assertEqual(resp.status_code, 409)
        self.assertIn('due_at', resp.data['erreurs'])
        resp = self._reporter(due_at='9999-12-31T23:59:59-17:25')
        self.assertEqual(resp.status_code, 400)

    def test_ricochet_hors_calendrier_409_rien_ecrit(self):
        """api-fuzz-full 27/10 (ENF11) — date conforme (an 5298) mais une
        touche SUIVANTE déjà en l'an 8000 glisserait au-delà de l'an 9999 :
        ``OverflowError`` → 500 « geste annulé » ; désormais 409 nommé, et
        RIEN n'est écrit (ni la touche, ni la suivante)."""
        loin = datetime.datetime(8000, 1, 5, 10, 0, tzinfo=horaires.CASABLANCA)
        suivante = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=7,
            canal=RelanceEtape.Canal.APPEL, libelle='Appel 5', due_at=loin,
            due_date=loin.date(), due_initial_at=loin,
            cadence_depart=MERCREDI - datetime.timedelta(days=2))
        avant = self.etape.due_at
        resp = self._reporter(due_at='5298-05-29T10:15:47-02:40')
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertIn('due_at', resp.data['erreurs'])
        self.etape.refresh_from_db()
        suivante.refresh_from_db()
        self.assertEqual(self.etape.due_at, avant)
        self.assertEqual(suivante.due_at, loin)

    def test_motif_publie_du_jour_suit_le_calendrier(self):
        import re
        from apps.crm.schema_docs import MOTIF_JOUR_PUBLIE
        for jour in ('0000-10-01', '2026-02-30', '2026-04-31', '2026-13-01'):
            self.assertIsNone(re.fullmatch(MOTIF_JOUR_PUBLIE, jour), jour)
        for jour in ('0001-01-01', '0999-12-31', '2026-02-28', '9999-12-31'):
            self.assertTrue(re.fullmatch(MOTIF_JOUR_PUBLIE, jour), jour)
            datetime.date.fromisoformat(jour)

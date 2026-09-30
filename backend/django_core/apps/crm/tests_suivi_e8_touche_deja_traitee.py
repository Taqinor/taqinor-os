"""SUIVI E8 — « Fait » / « Sauter » / « Reporter » refusent une touche déjà
traitée.

SUIVI-PARCOURS 30/09/2026. ``views._marquer`` et ``reporter`` ne vérifiaient
pas le statut : une touche close (deux onglets ouverts, double clic, liste
périmée) pouvait être re-cochée — la suite du moteur rejouait une seconde
fois (barreau suivant, filet, arrêt de cadence) — ou reportée, ce qui
déplaçait tout le reste du plan depuis une touche qui n'était plus la
prochaine. Décision : 400 ``{"erreurs": {"etape": "Cette étape est déjà
traitée — rechargez la liste."}}`` quand la touche n'est plus À FAIRE, avant
toute écriture. ``annuler`` (RLC1) n'est pas concerné : il vise précisément
une touche traitée.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import marquer_etape_relance
from apps.crm.views import MESSAGE_ETAPE_DEJA_TRAITEE
from apps.parametres.models import CompanyProfile

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
FAIT = RelanceEtape.Statut.FAIT

_seq = itertools.count(1)


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E8 {n}', slug=f'suivi-e8-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'suivi-e8-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E8 {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266180{n:04d}')

    def _touche(self):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=2,
            canal=RelanceEtape.Canal.APPEL, libelle="Appel d'ouverture",
            due_at=GEL, due_date=GEL.date(), cadence_depart=GEL)

    def _touche_faite(self):
        etape = self._touche()
        marquer_etape_relance(etape, self.acteur, FAIT, outcome='non_joint')
        etape.refresh_from_db()
        return etape

    def _post(self, etape, action, corps=None):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/{action}/',
            corps or {}, format='json')

    def _refus(self, resp):
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['erreurs']['etape'],
                         MESSAGE_ETAPE_DEJA_TRAITEE)


class ToucheDejaTraiteeTests(_Base):

    def test_un_second_fait_est_refuse_sans_rien_rejouer(self):
        etape = self._touche_faite()
        activites = self.lead.activites.count()
        touches = self.lead.relance_etapes.count()
        self._refus(self._post(etape, 'fait', {'outcome': 'joint'}))
        etape.refresh_from_db()
        self.assertEqual(etape.outcome, 'non_joint')
        self.assertEqual(self.lead.activites.count(), activites)
        self.assertEqual(self.lead.relance_etapes.count(), touches)

    def test_sauter_une_touche_faite_est_refuse(self):
        etape = self._touche_faite()
        self._refus(self._post(etape, 'sauter'))
        etape.refresh_from_db()
        self.assertEqual(etape.statut, FAIT)

    def test_reporter_une_touche_faite_est_refuse(self):
        etape = self._touche_faite()
        avant = etape.due_at
        self._refus(self._post(etape, 'reporter',
                               {'rappel_le': '2026-09-28',
                                'rappel_heure': '11:00'}))
        etape.refresh_from_db()
        self.assertEqual(etape.due_at, avant)

    def test_une_touche_annulee_par_le_moteur_est_refusee_aussi(self):
        etape = self._touche()
        etape.statut = RelanceEtape.Statut.ANNULEE
        etape.save(update_fields=['statut'])
        self._refus(self._post(etape, 'fait', {'outcome': 'joint'}))
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead, outcome='joint').exists())


class TemoinsTests(_Base):

    def test_une_touche_a_faire_reste_acceptee(self):
        resp = self._post(self._touche(), 'fait', {'outcome': 'non_joint'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], FAIT)

    def test_annuler_une_touche_traitee_reste_permis(self):
        etape = self._touche_faite()
        resp = self._post(etape, 'annuler')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], RelanceEtape.Statut.A_FAIRE)

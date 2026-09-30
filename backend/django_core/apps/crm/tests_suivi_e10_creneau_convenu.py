"""SUIVI E10 — « Message — proposer un créneau » : le créneau convenu
devient un APPEL.

SUIVI-PARCOURS 30/09/2026 (table : « Créneau convenu le… » → étape
``rappel_convenu``, jour ``date_choisie``). Sur l'étape « Message — proposer
un créneau pour l'appel », « À rappeler le… » DÉPLAÇAIT l'étape message
telle quelle (règle CAD3 des étapes de filet) : le jour convenu, la
commerciale retrouvait un MESSAGE à envoyer, et l'étape « Rappeler le client
— rappel convenu » restait inatteignable depuis l'écran. Décision : l'étape
message est CLOSE (FAIT, issue « à rappeler ») et l'appel « rappel convenu »
est posé à la date ET à l'heure convenues, recalées sur la fenêtre d'appel.
Code d'effet ``etape_rappel_convenu_a_la_date`` ; ``prochaine_touche`` =
cette étape.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca ; créneau convenu le
lundi 28/09.
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm import suite_touche as st
from apps.crm.cadence_config import (
    CLE_APPEL_APRES_REPONSE, CLE_MESSAGE_CRENEAU, CLE_RAPPEL_CONVENU, q_etape)
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
CRENEAU = datetime.date(2026, 9, 28)
A_FAIRE = RelanceEtape.Statut.A_FAIRE

_seq = itertools.count(1)


def _heure_locale(etape):
    return etape.due_at.astimezone(horaires.CASABLANCA).strftime('%H:%M')


class PromesseTests(SimpleTestCase):

    def test_le_creneau_convenu_annonce_l_appel_a_la_date(self):
        etape = RelanceEtape(cadence='generique', ordre=1,
                             canal=RelanceEtape.Canal.WHATSAPP,
                             cle=CLE_MESSAGE_CRENEAU,
                             libelle=services.FILET_MESSAGE_CRENEAU_LIBELLE,
                             statut=A_FAIRE)
        etape.lead = Lead(nom='témoin', stage=stages.CONTACTED)
        promesses = st.promesses_touche(etape, ordres=frozenset(),
                                        est_actif=lambda c: True)
        self.assertEqual(promesses['rappel'],
                         [st.ETAPE_RAPPEL_CONVENU_A_LA_DATE])

    def test_ailleurs_l_etape_de_filet_reste_deplacee(self):
        etape = RelanceEtape(cadence='generique', ordre=1,
                             canal=RelanceEtape.Canal.APPEL,
                             cle=CLE_APPEL_APRES_REPONSE,
                             libelle=services.FILET_APPEL_LIBELLE,
                             statut=A_FAIRE)
        etape.lead = Lead(nom='témoin', stage=stages.CONTACTED)
        promesses = st.promesses_touche(etape, ordres=frozenset(),
                                        est_actif=lambda c: True)
        self.assertEqual(promesses['rappel'], [st.ETAPE_DEPLACEE_A_LA_DATE])


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E10 {n}', slug=f'suivi-e10-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e10-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E10 {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266101{n:04d}')

    def _filet(self, cle, libelle, canal):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='generique',
            ordre=1, canal=canal, cle=cle, libelle=libelle, due_at=GEL,
            due_date=GEL.date())

    def _message_creneau(self):
        return self._filet(CLE_MESSAGE_CRENEAU,
                           services.FILET_MESSAGE_CRENEAU_LIBELLE,
                           RelanceEtape.Canal.WHATSAPP)

    def _rappel(self, etape, heure):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'outcome': 'rappel', 'rappel_le': CRENEAU.isoformat(),
             'rappel_heure': heure}, format='json')


class CreneauConvenuTests(_Base):

    def test_le_creneau_devient_un_appel_a_la_date_et_a_l_heure(self):
        message = self._message_creneau()
        resp = self._rappel(message, '17:30')

        self.assertEqual(resp.status_code, 200, resp.data)
        message.refresh_from_db()
        self.assertEqual(message.statut, RelanceEtape.Statut.FAIT)
        self.assertEqual(message.outcome, 'rappel')
        rappel = self.lead.relance_etapes.get(q_etape(CLE_RAPPEL_CONVENU),
                                              statut=A_FAIRE)
        self.assertEqual(rappel.canal, RelanceEtape.Canal.APPEL)
        self.assertEqual(rappel.due_date, CRENEAU)
        self.assertEqual(_heure_locale(rappel), '17:30')
        self.assertEqual(
            list(self.lead.relance_etapes.filter(statut=A_FAIRE)), [rappel])
        prochaine = resp.data['prochaine_touche']
        self.assertEqual(prochaine['cle'], CLE_RAPPEL_CONVENU)
        self.assertEqual(prochaine['due_date'], CRENEAU.isoformat())
        self.assertTrue(self.lead.activites.filter(
            body__startswith='Créneau convenu avec le client',
            user__isnull=True).exists())

    def test_l_heure_est_recalee_sur_la_fenetre_d_appel(self):
        resp = self._rappel(self._message_creneau(), '07:00')
        self.assertEqual(resp.status_code, 200, resp.data)
        rappel = self.lead.relance_etapes.get(q_etape(CLE_RAPPEL_CONVENU))
        self.assertEqual(rappel.due_date, CRENEAU)
        self.assertGreaterEqual(_heure_locale(rappel), '09:00')


class TemoinFiletTests(_Base):
    """Les autres étapes de filet gardent CAD3 : déplacées à la date."""

    def test_appel_apres_reponse_est_deplace(self):
        appel = self._filet(CLE_APPEL_APRES_REPONSE,
                            services.FILET_APPEL_LIBELLE,
                            RelanceEtape.Canal.APPEL)
        resp = self._rappel(appel, '11:00')
        self.assertEqual(resp.status_code, 200, resp.data)
        appel.refresh_from_db()
        self.assertEqual(appel.statut, A_FAIRE)
        self.assertEqual(appel.due_date, CRENEAU)
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_RAPPEL_CONVENU)).exists())

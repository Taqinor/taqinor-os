"""SUIVI E15 — « Deuxième affaire » s'arrête comme la prise de contact.

SUIVI-PARCOURS 30/09/2026 (table : la deuxième affaire est rangée sous les
types « Appel / Message de prise de contact »). ``CADENCES_ARRETEES_PAR_ISSUE``
ne connaissait pas la cadence ``deuxieme_affaire`` : « Client joint » y
posait l'étape de filet ET faisait naître le barreau 2 (deux touches
ouvertes pour un client déjà joint), et « Refus » laissait le barreau 2
suivre. Décision : ``deuxieme_affaire`` est arrêtée par ``joint``,
``interesse``, ``visite_acceptee`` et ``refuse``, exactement comme
``contact``.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
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
from apps.crm import cadence_reperes
from apps.crm import suite_touche as st
from apps.crm.cadence_config import CLE_APPEL_APRES_REPONSE, CLE_DECIDER_SUITE
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
A_FAIRE = RelanceEtape.Statut.A_FAIRE
ISSUES = ('joint', 'interesse', cadence_reperes.OUTCOME_VISITE_ACCEPTEE, 'refuse')

_seq = itertools.count(1)


def _message():
    etape = RelanceEtape(cadence='deuxieme_affaire', ordre=1,
                         canal=RelanceEtape.Canal.WHATSAPP,
                         libelle="Message d'identité", statut=A_FAIRE)
    etape.lead = Lead(nom='témoin', stage=stages.NEW)
    return etape


class TableEtPromessesTests(SimpleTestCase):

    def test_la_table_d_arret_connait_la_deuxieme_affaire(self):
        for issue in ISSUES:
            with self.subTest(issue=issue):
                self.assertIn('deuxieme_affaire',
                              services.CADENCES_ARRETEES_PAR_ISSUE[issue])
                self.assertFalse(services.issue_fait_naitre_la_suite(
                    issue, 'deuxieme_affaire'))

    def test_les_promesses_ne_disent_plus_la_touche_suivante(self):
        promesses = st.promesses_touche(
            _message(), ordres=frozenset({1, 2}), est_actif=lambda c: True)
        self.assertEqual(promesses['joint'],
                         [st.CONTACT_ARRETEE, st.ETAPE_APPELER])
        self.assertEqual(promesses['refuse'],
                         [st.RELANCES_ARRETEES, st.ETAPE_DECIDER_SUITE])
        self.assertEqual(promesses[cadence_reperes.OUTCOME_VISITE_ACCEPTEE],
                         [st.CONTACT_ARRETEE, st.ETAPE_PLANIFIER_VISITE])


class DeuxiemeAffaireApiTests(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E15 {n}', slug=f'suivi-e15-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e15-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Client acquis E15 {n}',
            stage=stages.NEW, owner=self.acteur,
            telephone=f'+21266115{n:04d}')
        self.message = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='deuxieme_affaire',
            ordre=1, canal=RelanceEtape.Canal.WHATSAPP,
            libelle="Message d'identité", due_at=GEL, due_date=GEL.date(),
            cadence_depart=GEL)

    def _fait(self, outcome):
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{self.message.pk}/fait/',
            {'outcome': outcome}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_client_joint_une_seule_suite(self):
        self._fait('joint')
        [ouverte] = list(self.lead.relance_etapes.filter(statut=A_FAIRE))
        self.assertEqual(ouverte.cle, CLE_APPEL_APRES_REPONSE)
        self.assertFalse(self.lead.relance_etapes.filter(
            cadence='deuxieme_affaire', ordre=2).exists())

    def test_refus_arrete_la_deuxieme_affaire(self):
        self._fait('refuse')
        [ouverte] = list(self.lead.relance_etapes.filter(statut=A_FAIRE))
        self.assertEqual(ouverte.cle, CLE_DECIDER_SUITE)

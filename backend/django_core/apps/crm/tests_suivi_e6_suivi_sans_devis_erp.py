"""SUIVI E6 — le suivi de proposition SANS devis dans l'ERP est poursuivi.

SUIVI-PARCOURS 30/09/2026. Un devis parti hors ERP (WhatsApp) fait démarrer
un suivi de proposition SANS objet devis (TREADMILL-1538). Deux trous :

(i) « Client joint » sur un barreau de ce suivi re-posait « Préparer et
    envoyer le devis » À CÔTÉ du barreau suivant — deux touches ouvertes ;
(ii) clore l'étape « Question de prix » ne REPRENAIT pas le suivi : elle
    re-posait l'étape devis, et « Devis envoyé » rejouait le plan depuis le
    barreau 1.

Décision (``assurer_prochaine_etape_apres_succes``) : sans devis relançable
dans l'ERP mais avec un suivi déjà servi, POURSUIVRE depuis
``dernier_barreau_consomme(lead, 'apres_devis', None)`` ; l'étape générique
seulement si le plan est épuisé. « Devis parti » (``brouillon_compris``) ne
redémarre un plan sans devis que si AUCUN barreau n'a été consommé.

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
from apps.crm import suite_touche as st
from apps.crm.cadence_config import CLE_DEVIS, q_etape
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
DEPART = GEL - datetime.timedelta(days=2)
A_FAIRE = RelanceEtape.Statut.A_FAIRE
FAIT = RelanceEtape.Statut.FAIT

_seq = itertools.count(1)


def _gabarit(ordre):
    return next(e for e in CADENCES_DEFAUT['apres_devis']
                if e['ordre'] == ordre)


class PromesseTests(SimpleTestCase):

    def test_client_joint_sans_devis_annonce_la_seule_touche_suivante(self):
        etape = RelanceEtape(cadence='apres_devis', ordre=2,
                             canal=RelanceEtape.Canal.APPEL,
                             libelle='Appel de suivi',
                             statut=A_FAIRE, devis_id=None)
        etape.lead = Lead(nom='témoin', stage=stages.QUOTE_SENT)
        promesses = st.promesses_touche(
            etape, ordres=frozenset(e['ordre'] for e in
                                    CADENCES_DEFAUT['apres_devis']),
            est_actif=lambda c: True)
        self.assertEqual(promesses['joint'], [st.TOUCHE_SUIVANTE])


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E6 {n}', slug=f'suivi-e6-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e6-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E6 {n}',
            stage=stages.QUOTE_SENT, owner=self.acteur,
            telephone=f'+21266160{n:04d}')

    def _barreau(self, ordre, statut=A_FAIRE):
        gabarit = _gabarit(ordre)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=ordre, canal=gabarit['canal'], libelle=gabarit['libelle'],
            devis=None, statut=statut, due_at=GEL, due_date=GEL.date(),
            cadence_depart=DEPART,
            traite_par=None if statut == A_FAIRE else self.acteur,
            traite_le=None if statut == A_FAIRE else GEL)

    def _fait(self, etape, **corps):
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/', corps,
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def _ouvertes(self):
        return list(self.lead.relance_etapes.filter(statut=A_FAIRE))

    def _assert_relance_date(self, ouverte):
        """SUIVI I6 — la touche reprise (ou démarrée) par le filet porte
        ``Lead.relance_date`` : jamais vide quand une touche est ouverte."""
        self.lead.refresh_from_db(fields=['relance_date'])
        self.assertEqual(self.lead.relance_date, ouverte.due_date)


class SuiviSansDevisPoursuiviTests(_Base):

    def test_client_joint_ne_pose_plus_l_etape_devis_a_cote(self):
        appel = self._barreau(2)
        self._fait(appel, outcome='joint')
        [ouverte] = self._ouvertes()
        self.assertEqual(ouverte.cadence, 'apres_devis')
        self.assertGreater(ouverte.ordre, 2)
        self.assertIsNone(ouverte.devis_id)
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_DEVIS)).exists())
        self._assert_relance_date(ouverte)

    def test_la_question_de_prix_reprend_le_suivi(self):
        appel = self._barreau(2)
        self._fait(appel, reponse=services.REPONSE_QUESTION_PRIX)
        question = self.lead.relance_etapes.get(
            libelle=services.QUESTION_PRIX_LIBELLE, statut=A_FAIRE)

        self._fait(question)

        [ouverte] = self._ouvertes()
        self.assertEqual(ouverte.cadence, 'apres_devis')
        self.assertGreater(ouverte.ordre, 2)
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_DEVIS)).exists())
        self._assert_relance_date(ouverte)

    def test_devis_parti_poursuit_sans_rejouer_depuis_le_barreau_1(self):
        self._barreau(2, statut=FAIT)
        devis = services.poser_etape_preparer_devis(
            self.lead, origine='test', user=self.acteur)
        self._fait(devis)
        [ouverte] = self._ouvertes()
        self.assertEqual(ouverte.cadence, 'apres_devis')
        self.assertGreater(ouverte.ordre, 2)
        self.assertFalse(self.lead.relance_etapes.filter(
            cadence='apres_devis', ordre=1).exists())
        self._assert_relance_date(ouverte)

    def test_plan_epuise_l_etape_generique_prend_le_relais(self):
        self._barreau(10, statut=FAIT)
        decider = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='generique',
            ordre=1, canal=RelanceEtape.Canal.APPEL,
            libelle=services.FILET_REFUS_LIBELLE, due_at=GEL,
            due_date=GEL.date())
        self._fait(decider)
        [ouverte] = self._ouvertes()
        self.assertEqual(ouverte.cle, CLE_DEVIS)
        self._assert_relance_date(ouverte)


class TemoinDemarrageTests(_Base):
    """Aucun barreau consommé : « devis parti » DÉMARRE le suivi sans devis
    (TREADMILL-1538, inchangé)."""

    def test_devis_parti_sans_aucun_suivi_demarre_au_barreau_1(self):
        devis = services.poser_etape_preparer_devis(
            self.lead, origine='test', user=self.acteur)
        self._fait(devis)
        [ouverte] = self._ouvertes()
        self.assertEqual((ouverte.cadence, ouverte.ordre), ('apres_devis', 1))
        self.assertIsNone(ouverte.devis_id)
        self._assert_relance_date(ouverte)

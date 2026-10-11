"""SUIVI E9 — la réponse du « Fait » NOMME l'étape suivante.

SUIVI-PARCOURS 30/09/2026. ``prochaine_touche`` (réponse de ``fait``, du
report d'une étape de filet et de ``piece-recue``) ne portait que
``{due_at, due_date, canal}`` : l'écran annonçait « Prochain appel
programmé » pour « Préparer et envoyer le devis ». Décision (ADDITIVE) :
``libelle`` (celui de l'étape) et ``cle`` (``cadence_config.cle_de`` — aussi
pour une étape posée avant la clé ; ``''`` pour un barreau du protocole),
servis par UNE fonction (``views._prochaine_touche_publique``).

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime
import itertools
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages, cadence_reperes
from apps.crm import cadence_reponses
from apps.crm.cadence_config import CLE_DEVIS
from apps.crm.models import Lead, RelanceEtape
from apps.crm.cadence_views import _prochaine_touche_publique
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
A_FAIRE = RelanceEtape.Statut.A_FAIRE
CHAMPS = {'due_at', 'due_date', 'canal', 'libelle', 'cle'}

PIECE_RECUE = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'relance_piece_recue.json').read_text(encoding='utf-8'))

_seq = itertools.count(1)


class FormePubliqueTests(SimpleTestCase):

    def _etape(self, **champs):
        valeurs = dict(cadence='generique', ordre=1,
                       canal=RelanceEtape.Canal.APPEL, due_at=GEL,
                       due_date=GEL.date())
        valeurs.update(champs)
        return RelanceEtape(**valeurs)

    def test_une_etape_renommee_garde_sa_cle(self):
        forme = _prochaine_touche_publique(
            self._etape(cle=CLE_DEVIS, libelle='Faire le devis'))
        self.assertEqual(set(forme), CHAMPS)
        self.assertEqual(forme['libelle'], 'Faire le devis')
        self.assertEqual(forme['cle'], CLE_DEVIS)
        self.assertEqual(forme['canal'], RelanceEtape.Canal.APPEL)
        self.assertEqual(forme['due_date'], GEL.date().isoformat())
        self.assertEqual(forme['due_at'], GEL.isoformat())

    def test_une_etape_posee_avant_la_cle_est_reconnue(self):
        forme = _prochaine_touche_publique(
            self._etape(libelle=cadence_reperes.FILET_JOINT_LIBELLE))
        self.assertEqual(forme['cle'], CLE_DEVIS)

    def test_un_barreau_du_protocole_n_a_pas_de_cle(self):
        forme = _prochaine_touche_publique(self._etape(
            cadence='contact', ordre=2, libelle="Appel d'ouverture"))
        self.assertEqual(forme['cle'], '')
        self.assertEqual(forme['libelle'], "Appel d'ouverture")

    def test_rien_d_ouvert(self):
        self.assertIsNone(_prochaine_touche_publique(None))

    def test_le_contrat_piece_recue_porte_la_meme_forme(self):
        self.assertEqual(set(PIECE_RECUE['exemple']['prochaine_touche']),
                         CHAMPS)


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E9 {n}', slug=f'suivi-e9-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e9-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E9 {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266190{n:04d}')

    def _touche(self, **champs):
        valeurs = dict(company=self.company, lead=self.lead, due_at=GEL,
                       due_date=GEL.date())
        valeurs.update(champs)
        return RelanceEtape.objects.create(**valeurs)


class ReponsesNommentLEtapeTests(_Base):

    def test_client_joint_annonce_preparer_le_devis_par_son_nom(self):
        appel = self._touche(cadence='contact', ordre=2,
                             canal=RelanceEtape.Canal.APPEL,
                             libelle="Appel d'ouverture", cadence_depart=GEL)
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{appel.pk}/fait/',
            {'outcome': 'joint'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        devis = self.lead.relance_etapes.get(cle=CLE_DEVIS, statut=A_FAIRE)
        prochaine = resp.data['prochaine_touche']
        self.assertEqual(set(prochaine), CHAMPS)
        self.assertEqual(prochaine['cle'], CLE_DEVIS)
        self.assertEqual(prochaine['libelle'], devis.libelle)

    def test_le_report_d_une_etape_de_filet_la_nomme(self):
        filet = self._touche(cadence='generique', ordre=1,
                             canal=RelanceEtape.Canal.APPEL,
                             libelle=cadence_reperes.FILET_REFUS_LIBELLE)
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{filet.pk}/fait/',
            {'outcome': 'rappel', 'rappel_le': '2026-09-28',
             'rappel_heure': '11:00'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        prochaine = resp.data['prochaine_touche']
        self.assertEqual(prochaine['libelle'], cadence_reperes.FILET_REFUS_LIBELLE)
        self.assertEqual(prochaine['cle'], 'decider_suite')
        self.assertEqual(prochaine['due_date'], '2026-09-28')

    def test_piece_recue_nomme_l_etape_devis(self):
        message = self._touche(cadence='contact', ordre=1,
                               canal=RelanceEtape.Canal.WHATSAPP,
                               libelle="Message d'identité",
                               cadence_depart=GEL)
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{message.pk}/piece-recue/',
            {'type_piece': 'facture'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['prochaine_touche']['cle'], CLE_DEVIS)
        self.assertEqual(set(resp.data['prochaine_touche']), CHAMPS)


class LaPlusProcheToucheTests(_Base):
    """SUIVI I7 (écart confirmé par le vérificateur) — ``prochaine_touche``
    est TOUJOURS la plus proche touche OUVERTE du lead, jamais l'étape qu'une
    branche vient de déplacer ou de poser : ici « Le PDF s'ouvre bien ? »
    tombe DEMAIN, avant la date choisie (lundi 28/09)."""

    def setUp(self):
        super().setUp()
        demain = GEL + datetime.timedelta(days=1)
        gabarit = next(e for e in CADENCES_DEFAUT['apres_devis']
                       if e['ordre'] == 1)
        self.proche = self._touche(
            cadence='apres_devis', ordre=1, canal=gabarit['canal'],
            libelle=gabarit['libelle'], due_at=demain,
            due_date=demain.date(), cadence_depart=GEL)

    def _rappel(self, etape):
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'outcome': 'rappel', 'rappel_le': '2026-09-28',
             'rappel_heure': '11:00'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def _assert_la_plus_proche(self, resp):
        prochaine = resp.data['prochaine_touche']
        self.assertEqual(prochaine['due_date'],
                         self.proche.due_date.isoformat())
        self.assertEqual(prochaine['libelle'], self.proche.libelle)
        self.assertEqual(prochaine['cle'], '')

    def test_etape_de_filet_deplacee_plus_loin(self):
        passation = self._touche(cadence='generique',
                                 ordre=cadence_reponses.PASSATION_ORDRE,
                                 canal=RelanceEtape.Canal.WHATSAPP,
                                 libelle=cadence_reperes.PASSATION_LIBELLE)
        resp = self._rappel(passation)
        passation.refresh_from_db()
        self.assertEqual(passation.statut, A_FAIRE)
        self.assertEqual(passation.due_date, datetime.date(2026, 9, 28))
        self._assert_la_plus_proche(resp)

    def test_rappel_convenu_pose_plus_loin(self):
        creneau = self._touche(cadence='generique', ordre=1,
                               canal=RelanceEtape.Canal.WHATSAPP,
                               cle='message_creneau',
                               libelle=cadence_reperes.FILET_MESSAGE_CRENEAU_LIBELLE)
        resp = self._rappel(creneau)
        self.assertTrue(self.lead.relance_etapes.filter(
            cle='rappel_convenu', statut=A_FAIRE,
            due_date=datetime.date(2026, 9, 28)).exists())
        self._assert_la_plus_proche(resp)

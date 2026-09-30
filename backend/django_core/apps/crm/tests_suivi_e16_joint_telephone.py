"""SUIVI E16 — « Client joint au téléphone » sur une touche MESSAGE.

SUIVI-PARCOURS 30/09/2026 (table : réponse ``joint_telephone`` des types
« Message de prise de contact », « Message de suivi de la proposition » et
« Message de réveil »). La commerciale appelle au lieu d'écrire et le client
décroche : la seule réponse était « Le client a répondu » — issue « joint »
sur une ligne de chatter WhatsApp — et le récepteur MRY9 posait « Appeler le
client — il a répondu au message », un second appel pour un client qu'on
venait d'avoir.

Décision : nouvelle réponse ``joint_telephone`` (touches ÉCRITES du protocole,
deuxième affaire comprise ; jamais un geste de visite ni une étape de
filet). Issue « joint », mais la ligne de chatter est un APPEL
(``marquer_etape_relance(..., canal_reel=appel)``) : la suite est celle d'un
appel abouti — prise de contact : « Préparer et envoyer le devis » demain ;
suivi de proposition : le barreau suivant ; réveil : le dossier sort du
Froid et un suivi pendant reprend, sinon l'étape devis.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca (« demain » = jeudi
24/09).
"""
import datetime
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm import suite_touche as st
from apps.crm.cadence_config import (
    CLE_APPEL_APRES_REPONSE, CLE_CONFIRMATION, CLE_DEVIS, CLE_MESSAGE_CRENEAU,
    cle_de, q_etape)
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape
from apps.ventes.models import Devis

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
DEMAIN = datetime.date(2026, 9, 24)
A_FAIRE = RelanceEtape.Statut.A_FAIRE
FAIT = RelanceEtape.Statut.FAIT
APPEL = RelanceEtape.Canal.APPEL
WHATSAPP = RelanceEtape.Canal.WHATSAPP
EMAIL = RelanceEtape.Canal.EMAIL
JOINT_TELEPHONE = services.REPONSE_JOINT_TELEPHONE

_seq = itertools.count(1)


def _ordres(cadence):
    return frozenset(e['ordre'] for e in CADENCES_DEFAUT.get(cadence, []))


def _gabarit(cadence, ordre):
    return next(e for e in CADENCES_DEFAUT[cadence] if e['ordre'] == ordre)


def _touche(cadence, ordre, canal, *, stage=stages.CONTACTED, cle='',
            libelle='Touche', devis=False):
    etape = RelanceEtape(cadence=cadence, ordre=ordre, canal=canal,
                         libelle=libelle, cle=cle, statut=A_FAIRE,
                         devis_id=903 if devis else None)
    etape.lead = Lead(nom='témoin', stage=stage)
    return etape


def _promesses(etape):
    return st.promesses_touche(etape, ordres=_ordres(etape.cadence),
                               est_actif=lambda cle: True)


class ReponseServieTests(SimpleTestCase):

    def test_servie_juste_apres_client_joint_sur_les_touches_ecrites(self):
        for cadence in ('contact', 'deuxieme_affaire', 'apres_devis',
                        'reveil'):
            for canal in (WHATSAPP, EMAIL):
                with self.subTest(cadence=cadence, canal=canal):
                    cles = st.cles_de_reponse(_touche(cadence, 1, canal))
                    self.assertEqual(
                        cles[cles.index('joint') + 1], JOINT_TELEPHONE)

    def test_jamais_sur_un_appel(self):
        for cadence in ('contact', 'deuxieme_affaire', 'apres_devis',
                        'reveil', 'generique'):
            with self.subTest(cadence=cadence):
                self.assertNotIn(JOINT_TELEPHONE,
                                 st.cles_de_reponse(_touche(cadence, 1, APPEL)))


class PromessesTests(SimpleTestCase):
    """La promesse est celle d'un APPEL abouti, jamais celle d'un message
    répondu (« Appeler le client »)."""

    def test_prise_de_contact_et_deuxieme_affaire_le_devis_demain(self):
        for cadence in ('contact', 'deuxieme_affaire'):
            with self.subTest(cadence=cadence):
                promesses = _promesses(_touche(cadence, 1, WHATSAPP))
                self.assertEqual(promesses['joint'],
                                 [st.CONTACT_ARRETEE, st.ETAPE_APPELER])
                self.assertEqual(promesses[JOINT_TELEPHONE],
                                 [st.CONTACT_ARRETEE, st.ETAPE_DEVIS_DEMAIN])

    def test_suivi_de_proposition_le_barreau_suivant(self):
        derniere = max(_ordres('apres_devis'))
        milieu = _promesses(_touche('apres_devis', 1, WHATSAPP,
                                    stage=stages.QUOTE_SENT, devis=True))
        self.assertEqual(milieu[JOINT_TELEPHONE], [st.TOUCHE_SUIVANTE])
        fin = _promesses(_touche('apres_devis', derniere, WHATSAPP,
                                 stage=stages.QUOTE_SENT, devis=True))
        # SUIVI E22 (30/09/2026) — sur la DERNIÈRE touche du suivi, « Client
        # joint » (message répondu ou au téléphone) pose « Décider la suite »,
        # jamais « l'appeler » ni l'étape devis d'un devis déjà parti.
        self.assertEqual(fin['joint'], [st.ETAPE_DECIDER_SUITE])
        self.assertEqual(fin[JOINT_TELEPHONE], [st.ETAPE_DECIDER_SUITE])

    def test_reveil_sort_du_froid_et_reprend(self):
        promesses = _promesses(_touche('reveil', 2, WHATSAPP,
                                       stage=stages.COLD))
        self.assertEqual(
            promesses[JOINT_TELEPHONE],
            [st.SORT_DU_FROID, st.REVEILS_ARRETES,
             st.ETAPE_DEVIS_DEMAIN_SAUF_SUIVI])


class RestrictionsTests(SimpleTestCase):
    """``refus_reponse_touche`` : touches ÉCRITES du protocole seulement,
    avec un message qui NOMME la réponse."""

    def test_acceptee_sur_un_message_du_protocole(self):
        for cadence in ('contact', 'deuxieme_affaire', 'apres_devis',
                        'reveil'):
            with self.subTest(cadence=cadence):
                self.assertIsNone(services.refus_reponse_touche(
                    _touche(cadence, 1, WHATSAPP), JOINT_TELEPHONE))

    def test_refusee_sur_un_appel(self):
        refus = services.refus_reponse_touche(
            _touche('contact', 2, APPEL), JOINT_TELEPHONE)
        self.assertIn('« Client joint au téléphone »', refus)
        self.assertIn('WhatsApp', refus)

    def test_refusee_sur_un_geste_de_visite(self):
        confirmation = _touche('apres_devis', services.VISITE_ORDRE_CONFIRMATION,
                               WHATSAPP, cle=CLE_CONFIRMATION, devis=True)
        refus = services.refus_reponse_touche(confirmation, JOINT_TELEPHONE)
        self.assertIn('« Client joint au téléphone »', refus)
        self.assertIn('protocole', refus)

    def test_refusee_sur_une_etape_de_filet(self):
        creneau = _touche('generique', 1, WHATSAPP, cle=CLE_MESSAGE_CRENEAU)
        refus = services.refus_reponse_touche(creneau, JOINT_TELEPHONE)
        self.assertIn('« Client joint au téléphone »', refus)


class JointTelephoneApiTests(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.n = n
        self.company = Company.objects.create(
            nom=f'Suivi E16 {n}', slug=f'suivi-e16-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e16-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _lead(self, stage):
        return Lead.objects.create(
            company=self.company, nom=f'Prospect E16 {self.n}',
            stage=stage, owner=self.acteur,
            telephone=f'+21266216{self.n:04d}')

    def _devis(self, lead):
        client = Client.objects.create(
            company=self.company, nom=f'Client E16 {self.n}',
            email=f'suivi-e16-{self.n}@example.com')
        return Devis.objects.create(
            company=self.company, reference=f'DEV-E16-{self.n:05d}',
            client=client, lead=lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'),
            date_envoi=GEL - datetime.timedelta(days=7))

    def _barreau(self, lead, cadence, ordre, *, devis=None, statut=A_FAIRE,
                 due=None, depart=None):
        gabarit = _gabarit(cadence, ordre)
        due = due or GEL
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence=cadence, ordre=ordre,
            canal=gabarit['canal'], libelle=gabarit['libelle'], devis=devis,
            statut=statut, due_at=due,
            due_date=due.astimezone(horaires.CASABLANCA).date(),
            cadence_depart=depart or GEL,
            traite_par=None if statut == A_FAIRE else self.acteur,
            traite_le=None if statut == A_FAIRE else due)

    def _repondre(self, etape, **corps):
        corps['reponse'] = JOINT_TELEPHONE
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/', corps,
            format='json')

    def _ouvertes(self, lead, *q):
        return lead.relance_etapes.filter(*q, statut=A_FAIRE)

    def test_prise_de_contact_la_suite_d_un_appel_abouti(self):
        lead = self._lead(stages.NEW)
        message = self._barreau(lead, 'contact', 1)
        self.assertIn(message.canal, (WHATSAPP, EMAIL))

        resp = self._repondre(message, note='Il a décroché tout de suite')

        self.assertEqual(resp.status_code, 200, resp.data)
        message.refresh_from_db()
        self.assertEqual(message.statut, FAIT)
        self.assertEqual(message.outcome, 'joint')
        self.assertEqual(message.note, 'Client joint au téléphone — Il a '
                                       'décroché tout de suite')
        # La ligne de chatter de la touche est un APPEL abouti.
        ligne = LeadActivity.objects.get(
            lead=lead, body__startswith=services.prefixe_activite_touche(
                message))
        self.assertEqual(ligne.kind, LeadActivity.Kind.APPEL)
        self.assertEqual(ligne.outcome, 'joint')
        self.assertIn('Appel au lieu de', ligne.body)
        # La suite d'un appel : l'étape devis demain, jamais « appeler ».
        [ouverte] = list(self._ouvertes(lead))
        self.assertEqual(cle_de(ouverte), CLE_DEVIS)
        self.assertEqual(ouverte.due_date, DEMAIN)
        self.assertFalse(self._ouvertes(
            lead, q_etape(CLE_APPEL_APRES_REPONSE)).exists())
        self.assertEqual(resp.data['prochaine_touche']['cle'], CLE_DEVIS)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)

    def test_suivi_de_proposition_le_barreau_suivant(self):
        lead = self._lead(stages.QUOTE_SENT)
        devis = self._devis(lead)
        message = self._barreau(lead, 'apres_devis', 1, devis=devis)
        self.assertIn(message.canal, (WHATSAPP, EMAIL))

        resp = self._repondre(message)

        self.assertEqual(resp.status_code, 200, resp.data)
        ouvertes = list(self._ouvertes(lead))
        self.assertEqual(len(ouvertes), 1, ouvertes)
        self.assertEqual(ouvertes[0].cadence, 'apres_devis')
        self.assertGreater(ouvertes[0].ordre, 1)
        self.assertFalse(self._ouvertes(
            lead, q_etape(CLE_APPEL_APRES_REPONSE, CLE_DEVIS)).exists())

    def test_reveil_sort_du_froid_et_pose_le_devis(self):
        lead = self._lead(stages.COLD)
        depart = GEL - datetime.timedelta(days=30)
        self._barreau(lead, 'reveil', 1, statut=FAIT,
                      due=GEL - datetime.timedelta(days=30), depart=depart)
        reveil = self._barreau(lead, 'reveil', 2, depart=depart)
        self.assertIn(reveil.canal, (WHATSAPP, EMAIL))

        resp = self._repondre(reveil)

        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)
        self.assertFalse(self._ouvertes(lead).filter(
            cadence='reveil').exists())
        self.assertTrue(self._ouvertes(
            lead, q_etape(CLE_DEVIS)).filter(due_date=DEMAIN).exists())
        self.assertFalse(self._ouvertes(
            lead, q_etape(CLE_APPEL_APRES_REPONSE)).exists())

    def test_refusee_sur_un_appel_du_protocole(self):
        lead = self._lead(stages.CONTACTED)
        appel = RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=2,
            canal=APPEL, libelle="Appel d'ouverture", due_at=GEL,
            due_date=GEL.date(), cadence_depart=GEL)

        resp = self._repondre(appel)

        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('« Client joint au téléphone »',
                      resp.data['erreurs']['reponse'])
        appel.refresh_from_db()
        self.assertEqual(appel.statut, A_FAIRE)

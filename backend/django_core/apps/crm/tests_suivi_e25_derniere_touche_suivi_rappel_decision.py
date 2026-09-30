"""SUIVI E25 — la DERNIÈRE touche du suivi : « Décision à plusieurs » et « À rappeler le… ».

Même règle que les décisions fondateur du 30/09/2026 (E22, E23) : sur la dernière touche,
« le client est joint mais rien ne suit » → « Décider la suite » demain ; « le client demande
un rappel » → « Rappeler le client — rappel convenu » à la date convenue. Table du parcours
(``frontend/src/features/crm/relances/parcours_suivi.json``) : types « Appel de suivi de la
proposition » et « Message de suivi de la proposition », variantes ``derniere_touche`` sur
``rappel`` (étape ``rappel_convenu`` à la date choisie), ``decision_famille`` et
``decision_proprietaire`` (étape ``decider_suite`` demain).

Avant, sur le dernier barreau actif du gabarit ``apres_devis`` : « Décision à plusieurs »
posait l'étiquette puis « Préparer et envoyer le devis » demain (``etape_devis_demain``), et
« À rappeler le… » la même étape devis à la date choisie (``etape_devis_a_la_date``) — alors
que le devis était déjà parti. Désormais : l'étiquette, puis « Décider la suite » pour demain
(codes ``etiquette_decision`` + ``etape_decider_suite``) ; et le rappel convenu à la date et
à l'heure convenues (``etape_rappel_convenu_a_la_date``). Le dossier garde son étape ; sur
une touche qui n'est pas la dernière, rien ne change.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca (« demain » = jeudi 24/09) ; date
convenue : lundi 28/09/2026 à 11 h (dans la fenêtre d'appel, jamais recalée).
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
    CLE_DECIDER_SUITE, CLE_DEVIS, CLE_RAPPEL_CONVENU, cle_de, q_etape)
from apps.crm.models import Client, Lead, RelanceEtape
from apps.crm.parcours_suivi_outils import cas_de_la_famille, reponse_de
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape
from apps.ventes.models import Devis

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
DEMAIN = datetime.date(2026, 9, 24)
DATE_CHOISIE = datetime.date(2026, 9, 28)
HEURE_CHOISIE = '11:00'
A_FAIRE = RelanceEtape.Statut.A_FAIRE
FAIT = RelanceEtape.Statut.FAIT
APPEL = RelanceEtape.Canal.APPEL
WHATSAPP = RelanceEtape.Canal.WHATSAPP
FAMILLE = services.REPONSE_DECISION_FAMILLE
PROPRIETAIRE = services.REPONSE_DECISION_PROPRIETAIRE
ORDRES_SUIVI = frozenset(e['ordre'] for e in CADENCES_DEFAUT['apres_devis'])
#: Le dernier barreau du gabarit livré (« Mise en pause », un message).
DERNIER = max(ORDRES_SUIVI)
#: Le dernier APPEL du gabarit livré (« Appel de suivi », J+11) : il devient
#: la dernière touche quand la société désactive les deux messages suivants.
DERNIER_APPEL = max(e['ordre'] for e in CADENCES_DEFAUT['apres_devis']
                    if e['canal'] == APPEL)
SANS_LES_MESSAGES_DE_FIN = frozenset(o for o in ORDRES_SUIVI
                                     if o <= DERNIER_APPEL)
VARIANTE_DECIDER = {'contexte': 'derniere_touche',
                    'suite': {'type': 'etape', 'cle': CLE_DECIDER_SUITE,
                              'jour': 'demain'}}
VARIANTE_RAPPEL = {'contexte': 'derniere_touche',
                   'suite': {'type': 'etape', 'cle': CLE_RAPPEL_CONVENU,
                             'jour': 'date_choisie'}}
#: Les six nouvelles variantes de la table : (type, réponse) → variante.
VARIANTES = {
    (type_id, modele): (VARIANTE_RAPPEL if modele == 'rappel'
                        else VARIANTE_DECIDER)
    for type_id in ('suivi_appel', 'suivi_message')
    for modele in ('rappel', 'decision_famille', 'decision_proprietaire')}
FAMILLE_SUIVI = 'Suivi de proposition (après devis)'

_seq = itertools.count(1)


def _gabarit(ordre):
    return next(e for e in CADENCES_DEFAUT['apres_devis']
                if e['ordre'] == ordre)


def _touche(ordre):
    gabarit = _gabarit(ordre)
    etape = RelanceEtape(cadence='apres_devis', ordre=ordre,
                         canal=gabarit['canal'], libelle=gabarit['libelle'],
                         statut=A_FAIRE, devis_id=903)
    etape.lead = Lead(nom='témoin', stage=stages.FOLLOW_UP)
    return etape


def _promesses(etape, ordres):
    return st.promesses_touche(etape, ordres=ordres,
                               est_actif=lambda cle: True)


class PromessesTests(SimpleTestCase):
    """Les codes servis suivent l'effet, sur la dernière touche (message ou
    appel) comme sur les autres."""

    def _dernieres(self):
        return ((_touche(DERNIER), ORDRES_SUIVI),
                (_touche(DERNIER_APPEL), SANS_LES_MESSAGES_DE_FIN))

    def test_decision_a_plusieurs_sur_la_derniere_touche(self):
        for etape, ordres in self._dernieres():
            promesses = _promesses(etape, ordres)
            for cle in (FAMILLE, PROPRIETAIRE):
                with self.subTest(canal=etape.canal, reponse=cle):
                    self.assertEqual(promesses[cle], [st.ETIQUETTE_DECISION,
                                                      st.ETAPE_DECIDER_SUITE])

    def test_a_rappeler_le_sur_la_derniere_touche(self):
        for etape, ordres in self._dernieres():
            with self.subTest(canal=etape.canal):
                self.assertEqual(_promesses(etape, ordres)['rappel'],
                                 [st.ETAPE_RAPPEL_CONVENU_A_LA_DATE])

    def test_plus_jamais_l_etape_devis_sur_la_derniere_touche(self):
        for etape, ordres in self._dernieres():
            promesses = _promesses(etape, ordres)
            for cle in ('rappel', FAMILLE, PROPRIETAIRE):
                with self.subTest(canal=etape.canal, reponse=cle):
                    self.assertFalse({st.ETAPE_DEVIS_DEMAIN,
                                      st.ETAPE_DEVIS_A_LA_DATE}
                                     & set(promesses[cle]))

    def test_une_touche_qui_n_est_pas_la_derniere_est_inchangee(self):
        promesses = _promesses(_touche(DERNIER_APPEL), ORDRES_SUIVI)
        self.assertEqual(promesses['rappel'], [st.TOUCHE_SUIVANTE_A_LA_DATE])
        for cle in (FAMILLE, PROPRIETAIRE):
            with self.subTest(reponse=cle):
                self.assertEqual(promesses[cle], [st.ETIQUETTE_DECISION,
                                                  st.TOUCHE_SUIVANTE])


class TableTests(SimpleTestCase):
    """La table porte les six variantes ``derniere_touche`` — et la garde de
    parcours en fait six cas de plus."""

    def test_les_six_reponses_portent_leur_variante(self):
        for (type_id, modele), variante in VARIANTES.items():
            with self.subTest(etape=type_id, reponse=modele):
                reponse = reponse_de(type_id, modele)
                self.assertIn(variante, reponse.get('variantes', []))
                self.assertIn('Sur la dernière touche du suivi',
                              reponse['effet'])

    def test_la_garde_de_parcours_joue_les_six_cas(self):
        cas = {(c.type_id, c.reponse['modele']): c.suite
               for c in cas_de_la_famille(FAMILLE_SUIVI)
               if c.contexte == 'derniere_touche'
               and (c.type_id, c.reponse['modele']) in VARIANTES}
        self.assertEqual(cas, {cle: variante['suite']
                               for cle, variante in VARIANTES.items()})


class DerniereToucheApiTests(TestCase):
    """L'API réelle (``POST relance-etapes/<id>/fait/``), sur un dossier en
    « Relance » dont le devis est parti."""

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.n = n
        self.company = Company.objects.create(
            nom=f'Suivi E25 {n}', slug=f'suivi-e25-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        # Comme en production : les gabarits existent (le rang « dernier » se
        # lit sur les barreaux ACTIFS de la société).
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e25-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E25 {n}',
            stage=stages.FOLLOW_UP, owner=self.acteur,
            telephone=f'+21266225{n:04d}')
        client = Client.objects.create(
            company=self.company, nom=f'Client E25 {n}',
            email=f'suivi-e25-{n}@example.com')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-E25-{n:05d}',
            client=client, lead=self.lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'),
            date_envoi=GEL - datetime.timedelta(days=14))

    # ── fabrique ──

    def _barreau(self, ordre):
        gabarit = _gabarit(ordre)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=ordre, canal=gabarit['canal'], libelle=gabarit['libelle'],
            template_cle=gabarit.get('template_cle') or '', devis=self.devis,
            due_at=GEL, due_date=GEL.date(),
            cadence_depart=GEL - datetime.timedelta(days=14))

    def _desactiver_apres(self, ordre):
        """Paramètres → CRM : la société coupe les barreaux après ``ordre``,
        qui devient la DERNIÈRE touche du suivi."""
        CadenceRelanceEtape.objects.filter(
            company=self.company, cadence='apres_devis',
            ordre__gt=ordre).update(actif=False)

    def _fait(self, etape, **corps):
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/', corps,
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def _rappel(self, etape):
        return self._fait(etape, outcome='rappel',
                          rappel_le=DATE_CHOISIE.isoformat(),
                          rappel_heure=HEURE_CHOISIE)

    def _ouvertes(self):
        return list(self.lead.relance_etapes.filter(statut=A_FAIRE))

    # ── constats ──

    def _assert_sans_etape_devis(self):
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_DEVIS)).exists())
        self.assertFalse(self.lead.relance_etapes.filter(
            cadence='apres_devis', statut=A_FAIRE).exists())

    def _assert_decider_la_suite(self, resp, touche, fragment_de_note):
        touche.refresh_from_db()
        self.assertEqual((touche.statut, touche.outcome), (FAIT, 'rappel'))
        self.assertIn(fragment_de_note, touche.note)
        self.lead.refresh_from_db()
        self.assertIn('Décision à plusieurs', self.lead.tags or '')
        [decider] = self._ouvertes()
        self.assertEqual(cle_de(decider), CLE_DECIDER_SUITE)
        self.assertEqual(decider.due_date, DEMAIN)
        self._assert_sans_etape_devis()
        self.assertEqual(resp.data['prochaine_touche']['cle'],
                         CLE_DECIDER_SUITE)
        self.assertEqual(self.lead.relance_date, DEMAIN)
        self.assertEqual(self.lead.stage, stages.FOLLOW_UP)

    def _assert_rappel_convenu(self, resp, touche):
        touche.refresh_from_db()
        self.assertEqual((touche.statut, touche.outcome), (FAIT, 'rappel'))
        [rappel] = self._ouvertes()
        self.assertEqual(cle_de(rappel), CLE_RAPPEL_CONVENU)
        self.assertEqual(rappel.canal, APPEL)
        self.assertEqual(rappel.due_date, DATE_CHOISIE)
        self.assertEqual(
            rappel.due_at.astimezone(horaires.CASABLANCA).strftime('%H:%M'),
            HEURE_CHOISIE)
        self._assert_sans_etape_devis()
        self.assertEqual(resp.data['prochaine_touche']['cle'],
                         CLE_RAPPEL_CONVENU)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.relance_date, DATE_CHOISIE)
        self.assertEqual(self.lead.stage, stages.FOLLOW_UP)

    # ── la dernière touche ──

    def test_dernier_appel_decision_en_famille(self):
        self._desactiver_apres(DERNIER_APPEL)
        appel = self._barreau(DERNIER_APPEL)
        self.assertEqual(appel.canal, APPEL)

        resp = self._fait(appel, reponse=FAMILLE)

        self._assert_decider_la_suite(resp, appel, 'en famille')

    def test_dernier_message_decision_du_proprietaire(self):
        message = self._barreau(DERNIER)
        self.assertEqual(message.canal, WHATSAPP)

        resp = self._fait(message, reponse=PROPRIETAIRE)

        self._assert_decider_la_suite(resp, message, 'le propriétaire décide')

    def test_dernier_message_a_rappeler_le(self):
        message = self._barreau(DERNIER)

        resp = self._rappel(message)

        self._assert_rappel_convenu(resp, message)

    def test_dernier_appel_a_rappeler_le(self):
        self._desactiver_apres(DERNIER_APPEL)
        appel = self._barreau(DERNIER_APPEL)

        resp = self._rappel(appel)

        self._assert_rappel_convenu(resp, appel)

    # ── une touche qui n'est pas la dernière : inchangé ──

    def test_non_derniere_decision_fait_naitre_la_touche_suivante(self):
        appel = self._barreau(DERNIER_APPEL)
        self.assertFalse(services.est_derniere_touche_du_suivi(appel))

        self._fait(appel, reponse=FAMILLE)

        self.lead.refresh_from_db()
        self.assertIn('Décision à plusieurs', self.lead.tags or '')
        [suivante] = self._ouvertes()
        self.assertEqual(suivante.cadence, 'apres_devis')
        self.assertGreater(suivante.ordre, DERNIER_APPEL)
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_DECIDER_SUITE, CLE_DEVIS)).exists())

    def test_non_derniere_a_rappeler_le_date_la_touche_suivante(self):
        appel = self._barreau(DERNIER_APPEL)

        self._rappel(appel)

        [suivante] = self._ouvertes()
        self.assertEqual(suivante.cadence, 'apres_devis')
        self.assertGreater(suivante.ordre, DERNIER_APPEL)
        self.assertEqual(suivante.due_date, DATE_CHOISIE)
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_RAPPEL_CONVENU, CLE_DEVIS)).exists())

"""SUIVI E24 — la DEUXIÈME AFFAIRE suit E23 : « À rappeler le… » sur sa dernière touche.

La deuxième affaire (CAD128) est la prise de contact d'un client déjà acquis qui revient ; la
table du parcours (``frontend/src/features/crm/relances/parcours_suivi.json``) la range sous
les MÊMES types que la prise de contact (« Appel / Message de prise de contact ») — la
variante ``derniere_touche`` de « À rappeler le… » (étape ``rappel_convenu`` à la date
choisie, E23) vaut donc pour elle aussi.

Avant : sur le dernier barreau actif du gabarit ``deuxieme_affaire`` (l'« Appel d'ouverture »
du gabarit livré), le filet posait « Préparer et envoyer le devis » déplacé à la date choisie
(``etape_devis_a_la_date``). Désormais la touche est close « à rappeler » et l'appel
« Rappeler le client — rappel convenu » est posé à la date ET à l'heure convenues
(``services.repondre_rappel_convenu``). Le dossier reste dans son étape ; sur une touche qui
n'est pas la dernière, la touche suivante est datée, comme avant.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca ; date convenue : lundi 28/09/2026 à
11 h (dans la fenêtre d'appel, jamais recalée).
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
from apps.crm.cadence_config import CLE_DEVIS, CLE_RAPPEL_CONVENU, cle_de, q_etape
from apps.crm.models import Lead, RelanceEtape
from apps.crm.parcours_suivi_outils import etapes_de_la_table, reponse_de, type_de
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
DATE_CHOISIE = datetime.date(2026, 9, 28)
HEURE_CHOISIE = '11:00'
A_FAIRE = RelanceEtape.Statut.A_FAIRE
FAIT = RelanceEtape.Statut.FAIT
APPEL = RelanceEtape.Canal.APPEL
WHATSAPP = RelanceEtape.Canal.WHATSAPP
CADENCE = services.CADENCE_DEUXIEME_AFFAIRE
ORDRES = frozenset(e['ordre'] for e in CADENCES_DEFAUT[CADENCE])
#: Le dernier barreau du gabarit livré (l'« Appel d'ouverture »).
DERNIER = max(ORDRES)
#: Le premier (« Message d'identité ») : jamais le dernier avec le gabarit livré.
PREMIER = min(ORDRES)
#: La variante que la table porte sur « À rappeler le… » (E23).
VARIANTE = {'contexte': 'derniere_touche',
            'suite': {'type': 'etape', 'cle': CLE_RAPPEL_CONVENU,
                      'jour': 'date_choisie'}}

_seq = itertools.count(1)


def _gabarit(ordre):
    return next(e for e in CADENCES_DEFAUT[CADENCE] if e['ordre'] == ordre)


def _touche(ordre):
    gabarit = _gabarit(ordre)
    etape = RelanceEtape(cadence=CADENCE, ordre=ordre, canal=gabarit['canal'],
                         libelle=gabarit['libelle'], statut=A_FAIRE)
    etape.lead = Lead(nom='témoin', stage=stages.NEW)
    return etape


def _rappel_promis(etape, ordres):
    return st.promesses_touche(etape, ordres=ordres,
                               est_actif=lambda cle: True)['rappel']


def _heure_locale(etape):
    return etape.due_at.astimezone(horaires.CASABLANCA).strftime('%H:%M')


class PromessesTests(SimpleTestCase):

    def test_la_derniere_touche_annonce_le_rappel_convenu(self):
        self.assertEqual(_touche(DERNIER).canal, APPEL)
        self.assertEqual(_rappel_promis(_touche(DERNIER), ORDRES),
                         [st.ETAPE_RAPPEL_CONVENU_A_LA_DATE])
        # Le message devient la dernière touche quand la société coupe l'appel.
        self.assertEqual(_rappel_promis(_touche(PREMIER), frozenset({PREMIER})),
                         [st.ETAPE_RAPPEL_CONVENU_A_LA_DATE])

    def test_une_touche_qui_n_est_pas_la_derniere_date_la_suivante(self):
        self.assertEqual(_rappel_promis(_touche(PREMIER), ORDRES),
                         [st.TOUCHE_SUIVANTE_A_LA_DATE])

    def test_plus_jamais_l_etape_devis_a_la_date(self):
        self.assertNotIn(st.ETAPE_DEVIS_A_LA_DATE,
                         _rappel_promis(_touche(DERNIER), ORDRES))


class TableTests(SimpleTestCase):
    """La table range la deuxième affaire sous les types de la prise de
    contact : leur variante « À rappeler le… » en dernière touche vaut pour
    elle."""

    def test_les_types_de_la_prise_de_contact_reconnaissent_la_deuxieme_affaire(self):
        etapes = etapes_de_la_table()
        for type_id in ('contact_appel', 'contact_message'):
            with self.subTest(etape=type_id):
                self.assertIn(CADENCE,
                              etapes[type_id]['reconnaissance']['cadences'])
                self.assertIn(VARIANTE,
                              reponse_de(type_id, 'rappel').get('variantes', []))
        self.assertEqual(type_de(_touche(DERNIER)), 'contact_appel')
        self.assertEqual(type_de(_touche(PREMIER)), 'contact_message')


class LectureDuRangTests(SimpleTestCase):

    def test_les_deux_prises_de_contact_et_elles_seules(self):
        self.assertEqual(services.CADENCES_PRISE_DE_CONTACT,
                         ('contact', CADENCE))
        generique = RelanceEtape(cadence='generique', ordre=5, canal=APPEL,
                                 libelle='Dernière relance', statut=A_FAIRE)
        self.assertFalse(services.est_derniere_touche_de_contact(generique))
        self.assertFalse(services.est_derniere_touche_de_contact(None))


class DeuxiemeAffaireApiTests(TestCase):
    """L'API réelle (``POST relance-etapes/<id>/fait/``), sur la fiche d'un
    client acquis qui revient (cadence courte « deuxième affaire »)."""

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E24 {n}', slug=f'suivi-e24-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        # Comme en production : les gabarits existent (le rang « dernier » se
        # lit sur les barreaux ACTIFS de la société).
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e24-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Client acquis E24 {n}',
            stage=stages.NEW, owner=self.acteur,
            telephone=f'+21266224{n:04d}')

    def _barreau(self, ordre):
        gabarit = _gabarit(ordre)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence=CADENCE,
            ordre=ordre, canal=gabarit['canal'], libelle=gabarit['libelle'],
            template_cle=gabarit.get('template_cle') or '',
            due_at=GEL, due_date=GEL.date(), cadence_depart=GEL)

    def _rappel(self, etape):
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'outcome': 'rappel', 'rappel_le': DATE_CHOISIE.isoformat(),
             'rappel_heure': HEURE_CHOISIE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def _ouvertes(self):
        return list(self.lead.relance_etapes.filter(statut=A_FAIRE))

    def _assert_rappel_convenu(self, resp, touche):
        touche.refresh_from_db()
        self.assertEqual((touche.statut, touche.outcome), (FAIT, 'rappel'))
        [rappel] = self._ouvertes()
        self.assertEqual(cle_de(rappel), CLE_RAPPEL_CONVENU)
        self.assertEqual(rappel.canal, APPEL)
        self.assertEqual(rappel.due_date, DATE_CHOISIE)
        self.assertEqual(_heure_locale(rappel), HEURE_CHOISIE)
        # Plus jamais l'étape devis à la date choisie.
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_DEVIS)).exists())
        self.assertEqual(resp.data['prochaine_touche']['cle'],
                         CLE_RAPPEL_CONVENU)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.relance_date, DATE_CHOISIE)
        self.assertEqual(self.lead.stage, stages.NEW)

    def test_derniere_touche_appel_a_rappeler_le(self):
        appel = self._barreau(DERNIER)
        self.assertTrue(services.est_derniere_touche_de_contact(appel))

        resp = self._rappel(appel)

        self._assert_rappel_convenu(resp, appel)

    def test_le_message_devenu_derniere_touche(self):
        # Paramètres → CRM : la société coupe l'appel, le message d'identité
        # devient la DERNIÈRE touche de la deuxième affaire.
        CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=CADENCE,
            ordre__gt=PREMIER).update(actif=False)
        message = self._barreau(PREMIER)
        self.assertEqual(message.canal, WHATSAPP)
        self.assertTrue(services.est_derniere_touche_de_contact(message))

        resp = self._rappel(message)

        self._assert_rappel_convenu(resp, message)

    def test_une_touche_qui_n_est_pas_la_derniere_date_la_suivante(self):
        message = self._barreau(PREMIER)
        self.assertFalse(services.est_derniere_touche_de_contact(message))

        self._rappel(message)

        [suivante] = self._ouvertes()
        self.assertEqual((suivante.cadence, suivante.ordre), (CADENCE, DERNIER))
        self.assertEqual(suivante.due_date, DATE_CHOISIE)
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_RAPPEL_CONVENU, CLE_DEVIS)).exists())

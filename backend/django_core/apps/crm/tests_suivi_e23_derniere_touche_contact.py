"""SUIVI E23 — « À rappeler le… » sur la DERNIÈRE touche de la prise de contact.

Décision fondateur (Reda, 30/09/2026). Table du parcours
(``frontend/src/features/crm/relances/parcours_suivi.json``) : types « Appel
de prise de contact » et « Message de prise de contact », réponse ``rappel``,
variante ``derniere_touche`` → étape ``rappel_convenu`` à la date choisie.

Avant : sur le dernier barreau actif du gabarit ``contact``, aucune touche
suivante ne pouvait porter la date ; le filet posait « Préparer et envoyer le
devis », déplacé à la date choisie (code ``etape_devis_a_la_date``).
Décision : la touche est close « à rappeler » et l'étape « Rappeler le client
— rappel convenu » (un APPEL) est posée à la date ET à l'heure convenues,
recalées sur la fenêtre d'appel — exactement ce que fait déjà
``services.repondre_rappel_convenu`` (E10/E17). Le dossier reste dans son
étape. Sur une touche qui n'est pas la dernière, rien ne change : la touche
suivante du protocole est datée. Code servi sur le dernier barreau :
``etape_rappel_convenu_a_la_date`` (phrase existante). Le réveil (« Refus »
reste au Froid, E17 sur le dernier réveil) ne change pas.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca ; date convenue : lundi
28/09/2026 à 11 h (dans la fenêtre d'appel, jamais recalée).
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
from apps.crm.parcours_suivi_outils import cas_de_la_famille, reponse_de
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
ORDRES_CONTACT = frozenset(e['ordre'] for e in CADENCES_DEFAUT['contact'])
#: Le dernier barreau du gabarit livré (« Clôture », un message).
DERNIER = max(ORDRES_CONTACT)
#: Le dernier APPEL du gabarit livré (« Appel 6 (dernier) ») : il devient la
#: dernière touche quand la société désactive le message de clôture.
DERNIER_APPEL = max(e['ordre'] for e in CADENCES_DEFAUT['contact']
                    if e['canal'] == APPEL)
#: La variante que la table porte sur « À rappeler le… ».
VARIANTE = {'contexte': 'derniere_touche',
            'suite': {'type': 'etape', 'cle': CLE_RAPPEL_CONVENU,
                      'jour': 'date_choisie'}}
FAMILLE_CONTACT = 'Prise de contact'
REPONSES_RAPPEL = (('contact_appel', 'rappel'), ('contact_message', 'rappel'))

_seq = itertools.count(1)


def _gabarit(cadence, ordre):
    return next(e for e in CADENCES_DEFAUT[cadence] if e['ordre'] == ordre)


def _touche(cadence, ordre, stage=stages.NEW):
    gabarit = _gabarit(cadence, ordre)
    etape = RelanceEtape(cadence=cadence, ordre=ordre, canal=gabarit['canal'],
                         libelle=gabarit['libelle'], statut=A_FAIRE)
    etape.lead = Lead(nom='témoin', stage=stage)
    return etape


def _promesses(etape, ordres):
    return st.promesses_touche(etape, ordres=ordres,
                               est_actif=lambda cle: True)


def _heure_locale(etape):
    return etape.due_at.astimezone(horaires.CASABLANCA).strftime('%H:%M')


class PromessesTests(SimpleTestCase):
    """Le code servi suit l'effet : ``etape_rappel_convenu_a_la_date`` sur le
    dernier barreau de la prise de contact, la touche suivante partout
    ailleurs."""

    def test_derniere_touche_message_et_appel(self):
        sans_cloture = frozenset(o for o in ORDRES_CONTACT
                                 if o <= DERNIER_APPEL)
        for etape, ordres in ((_touche('contact', DERNIER), ORDRES_CONTACT),
                              (_touche('contact', DERNIER_APPEL),
                               sans_cloture)):
            with self.subTest(canal=etape.canal, ordre=etape.ordre):
                self.assertEqual(_promesses(etape, ordres)['rappel'],
                                 [st.ETAPE_RAPPEL_CONVENU_A_LA_DATE])

    def test_une_touche_qui_n_est_pas_la_derniere_date_la_suivante(self):
        for ordre in (min(ORDRES_CONTACT), DERNIER_APPEL):
            with self.subTest(ordre=ordre):
                promesses = _promesses(_touche('contact', ordre),
                                       ORDRES_CONTACT)
                self.assertEqual(promesses['rappel'],
                                 [st.TOUCHE_SUIVANTE_A_LA_DATE])

    def test_le_reveil_ne_change_pas(self):
        ordres = frozenset(e['ordre'] for e in CADENCES_DEFAUT['reveil'])
        dernier = _touche('reveil', max(ordres), stage=stages.COLD)
        promesses = _promesses(dernier, ordres)
        # E17 : le dernier réveil sort du Froid et pose le rappel convenu ;
        # « Refus » laisse le dossier au Froid.
        self.assertEqual(promesses['rappel'],
                         [st.SORT_DU_FROID, st.ETAPE_RAPPEL_CONVENU_A_LA_DATE])
        self.assertEqual(promesses['refuse'],
                         [st.RELANCES_ARRETEES, st.RESTE_AU_FROID])


class TableTests(SimpleTestCase):
    """La table porte la variante ``derniere_touche`` sur « À rappeler le… »
    des deux types de la prise de contact — et la garde de parcours en fait
    deux cas de plus."""

    def test_les_deux_reponses_portent_la_variante(self):
        for type_id, modele in REPONSES_RAPPEL:
            with self.subTest(etape=type_id):
                reponse = reponse_de(type_id, modele)
                self.assertIn(VARIANTE, reponse.get('variantes', []))
                self.assertIn('rappel convenu', reponse['effet'])

    def test_la_garde_de_parcours_joue_les_deux_cas(self):
        cas = {(c.type_id, c.reponse['modele'])
               for c in cas_de_la_famille(FAMILLE_CONTACT)
               if c.contexte == 'derniere_touche'
               and c.suite == VARIANTE['suite']}
        self.assertEqual(cas, set(REPONSES_RAPPEL))


class LectureDuRangTests(SimpleTestCase):
    """``est_derniere_touche_de_contact`` ne vaut que pour la cadence
    ``contact`` — sans requête ailleurs."""

    def test_une_autre_cadence_ou_aucune_touche(self):
        suivi = RelanceEtape(cadence='apres_devis', ordre=10,
                             canal=WHATSAPP, libelle='Mise en pause',
                             statut=A_FAIRE)
        self.assertFalse(services.est_derniere_touche_de_contact(suivi))
        self.assertFalse(services.est_derniere_touche_de_contact(None))


class DerniereToucheContactApiTests(TestCase):
    """L'API réelle (``POST relance-etapes/<id>/fait/``), sur un lead en
    prise de contact."""

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.n = n
        self.company = Company.objects.create(
            nom=f'Suivi E23 {n}', slug=f'suivi-e23-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        # Comme en production : les gabarits existent (le rang « dernier » se
        # lit sur les barreaux ACTIFS de la société).
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e23-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E23 {n}',
            stage=stages.NEW, owner=self.acteur,
            telephone=f'+21266223{n:04d}')

    # ── fabrique ──

    def _barreau(self, ordre):
        gabarit = _gabarit('contact', ordre)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=ordre, canal=gabarit['canal'], libelle=gabarit['libelle'],
            template_cle=gabarit.get('template_cle') or '',
            due_at=GEL, due_date=GEL.date(),
            cadence_depart=GEL - datetime.timedelta(days=14))

    def _desactiver_apres(self, ordre):
        """Paramètres → CRM : la société coupe les barreaux après ``ordre``,
        qui devient la DERNIÈRE touche de la prise de contact."""
        CadenceRelanceEtape.objects.filter(
            company=self.company, cadence='contact',
            ordre__gt=ordre).update(actif=False)

    def _rappel(self, etape, heure=HEURE_CHOISIE):
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'outcome': 'rappel', 'rappel_le': DATE_CHOISIE.isoformat(),
             'rappel_heure': heure}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def _ouvertes(self, *q):
        return self.lead.relance_etapes.filter(*q, statut=A_FAIRE)

    # ── constats ──

    def _assert_rappel_convenu(self, resp, touche):
        touche.refresh_from_db()
        self.assertEqual(touche.statut, FAIT)
        self.assertEqual(touche.outcome, 'rappel')
        [rappel] = list(self._ouvertes())
        self.assertEqual(cle_de(rappel), CLE_RAPPEL_CONVENU)
        self.assertEqual(rappel.canal, APPEL)
        self.assertEqual(rappel.due_date, DATE_CHOISIE)
        self.assertEqual(_heure_locale(rappel), HEURE_CHOISIE)
        # Jamais l'étape devis à la place (ni à côté).
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_DEVIS)).exists())
        # La réponse du « Fait » NOMME l'étape posée (E9).
        prochaine = resp.data['prochaine_touche']
        self.assertEqual(prochaine['cle'], CLE_RAPPEL_CONVENU)
        self.assertEqual(prochaine['libelle'], rappel.libelle)
        self.assertEqual(prochaine['due_date'], DATE_CHOISIE.isoformat())
        self.lead.refresh_from_db()
        # La file est recalée ; le dossier reste dans son étape.
        self.assertEqual(self.lead.relance_date, DATE_CHOISIE)
        self.assertEqual(self.lead.stage, stages.NEW)
        self.assertTrue(self.lead.activites.filter(
            body__startswith='Créneau convenu avec le client',
            user__isnull=True).exists())

    # ── la dernière touche ──

    def test_dernier_message_a_rappeler_le(self):
        cloture = self._barreau(DERNIER)
        self.assertEqual(cloture.canal, WHATSAPP)
        self.assertTrue(services.est_derniere_touche_de_contact(cloture))

        resp = self._rappel(cloture)

        self._assert_rappel_convenu(resp, cloture)

    def test_dernier_appel_a_rappeler_le(self):
        self._desactiver_apres(DERNIER_APPEL)
        appel = self._barreau(DERNIER_APPEL)
        self.assertEqual(appel.canal, APPEL)
        self.assertTrue(services.est_derniere_touche_de_contact(appel))

        resp = self._rappel(appel)

        self._assert_rappel_convenu(resp, appel)

    def test_l_heure_est_recalee_sur_la_fenetre_d_appel(self):
        cloture = self._barreau(DERNIER)

        self._rappel(cloture, heure='07:00')

        rappel = self.lead.relance_etapes.get(q_etape(CLE_RAPPEL_CONVENU))
        self.assertEqual(rappel.due_date, DATE_CHOISIE)
        self.assertGreaterEqual(_heure_locale(rappel), '09:00')

    # ── une touche qui n'est pas la dernière : inchangé ──

    def test_une_touche_qui_n_est_pas_la_derniere_date_la_suivante(self):
        appel = self._barreau(DERNIER_APPEL)
        self.assertFalse(services.est_derniere_touche_de_contact(appel))

        resp = self._rappel(appel)

        appel.refresh_from_db()
        self.assertEqual((appel.statut, appel.outcome), (FAIT, 'rappel'))
        [suivante] = list(self._ouvertes())
        self.assertEqual(suivante.cadence, 'contact')
        self.assertGreater(suivante.ordre, DERNIER_APPEL)
        self.assertEqual(suivante.due_date, DATE_CHOISIE)
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_RAPPEL_CONVENU, CLE_DEVIS)).exists())
        self.assertEqual(resp.data['prochaine_touche']['cle'], '')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.relance_date, DATE_CHOISIE)
        self.assertEqual(self.lead.stage, stages.NEW)

"""SUIVI E22 — « Client joint » sur la DERNIÈRE touche du suivi de proposition.

Décision fondateur (Reda, 30/09/2026). Table du parcours
(``frontend/src/features/crm/relances/parcours_suivi.json``) : types « Appel
de suivi de la proposition » (réponse ``joint``) et « Message de suivi de la
proposition » (réponses ``a_repondu`` et ``joint_telephone``), variante
``derniere_touche`` → étape ``decider_suite`` pour DEMAIN.

Avant : sur le dernier barreau actif du gabarit ``apres_devis``, un client
joint ne faisait naître aucun barreau et le filet du récepteur MRY9 posait
« Préparer et envoyer le devis » (ou « Appeler le client — il a répondu au
message ») — alors que le devis était DÉJÀ parti. Décision : la touche est
close « joint » comme avant, et « Décider la suite » (cadence générique) est
posée pour demain, comme après un refus — sans étape devis ; le dossier garde
son étape (« Relance »). Sur une touche qui n'est pas la dernière, rien ne
change : le barreau suivant naît. Code servi sur le dernier barreau :
``etape_decider_suite`` (phrase existante).

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca (« demain » = jeudi
24/09, jour ouvré, dans la fenêtre d'appel).
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

from apps.crm import horaires, stages, cadence_reperes
from apps.crm import cadence_reponses
from apps.crm import suite_touche as st
from apps.crm.cadence_config import (
    CLE_APPEL_APRES_REPONSE, CLE_DEBRIEF, CLE_DECIDER_SUITE, CLE_DEVIS,
    cle_de, q_etape)
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.crm.parcours_suivi_outils import cas_de_la_famille, reponse_de
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
JOINT_TELEPHONE = cadence_reponses.REPONSE_JOINT_TELEPHONE
ORDRES_SUIVI = frozenset(e['ordre'] for e in CADENCES_DEFAUT['apres_devis'])
#: Le dernier barreau du gabarit livré (« Mise en pause », un message).
DERNIER = max(ORDRES_SUIVI)
#: Le dernier APPEL du gabarit livré (« Appel de suivi », J+11) : il devient
#: la dernière touche quand la société désactive les deux messages suivants.
DERNIER_APPEL = max(e['ordre'] for e in CADENCES_DEFAUT['apres_devis']
                    if e['canal'] == APPEL)
#: La variante que la table porte sur les trois réponses « client joint ».
VARIANTE = {'contexte': 'derniere_touche',
            'suite': {'type': 'etape', 'cle': CLE_DECIDER_SUITE,
                      'jour': 'demain'}}
FAMILLE_SUIVI = 'Suivi de proposition (après devis)'
REPONSES_JOINTES = (('suivi_appel', 'joint'), ('suivi_message', 'a_repondu'),
                    ('suivi_message', 'joint_telephone'))

_seq = itertools.count(1)


def _gabarit(ordre):
    return next(e for e in CADENCES_DEFAUT['apres_devis']
                if e['ordre'] == ordre)


def _touche(ordre, *, canal=None, devis=True):
    gabarit = _gabarit(ordre)
    etape = RelanceEtape(cadence='apres_devis', ordre=ordre,
                         canal=canal or gabarit['canal'],
                         libelle=gabarit['libelle'], statut=A_FAIRE,
                         devis_id=903 if devis else None)
    etape.lead = Lead(nom='témoin', stage=stages.FOLLOW_UP)
    return etape


def _promesses(etape, ordres=ORDRES_SUIVI):
    return st.promesses_touche(etape, ordres=ordres,
                               est_actif=lambda cle: True)


class PromessesTests(SimpleTestCase):
    """Le code servi suit l'effet : ``etape_decider_suite`` sur le dernier
    barreau, le barreau suivant partout ailleurs."""

    def test_dernier_message_joint_et_joint_au_telephone(self):
        for devis in (True, False):
            with self.subTest(devis_dans_l_erp=devis):
                promesses = _promesses(_touche(DERNIER, devis=devis))
                self.assertEqual(promesses['joint'], [st.ETAPE_DECIDER_SUITE])
                self.assertEqual(promesses[JOINT_TELEPHONE],
                                 [st.ETAPE_DECIDER_SUITE])

    def test_dernier_appel_joint(self):
        ordres = frozenset(o for o in ORDRES_SUIVI if o <= DERNIER_APPEL)
        promesses = _promesses(_touche(DERNIER_APPEL), ordres=ordres)
        self.assertEqual(promesses['joint'], [st.ETAPE_DECIDER_SUITE])

    def test_une_touche_qui_n_est_pas_la_derniere_annonce_la_suivante(self):
        appel = _promesses(_touche(DERNIER_APPEL))
        self.assertEqual(appel['joint'], [st.TOUCHE_SUIVANTE])
        message = _promesses(_touche(min(ORDRES_SUIVI)))
        self.assertEqual(message['joint'], [st.TOUCHE_SUIVANTE])
        self.assertEqual(message[JOINT_TELEPHONE], [st.TOUCHE_SUIVANTE])

    def test_jamais_l_etape_devis_ni_l_appel_sur_la_derniere(self):
        promesses = _promesses(_touche(DERNIER))
        for cle in ('joint', JOINT_TELEPHONE):
            with self.subTest(reponse=cle):
                self.assertFalse(
                    {st.ETAPE_DEVIS_DEMAIN, st.ETAPE_APPELER}
                    & set(promesses[cle]))


class TableTests(SimpleTestCase):
    """La table du parcours porte la variante ``derniere_touche`` sur les
    trois réponses « client joint » du suivi de proposition — et la garde de
    parcours en fait trois cas de plus."""

    def test_les_trois_reponses_portent_la_variante(self):
        for type_id, modele in REPONSES_JOINTES:
            with self.subTest(etape=type_id, reponse=modele):
                reponse = reponse_de(type_id, modele)
                self.assertIn(VARIANTE, reponse.get('variantes', []))
                self.assertIn('Décider la suite', reponse['effet'])

    def test_la_garde_de_parcours_joue_les_trois_cas(self):
        # SUIVI E25 — « Décision à plusieurs » porte la même variante : on
        # vérifie que les trois réponses « client joint » en font partie.
        cas = {(c.type_id, c.reponse['modele'])
               for c in cas_de_la_famille(FAMILLE_SUIVI)
               if c.contexte == 'derniere_touche'
               and c.suite == VARIANTE['suite']}
        self.assertLessEqual(set(REPONSES_JOINTES), cas)


class LectureDuRangTests(SimpleTestCase):
    """``est_derniere_touche_du_suivi`` ne lit la société que pour un BARREAU
    du suivi : une étape de visite (qui porte la cadence sans être du
    protocole) ou une touche d'une autre cadence n'est jamais « la dernière
    du suivi » — sans requête."""

    def test_une_etape_de_visite_n_est_pas_un_barreau(self):
        debrief = RelanceEtape(
            cadence='apres_devis', ordre=cadence_reperes.VISITE_ORDRE_DEBRIEF,
            canal=APPEL, cle=CLE_DEBRIEF,
            libelle=cadence_reperes.VISITE_DEBRIEF_LIBELLE, statut=A_FAIRE)
        self.assertFalse(cadence_reponses.est_derniere_touche_du_suivi(debrief))

    def test_une_autre_cadence_ou_aucune_touche(self):
        contact = RelanceEtape(cadence='contact', ordre=11, canal=WHATSAPP,
                               libelle='Clôture', statut=A_FAIRE)
        self.assertFalse(cadence_reponses.est_derniere_touche_du_suivi(contact))
        self.assertFalse(cadence_reponses.est_derniere_touche_du_suivi(None))

    def test_une_ligne_de_chatter_ordinaire_ne_porte_aucune_touche(self):
        self.assertIsNone(cadence_reperes.touche_close_de(LeadActivity()))


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
            nom=f'Suivi E22 {n}', slug=f'suivi-e22-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        # Comme en production : les gabarits existent (le rang « dernier » se
        # lit sur les barreaux ACTIFS de la société).
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e22-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E22 {n}',
            stage=stages.FOLLOW_UP, owner=self.acteur,
            telephone=f'+21266222{n:04d}')

    # ── fabrique ──

    def _devis(self):
        client = Client.objects.create(
            company=self.company, nom=f'Client E22 {self.n}',
            email=f'suivi-e22-{self.n}@example.com')
        return Devis.objects.create(
            company=self.company, reference=f'DEV-E22-{self.n:05d}',
            client=client, lead=self.lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'),
            date_envoi=GEL - datetime.timedelta(days=14))

    def _barreau(self, ordre, *, devis=None):
        gabarit = _gabarit(ordre)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=ordre, canal=gabarit['canal'], libelle=gabarit['libelle'],
            template_cle=gabarit.get('template_cle') or '', devis=devis,
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

    def _ouvertes(self, *q):
        return self.lead.relance_etapes.filter(*q, statut=A_FAIRE)

    # ── constats ──

    def _assert_decider_la_suite(self, resp, touche):
        touche.refresh_from_db()
        self.assertEqual(touche.statut, FAIT)
        self.assertEqual(touche.outcome, 'joint')
        [decider] = list(self._ouvertes())
        self.assertEqual(cle_de(decider), CLE_DECIDER_SUITE)
        self.assertEqual(decider.cadence, 'generique')
        self.assertEqual(decider.canal, APPEL)
        self.assertEqual(decider.due_date, DEMAIN)
        # Jamais l'étape devis d'un devis déjà parti, ni « l'appeler ».
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_DEVIS, CLE_APPEL_APRES_REPONSE)).exists())
        # Aucun barreau du suivi ne naît après la dernière touche.
        self.assertFalse(self._ouvertes().filter(
            cadence='apres_devis').exists())
        # La réponse du « Fait » NOMME l'étape posée (E9).
        prochaine = resp.data['prochaine_touche']
        self.assertEqual(prochaine['cle'], CLE_DECIDER_SUITE)
        self.assertEqual(prochaine['libelle'], decider.libelle)
        self.assertEqual(prochaine['due_date'], DEMAIN.isoformat())
        self.lead.refresh_from_db()
        # La file est recalée sur l'étape posée ; le dossier garde son étape.
        self.assertEqual(self.lead.relance_date, DEMAIN)
        self.assertEqual(self.lead.stage, stages.FOLLOW_UP)
        self.assertFalse(self.lead.perdu)

    # ── la dernière touche ──

    def test_dernier_appel_client_joint(self):
        self._desactiver_apres(DERNIER_APPEL)
        appel = self._barreau(DERNIER_APPEL, devis=self._devis())
        self.assertEqual(appel.canal, APPEL)
        self.assertTrue(cadence_reponses.est_derniere_touche_du_suivi(appel))

        resp = self._fait(appel, outcome='joint')

        self._assert_decider_la_suite(resp, appel)

    def test_dernier_message_le_client_a_repondu(self):
        message = self._barreau(DERNIER, devis=self._devis())
        self.assertEqual(message.canal, WHATSAPP)

        resp = self._fait(message, outcome='joint')

        self._assert_decider_la_suite(resp, message)

    def test_dernier_message_client_joint_au_telephone(self):
        message = self._barreau(DERNIER, devis=self._devis())

        resp = self._fait(message, reponse=JOINT_TELEPHONE)

        self._assert_decider_la_suite(resp, message)
        # E16 inchangé : la ligne de chatter reste un APPEL abouti.
        ligne = LeadActivity.objects.get(
            lead=self.lead,
            body__startswith=cadence_reperes.prefixe_activite_touche(message))
        self.assertEqual(ligne.kind, LeadActivity.Kind.APPEL)

    def test_dernier_message_sans_devis_dans_l_erp(self):
        # Devis parti hors ERP (TREADMILL-1538) : même décision.
        message = self._barreau(DERNIER)

        resp = self._fait(message, outcome='joint')

        self._assert_decider_la_suite(resp, message)

    # ── une touche qui n'est pas la dernière : inchangé ──

    def test_une_touche_qui_n_est_pas_la_derniere_fait_naitre_la_suivante(self):
        appel = self._barreau(DERNIER_APPEL, devis=self._devis())
        self.assertFalse(cadence_reponses.est_derniere_touche_du_suivi(appel))

        resp = self._fait(appel, outcome='joint')

        [suivante] = list(self._ouvertes())
        self.assertEqual(suivante.cadence, 'apres_devis')
        self.assertGreater(suivante.ordre, DERNIER_APPEL)
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_DECIDER_SUITE, CLE_DEVIS,
                    CLE_APPEL_APRES_REPONSE)).exists())
        self.assertEqual(resp.data['prochaine_touche']['cle'], '')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.relance_date, suivante.due_date)
        self.assertEqual(self.lead.stage, stages.FOLLOW_UP)

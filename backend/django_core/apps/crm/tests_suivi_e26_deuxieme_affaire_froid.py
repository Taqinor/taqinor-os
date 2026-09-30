"""SUIVI E26 — la DEUXIÈME AFFAIRE finit comme la prise de contact : le Froid.

Décision fondateur (Reda, 30/09/2026) : quand la DERNIÈRE relance d'une deuxième affaire (CAD128 :
un client déjà signé qui revient, cadence courte d'un message et d'un appel) reste sans réponse,
le dossier part au FROID avec ses réveils — comme la prise de contact.

Avant : ``cloturer_cadence`` ne connaissait pas cette cadence ; le filet posait « Préparer et
envoyer le devis » pour le lendemain — un chiffrage réclamé pour quelqu'un que personne n'avait eu
au téléphone — alors que la table du parcours (donc l'écran et le guide PDF) range la deuxième
affaire sous les types de la prise de contact, dont la dernière touche sans réponse annonce le
Froid. La promesse servie (``suite_touche``) et l'effet (``services._CLOTURE_PLAFOND``) disent
maintenant la même chose ; la garde de parité CAD17 rejoue aussi ce cas.

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
from apps.crm.views import _DEFAULT_TAGS
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
A_FAIRE = RelanceEtape.Statut.A_FAIRE
FAIT = RelanceEtape.Statut.FAIT
CADENCE = services.CADENCE_DEUXIEME_AFFAIRE
ORDRES = frozenset(e['ordre'] for e in CADENCES_DEFAUT[CADENCE])
DERNIER = max(ORDRES)
PREMIER = min(ORDRES)
TAG = services._CLOTURE_TAG_DEUXIEME_AFFAIRE

_seq = itertools.count(1)


def _gabarit(ordre):
    return next(e for e in CADENCES_DEFAUT[CADENCE] if e['ordre'] == ordre)


def _touche(ordre):
    gabarit = _gabarit(ordre)
    etape = RelanceEtape(cadence=CADENCE, ordre=ordre, canal=gabarit['canal'],
                         libelle=gabarit['libelle'], statut=A_FAIRE)
    etape.lead = Lead(nom='témoin', stage=stages.NEW)
    return etape


def _promesses(etape, ordres=ORDRES):
    return st.promesses_touche(etape, ordres=ordres, est_actif=lambda cle: True)


class PromessesTests(SimpleTestCase):
    """Ce que l'écran ANNONCE sous « Pas de réponse » (et « Sauter »)."""

    def test_la_derniere_touche_sans_reponse_annonce_le_froid(self):
        promesses = _promesses(_touche(DERNIER))
        self.assertEqual(promesses['non_joint'], [st.DERNIERE_FROID_REVEILS])
        # « Sauter » la dernière touche épuise la cadence de la même façon.
        if st.CLE_SAUTER in promesses:
            self.assertEqual(promesses[st.CLE_SAUTER], [st.DERNIERE_FROID_REVEILS])

    def test_sans_reponse_plus_jamais_l_etape_devis_du_lendemain(self):
        # « Client joint », lui, annonce toujours le devis (c'est la bonne suite) : seules
        # les fins SANS réponse ne réclament plus de chiffrage.
        promesses = _promesses(_touche(DERNIER))
        for cle in ('non_joint', st.CLE_SAUTER):
            if cle in promesses:
                with self.subTest(reponse=cle):
                    self.assertNotIn(st.ETAPE_DEVIS_DEMAIN, promesses[cle])
        self.assertIn(st.ETAPE_DEVIS_DEMAIN, promesses['joint'])

    def test_une_touche_qui_n_est_pas_la_derniere_annonce_la_suivante(self):
        self.assertEqual(_promesses(_touche(PREMIER))['non_joint'],
                         [st.TOUCHE_SUIVANTE])

    def test_le_message_devenu_derniere_touche_annonce_le_froid(self):
        # La société coupe l'appel : le message d'identité devient la dernière touche.
        self.assertEqual(
            _promesses(_touche(PREMIER), frozenset({PREMIER}))['non_joint'],
            [st.DERNIERE_FROID_REVEILS])

    def test_l_etiquette_de_cloture_est_dans_le_catalogue_des_etiquettes(self):
        # Un seul libellé : celui que le moteur pose est celui que Paramètres → CRM seede.
        self.assertIn(TAG, _DEFAULT_TAGS)
        self.assertNotEqual(TAG, services._CLOTURE_TAG_INJOIGNABLE)


class DeuxiemeAffaireFroidApiTests(TestCase):
    """L'API réelle (``POST relance-etapes/<id>/fait/``) sur la fiche d'un client acquis qui
    revient : la promesse et l'effet, constatés en base."""

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E26 {n}', slug=f'suivi-e26-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e26-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.telephone = f'+21266226{n:04d}'
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Client acquis E26 {n}',
            stage=stages.NEW, owner=self.acteur, telephone=self.telephone)

    def _barreau(self, ordre, lead=None):
        gabarit = _gabarit(ordre)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead or self.lead, cadence=CADENCE,
            ordre=ordre, canal=gabarit['canal'], libelle=gabarit['libelle'],
            template_cle=gabarit.get('template_cle') or '',
            due_at=GEL, due_date=GEL.date(), cadence_depart=GEL)

    def _sans_reponse(self, etape):
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'outcome': 'non_joint'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def _ouvertes(self, lead=None):
        return list((lead or self.lead).relance_etapes.filter(statut=A_FAIRE))

    def _assert_au_froid(self, lead):
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.COLD)
        self.assertFalse(lead.perdu, 'le Froid est un parking, jamais une perte')
        self.assertIn(TAG, lead.tags or '')
        self.assertNotIn(services._CLOTURE_TAG_INJOIGNABLE, lead.tags or '')
        ouvertes = self._ouvertes(lead)
        self.assertTrue(ouvertes, 'aucun réveil programmé')
        self.assertEqual({e.cadence for e in ouvertes}, {'reveil'})
        # Plus jamais « Préparer et envoyer le devis » pour quelqu'un qu'on n'a pas joint.
        self.assertFalse(lead.relance_etapes.filter(q_etape(CLE_DEVIS)).exists())

    def test_la_derniere_touche_sans_reponse_parque_au_froid(self):
        appel = self._barreau(DERNIER)
        self.assertEqual(_promesses(appel)['non_joint'], [st.DERNIERE_FROID_REVEILS])

        self._sans_reponse(appel)

        appel.refresh_from_db()
        self.assertEqual((appel.statut, appel.outcome), (FAIT, 'non_joint'))
        self._assert_au_froid(self.lead)

    def test_une_touche_qui_n_est_pas_la_derniere_fait_naitre_la_suivante(self):
        message = self._barreau(PREMIER)

        self._sans_reponse(message)

        [suivante] = self._ouvertes()
        self.assertEqual((suivante.cadence, suivante.ordre), (CADENCE, DERNIER))
        self.lead.refresh_from_db()
        self.assertNotEqual(self.lead.stage, stages.COLD)
        self.assertNotIn(TAG, self.lead.tags or '')

    def test_un_dossier_qui_a_progresse_ne_retombe_pas_au_froid(self):
        # Même plafond que la prise de contact : un devis parti entre-temps n'est jamais
        # effacé par une relance restée ouverte.
        Lead.objects.filter(pk=self.lead.pk).update(stage=stages.QUOTE_SENT)
        appel = self._barreau(DERNIER)

        self._sans_reponse(appel)

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)
        self.assertNotIn(TAG, self.lead.tags or '')

    def test_de_bout_en_bout_un_client_signe_revient_et_ne_repond_pas(self):
        """Le chemin RÉEL : une fiche signée existe, le même numéro crée une fiche neuve par
        l'API → cadence courte « deuxième affaire » → « pas de réponse » jusqu'au bout."""
        Lead.objects.filter(pk=self.lead.pk).update(stage=stages.SIGNED)
        resp = self.api.post('/api/django/crm/leads/', {
            'nom': 'Client qui revient E26', 'telephone': self.telephone,
            'owner': self.acteur.pk}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        nouveau = Lead.objects.get(pk=resp.data['id'])
        self.assertEqual({e.cadence for e in nouveau.relance_etapes.all()}, {CADENCE})

        for _tour in range(len(ORDRES) + 1):
            ouvertes = [e for e in self._ouvertes(nouveau) if e.cadence == CADENCE]
            if not ouvertes:
                break
            etape = ouvertes[0]
            # Chaque touche est traitée À SON HEURE (jamais en avance) : l'horloge avance
            # par un bloc imbriqué, le jeton suit.
            with frozen(max(etape.due_at, GEL) + datetime.timedelta(minutes=5)):
                self.api.credentials(
                    HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
                self._sans_reponse(etape)

        self.assertEqual(
            nouveau.relance_etapes.filter(cadence=CADENCE, statut=FAIT).count(),
            len(ORDRES))
        self._assert_au_froid(nouveau)
        # La fiche signée, elle, n'a pas bougé.
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.SIGNED)

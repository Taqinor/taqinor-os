"""SUIVI E17 — « À rappeler le… » sur le DERNIER réveil.

SUIVI-PARCOURS 30/09/2026 (table : types « Appel de réveil » et « Message de
réveil », réponse « rappel », variante ``derniere_touche`` → étape
``rappel_convenu`` à la date choisie). Sur le dernier réveil, aucun réveil
suivant ne pouvait porter la date : elle était PERDUE (code
``dernier_reveil_date_perdue`` — le dossier restait au Froid sans rien) ou,
hors Froid, remplacée par l'étape devis (``etape_devis_a_la_date_sauf_suivi``).

Décision : le dossier sort du Froid (→ Contacté, ``avancer_stage_lead_vers``),
un réveil resté ouvert s'arrête, et l'appel « Rappeler le client — rappel
convenu » est posé à la date ET à l'heure choisies. Codes :
``sort_du_froid`` (au Froid) + ``etape_rappel_convenu_a_la_date`` ; les deux
anciens codes disparaissent du vocabulaire. Un réveil qui n'est PAS le
dernier garde son effet : le réveil suivant est déplacé à la date.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca ; date choisie : lundi
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

from apps.crm import horaires, stages, cadence_reponses
from apps.crm import suite_touche as st
from apps.crm.cadence_config import CLE_RAPPEL_CONVENU, cle_de
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
DATE_CHOISIE = datetime.date(2026, 9, 28)
HEURE_CHOISIE = '11:00'
A_FAIRE = RelanceEtape.Statut.A_FAIRE
FAIT = RelanceEtape.Statut.FAIT
ORDRES_REVEIL = frozenset(e['ordre'] for e in CADENCES_DEFAUT['reveil'])
DERNIER = max(ORDRES_REVEIL)
PREMIER = min(ORDRES_REVEIL)

_seq = itertools.count(1)


def _reveil(ordre, stage):
    gabarit = next(e for e in CADENCES_DEFAUT['reveil'] if e['ordre'] == ordre)
    etape = RelanceEtape(cadence='reveil', ordre=ordre,
                         canal=gabarit['canal'], libelle=gabarit['libelle'],
                         statut=A_FAIRE)
    etape.lead = Lead(nom='témoin', stage=stage)
    return etape


class PromessesTests(SimpleTestCase):

    def _rappel(self, ordre, stage):
        return st.promesses_touche(_reveil(ordre, stage), ordres=ORDRES_REVEIL,
                                   est_actif=lambda cle: True)['rappel']

    def test_dernier_reveil_au_froid(self):
        self.assertEqual(self._rappel(DERNIER, stages.COLD),
                         [st.SORT_DU_FROID, st.ETAPE_RAPPEL_CONVENU_A_LA_DATE])

    def test_dernier_reveil_hors_froid(self):
        self.assertEqual(self._rappel(DERNIER, stages.CONTACTED),
                         [st.ETAPE_RAPPEL_CONVENU_A_LA_DATE])

    def test_un_reveil_qui_n_est_pas_le_dernier_deplace_le_suivant(self):
        self.assertEqual(self._rappel(PREMIER, stages.COLD),
                         [st.TOUCHE_SUIVANTE_A_LA_DATE])

    def test_les_codes_de_la_date_perdue_ont_disparu(self):
        self.assertNotIn('dernier_reveil_date_perdue', st.CODES)
        self.assertNotIn('etape_devis_a_la_date_sauf_suivi', st.CODES)


class DernierReveilApiTests(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.n = n
        self.company = Company.objects.create(
            nom=f'Suivi E17 {n}', slug=f'suivi-e17-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e17-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _lead(self, stage):
        return Lead.objects.create(
            company=self.company, nom=f'Dormant E17 {self.n}', stage=stage,
            owner=self.acteur, telephone=f'+21266217{self.n:04d}')

    def _touche(self, lead, ordre, *, statut=A_FAIRE, due=None):
        gabarit = next(e for e in CADENCES_DEFAUT['reveil']
                       if e['ordre'] == ordre)
        due = due or GEL
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='reveil', ordre=ordre,
            canal=gabarit['canal'], libelle=gabarit['libelle'], statut=statut,
            due_at=due, due_date=due.astimezone(horaires.CASABLANCA).date(),
            cadence_depart=GEL - datetime.timedelta(days=30),
            traite_par=None if statut == A_FAIRE else self.acteur,
            traite_le=None if statut == A_FAIRE else due)

    def _rappel(self, etape):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'outcome': 'rappel', 'rappel_le': DATE_CHOISIE.isoformat(),
             'rappel_heure': HEURE_CHOISIE}, format='json')

    def _assert_rappel_convenu(self, lead, resp):
        [ouverte] = list(lead.relance_etapes.filter(statut=A_FAIRE))
        self.assertEqual(cle_de(ouverte), CLE_RAPPEL_CONVENU)
        self.assertEqual(ouverte.canal, RelanceEtape.Canal.APPEL)
        self.assertEqual(ouverte.due_date, DATE_CHOISIE)
        self.assertEqual(
            ouverte.due_at.astimezone(horaires.CASABLANCA).strftime('%H:%M'),
            HEURE_CHOISIE)
        self.assertEqual(resp.data['prochaine_touche']['cle'],
                         CLE_RAPPEL_CONVENU)

    def test_est_dernier_reveil_lit_les_barreaux_de_la_societe(self):
        lead = self._lead(stages.COLD)
        self.assertTrue(cadence_reponses.est_dernier_reveil(
            self._touche(lead, DERNIER)))
        self.assertFalse(cadence_reponses.est_dernier_reveil(
            self._touche(lead, PREMIER)))

    def test_au_froid_le_dossier_sort_et_le_rappel_est_pose(self):
        lead = self._lead(stages.COLD)
        self._touche(lead, PREMIER, statut=FAIT,
                     due=GEL - datetime.timedelta(days=30))
        dernier = self._touche(lead, DERNIER)

        resp = self._rappel(dernier)

        self.assertEqual(resp.status_code, 200, resp.data)
        dernier.refresh_from_db()
        self.assertEqual(dernier.statut, FAIT)
        self.assertEqual(dernier.outcome, 'rappel')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)
        self._assert_rappel_convenu(lead, resp)

    def test_hors_froid_le_rappel_est_pose(self):
        lead = self._lead(stages.CONTACTED)
        self._touche(lead, PREMIER, statut=FAIT,
                     due=GEL - datetime.timedelta(days=30))
        dernier = self._touche(lead, DERNIER)

        resp = self._rappel(dernier)

        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)
        self._assert_rappel_convenu(lead, resp)

    def test_un_reveil_reste_ouvert_s_arrete_avec_le_froid(self):
        lead = self._lead(stages.COLD)
        premier = self._touche(lead, PREMIER,
                               due=GEL + datetime.timedelta(days=2))
        dernier = self._touche(lead, DERNIER)

        resp = self._rappel(dernier)

        self.assertEqual(resp.status_code, 200, resp.data)
        premier.refresh_from_db()
        self.assertEqual(premier.statut, RelanceEtape.Statut.ANNULEE)
        self._assert_rappel_convenu(lead, resp)

    def test_le_premier_reveil_deplace_le_suivant(self):
        lead = self._lead(stages.COLD)
        premier = self._touche(lead, PREMIER)
        dernier = self._touche(lead, DERNIER,
                               due=GEL + datetime.timedelta(days=30))

        resp = self._rappel(premier)

        self.assertEqual(resp.status_code, 200, resp.data)
        dernier.refresh_from_db()
        self.assertEqual(dernier.statut, A_FAIRE)
        self.assertEqual(dernier.due_date, DATE_CHOISIE)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.COLD)
        self.assertFalse(lead.relance_etapes.filter(
            cle=CLE_RAPPEL_CONVENU).exists())

"""COCKPIT-CONTRÔLE B8 — une étape close garde l'échéance de son traitement.

Relevé du 30/09/2026 : une touche répondue « Visite acceptée » par
``POST crm/leads/<id>/visites/planifier/`` (avec ``etape``) finissait close
mais DATÉE APRÈS la visite. La planification décale d'abord le suivi pendant
— cette touche comprise — jusqu'après la visite
(``suspendre_plan_jusqu_apres_visite``, un déplacement du moteur), PUIS
``clore_etape_apres_planification`` la clôt : le contrôle du suivi la jugeait
sur un jour à venir, et le journal la disait « traitée en avance ».

Règle : UNE ÉTAPE CLOSE GARDE L'ÉCHÉANCE QU'ELLE AVAIT QUAND ON L'A TRAITÉE.
La vue lit ``(due_at, due_date, due_initial_at)`` AVANT la planification, et
la clôture les rétablit (ces trois colonnes seulement). Le reste du plan, lui,
reprend APRÈS la visite — exactement comme sans ``etape``.

Horloge FIXE : mercredi 30/09/2026, 10 h à Casablanca ; visite le lundi 05/10.
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import controle_suivi as cs
from apps.crm import horaires, services, stages
from apps.crm import suite_touche as st
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

CASA = horaires.CASABLANCA
GEL = datetime.datetime(2026, 9, 30, 10, 0, tzinfo=CASA)
AUJOURDHUI = GEL.date()
VISITE_LE = datetime.date(2026, 10, 5)
A_FAIRE = RelanceEtape.Statut.A_FAIRE
FAIT = RelanceEtape.Statut.FAIT

_seq = itertools.count(1)


def _a(decalage, heure, minute=0):
    jour = AUJOURDHUI + datetime.timedelta(days=decalage)
    return datetime.datetime.combine(jour, datetime.time(heure, minute),
                                     tzinfo=CASA)


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.n = n
        self.company = Company.objects.create(
            nom=f'Cockpit echeance {n}', slug=f'cockpit-echeance-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'cockpit-echeance-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self._k = itertools.count(1)

    def _dossier(self, *, due_suivi):
        """Un lead « devis envoyé » dont le suivi de proposition est pendant :
        la touche d'appel ``due_suivi`` et, derrière elle, le message
        suivant du plan deux jours plus tard."""
        k = next(self._k)
        lead = Lead.objects.create(
            company=self.company, nom=f'Prospect echeance {self.n}-{k}',
            stage=stages.QUOTE_SENT, owner=self.acteur,
            telephone=f'+212661{self.n:03d}{k:03d}')
        depart = GEL - datetime.timedelta(days=3)
        suivi = RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='apres_devis', ordre=1,
            canal=RelanceEtape.Canal.APPEL, libelle='Appel de suivi',
            due_at=due_suivi, due_date=due_suivi.astimezone(CASA).date(),
            cadence_depart=depart)
        suite = RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='apres_devis', ordre=2,
            canal=RelanceEtape.Canal.WHATSAPP, libelle='Message de suivi',
            due_at=_a(2, 11), due_date=_a(2, 11).date(),
            cadence_depart=depart)
        return lead, suivi, suite

    def _planifier(self, lead, **corps):
        corps.setdefault('date_prevue', VISITE_LE.isoformat())
        return self.api.post(
            f'/api/django/crm/leads/{lead.pk}/visites/planifier/', corps,
            format='json')


class LEcheanceDuTraitementTests(_Base):

    def test_une_touche_due_aujourdhui_reste_due_aujourdhui(self):
        lead, suivi, _suite = self._dossier(due_suivi=_a(0, 9))
        origine = (suivi.due_at, suivi.due_date, suivi.due_initial_at)
        resp = self._planifier(lead, etape=suivi.pk,
                               note_etape='RDV pris pour lundi')
        self.assertEqual(resp.status_code, 201, resp.data)

        suivi.refresh_from_db()
        self.assertEqual(suivi.statut, FAIT)
        self.assertEqual(suivi.outcome, services.OUTCOME_VISITE_ACCEPTEE)
        self.assertEqual(suivi.note, 'RDV pris pour lundi')
        self.assertEqual(
            (suivi.due_at, suivi.due_date, suivi.due_initial_at), origine)
        self.assertEqual(suivi.due_date, AUJOURDHUI)
        self.assertEqual(suivi.traite_le.astimezone(CASA).date(), AUJOURDHUI)
        self.assertEqual(suivi.nb_reports, 0)
        # Le journal dit la vraie échéance : rien n'a été fait « en avance ».
        self.assertFalse(LeadActivity.objects.filter(
            lead=lead, body__contains='Traitée en avance').exists())

    def test_une_touche_en_retard_garde_son_echeance_passee(self):
        lead, suivi, _suite = self._dossier(due_suivi=_a(-1, 10))
        resp = self._planifier(lead, etape=suivi.pk)
        self.assertEqual(resp.status_code, 201, resp.data)
        suivi.refresh_from_db()
        self.assertEqual(suivi.statut, FAIT)
        self.assertEqual(suivi.due_date, AUJOURDHUI
                         - datetime.timedelta(days=1))
        self.assertEqual(suivi.due_initial_at, _a(-1, 10))

    def test_le_controle_la_juge_sur_le_jour_de_son_traitement(self):
        lead, suivi, _suite = self._dossier(due_suivi=_a(0, 9))
        self.assertEqual(
            self._planifier(lead, etape=suivi.pk).status_code, 201)
        controle = cs.controle_suivi(self.company, self.acteur)
        verdict = controle['verdict']
        self.assertEqual((verdict['du'], verdict['a_temps']), (1, 1))
        [ligne] = [ligne for ligne in controle['par_type']
                   if ligne['type_etape'] == st.TYPE_SUIVI_APPEL]
        self.assertEqual(ligne['reponses'],
                         [{'cle': services.OUTCOME_VISITE_ACCEPTEE, 'n': 1}])
        [case] = [case for case in controle['jours']
                  if case['date'] == AUJOURDHUI.isoformat()]
        self.assertEqual((case['du'], case['a_temps'], case['etat']),
                         (1, 1, cs.ETAT_VERT))


class LeSuiviRepartApresLaVisiteTests(_Base):

    def test_la_suite_du_plan_reprend_apres_la_visite(self):
        lead, suivi, suite = self._dossier(due_suivi=_a(0, 9))
        self.assertEqual(
            self._planifier(lead, etape=suivi.pk).status_code, 201)
        suite.refresh_from_db()
        self.assertEqual(suite.statut, A_FAIRE)
        self.assertGreater(suite.due_date, VISITE_LE)
        # Un décalage du MOTEUR, jamais un report compté à la commerciale.
        self.assertEqual(suite.nb_reports, 0)
        suivis = [etape for etape in lead.relance_etapes.filter(
            statut=A_FAIRE) if st.type_etape(etape) in st.TYPES_BARREAU]
        self.assertEqual([etape.pk for etape in suivis], [suite.pk])

    def test_la_suite_est_decalee_exactement_comme_sans_etape(self):
        """B8 ne rétablit QUE la touche close : planifier avec ``etape`` ou
        sans elle laisse la suite du plan au même instant."""
        avec, suivi, suite_avec = self._dossier(due_suivi=_a(0, 9))
        sans, _touche, suite_sans = self._dossier(due_suivi=_a(0, 9))
        self.assertEqual(
            self._planifier(avec, etape=suivi.pk).status_code, 201)
        self.assertEqual(self._planifier(sans).status_code, 201)
        suite_avec.refresh_from_db()
        suite_sans.refresh_from_db()
        self.assertEqual(suite_avec.due_at, suite_sans.due_at)
        self.assertEqual(suite_avec.cadence_depart, suite_sans.cadence_depart)

"""SUIVI E5 — RE-planifier déplace la visite existante, jamais une seconde
visite.

SUIVI-PARCOURS 30/09/2026 (table : « Reportée à une autre date » sur la
confirmation, « La visite n'a pas eu lieu — nouvelle date » sur le débrief).
``apps.visites.services.planifier_visite`` créait TOUJOURS une nouvelle
``VisiteTerrain`` : un report laissait deux rendez-vous, et le technicien se
serait déplacé deux fois. Décision : ``replanifier=True`` DÉPLACE le
rendez-vous en attente du lead (BROUILLON, jamais commencé, daté — le plus
récent) : date, assigné s'il est fourni, notes complétées, assigné prévenu
quand l'assigné ou la date change, ``visite_planifiee`` publié (le CRM recale
confirmation et débrief). S'il n'y en a aucun, la visite est créée. Mêmes
gardes (date passée, commercial d'une autre société).

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.cadence_config import CLE_CONFIRMATION, CLE_DEBRIEF, q_etape
from apps.crm.models import Lead, RelanceEtape
from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape
from apps.visites import services as visites_services
from apps.visites.models import VisiteTerrain

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
#: Lundi 28/09 puis jeudi 01/10 : le rendez-vous, puis son report.
PREMIERE_DATE = datetime.date(2026, 9, 28)
NOUVELLE_DATE = datetime.date(2026, 10, 1)
A_FAIRE = RelanceEtape.Statut.A_FAIRE

_seq = itertools.count(1)


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E5 {n}', slug=f'suivi-e5-{n}')
        self.autre = Company.objects.create(
            nom=f'Suivi E5 autre {n}', slug=f'suivi-e5-autre-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e5-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.technicien = User.objects.create_user(
            username=f'suivi-e5-tech-{n}', password='x',
            company=self.company)
        self.second_technicien = User.objects.create_user(
            username=f'suivi-e5-tech2-{n}', password='x',
            company=self.company)
        self.etranger = User.objects.create_user(
            username=f'suivi-e5-etranger-{n}', password='x',
            company=self.autre)
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E5 {n}',
            stage=stages.QUOTE_SENT, owner=self.acteur,
            telephone=f'+21266150{n:04d}')

    def _planifier(self, date_prevue, **kw):
        return visites_services.planifier_visite(
            self.lead, self.acteur, date_prevue, **kw)

    def _visites(self):
        return VisiteTerrain.objects.filter(lead=self.lead)


class ReplanifierTests(_Base):

    def test_le_rendez_vous_en_attente_est_deplace_jamais_double(self):
        visite, erreurs = self._planifier(
            PREMIERE_DATE, commercial=self.technicien, notes='Portail bleu')
        self.assertEqual(erreurs, {})

        deplacee, erreurs = self._planifier(
            NOUVELLE_DATE, commercial=self.second_technicien,
            notes='Le client est absent lundi', replanifier=True)

        self.assertEqual(erreurs, {})
        self.assertEqual(deplacee.pk, visite.pk)
        self.assertEqual(self._visites().count(), 1)
        deplacee.refresh_from_db()
        self.assertEqual(deplacee.date_prevue, NOUVELLE_DATE)
        self.assertEqual(deplacee.commercial_id, self.second_technicien.pk)
        self.assertIn('Portail bleu', deplacee.notes)
        self.assertIn('Le client est absent lundi', deplacee.notes)
        self.assertIn('28/09/2026', deplacee.notes)
        # Le nouvel assigné est prévenu (primitive VTA7 existante).
        self.assertTrue(Notification.objects.filter(
            recipient=self.second_technicien,
            event_type=EventType.VISITE_TERRAIN_ASSIGNEE).exists())

    def test_le_crm_suit_la_nouvelle_date(self):
        self._planifier(PREMIERE_DATE, commercial=self.technicien)
        self._planifier(NOUVELLE_DATE, replanifier=True)

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.visite_prevue_le, NOUVELLE_DATE)
        confirmations = self.lead.relance_etapes.filter(
            q_etape(CLE_CONFIRMATION), statut=A_FAIRE)
        debriefs = self.lead.relance_etapes.filter(
            q_etape(CLE_DEBRIEF), statut=A_FAIRE)
        self.assertEqual(confirmations.count(), 1)
        self.assertEqual(debriefs.count(), 1)
        self.assertGreater(debriefs.get().due_date, NOUVELLE_DATE)

    def test_meme_assigne_meme_date_personne_n_est_renotifie(self):
        self._planifier(PREMIERE_DATE, commercial=self.technicien)
        avant = Notification.objects.filter(
            recipient=self.technicien).count()
        self._planifier(PREMIERE_DATE, replanifier=True)
        self.assertEqual(
            Notification.objects.filter(recipient=self.technicien).count(),
            avant)

    def test_sans_rendez_vous_en_attente_la_visite_est_creee(self):
        visite, erreurs = self._planifier(NOUVELLE_DATE, replanifier=True)
        self.assertEqual(erreurs, {})
        self.assertEqual(self._visites().count(), 1)
        self.assertEqual(visite.date_prevue, NOUVELLE_DATE)

    def test_une_visite_commencee_n_est_jamais_deplacee(self):
        visite, _ = self._planifier(PREMIERE_DATE,
                                    commercial=self.technicien)
        visite.en_route_le = GEL
        visite.save(update_fields=['en_route_le'])

        nouvelle, _ = self._planifier(NOUVELLE_DATE, replanifier=True)

        self.assertNotEqual(nouvelle.pk, visite.pk)
        visite.refresh_from_db()
        self.assertEqual(visite.date_prevue, PREMIERE_DATE)

    def test_sans_replanifier_le_comportement_historique_cree(self):
        self._planifier(PREMIERE_DATE)
        self._planifier(NOUVELLE_DATE)
        self.assertEqual(self._visites().count(), 2)


class GardesTests(_Base):

    def test_date_passee_refusee_avant_tout_deplacement(self):
        visite, _ = self._planifier(PREMIERE_DATE)
        refus, erreurs = self._planifier(
            GEL.date() - datetime.timedelta(days=1), replanifier=True)
        self.assertIsNone(refus)
        self.assertIn('date_prevue', erreurs)
        visite.refresh_from_db()
        self.assertEqual(visite.date_prevue, PREMIERE_DATE)

    def test_commercial_d_une_autre_societe_refuse(self):
        visite, _ = self._planifier(PREMIERE_DATE,
                                    commercial=self.technicien)
        refus, erreurs = self._planifier(
            NOUVELLE_DATE, commercial=self.etranger, replanifier=True)
        self.assertIsNone(refus)
        self.assertIn('commercial', erreurs)
        visite.refresh_from_db()
        self.assertEqual(visite.commercial_id, self.technicien.pk)

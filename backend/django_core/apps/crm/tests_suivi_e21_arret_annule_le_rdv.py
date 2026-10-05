"""SUIVI E21 — quand tout s'arrête, le rendez-vous en attente s'annule aussi.

SUIVI-PARCOURS 30/09/2026 (table : « Confirmer la visite » → « Ne veut plus du
projet » : « Toutes les relances s'arrêtent, le rendez-vous est annulé »).
« Refus » (issue ``refuse``), « Perdu » (réponse E2 et la bascule « perdu » de
la fiche) et « Ne plus me contacter » (réponse et bascule de la fiche)
arrêtaient les relances mais laissaient la visite planifiée dans le module
Visites : le technicien se serait déplacé chez un client qui a refusé.

Décision : dans ces trois cas, ``annuler_rendez_vous_sur_arret`` annule le
rendez-vous EN ATTENTE (porte E4 ``apps.visites.services.annuler_rendez_vous``,
best-effort) et vide ``Lead.visite_prevue_le`` — une date PASSÉE reste sur la
fiche (historique). UNE note système le dit, seulement quand un rendez-vous a
réellement été annulé.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca ; rendez-vous le lundi
28/09.
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm.cadence_config import (
    CLE_CONFIRMATION, CLE_DECIDER_SUITE, q_etape)
from apps.crm.models import Lead, MotifPerte, RelanceEtape
from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape
from apps.visites import services as visites_services

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
VISITE_LE = datetime.date(2026, 9, 28)
MOTIF = 'Prix trop élevé'
A_FAIRE = RelanceEtape.Statut.A_FAIRE
NOTE_RDV = 'Rendez-vous de visite'

_seq = itertools.count(1)


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E21 {n}', slug=f'suivi-e21-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        MotifPerte.objects.create(company=self.company, nom=MOTIF)
        self.acteur = User.objects.create_user(
            username=f'suivi-e21-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.technicien = User.objects.create_user(
            username=f'suivi-e21-tech-{n}', password='x',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E21 {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266221{n:04d}')

    def _planifier(self):
        visite, erreurs = visites_services.planifier_visite(
            self.lead, self.acteur, VISITE_LE, commercial=self.technicien)
        self.assertEqual(erreurs, {})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.visite_prevue_le, VISITE_LE)
        return visite

    def _fait(self, etape, corps):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/', corps,
            format='json')

    def _notes_rdv(self):
        return self.lead.activites.filter(body__startswith=NOTE_RDV,
                                          user__isnull=True)

    def _assert_annule(self, visite, cause):
        visite.refresh_from_db()
        self.assertIsNone(visite.date_prevue)
        self.assertIn(f'Rendez-vous du 28/09/2026 annulé — {cause}.',
                      visite.notes)
        self.assertTrue(Notification.objects.filter(
            recipient=self.technicien,
            event_type=EventType.VISITE_TERRAIN_ASSIGNEE,
            title='Visite technique annulée').exists())
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.visite_prevue_le)
        # UNE note système, même si deux arrêts se succèdent (la réponse
        # puis le récepteur « refus ») : le second ne trouve plus rien.
        [note] = list(self._notes_rdv())
        self.assertEqual(
            note.body,
            f'{NOTE_RDV} du 28/09/2026 annulé (le technicien est prévenu) : '
            f'{cause}.')


class ArretParUneToucheTests(_Base):

    def test_refus_sur_la_confirmation(self):
        visite = self._planifier()
        confirmation = self.lead.relance_etapes.get(
            q_etape(CLE_CONFIRMATION), statut=A_FAIRE)

        resp = self._fait(confirmation, {'outcome': 'refuse'})

        self.assertEqual(resp.status_code, 200, resp.data)
        self._assert_annule(visite, services.CAUSE_RDV_REFUS)
        # La décision reste humaine : « Décider la suite » est posée.
        self.assertTrue(self.lead.relance_etapes.filter(
            q_etape(CLE_DECIDER_SUITE), statut=A_FAIRE).exists())

    def test_perdu_sur_decider_la_suite(self):
        visite = self._planifier()
        decider = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='generique',
            ordre=1, canal=RelanceEtape.Canal.APPEL, cle=CLE_DECIDER_SUITE,
            libelle='Décider la suite — perdu (motif) ou relance ultérieure',
            due_at=GEL, due_date=GEL.date())

        resp = self._fait(decider, {'reponse': services.REPONSE_PERDU,
                                    'motif_perte': MOTIF})

        self.assertEqual(resp.status_code, 200, resp.data)
        self._assert_annule(visite, services.cause_rdv_perdu(MOTIF))
        self.assertTrue(self.lead.perdu)

    def test_ne_plus_me_contacter(self):
        visite = self._planifier()
        confirmation = self.lead.relance_etapes.get(
            q_etape(CLE_CONFIRMATION), statut=A_FAIRE)

        resp = self._fait(confirmation,
                          {'reponse': services.REPONSE_NE_PLUS_CONTACTER})

        self.assertEqual(resp.status_code, 200, resp.data)
        self._assert_annule(visite, services.CAUSE_RDV_NE_PLUS_CONTACTER)
        self.assertTrue(self.lead.ne_plus_contacter)


class ArretParLaFicheTests(_Base):

    def _patch(self, corps):
        return self.api.patch(f'/api/django/crm/leads/{self.lead.pk}/',
                              corps, format='json')

    def test_bascule_perdu(self):
        visite = self._planifier()

        resp = self._patch({'perdu': True, 'motif_perte': MOTIF})

        self.assertEqual(resp.status_code, 200, resp.data)
        self._assert_annule(visite, services.cause_rdv_perdu(MOTIF))

    def test_bascule_ne_plus_contacter(self):
        visite = self._planifier()

        resp = self._patch({'ne_plus_contacter': True})

        self.assertEqual(resp.status_code, 200, resp.data)
        self._assert_annule(visite, services.CAUSE_RDV_NE_PLUS_CONTACTER)


class VisitePasseeTests(_Base):

    def test_une_date_de_visite_passee_reste_sur_la_fiche(self):
        passee = GEL.date() - datetime.timedelta(days=2)
        self.lead.visite_prevue_le = passee
        self.lead.save(update_fields=['visite_prevue_le'])
        appel = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=2, canal=RelanceEtape.Canal.APPEL,
            libelle="Appel d'ouverture", due_at=GEL, due_date=GEL.date(),
            cadence_depart=GEL)

        resp = self._fait(appel, {'outcome': 'refuse'})

        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.visite_prevue_le, passee)
        self.assertFalse(self._notes_rdv().exists())

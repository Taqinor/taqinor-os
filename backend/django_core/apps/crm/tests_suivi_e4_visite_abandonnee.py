"""SUIVI E4 — refuser ou annuler la VISITE n'est pas refuser la PROPOSITION.

SUIVI-PARCOURS 30/09/2026. « Ne veut plus de visite » / « Annule le
rendez-vous » envoyaient « refus » : TOUT le suivi mourait, proposition
comprise, et le rendez-vous restait dans le module Visites (le technicien se
serait déplacé). Nouvelle réponse ``visite_abandonnee``, valable sur
« Planifier la visite », « Confirmer la visite » et « Débrief visite ».
Effet, dans l'ordre : la touche est close (FAIT, issue « joint », note
typée) ; le rendez-vous en attente est ANNULÉ côté visites
(``apps.visites.services.annuler_rendez_vous`` : date vidée, ligne de notes,
technicien prévenu, aucune suppression) ; ``Lead.visite_prevue_le`` vidé ; les
AUTRES gestes de visite (jamais « Préparer le devis modifié ») annulés ; UNE
note système ; le filet sans jamais démarrer le suivi : un suivi pendant
continue seul, sinon « Préparer et envoyer le devis ».

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca ; rendez-vous le lundi
28/09.
"""
import datetime
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm.cadence_config import (
    CLE_CONFIRMATION, CLE_DEBRIEF, CLE_DEVIS, CLE_DEVIS_MODIFIE, CLE_PLANIFIER,
    q_etape)
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape
from apps.ventes.models import Devis
from apps.visites import services as visites_services
from apps.visites.models import VisiteTerrain

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
VISITE_LE = datetime.date(2026, 9, 28)
A_FAIRE = RelanceEtape.Statut.A_FAIRE
ANNULEE = RelanceEtape.Statut.ANNULEE
FAIT = RelanceEtape.Statut.FAIT

_seq = itertools.count(1)


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E4 {n}', slug=f'suivi-e4-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e4-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.technicien = User.objects.create_user(
            username=f'suivi-e4-tech-{n}', password='x',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E4 {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266140{n:04d}')

    def _planifier(self):
        visite, erreurs = visites_services.planifier_visite(
            self.lead, self.acteur, VISITE_LE, commercial=self.technicien)
        self.assertEqual(erreurs, {})
        return visite

    def _etape(self, cle):
        return self.lead.relance_etapes.get(q_etape(cle), statut=A_FAIRE)

    def _abandonner(self, etape, **corps):
        corps['reponse'] = services.REPONSE_VISITE_ABANDONNEE
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/', corps,
            format='json')

    def _ouvertes(self, *q):
        return self.lead.relance_etapes.filter(*q, statut=A_FAIRE)


class AnnuleLeRendezVousTests(_Base):

    def test_annule_le_rendez_vous_depuis_la_confirmation(self):
        visite = self._planifier()
        confirmation = self._etape(CLE_CONFIRMATION)
        debrief = self._etape(CLE_DEBRIEF)

        resp = self._abandonner(confirmation, note='Il a trouvé moins cher')

        self.assertEqual(resp.status_code, 200, resp.data)
        confirmation.refresh_from_db()
        self.assertEqual(confirmation.statut, FAIT)
        self.assertEqual(confirmation.outcome, 'joint')
        self.assertEqual(
            confirmation.note,
            'Visite abandonnée — le client ne veut plus de visite — Il a '
            'trouvé moins cher')
        # Le rendez-vous est annulé côté visites, jamais supprimé.
        visite.refresh_from_db()
        self.assertIsNone(visite.date_prevue)
        self.assertIn('Rendez-vous du 28/09/2026 annulé à la demande du '
                      'client.', visite.notes)
        self.assertTrue(Notification.objects.filter(
            recipient=self.technicien,
            event_type=EventType.VISITE_TERRAIN_ASSIGNEE,
            title='Visite technique annulée').exists())
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.visite_prevue_le)
        debrief.refresh_from_db()
        self.assertEqual(debrief.statut, ANNULEE)
        self.assertEqual(debrief.note, services.NOTE_VISITE_ABANDONNEE)
        self.assertEqual(self.lead.activites.filter(
            body__startswith='Visite abandonnée à la demande du client',
            user__isnull=True).count(), 1)
        # Aucun suivi pendant : « Préparer et envoyer le devis ».
        self.assertTrue(self._ouvertes(q_etape(CLE_DEVIS)).exists())
        self.assertEqual(resp.data['prochaine_touche']['cle'], CLE_DEVIS)

    def test_la_proposition_continue_seule_depuis_le_debrief(self):
        self.lead.stage = stages.QUOTE_SENT
        self.lead.save(update_fields=['stage'])
        client = Client.objects.create(
            company=self.company, nom='Client E4',
            email=f'suivi-e4-{next(_seq)}@example.com')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-E4-{next(_seq):05d}',
            client=client, lead=self.lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'),
            date_envoi=GEL - datetime.timedelta(days=7))
        plan = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=4, canal=RelanceEtape.Canal.WHATSAPP,
            libelle='Preuve — chantier comparable', devis=devis,
            due_at=GEL + datetime.timedelta(days=6),
            due_date=(GEL + datetime.timedelta(days=6)).date(),
            cadence_depart=GEL - datetime.timedelta(days=7))
        self._planifier()
        debrief = self._etape(CLE_DEBRIEF)

        resp = self._abandonner(debrief)

        self.assertEqual(resp.status_code, 200, resp.data)
        plan.refresh_from_db()
        self.assertEqual(plan.statut, A_FAIRE)
        self.assertEqual(set(self._ouvertes().values_list('pk', flat=True)),
                         {plan.pk})
        self.assertFalse(self._ouvertes(q_etape(CLE_DEVIS)).exists())

    def test_depuis_planifier_la_visite(self):
        planifier = services.poser_filet_visite_a_planifier(
            self.lead, self.acteur)
        resp = self._abandonner(planifier)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(self._ouvertes(q_etape(
            CLE_PLANIFIER, CLE_CONFIRMATION, CLE_DEBRIEF)).exists())
        self.assertTrue(self._ouvertes(q_etape(CLE_DEVIS)).exists())

    def test_le_devis_modifie_n_est_jamais_retire(self):
        self._planifier()
        modifie = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=services.VISITE_ORDRE_DEBRIEF + 5,
            canal=RelanceEtape.Canal.APPEL, cle=CLE_DEVIS_MODIFIE,
            libelle=services.VISITE_DEVIS_LIBELLE,
            due_at=GEL + datetime.timedelta(days=1),
            due_date=(GEL + datetime.timedelta(days=1)).date())
        resp = self._abandonner(self._etape(CLE_CONFIRMATION))
        self.assertEqual(resp.status_code, 200, resp.data)
        modifie.refresh_from_db()
        self.assertEqual(modifie.statut, A_FAIRE)


class RefusNommesTests(_Base):

    def test_hors_des_gestes_de_visite_la_reponse_est_refusee(self):
        appel = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=2, canal=RelanceEtape.Canal.APPEL,
            libelle="Appel d'ouverture", due_at=GEL, due_date=GEL.date())
        resp = self._abandonner(appel)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('« Ne veut plus de visite »',
                      resp.data['erreurs']['reponse'])
        appel.refresh_from_db()
        self.assertEqual(appel.statut, A_FAIRE)


class AnnulerRendezVousServiceTests(_Base):
    """La porte de l'app visites : seuls les rendez-vous EN ATTENTE."""

    def test_seuls_les_rendez_vous_en_attente_sont_annules(self):
        en_attente = self._planifier()
        commencee = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, date_prevue=VISITE_LE,
            en_route_le=GEL)
        passee = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead,
            date_prevue=GEL.date() - datetime.timedelta(days=2))
        terminee = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, date_prevue=VISITE_LE,
            statut=VisiteTerrain.Statut.TERMINEE)

        annules = visites_services.annuler_rendez_vous(
            self.lead, self.acteur)

        self.assertEqual(annules, 1)
        en_attente.refresh_from_db()
        self.assertIsNone(en_attente.date_prevue)
        for visite in (commencee, passee, terminee):
            visite.refresh_from_db()
            self.assertIsNotNone(visite.date_prevue)
        # Aucune suppression : les quatre visites sont toujours là.
        self.assertEqual(
            VisiteTerrain.objects.filter(lead=self.lead).count(), 4)

    def test_un_motif_remplace_la_formule_du_client(self):
        visite = self._planifier()
        visites_services.annuler_rendez_vous(
            self.lead, self.acteur, motif='dossier perdu (Prix)')
        visite.refresh_from_db()
        self.assertIn('Rendez-vous du 28/09/2026 annulé — dossier perdu '
                      '(Prix).', visite.notes)
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead, body__contains='annulé — dossier').exists())

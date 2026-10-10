"""SUIVI E18 — l'endpoint de planification clôt la touche qui l'a demandée.

SUIVI-PARCOURS 30/09/2026 (table : réponse « Visite acceptée » — « La
planification s'ouvre avant tout enregistrement »). L'écran envoyait
« Fait visite acceptée » AVANT de planifier : l'étape « Planifier la visite »
naissait, puis la planification l'annulait aussitôt. Désormais
``POST crm/leads/<id>/visites/planifier/`` accepte ``etape`` (une touche de CE
lead — 400 nommé sinon, avant toute écriture) et ``note_etape`` : après la
planification réussie, la touche encore à faire est close « visite
acceptée » ; déjà annulée par la planification (« Planifier la visite »,
étape devis mise en attente), elle reste annulée et la note part dans une
ligne de chatter ; « Confirmer » / « Débrief » ouvertes suivent le
rendez-vous et restent ouvertes. ``replanifier`` déplace le rendez-vous en
attente (E5). La réponse devient ``{visite, prochaine_touche}``.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime
import itertools
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm import cadence_filet
from apps.crm import cadence_reperes
from apps.crm.cadence_config import (
    CLE_CONFIRMATION, CLE_DEBRIEF, CLE_DEVIS, CLE_PLANIFIER, q_etape)
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape
from apps.visites.models import VisiteTerrain

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
VISITE_LE = '2026-09-28'
NOUVELLE_DATE = '2026-10-01'
A_FAIRE = RelanceEtape.Statut.A_FAIRE
ANNULEE = RelanceEtape.Statut.ANNULEE
FAIT = RelanceEtape.Statut.FAIT

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_visite_planifier.json').read_text(encoding='utf-8'))

_seq = itertools.count(1)


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E18 {n}', slug=f'suivi-e18-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e18-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = self._lead(stages.NEW)

    def _lead(self, stage):
        n = next(_seq)
        return Lead.objects.create(
            company=self.company, nom=f'Prospect E18 {n}', stage=stage,
            owner=self.acteur, telephone=f'+21266181{n:04d}')

    def _touche(self, lead=None, **champs):
        valeurs = dict(company=self.company, lead=lead or self.lead,
                       due_at=GEL, due_date=GEL.date())
        valeurs.update(champs)
        return RelanceEtape.objects.create(**valeurs)

    def _appel_contact(self, ordre=2):
        return self._touche(cadence='contact', ordre=ordre,
                            canal=RelanceEtape.Canal.APPEL,
                            libelle="Appel d'ouverture", cadence_depart=GEL)

    def _planifier(self, **corps):
        corps.setdefault('date_prevue', VISITE_LE)
        return self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/visites/planifier/',
            corps, format='json')

    def _ouvertes(self, *q):
        return self.lead.relance_etapes.filter(*q, statut=A_FAIRE)


class LaTouchEstCloseTests(_Base):

    def test_appel_de_prise_de_contact_clos_visite_acceptee(self):
        appel = self._appel_contact()
        resp = self._planifier(etape=appel.pk, note_etape='RDV pris lundi')
        self.assertEqual(resp.status_code, 201, resp.data)

        appel.refresh_from_db()
        self.assertEqual(appel.statut, FAIT)
        self.assertEqual(appel.outcome, cadence_reperes.OUTCOME_VISITE_ACCEPTEE)
        self.assertEqual(appel.note, 'RDV pris lundi')
        # Le rendez-vous est calé : aucune étape « planifier la visite ».
        self.assertFalse(self._ouvertes(q_etape(CLE_PLANIFIER)).exists())
        self.assertTrue(self._ouvertes(q_etape(CLE_CONFIRMATION)).exists())
        self.assertTrue(self._ouvertes(q_etape(CLE_DEBRIEF)).exists())
        self.assertFalse(self.lead.relance_etapes.filter(
            cadence='contact', statut=A_FAIRE).exists())
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)
        self.assertEqual(VisiteTerrain.objects.filter(lead=self.lead).count(),
                         1)

    def test_la_reponse_porte_la_prochaine_touche(self):
        appel = self._appel_contact()
        resp = self._planifier(etape=appel.pk)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(set(resp.data), set(CONTRAT['exemple']))
        prochaine = resp.data['prochaine_touche']
        self.assertEqual(set(prochaine),
                         set(CONTRAT['exemple']['prochaine_touche']))
        self.assertEqual(prochaine['cle'], CLE_CONFIRMATION)

    def test_sans_etape_le_comportement_historique(self):
        resp = self._planifier()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('prochaine_touche', resp.data)


class LaTouchDejaAnnuleeResteAnnuleeTests(_Base):

    def test_l_etape_planifier_reste_annulee_et_la_note_part_au_chatter(self):
        planifier = cadence_filet.poser_filet_visite_a_planifier(
            self.lead, self.acteur)
        resp = self._planifier(etape=planifier.pk, note_etape='Calé au tél.')
        self.assertEqual(resp.status_code, 201, resp.data)
        planifier.refresh_from_db()
        self.assertEqual(planifier.statut, ANNULEE)
        self.assertTrue(self.lead.activites.filter(
            body__contains='Calé au tél.').exists())

    def test_l_etape_devis_mise_en_attente_reste_annulee(self):
        devis = services.poser_etape_preparer_devis(
            self.lead, origine='test', user=self.acteur)
        self.assertTrue(devis is not None and devis.cle == CLE_DEVIS)
        resp = self._planifier(etape=devis.pk, note_etape='Visite d’abord')
        self.assertEqual(resp.status_code, 201, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, ANNULEE)
        self.assertEqual(devis.outcome, '')
        self.assertTrue(self.lead.activites.filter(
            body__contains='Visite d’abord').exists())


class ReplanifierDepuisLaConfirmationTests(_Base):

    def test_la_confirmation_suit_le_rendez_vous_et_reste_ouverte(self):
        resp = self._planifier()
        self.assertEqual(resp.status_code, 201, resp.data)
        confirmation = self._ouvertes(q_etape(CLE_CONFIRMATION)).get()

        resp = self._planifier(date_prevue=NOUVELLE_DATE, replanifier=True,
                               etape=confirmation.pk)

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(VisiteTerrain.objects.filter(lead=self.lead).count(),
                         1)
        confirmation.refresh_from_db()
        self.assertEqual(confirmation.statut, A_FAIRE)
        self.assertEqual(confirmation.due_date,
                         datetime.date(2026, 9, 30))
        self.assertEqual(self._ouvertes(q_etape(CLE_CONFIRMATION)).count(), 1)


class RefusNommesTests(_Base):

    def test_une_touche_d_un_autre_lead_est_refusee_avant_toute_ecriture(self):
        autre = self._lead(stages.CONTACTED)
        etrangere = self._touche(lead=autre, cadence='contact', ordre=2,
                                 canal=RelanceEtape.Canal.APPEL,
                                 libelle="Appel d'ouverture")
        resp = self._planifier(etape=etrangere.pk)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('etape', resp.data)
        self.assertEqual(resp.data, CONTRAT['exemple_erreur_etape'])
        self.assertFalse(VisiteTerrain.objects.filter(
            lead=self.lead).exists())
        etrangere.refresh_from_db()
        self.assertEqual(etrangere.statut, A_FAIRE)

    def test_un_identifiant_illisible_est_refuse(self):
        resp = self._planifier(etape='abc')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('etape', resp.data)
        self.assertFalse(VisiteTerrain.objects.filter(
            lead=self.lead).exists())

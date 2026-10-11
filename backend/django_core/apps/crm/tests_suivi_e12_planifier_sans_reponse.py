"""SUIVI E12 — « Planifier la visite » sans réponse → reposée DEMAIN.

SUIVI-PARCOURS 30/09/2026 (table : ``planifier`` × « Sans réponse » → étape
``planifier`` demain). L'appel pour caler la date de la visite qui n'aboutit
pas laissait le filet poser « Préparer et envoyer le devis » : le client
avait pourtant ACCEPTÉ la visite. Décision : la touche est close (l'appel
compte, issue « non joint ») et une NOUVELLE étape « Planifier la visite
technique convenue » est posée pour le lendemain. Code d'effet
``etape_planifier_demain``.

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

from apps.crm import horaires, stages, cadence_filet
from apps.crm import cadence_reperes
from apps.crm import suite_touche as st
from apps.crm.cadence_config import CLE_DEVIS, CLE_PLANIFIER, q_etape
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
DEMAIN = datetime.date(2026, 9, 24)
A_FAIRE = RelanceEtape.Statut.A_FAIRE

_seq = itertools.count(1)


class PromesseTests(SimpleTestCase):

    def test_sans_reponse_annonce_planifier_demain(self):
        etape = RelanceEtape(cadence='apres_devis',
                             ordre=cadence_reperes.VISITE_ORDRE_FILET,
                             canal=RelanceEtape.Canal.APPEL,
                             libelle=cadence_reperes.VISITE_FILET_LIBELLE,
                             statut=A_FAIRE)
        etape.lead = Lead(nom='témoin', stage=stages.CONTACTED)
        promesses = st.promesses_touche(etape, ordres=frozenset(),
                                        est_actif=lambda c: True)
        self.assertEqual(promesses['non_joint'], [st.ETAPE_PLANIFIER_DEMAIN])


class PlanifierSansReponseTests(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E12 {n}', slug=f'suivi-e12-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e12-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E12 {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266112{n:04d}')
        self.planifier = cadence_filet.poser_filet_visite_a_planifier(
            self.lead, self.acteur)

    def _sans_reponse(self, etape):
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'outcome': 'non_joint', 'note': 'Répondeur'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def test_une_nouvelle_etape_planifier_est_posee_pour_demain(self):
        resp = self._sans_reponse(self.planifier)

        self.planifier.refresh_from_db()
        self.assertEqual(self.planifier.statut, RelanceEtape.Statut.FAIT)
        self.assertEqual(self.planifier.outcome, 'non_joint')
        nouvelle = self.lead.relance_etapes.get(q_etape(CLE_PLANIFIER),
                                                statut=A_FAIRE)
        self.assertNotEqual(nouvelle.pk, self.planifier.pk)
        self.assertEqual(nouvelle.due_date, DEMAIN)
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_DEVIS)).exists())
        self.assertEqual(resp.data['prochaine_touche']['cle'], CLE_PLANIFIER)

    def test_deux_fois_sans_reponse_on_reessaie_encore(self):
        self._sans_reponse(self.planifier)
        seconde = self.lead.relance_etapes.get(q_etape(CLE_PLANIFIER),
                                               statut=A_FAIRE)
        self._sans_reponse(seconde)
        self.assertEqual(self.lead.relance_etapes.filter(
            q_etape(CLE_PLANIFIER), statut=A_FAIRE).count(), 1)
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_DEVIS)).exists())

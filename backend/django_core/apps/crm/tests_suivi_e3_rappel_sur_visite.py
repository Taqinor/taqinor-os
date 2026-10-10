"""SUIVI E3 — « À rappeler le… » sur une étape de VISITE la DÉPLACE.

SUIVI-PARCOURS 30/09/2026. La règle CAD3 (« à rappeler » REPORTE l'étape au
lieu de la consommer) ne valait que pour les étapes de filet. Sur une étape
de visite (planifier, débrief, devis modifié), l'étape était close, le filet
posait « Préparer et envoyer le devis » et c'était ELLE qui était déplacée :
la visite à planifier ou le débrief disparaissait de la file. Décision : même
branche que le filet — l'étape garde son identité, déplacée à la date ; code
d'effet ``etape_deplacee_a_la_date`` (``prochaine_relance_a_la_date``
disparaît du vocabulaire).

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca ; rappel le lundi
28/09 à 11 h (dans la fenêtre d'appel).
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
from apps.crm import cadence_filet
from apps.crm import cadence_reperes
from apps.crm import suite_touche as st
from apps.crm.cadence_config import (
    CLE_DEBRIEF, CLE_DEVIS, CLE_DEVIS_MODIFIE, CLE_PLANIFIER, q_etape)
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
RAPPEL_JOUR = datetime.date(2026, 9, 28)
A_FAIRE = RelanceEtape.Statut.A_FAIRE

_seq = itertools.count(1)


class PromesseTests(SimpleTestCase):

    def test_le_rappel_sur_une_etape_de_visite_la_deplace(self):
        for cle, libelle in ((CLE_PLANIFIER, cadence_reperes.VISITE_FILET_LIBELLE),
                             (CLE_DEBRIEF, cadence_reperes.VISITE_DEBRIEF_LIBELLE),
                             (CLE_DEVIS_MODIFIE,
                              cadence_reperes.VISITE_DEVIS_LIBELLE)):
            with self.subTest(cle=cle):
                etape = RelanceEtape(
                    cadence='apres_devis', ordre=cadence_reperes.VISITE_ORDRE_DEBRIEF,
                    canal=RelanceEtape.Canal.APPEL, libelle=libelle,
                    statut=A_FAIRE)
                etape.lead = Lead(nom='témoin', stage=stages.QUOTE_SENT)
                promesses = st.promesses_touche(
                    etape, ordres=frozenset(), est_actif=lambda c: True)
                self.assertEqual(promesses['rappel'],
                                 [st.ETAPE_DEPLACEE_A_LA_DATE])

    def test_le_code_prochaine_relance_a_la_date_a_disparu(self):
        self.assertNotIn('prochaine_relance_a_la_date', st.CODES)
        self.assertFalse(hasattr(st, 'PROCHAINE_RELANCE_A_LA_DATE'))


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E3 {n}', slug=f'suivi-e3-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e3-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E3 {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266130{n:04d}')

    def _rappeler(self, etape):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'outcome': 'rappel', 'rappel_le': RAPPEL_JOUR.isoformat(),
             'rappel_heure': '11:00'}, format='json')

    def _deplacee(self, etape, resp):
        self.assertEqual(resp.status_code, 200, resp.data)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, A_FAIRE)
        self.assertEqual(etape.due_date, RAPPEL_JOUR)
        # Rien n'a pris sa place : pas d'étape « préparer le devis ».
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_DEVIS)).exists())
        self.assertEqual(resp.data['prochaine_touche']['due_date'],
                         RAPPEL_JOUR.isoformat())


class RappelSurVisiteTests(_Base):

    def test_planifier_la_visite_est_deplacee(self):
        planifier = cadence_filet.poser_filet_visite_a_planifier(
            self.lead, self.acteur)
        resp = self._rappeler(planifier)
        self._deplacee(planifier, resp)
        self.assertEqual(resp.data['prochaine_touche']['cle'], CLE_PLANIFIER)

    def test_le_debrief_est_deplace(self):
        services.appliquer_visite_planifiee(
            self.lead, self.acteur, GEL.date())
        debrief = self.lead.relance_etapes.get(q_etape(CLE_DEBRIEF),
                                               statut=A_FAIRE)
        # La confirmation (visite du jour) n'a plus d'objet pour ce test.
        self.lead.relance_etapes.exclude(pk=debrief.pk).delete()
        resp = self._rappeler(debrief)
        self._deplacee(debrief, resp)
        self.assertEqual(self.lead.relance_etapes.filter(
            q_etape(CLE_DEBRIEF)).count(), 1)

    def test_le_devis_modifie_est_deplace(self):
        modifie = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=cadence_reperes.VISITE_ORDRE_DEBRIEF,
            canal=RelanceEtape.Canal.APPEL, cle=CLE_DEVIS_MODIFIE,
            libelle=cadence_reperes.VISITE_DEVIS_LIBELLE, due_at=GEL,
            due_date=GEL.date())
        self._deplacee(modifie, self._rappeler(modifie))


class TemoinBarreauTests(_Base):
    """Un barreau du PROTOCOLE garde MRY10 : la touche est consommée et c'est
    la SUIVANTE qui porte la date."""

    def test_un_barreau_est_toujours_consomme(self):
        appel = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=2, canal=RelanceEtape.Canal.APPEL,
            libelle="Appel d'ouverture", due_at=GEL, due_date=GEL.date(),
            cadence_depart=GEL)
        resp = self._rappeler(appel)
        self.assertEqual(resp.status_code, 200, resp.data)
        appel.refresh_from_db()
        self.assertEqual(appel.statut, RelanceEtape.Statut.FAIT)
        suivante = self.lead.relance_etapes.get(statut=A_FAIRE)
        self.assertEqual(suivante.cadence, 'contact')
        self.assertEqual(suivante.due_date, RAPPEL_JOUR)

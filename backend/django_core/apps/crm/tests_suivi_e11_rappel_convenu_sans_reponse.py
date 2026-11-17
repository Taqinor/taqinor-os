"""SUIVI E11 — « Rappel convenu » sans réponse → dernier essai.

SUIVI-PARCOURS 30/09/2026 (table : ``rappel_convenu`` × « Pas de réponse » →
étape ``dernier_appel`` demain). Le client avait fixé LUI-MÊME le moment du
rappel ; qu'il ne décroche pas ne doit pas faire réclamer tout de suite un
devis : ``CLE_RAPPEL_CONVENU`` rejoint l'escalier
``_FILET_SANS_REPONSE_PALIERS`` (issue « non joint » → « Rappeler — dernier
essai avant de chiffrer »). Un palier désactivé dans Paramètres est SAUTÉ,
comme les autres : la suite est alors le devis.

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
from apps.crm import cadence_reponses
from apps.crm import suite_touche as st
from apps.crm.cadence_config import (
    CLE_DERNIER_APPEL, CLE_DEVIS, CLE_RAPPEL_CONVENU, q_etape)
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import (
    CADENCES_DEFAUT, Cadence, CadenceRelanceEtape)

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
DEMAIN = datetime.date(2026, 9, 24)
A_FAIRE = RelanceEtape.Statut.A_FAIRE

_seq = itertools.count(1)


def _tous_actifs(cle):
    return True


def _sans_dernier_appel(cle):
    return cle != CLE_DERNIER_APPEL


class EscalierTests(SimpleTestCase):

    def test_le_rappel_convenu_sans_reponse_monte_au_dernier_essai(self):
        self.assertEqual(cadence_filet.prochain_palier_sans_reponse(
            CLE_RAPPEL_CONVENU, 'non_joint', _tous_actifs), CLE_DERNIER_APPEL)
        self.assertEqual(
            cadence_reponses._palier_sans_reponse(cadence_reperes.FILET_RAPPEL_LIBELLE,
                                                  'non_joint'),
            (cadence_reperes.FILET_DERNIER_APPEL_LIBELLE, RelanceEtape.Canal.APPEL,
             cadence_reperes.FILET_JOINT_DELAI_JOURS))

    def test_palier_desactive_saute(self):
        self.assertIsNone(cadence_filet.prochain_palier_sans_reponse(
            CLE_RAPPEL_CONVENU, 'non_joint', _sans_dernier_appel))

    def test_seul_le_sans_reponse_monte(self):
        self.assertIsNone(cadence_filet.prochain_palier_sans_reponse(
            CLE_RAPPEL_CONVENU, 'rappel', _tous_actifs))

    def test_la_promesse_dit_le_dernier_essai(self):
        etape = RelanceEtape(cadence='generique', ordre=1,
                             canal=RelanceEtape.Canal.APPEL,
                             cle=CLE_RAPPEL_CONVENU,
                             libelle=cadence_reperes.FILET_RAPPEL_LIBELLE,
                             statut=A_FAIRE)
        etape.lead = Lead(nom='témoin', stage=stages.CONTACTED)
        self.assertEqual(
            st.promesses_touche(etape, ordres=frozenset(),
                                est_actif=_tous_actifs)['non_joint'],
            [st.ETAPE_DERNIER_APPEL])
        self.assertEqual(
            st.promesses_touche(etape, ordres=frozenset(),
                                est_actif=_sans_dernier_appel)['non_joint'],
            [st.ETAPE_DEVIS_DEMAIN_SAUF_SUIVI])


class RappelConvenuSansReponseTests(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E11 {n}', slug=f'suivi-e11-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e11-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E11 {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266111{n:04d}')
        self.rappel = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='generique',
            ordre=1, canal=RelanceEtape.Canal.APPEL, cle=CLE_RAPPEL_CONVENU,
            libelle=cadence_reperes.FILET_RAPPEL_LIBELLE, due_at=GEL,
            due_date=GEL.date())

    def _sans_reponse(self):
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{self.rappel.pk}/fait/',
            {'outcome': 'non_joint', 'note': 'Répondeur'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def test_le_dernier_essai_est_pose_demain(self):
        resp = self._sans_reponse()
        essai = self.lead.relance_etapes.get(q_etape(CLE_DERNIER_APPEL),
                                             statut=A_FAIRE)
        self.assertEqual(essai.due_date, DEMAIN)
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_DEVIS)).exists())
        self.assertEqual(resp.data['prochaine_touche']['cle'],
                         CLE_DERNIER_APPEL)

    def test_palier_desactive_le_devis_prend_le_relais(self):
        CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=Cadence.APRES_CONTACT,
            cle=CLE_DERNIER_APPEL).update(actif=False)
        self._sans_reponse()
        self.assertFalse(self.lead.relance_etapes.filter(
            q_etape(CLE_DERNIER_APPEL)).exists())
        self.assertTrue(self.lead.relance_etapes.filter(
            q_etape(CLE_DEVIS), statut=A_FAIRE).exists())

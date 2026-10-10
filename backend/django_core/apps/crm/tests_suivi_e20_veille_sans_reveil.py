"""SUIVI E20 — veille de plus d'un mois sans gabarit « réveil » actif.

SUIVI-PARCOURS 30/09/2026 (table : « Plus tard — pas maintenant » → « Veille :
cette même touche revient à la date convenue »). Au-delà d'un mois, la veille
bascule en réveil daté (CAD26) : ``_basculer_veille_en_reveil`` ARRÊTAIT la
cadence en cours puis découvrait que la société n'avait aucun barreau
« réveil » actif (Paramètres) — le lead actif restait à ZÉRO touche.

Décision : sans réveil possible, rien n'est arrêté ; la veille SIMPLE
s'applique (la touche est déplacée à la date du client, reprise au même
barreau). Jamais un lead actif à zéro touche.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca ; date convenue : lundi
09/11/2026 (plus d'un mois).
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages, cadence_reponses
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
DATE_LOINTAINE = datetime.date(2026, 11, 9)
A_FAIRE = RelanceEtape.Statut.A_FAIRE
ANNULEE = RelanceEtape.Statut.ANNULEE

_seq = itertools.count(1)


class VeilleSansReveilTests(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E20 {n}', slug=f'suivi-e20-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e20-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Veille E20 {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266220{n:04d}')
        self.touche = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=2,
            canal=RelanceEtape.Canal.APPEL, libelle="Appel d'ouverture",
            due_at=GEL, due_date=GEL.date(), cadence_depart=GEL)

    def _sans_reveil(self):
        CadenceRelanceEtape.objects.filter(
            company=self.company, cadence='reveil').update(actif=False)

    def _plus_tard(self):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{self.touche.pk}/fait/',
            {'reponse': cadence_reponses.REPONSE_PLUS_TARD,
             'rappel_le': DATE_LOINTAINE.isoformat()}, format='json')

    def test_sans_reveil_actif_la_touche_est_deplacee_rien_n_est_arrete(self):
        self._sans_reveil()

        resp = self._plus_tard()

        self.assertEqual(resp.status_code, 200, resp.data)
        self.touche.refresh_from_db()
        self.assertEqual(self.touche.statut, A_FAIRE)
        self.assertEqual(self.touche.due_date, DATE_LOINTAINE)
        self.assertFalse(self.lead.relance_etapes.filter(
            statut=ANNULEE).exists())
        self.assertFalse(self.lead.relance_etapes.filter(
            cadence='reveil').exists())
        self.assertEqual(resp.data['prochaine_touche']['due_date'],
                         DATE_LOINTAINE.isoformat())

    def test_le_service_rend_la_meme_touche(self):
        self._sans_reveil()

        reprise = cadence_reponses.mettre_en_veille(
            self.lead, self.acteur, DATE_LOINTAINE, etape=self.touche)

        self.assertEqual(reprise.pk, self.touche.pk)
        self.assertEqual(reprise.due_date, DATE_LOINTAINE)

    def test_avec_reveil_actif_la_bascule_reste(self):
        resp = self._plus_tard()

        self.assertEqual(resp.status_code, 200, resp.data)
        self.touche.refresh_from_db()
        self.assertEqual(self.touche.statut, ANNULEE)
        self.assertTrue(self.lead.relance_etapes.filter(
            cadence='reveil', statut=A_FAIRE).exists())

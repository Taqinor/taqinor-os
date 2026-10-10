"""ACRM36 (C-ACRM-031) — le ``samedi_ok`` (et l'``heure_cible``) d'un barreau
voyage jusqu'à TOUTES les recompositions d'horaire.

Sonde V_VB LSVC1-3 : barreau ``samedi_ok=True`` posé par l'API Paramètres,
touche suivante recalée par ``cadence_temps.echeance_jamais_echue`` →
lundi 12/10 au lieu du samedi 10/10 annoncé par l'aperçu MRY30. Ce que
l'aperçu annonce est désormais ce qui naît.

Horloge : ``maintenant=`` (paramètre réel du code) et ``testkit.time.frozen``
— aucune doublure de la source testée.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import cadence_temps, horaires, stages, cadence_plan
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models_relance import CadenceRelanceEtape
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS

User = get_user_model()
VENDREDI_SOIR = datetime.datetime(2026, 10, 9, 20, 0,
                                  tzinfo=horaires.CASABLANCA)
SAMEDI = datetime.date(2026, 10, 10)
LUNDI = datetime.date(2026, 10, 12)


def _jour(instant):
    return instant.astimezone(horaires.CASABLANCA).date()


class SamediTransmisTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM36 Solaire', slug='acrm36-samedi')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.user = User.objects.create_user(
            username='acrm36-dir', password='x', company=self.company,
            role=role)
        self.lead = Lead.objects.create(
            company=self.company, nom='Samedi', owner=self.user,
            stage=stages.CONTACTED, telephone='+212661363636')
        RelanceEtape.objects.filter(lead=self.lead).delete()
        # Le barreau 2 (« Appel d'ouverture ») ouvert le samedi PAR L'API.
        self.barreau = CadenceRelanceEtape.cadence_pour(
            self.company, 'contact')[1]
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.user)}'))
        resp = api.patch(
            f'/api/django/parametres/cadence-relance/{self.barreau.pk}/',
            {'samedi_ok': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

    def _materialiser_barreau_2(self):
        with frozen(VENDREDI_SOIR):
            cadence_plan.initialiser_plan_relance(
                self.lead, self.user, cadence='contact')
            touche = (RelanceEtape.objects
                      .filter(lead=self.lead, cadence='contact')
                      .order_by('ordre').first())
            RelanceEtape.objects.filter(pk=touche.pk).update(
                statut=RelanceEtape.Statut.FAIT, traite_le=VENDREDI_SOIR,
                cadence_depart=VENDREDI_SOIR)
            touche.refresh_from_db()
            suivante = cadence_plan.materialiser_touche_suivante(
                touche, self.user)
        self.assertIsNotNone(suivante)
        self.assertEqual(suivante.ordre, self.barreau.ordre)
        suivante.refresh_from_db()
        return suivante

    def test_samedi_ok_tient(self):
        nee_echue = VENDREDI_SOIR - datetime.timedelta(days=2)
        echeance = cadence_temps.echeance_jamais_echue(
            nee_echue, company=self.company, canal='appel', samedi=True,
            maintenant=VENDREDI_SOIR)
        self.assertEqual(_jour(echeance), SAMEDI)
        suivante = self._materialiser_barreau_2()
        self.assertEqual(_jour(suivante.due_at), SAMEDI)

    def test_sans_samedi_lundi(self):
        nee_echue = VENDREDI_SOIR - datetime.timedelta(days=2)
        echeance = cadence_temps.echeance_jamais_echue(
            nee_echue, company=self.company, canal='appel',
            maintenant=VENDREDI_SOIR)
        self.assertEqual(_jour(echeance), LUNDI)
        CadenceRelanceEtape.objects.filter(pk=self.barreau.pk).update(
            samedi_ok=False)
        suivante = self._materialiser_barreau_2()
        self.assertEqual(_jour(suivante.due_at), LUNDI)

    def test_parite_partition_materialisation(self):
        suivante = self._materialiser_barreau_2()
        with frozen(VENDREDI_SOIR):
            partition = dict(
                (g.ordre, e) for g, e in cadence_plan.calculer_echeances_cadence(
                    self.lead, 'contact', VENDREDI_SOIR))
        self.assertEqual(_jour(partition[self.barreau.ordre]),
                         _jour(suivante.due_at))
        self.assertEqual(_jour(suivante.due_at), SAMEDI)

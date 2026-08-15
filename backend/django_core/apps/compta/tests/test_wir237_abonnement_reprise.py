"""WIR237 — Abonnements monitoring : la facturation manuelle ne GÈLE plus
l'abonnement, et la suspension est réversible.

Deux défauts constatés :
  1. l'action HTTP ``facturer`` appelait la facturation SEULE, jamais le
     renouvellement : ``prochaine_echeance`` ne bougeait pas, l'abonnement
     restait « dû » pour le sélecteur du beat tout en étant bloqué à jamais
     par sa propre garde d'idempotence (``derniere_facturation`` == période) ;
  2. ``suspendre`` n'avait aucune transition inverse — un abonnement suspendu
     l'était définitivement (le PATCH direct de ``statut`` étant proscrit
     depuis YSUBS4).

Couvre : l'échéance avance après ``facturer`` et l'abonnement reste
sélectionnable par le beat ; la double facturation reste refusée ;
suspendu → actif ok, actif → no-op, résilié → refusé ; isolation société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import selectors as compta_selectors
from apps.compta import services as compta_services
from apps.compta.models import AbonnementMonitoring
from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()


def make_company(slug='wir237-co', nom='WIR237 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='WIR237',
            telephone='+212600023701')
        self.abonnement = AbonnementMonitoring.objects.create(
            company=self.company, client_id=self.client_obj.id,
            periodicite='mensuel', montant=Decimal('199'),
            date_debut=date(2026, 1, 1),
            prochaine_echeance=date(2026, 2, 1))
        self.user = make_user(self.company, 'wir237-admin')
        self.api = auth(self.user)

    def _url(self, action):
        return (f'/api/django/compta/abonnements-monitoring/'
                f'{self.abonnement.id}/{action}/')


class FacturerAvanceEcheanceTests(_Base):
    def test_facturer_avance_la_prochaine_echeance(self):
        resp = self.api.post(self._url('facturer'))
        self.assertEqual(resp.status_code, 201, resp.data)
        self.abonnement.refresh_from_db()
        # Période facturée = l'ancienne échéance ; la nouvelle est une
        # période PLUS LOIN (mensuel → +1 mois).
        self.assertEqual(
            self.abonnement.derniere_facturation, date(2026, 2, 1))
        self.assertGreater(
            self.abonnement.prochaine_echeance, date(2026, 2, 1))

    def test_labonnement_reste_selectionnable_par_le_beat(self):
        """Le gel se voyait ici : échéance figée ⇒ toujours « dû » ⇒ le beat
        le reprenait chaque jour pour se heurter à l'idempotence."""
        self.api.post(self._url('facturer'))
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.statut, AbonnementMonitoring.Statut.ACTIF)
        # À la nouvelle échéance, l'abonnement est de nouveau dû — donc
        # toujours dans le périmètre du beat, sans blocage d'idempotence.
        dus = compta_selectors.abonnements_monitoring_dus_facturation(
            self.company, today=self.abonnement.prochaine_echeance)
        self.assertIn(self.abonnement.id, [a.id for a in dus])

    def test_double_facturation_refusee(self):
        self.assertEqual(self.api.post(self._url('facturer')).status_code, 201)
        # Deuxième appel immédiat : la période courante n'est pas encore due
        # et, si elle l'était, la garde d'idempotence tiendrait — dans les
        # deux cas AUCUNE seconde facture.
        deuxieme = self.api.post(self._url('facturer'))
        self.assertEqual(deuxieme.status_code, 400, deuxieme.data)
        self.assertIn('due', str(deuxieme.data['detail']))
        self.assertEqual(
            Facture.objects.filter(client=self.client_obj).count(), 1)


class ReactiverServiceTests(_Base):
    def test_suspendu_vers_actif(self):
        compta_services.suspendre_abonnement_monitoring(self.abonnement)
        compta_services.reactiver_abonnement_monitoring(self.abonnement)
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.statut, AbonnementMonitoring.Statut.ACTIF)

    def test_idempotent_sur_un_abonnement_deja_actif(self):
        echeance = self.abonnement.prochaine_echeance
        compta_services.reactiver_abonnement_monitoring(self.abonnement)
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.statut, AbonnementMonitoring.Statut.ACTIF)
        # Reprendre n'est pas facturer : l'échéance ne bouge pas.
        self.assertEqual(self.abonnement.prochaine_echeance, echeance)

    def test_resilie_refuse(self):
        compta_services.resilier_abonnement_monitoring(
            self.abonnement, motif='Fin de contrat')
        with self.assertRaises(compta_services.AbonnementMonitoringError):
            compta_services.reactiver_abonnement_monitoring(self.abonnement)
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.statut, AbonnementMonitoring.Statut.RESILIE)

    def test_reprise_redonne_le_droit_de_facturer(self):
        compta_services.suspendre_abonnement_monitoring(self.abonnement)
        with self.assertRaises(compta_services.AbonnementMonitoringError):
            compta_services.facturer_abonnement_monitoring(self.abonnement)
        compta_services.reactiver_abonnement_monitoring(self.abonnement)
        facture = compta_services.facturer_abonnement_monitoring(
            self.abonnement)
        self.assertEqual(facture.montant_ttc, Decimal('199.00'))


class ReactiverEndpointTests(_Base):
    def test_endpoint_suspendu_vers_actif_200(self):
        self.assertEqual(
            self.api.post(self._url('suspendre')).status_code, 200)
        resp = self.api.post(self._url('reactiver'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'],
                         AbonnementMonitoring.Statut.ACTIF)

    def test_endpoint_resilie_400_message_fr(self):
        self.api.post(self._url('resilier'), {'motif': 'Fin'}, format='json')
        resp = self.api.post(self._url('reactiver'))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('résilié', str(resp.data['detail']))

    def test_isolation_societe(self):
        autre = make_company('wir237-autre', 'Autre WIR237')
        api_autre = auth(make_user(autre, 'wir237-autre-admin'))
        resp = api_autre.post(self._url('reactiver'))
        self.assertEqual(resp.status_code, 404)

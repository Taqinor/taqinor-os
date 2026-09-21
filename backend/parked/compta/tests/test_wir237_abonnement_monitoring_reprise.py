"""Tests WIR237 — AbonnementMonitoring : la facturation manuelle ne GÈLE plus
l'abonnement, et la suspension n'est plus sans retour.

Deux défauts corrigés :
  * l'action HTTP ``facturer`` appelait ``facturer_abonnement_monitoring``
    SEUL, qui n'avance pas ``prochaine_echeance`` : facturer depuis l'écran
    figeait l'abonnement sur la période déjà facturée, que le beat quotidien
    re-sélectionnait indéfiniment pour se heurter à la garde d'idempotence.
    Elle passe désormais par la variante BEAT (facture PUIS renouvelle) ;
  * aucun chemin ne ramenait un abonnement SUSPENDU à l'état ACTIF —
    ``reactiver`` (SUSPENDU → ACTIF seul, idempotent, RÉSILIÉ refusé).
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
        # Échéance ÉCHUE : l'abonnement est donc dû aujourd'hui pour le beat.
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


class TestFacturerAvanceLEcheance(_Base):
    def test_facturer_avance_prochaine_echeance(self):
        avant = self.abonnement.prochaine_echeance
        resp = self.api.post(self._url('facturer'))
        self.assertEqual(resp.status_code, 201, resp.data)
        self.abonnement.refresh_from_db()
        self.assertGreater(self.abonnement.prochaine_echeance, avant)
        # L'échéance avancée est RENVOYÉE (l'écran ne la devine pas).
        self.assertEqual(
            resp.data['prochaine_echeance'],
            self.abonnement.prochaine_echeance)

    def test_abonnement_reste_selectionne_par_le_beat(self):
        """Le beat ne doit plus re-sélectionner l'abonnement pour la période
        qu'on vient de facturer, mais bien le reprendre à la SUIVANTE."""
        dus = compta_selectors.abonnements_monitoring_dus_facturation(
            self.company, today=date(2026, 2, 1))
        self.assertIn(self.abonnement.id, [a.id for a in dus])

        self.api.post(self._url('facturer'))
        self.abonnement.refresh_from_db()
        echeance = self.abonnement.prochaine_echeance

        # Le jour même : plus dû (période déjà facturée + échéance avancée).
        dus = compta_selectors.abonnements_monitoring_dus_facturation(
            self.company, today=date(2026, 2, 1))
        self.assertNotIn(self.abonnement.id, [a.id for a in dus])

        # À la nouvelle échéance : de nouveau sélectionné — l'abonnement n'est
        # PAS gelé (c'est exactement ce que la facturation manuelle cassait).
        dus = compta_selectors.abonnements_monitoring_dus_facturation(
            self.company, today=echeance)
        self.assertIn(self.abonnement.id, [a.id for a in dus])

    def test_double_facturation_refusee(self):
        self.assertEqual(self.api.post(self._url('facturer')).status_code, 201)
        resp = self.api.post(self._url('facturer'))
        # La 2e facturation vise la période SUIVANTE, non encore due : elle est
        # refusée par la garde de service, et aucune 2e facture n'est émise.
        # (Sans cette 2e garde, l'enchaînement du renouvellement aurait rendu la
        # garde d'idempotence par période inopérante — le 2e clic facturerait
        # d'avance la période suivante.)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(
            Facture.objects.filter(client=self.client_obj).count(), 1)

    def test_periode_non_due_refusee_au_service(self):
        self.abonnement.prochaine_echeance = date(2099, 1, 1)
        self.abonnement.save(update_fields=['prochaine_echeance'])
        with self.assertRaises(compta_services.AbonnementMonitoringError):
            compta_services.facturer_abonnement_monitoring(self.abonnement)
        self.assertEqual(
            Facture.objects.filter(client=self.client_obj).count(), 0)


class TestReactiver(_Base):
    def test_suspendu_vers_actif(self):
        compta_services.suspendre_abonnement_monitoring(self.abonnement)
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.statut, AbonnementMonitoring.Statut.SUSPENDU)

        resp = self.api.post(self._url('reactiver'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.statut, AbonnementMonitoring.Statut.ACTIF)
        # …et la facturation redevient possible.
        self.assertEqual(self.api.post(self._url('facturer')).status_code, 201)

    def test_reactiver_est_idempotent_sur_un_actif(self):
        echeance = self.abonnement.prochaine_echeance
        resp = self.api.post(self._url('reactiver'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.statut, AbonnementMonitoring.Statut.ACTIF)
        # Reprendre n'est PAS facturer : l'échéance ne bouge pas.
        self.assertEqual(self.abonnement.prochaine_echeance, echeance)

    def test_resilie_refuse(self):
        compta_services.resilier_abonnement_monitoring(
            self.abonnement, motif='Client parti')
        resp = self.api.post(self._url('reactiver'))
        self.assertEqual(resp.status_code, 400, resp.data)
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.statut, AbonnementMonitoring.Statut.RESILIE)

    def test_service_resilie_leve(self):
        compta_services.resilier_abonnement_monitoring(
            self.abonnement, motif='Client parti')
        with self.assertRaises(compta_services.AbonnementMonitoringError):
            compta_services.reactiver_abonnement_monitoring(self.abonnement)

    def test_isolation_societe(self):
        compta_services.suspendre_abonnement_monitoring(self.abonnement)
        autre = make_company('wir237-autre', 'Autre Co')
        api_autre = auth(make_user(autre, 'wir237-autre-admin'))
        resp = api_autre.post(self._url('reactiver'))
        self.assertEqual(resp.status_code, 404)
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.statut, AbonnementMonitoring.Statut.SUSPENDU)

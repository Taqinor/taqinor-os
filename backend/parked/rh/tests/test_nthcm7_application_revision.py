"""Tests NTHCM7 — application d'un cycle clos → nouvelle ``Remuneration``.

Couvre :
* appliquer un cycle CLOS crée UNE ``Remuneration`` par proposition
  approuvée, datée de la ``date_effet`` du cycle ;
* ré-appliquer ne duplique RIEN (idempotence via ``appliquee``) ;
* les propositions rejetées/proposées ne créent rien ;
* un cycle non clos est refusé 400 ;
* la notification à l'employé ne contient AUCUN montant (patron XRH26) ;
* la trace chatter n'expose AUCUN montant (le chatter est gaté ``rh_voir``,
  les salaires ``salaires_voir``).
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    CycleRevisionSalariale,
    DossierActivity,
    DossierEmploye,
    PropositionRevision,
    Remuneration,
)
from apps.roles.models import Role

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, permissions=('salaires_voir',)):
    role = Role.objects.create(
        company=company, nom=f'role-{username}', permissions=list(permissions))
    return User.objects.create_user(
        username=username, password='x', company=company, role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AppliquerCycleTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm7-a', 'A')
        self.rh = make_user(self.co, 'nthcm7-rh')
        self.api = auth(self.rh)
        self.user_employe = make_user(
            self.co, 'nthcm7-employe', permissions=['rh_voir'])
        self.employe = DossierEmploye.objects.create(
            company=self.co, matricule='E-1', nom='Alpha', prenom='Un',
            user=self.user_employe)
        self.autre = DossierEmploye.objects.create(
            company=self.co, matricule='E-2', nom='Beta', prenom='Deux')
        Remuneration.objects.create(
            company=self.co, employe=self.employe, montant=Decimal('10000'),
            date_effet=date(2026, 1, 1))
        self.cycle = CycleRevisionSalariale.objects.create(
            company=self.co, libelle='Révision 2027', periode='2027',
            statut=CycleRevisionSalariale.Statut.CLOS,
            date_effet=date(2027, 1, 1))
        self.approuvee = PropositionRevision.objects.create(
            company=self.co, cycle=self.cycle, employe=self.employe,
            salaire_actuel=Decimal('10000'),
            augmentation_pct_proposee=Decimal('5'),
            augmentation_montant_proposee=Decimal('500'),
            statut=PropositionRevision.Statut.APPROUVEE)
        self.rejetee = PropositionRevision.objects.create(
            company=self.co, cycle=self.cycle, employe=self.autre,
            salaire_actuel=Decimal('8000'),
            augmentation_pct_proposee=Decimal('2'),
            augmentation_montant_proposee=Decimal('160'),
            statut=PropositionRevision.Statut.REJETEE)

    def _appliquer(self):
        return self.api.post(
            f'/api/django/rh/cycles-revision/{self.cycle.id}/appliquer/',
            {}, format='json')

    def test_application_cree_une_remuneration_par_proposition_approuvee(self):
        resp = self._appliquer()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['appliquees'], 1)
        nouvelles = Remuneration.objects.filter(
            employe=self.employe, date_effet=date(2027, 1, 1))
        self.assertEqual(nouvelles.count(), 1)
        self.assertEqual(nouvelles.first().montant, Decimal('10500.00'))
        self.approuvee.refresh_from_db()
        self.assertTrue(self.approuvee.appliquee)
        self.assertIsNotNone(self.approuvee.date_application)

    def test_reappliquer_ne_duplique_rien(self):
        self.assertEqual(self._appliquer().data['appliquees'], 1)
        resp2 = self._appliquer()
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(resp2.data['appliquees'], 0)
        self.assertEqual(
            Remuneration.objects.filter(employe=self.employe).count(), 2)

    def test_proposition_rejetee_ne_cree_rien(self):
        self._appliquer()
        self.assertEqual(
            Remuneration.objects.filter(employe=self.autre).count(), 0)
        self.rejetee.refresh_from_db()
        self.assertFalse(self.rejetee.appliquee)

    def test_cycle_non_clos_refuse_400(self):
        self.cycle.statut = CycleRevisionSalariale.Statut.OUVERT
        self.cycle.save(update_fields=['statut'])
        resp = self._appliquer()
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(
            Remuneration.objects.filter(employe=self.employe).count(), 1)

    def test_trace_chatter_sans_montant(self):
        self._appliquer()
        logs = DossierActivity.objects.filter(
            employe=self.employe, field='remuneration')
        self.assertEqual(logs.count(), 1)
        trace = f'{logs.first().old_value} {logs.first().new_value}'
        # Le chatter est gaté ``rh_voir`` : aucun montant ne doit y figurer.
        self.assertNotIn('10000', trace)
        self.assertNotIn('10500', trace)
        # Seul le POURCENTAGE est tracé, jamais le salaire.
        self.assertIn('%', trace)
        self.assertIn('Révision 2027', trace)

    def test_notification_sans_montant(self):
        with patch('apps.notifications.services.notify') as faux_notify:
            self._appliquer()
        self.assertTrue(faux_notify.called)
        _, kwargs = faux_notify.call_args
        corps = f"{kwargs.get('title', '')} {kwargs.get('body', '')}"
        self.assertNotIn('10500', corps)
        self.assertNotIn('500', corps)

    def test_employe_sans_compte_utilisateur_ne_bloque_pas(self):
        sans_compte = DossierEmploye.objects.create(
            company=self.co, matricule='E-3', nom='Gamma', prenom='Trois')
        PropositionRevision.objects.create(
            company=self.co, cycle=self.cycle, employe=sans_compte,
            salaire_actuel=Decimal('7000'),
            augmentation_pct_proposee=Decimal('1'),
            augmentation_montant_proposee=Decimal('70'),
            statut=PropositionRevision.Statut.APPROUVEE)
        resp = self._appliquer()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['appliquees'], 2)

    def test_service_refuse_cycle_non_clos(self):
        self.cycle.statut = CycleRevisionSalariale.Statut.CALIBRATION
        self.cycle.save(update_fields=['statut'])
        with self.assertRaises(services.CycleNonClosError):
            services.appliquer_cycle_revision(self.cycle, self.rh)

    def test_date_effet_absente_retombe_sur_date_fin(self):
        self.cycle.date_effet = None
        self.cycle.date_fin = date(2027, 3, 31)
        self.cycle.save(update_fields=['date_effet', 'date_fin'])
        self._appliquer()
        self.assertTrue(
            Remuneration.objects.filter(
                employe=self.employe, date_effet=date(2027, 3, 31)).exists())

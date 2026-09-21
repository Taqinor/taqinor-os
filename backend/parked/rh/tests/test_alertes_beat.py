"""Tests YHIRE8 — Alertes RH inscrites au planificateur (tasks Celery).

Couvre :
* ``rh.alertes_expiration`` notifie UNE fois une habilitation expirant sous
  30 j (idempotence : un second appel le même jour ne re-notifie pas).
* ``rh.alertes_cdd`` notifie UNE fois un CDD à échéance sous 30 j (idempotence
  identique) ; un CDI n'est jamais notifié.
* Isolation multi-société : une société sans anomalie ne notifie personne.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.notifications.models import Notification
from apps.rh.models import DossierEmploye, Habilitation
from apps.rh.tasks import alertes_cdd, alertes_expiration

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_admin(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy='admin')


def make_dossier(company, matricule, **kwargs):
    defaults = dict(
        nom='Test', prenom='Employé', statut=DossierEmploye.Statut.ACTIF,
    )
    defaults.update(kwargs)
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, **defaults)


class AlertesExpirationBeatTests(TestCase):
    def setUp(self):
        self.company = make_company('rh-yhire8', 'YHIRE8 SARL')
        self.admin = make_admin(self.company, 'admin_yhire8')
        self.dossier = make_dossier(self.company, 'M-YH8-1')

    def test_habilitation_expirant_notifie_une_fois(self):
        Habilitation.objects.create(
            company=self.company, employe=self.dossier,
            type_habilitation='b1v', actif=True,
            date_validite=timezone.localdate() + timedelta(days=10),
        )
        result = alertes_expiration()
        self.assertEqual(result['echeances'], 1)
        self.assertEqual(result['notifications'], 1)
        self.assertEqual(
            Notification.objects.filter(recipient=self.admin).count(), 1)

        # Deuxième exécution le même jour : aucune notification supplémentaire.
        alertes_expiration()
        self.assertEqual(
            Notification.objects.filter(recipient=self.admin).count(), 1)

    def test_aucune_echeance_aucune_notification(self):
        result = alertes_expiration()
        self.assertEqual(result['echeances'], 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_societe_isolee(self):
        autre_company = make_company('rh-yhire8-b', 'Autre SARL')
        autre_admin = make_admin(autre_company, 'admin_yhire8_b')
        Habilitation.objects.create(
            company=self.company, employe=self.dossier,
            type_habilitation='b1v', actif=True,
            date_validite=timezone.localdate() + timedelta(days=5),
        )
        alertes_expiration()
        self.assertEqual(
            Notification.objects.filter(recipient=autre_admin).count(), 0)


class AlertesCddBeatTests(TestCase):
    def setUp(self):
        self.company = make_company('rh-yhire8-cdd', 'YHIRE8 CDD SARL')
        self.admin = make_admin(self.company, 'admin_yhire8_cdd')

    def test_cdd_a_echeance_notifie_une_fois(self):
        make_dossier(
            self.company, 'M-CDD-1',
            type_contrat=DossierEmploye.TypeContrat.CDD,
            contrat_date_fin=timezone.localdate() + timedelta(days=20),
        )
        result = alertes_cdd()
        self.assertEqual(result['contrats'], 1)
        self.assertEqual(result['notifications'], 1)
        self.assertEqual(
            Notification.objects.filter(recipient=self.admin).count(), 1)

        # Ré-exécution le même jour : silence (déjà notifié).
        alertes_cdd()
        self.assertEqual(
            Notification.objects.filter(recipient=self.admin).count(), 1)

    def test_cdi_jamais_notifie(self):
        make_dossier(
            self.company, 'M-CDI-1',
            type_contrat=DossierEmploye.TypeContrat.CDI,
        )
        result = alertes_cdd()
        self.assertEqual(result['contrats'], 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_cdd_hors_fenetre_ignore(self):
        make_dossier(
            self.company, 'M-CDD-2',
            type_contrat=DossierEmploye.TypeContrat.CDD,
            contrat_date_fin=timezone.localdate() + timedelta(days=90),
        )
        result = alertes_cdd()
        self.assertEqual(result['contrats'], 0)

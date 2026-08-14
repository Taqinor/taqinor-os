"""NTMFG32 — Tâche planifiée : rappel d'entretien de poste de charge à
échéance proche.

Critère : la notification part exactement une fois à J-7, jamais en double,
jamais pour une échéance déjà traitée."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.mrp.models import EcheanceEntretienPoste, PlanEntretienPoste, PosteDeCharge
from apps.mrp.services import echeances_a_relancer_j7, notifier_echeances_j7
from apps.mrp.tasks import rappeler_entretiens_poste_j7_task
from apps.notifications.models import Notification

from ._fixtures import make_company, make_user


class EcheancesARelancerJ7Tests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ntmfg32-1', 'MRP NTMFG32 1')
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-J7', nom='Compresseur')
        self.plan = PlanEntretienPoste.objects.create(
            poste_charge=self.poste, description='Vidange', intervalle_jours=90)

    def test_echeance_a_j7_exact_est_candidate(self):
        today = timezone.localdate()
        echeance = EcheanceEntretienPoste.objects.create(
            plan=self.plan, date_prevue=today + timedelta(days=7))
        candidates = list(echeances_a_relancer_j7(self.company, today=today))
        self.assertEqual([e.pk for e in candidates], [echeance.pk])

    def test_echeance_trop_lointaine_exclue(self):
        today = timezone.localdate()
        EcheanceEntretienPoste.objects.create(
            plan=self.plan, date_prevue=today + timedelta(days=8))
        candidates = list(echeances_a_relancer_j7(self.company, today=today))
        self.assertEqual(candidates, [])

    def test_echeance_deja_en_retard_exclue(self):
        today = timezone.localdate()
        EcheanceEntretienPoste.objects.create(
            plan=self.plan, date_prevue=today - timedelta(days=1))
        candidates = list(echeances_a_relancer_j7(self.company, today=today))
        self.assertEqual(candidates, [])

    def test_echeance_deja_notifiee_exclue(self):
        today = timezone.localdate()
        EcheanceEntretienPoste.objects.create(
            plan=self.plan, date_prevue=today + timedelta(days=3), notifie=True)
        candidates = list(echeances_a_relancer_j7(self.company, today=today))
        self.assertEqual(candidates, [])

    def test_echeance_planifiee_ou_faite_exclue(self):
        today = timezone.localdate()
        EcheanceEntretienPoste.objects.create(
            plan=self.plan, date_prevue=today + timedelta(days=3),
            statut=EcheanceEntretienPoste.Statut.PLANIFIE)
        EcheanceEntretienPoste.objects.create(
            plan=self.plan, date_prevue=today + timedelta(days=3),
            statut=EcheanceEntretienPoste.Statut.FAIT)
        candidates = list(echeances_a_relancer_j7(self.company, today=today))
        self.assertEqual(candidates, [])


class NotifierEcheancesJ7Tests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ntmfg32-notif-1', 'MRP NTMFG32 NOTIF 1')
        self.responsable = make_user(
            self.company, 'mrp-ntmfg32-resp', role='responsable')
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-J7N', nom='Sertisseuse')
        self.plan = PlanEntretienPoste.objects.create(
            poste_charge=self.poste, description='Étalonnage', intervalle_jours=60)

    def test_notifie_exactement_une_fois(self):
        today = timezone.localdate()
        echeance = EcheanceEntretienPoste.objects.create(
            plan=self.plan, date_prevue=today + timedelta(days=7))

        notifiees = notifier_echeances_j7(self.company, today=today)
        self.assertEqual([e.pk for e in notifiees], [echeance.pk])
        echeance.refresh_from_db()
        self.assertTrue(echeance.notifie)
        self.assertEqual(
            Notification.objects.filter(
                company=self.company, recipient=self.responsable).count(), 1)

        # Ré-exécution le lendemain : jamais de doublon (déjà notifiée).
        notifiees_encore = notifier_echeances_j7(self.company, today=today + timedelta(days=1))
        self.assertEqual(notifiees_encore, [])
        self.assertEqual(
            Notification.objects.filter(
                company=self.company, recipient=self.responsable).count(), 1)

    def test_task_isolation_cross_tenant(self):
        autre_company = make_company('mrp-ntmfg32-notif-2', 'MRP NTMFG32 NOTIF 2')
        make_user(autre_company, 'mrp-ntmfg32-resp2', role='responsable')
        today = timezone.localdate()
        EcheanceEntretienPoste.objects.create(
            plan=self.plan, date_prevue=today + timedelta(days=2))

        result = rappeler_entretiens_poste_j7_task()

        self.assertEqual(result[self.company.id], 1)
        self.assertEqual(result[autre_company.id], 0)

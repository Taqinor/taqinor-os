"""VX99 — étend YEVNT8 à ``installations.DemandeAchat`` (soumission →
managers ; décision → ``created_by``), source restante de l'agrégateur
cross-app ``reporting/approbations.py`` qui passe par un ``save()`` ordinaire
(SOLMVP19 : la source ``ged.DemandeApprobation`` est sortie avec l'app ged).

``contrats.EtapeApprobation`` (3e source) reste [BLOCKED] : elle est créée via
``bulk_create()`` (``lancer_workflow_approbation``), qui n'émet jamais de
signal ``post_save`` — voir la docstring de tête de ``signals.py``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from .models import EventType, Notification

User = get_user_model()


def _make_company(name='Vx99Co'):
    return Company.objects.create(nom=name)


def _make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy=role_legacy)


class DemandeAchatNotifyTests(TestCase):

    def setUp(self):
        self.company = _make_company('Vx99InstallCo')
        self.approver = _make_user(self.company, 'vx99-approver', role_legacy='admin')
        self.requester = _make_user(self.company, 'vx99-requester')

    def _make_da(self, reference='DA-VX99-1'):
        from apps.installations.models import DemandeAchat
        return DemandeAchat.objects.create(
            company=self.company, reference=reference, objet='Onduleurs',
            created_by=self.requester)

    def test_submission_notifies_managers(self):
        from apps.installations.models import DemandeAchat
        da = self._make_da()
        Notification.objects.all().delete()

        da.statut = DemandeAchat.Statut.SOUMISE
        da.save()

        notifs = Notification.objects.filter(
            recipient=self.approver, event_type=EventType.APPROVAL_REQUESTED)
        self.assertEqual(notifs.count(), 1)

    def test_approval_decision_notifies_requester(self):
        from apps.installations.models import DemandeAchat
        da = self._make_da('DA-VX99-2')
        da.statut = DemandeAchat.Statut.SOUMISE
        da.save()
        Notification.objects.all().delete()

        da.statut = DemandeAchat.Statut.APPROUVEE
        da.approuvee_par = self.approver
        da.save()

        notifs = Notification.objects.filter(
            recipient=self.requester, event_type=EventType.APPROVAL_DECIDED)
        self.assertEqual(notifs.count(), 1)
        self.assertIn('approuvée', notifs.first().body)

    def test_refusal_notifies_requester_with_motif(self):
        from apps.installations.models import DemandeAchat
        da = self._make_da('DA-VX99-3')
        da.statut = DemandeAchat.Statut.SOUMISE
        da.save()
        Notification.objects.all().delete()

        da.statut = DemandeAchat.Statut.REFUSEE
        da.motif_refus = 'Budget dépassé.'
        da.save()

        notifs = Notification.objects.filter(
            recipient=self.requester, event_type=EventType.APPROVAL_DECIDED)
        self.assertEqual(notifs.count(), 1)
        self.assertIn('refusée', notifs.first().body)
        self.assertIn('Budget dépassé', notifs.first().body)

    def test_resave_same_statut_does_not_reemit(self):
        from apps.installations.models import DemandeAchat
        da = self._make_da('DA-VX99-4')
        da.statut = DemandeAchat.Statut.SOUMISE
        da.save()
        Notification.objects.all().delete()

        da.save()  # re-save, toujours SOUMISE
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.APPROVAL_REQUESTED).count(), 0)

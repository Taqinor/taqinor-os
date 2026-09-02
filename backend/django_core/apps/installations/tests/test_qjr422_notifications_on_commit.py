"""QJR422 / QJR4-05 — les entrées-sorties des RÉCEPTEURS passent APRÈS le
commit : plus d'e-mail SMTP ni de push synchrone sous les verrous.

CE QUI ÉTAIT FAUX. ``devis_accepted`` est émis DANS la transaction
d'acceptation (``ventes/domain/cycle_vie.py``), qui tient les
``select_for_update`` du groupe de variantes. De là :
``installations/receivers.py`` → ``services.create_installation_from_devis``
→ ``_notifier_chantier_assigne`` → ``notify(...)``, un envoi SMTP et web-push
SYNCHRONE exécuté pendant que les verrous sont tenus. Un serveur de messagerie
lent tenait donc la transaction — et les verrous — ouverts pendant tout le
délai réseau. Le jumeau, plus directement vérifiable, est
``_notifier_reassignation``, appelé à l'intérieur du ``with
transaction.atomic()`` + ``select_for_update()`` de ``replanifier_en_masse``.

LA RÈGLE. Les deux envois partent par ``transaction.on_commit`` : rien n'est
émis pendant la transaction, tout part une fois validée, et RIEN ne part si
elle échoue (on ne notifie pas un chantier qui n'existe pas). Le contenu et le
nombre des notifications nominales sont inchangés.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.installations.tests.test_qjr422_notifications_on_commit -v 2
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import Intervention
from apps.installations.services import (
    _notifier_reassignation, create_installation_from_devis)
from apps.notifications.models import EventType, Notification
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()


class _Base(TestCase):
    slug = 'qjr422'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.tech = User.objects.create_user(
            username='%s-tech' % self.slug, password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR422',
            email='%s@example.invalid' % self.slug)
        self._n = 0

    def _devis(self):
        self._n += 1
        return Devis.objects.create(
            company=self.company,
            reference='DEV-QJR422-%s-%04d' % (self.company.pk, self._n),
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), mode_installation='residentiel')

    def _notifs(self, event_type):
        return Notification.objects.filter(event_type=event_type)


class RienNePartPendantLaTransaction(_Base):
    """LE TEST ROUGE — aujourd'hui l'envoi part SOUS les verrous."""

    slug = 'qjr422-pendant'

    def test_aucune_notification_pendant_la_creation_du_chantier(self):
        devis = self._devis()
        with self.captureOnCommitCallbacks(execute=False) as rappels:
            create_installation_from_devis(devis, self.tech, self.company)
            self.assertEqual(
                self._notifs(EventType.CHANTIER_ASSIGNE).count(), 0,
                "la notification est partie PENDANT la transaction : c'est "
                "l'envoi SMTP/web-push synchrone tenu sous les verrous "
                "select_for_update de l'acceptation.")
        self.assertTrue(
            rappels,
            "aucun rappel de commit n'a été enregistré : l'envoi ne passe pas "
            'par transaction.on_commit.')

    def test_la_notification_part_apres_le_commit(self):
        """Second volet du même constat : elle part bien, juste APRÈS."""
        devis = self._devis()
        with self.captureOnCommitCallbacks(execute=True):
            inst, created = create_installation_from_devis(
                devis, self.tech, self.company)
        self.assertTrue(created)
        notifs = self._notifs(EventType.CHANTIER_ASSIGNE)
        self.assertEqual(notifs.count(), 1)
        self.assertIn(inst.reference, notifs.first().title)
        self.assertEqual(notifs.first().company_id, self.company.pk)


class UneTransactionEnEchecNEmetRien(_Base):
    """Second test du `Done =` — aujourd'hui elle peut notifier avant de tout
    perdre."""

    slug = 'qjr422-rollback'

    def test_un_rollback_n_envoie_aucune_notification(self):
        devis = self._devis()
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    create_installation_from_devis(
                        devis, self.tech, self.company)
                    raise RuntimeError('la transaction échoue (simulé)')

        self.assertEqual(
            self._notifs(EventType.CHANTIER_ASSIGNE).count(), 0,
            "un chantier qui n'existe pas ne doit être annoncé à personne : "
            "l'envoi doit être annulé avec la transaction.")


class LeJumeauReassignation(_Base):
    """`_notifier_reassignation` — appelé DANS l'atomic + select_for_update de
    ``replanifier_en_masse``."""

    slug = 'qjr422-reassign'

    def _intervention(self):
        devis = self._devis()
        with self.captureOnCommitCallbacks(execute=True):
            inst, _ = create_installation_from_devis(
                devis, self.tech, self.company)
        Notification.objects.all().delete()
        return Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='controle', created_by=self.tech,
            technicien=self.tech,
            date_prevue=date.today() + timedelta(days=3))

    def test_rien_pendant_la_transaction_tout_apres_le_commit(self):
        interv = self._intervention()
        with self.captureOnCommitCallbacks(execute=False) as rappels:
            _notifier_reassignation(interv, self.tech)
            self.assertEqual(
                self._notifs(EventType.CHANTIER_DUE).count(), 0,
                'la notification de réassignation est partie sous le verrou '
                "select_for_update de la replanification en masse.")
        self.assertTrue(rappels)
        for rappel in rappels:
            rappel()
        notifs = self._notifs(EventType.CHANTIER_DUE)
        self.assertEqual(notifs.count(), 1)
        self.assertIn(str(interv.id), notifs.first().title)

    def test_un_rollback_n_envoie_aucune_reassignation(self):
        interv = self._intervention()
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    _notifier_reassignation(interv, self.tech)
                    raise RuntimeError('la replanification échoue (simulé)')
        self.assertEqual(self._notifs(EventType.CHANTIER_DUE).count(), 0)

    def test_sans_technicien_aucun_rappel_n_est_enregistre(self):
        """Le no-op reste un no-op : aucune notification, aucun rappel."""
        interv = self._intervention()
        interv.technicien = None
        interv.save(update_fields=['technicien'])
        with self.captureOnCommitCallbacks(execute=True) as rappels:
            _notifier_reassignation(interv, self.tech)
        self.assertEqual(rappels, [])
        self.assertEqual(self._notifs(EventType.CHANTIER_DUE).count(), 0)

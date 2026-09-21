"""Tests ARC39 — Couverture notifications paie : run de paie prêt + RIB
divergent enregistré comme ``EventType`` (persistance in-app réelle).

Couvre :
* ``changer_statut(periode, STATUT_VALIDEE)`` déclenche
  ``notifier_run_pret`` (best-effort, jamais bloquant pour la transition) ;
* re-passer par un statut déjà ``validee`` (no-op de transition) NE
  renotifie PAS ;
* ``notifier_run_pret`` route via ``apps.notifications.services`` (repli
  Responsable/Admin) — event ``'paie_run_pret'`` ;
* ``'paie_run_pret'`` et ``'paie_rib_divergence'`` sont des ``EventType``
  ENREGISTRÉS : ``notify()``/``notify_many()`` persiste réellement la ligne
  ``Notification`` in-app (avant ARC39, un type non enregistré ne
  journalisait qu'un avertissement et renvoyait ``None``).
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.notifications.models import EventType, Notification
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    changer_statut,
    controler_coherence_rib,
    ensure_defaults,
    notifier_run_pret,
)
from apps.rh.models import DossierEmploye

User = get_user_model()


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class EventTypesRegistrationTests(TestCase):
    """ARC39 — les deux événements paie sont désormais des choix fermés."""

    def test_paie_run_pret_enregistre(self):
        self.assertIn('paie_run_pret', EventType.values)

    def test_paie_rib_divergence_enregistre(self):
        self.assertIn('paie_rib_divergence', EventType.values)


class ChangerStatutNotifieRunPretTests(TestCase):
    def setUp(self):
        self.co = make_company('arc39-run-pret')
        ensure_defaults(self.co)
        self.admin = User.objects.create_user(
            username='arc39-admin', password='x', role_legacy='admin',
            company=self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6,
            statut=PeriodePaie.STATUT_CALCULEE)

    def test_transition_vers_validee_appelle_notifier_run_pret(self):
        with mock.patch(
                'apps.paie.services.notifier_run_pret') as mock_notif:
            changer_statut(self.periode, PeriodePaie.STATUT_VALIDEE)
        mock_notif.assert_called_once_with(self.periode)

    def test_transition_vers_calculee_ne_notifie_pas(self):
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7,
            statut=PeriodePaie.STATUT_BROUILLON)
        with mock.patch(
                'apps.paie.services.notifier_run_pret') as mock_notif:
            changer_statut(periode, PeriodePaie.STATUT_CALCULEE)
        mock_notif.assert_not_called()

    def test_no_op_meme_statut_ne_renotifie_pas(self):
        changer_statut(self.periode, PeriodePaie.STATUT_VALIDEE)
        with mock.patch(
                'apps.paie.services.notifier_run_pret') as mock_notif:
            # Déjà 'validee' : ré-appeler avec la même cible est un no-op.
            changer_statut(self.periode, PeriodePaie.STATUT_VALIDEE)
        mock_notif.assert_not_called()

    def test_echec_notification_non_bloquant_pour_la_transition(self):
        with mock.patch(
                'apps.paie.services.notifier_run_pret',
                side_effect=RuntimeError('boom')):
            periode = changer_statut(self.periode, PeriodePaie.STATUT_VALIDEE)
        self.assertEqual(periode.statut, PeriodePaie.STATUT_VALIDEE)

    def test_notifier_run_pret_route_via_notify_many(self):
        with mock.patch(
                'apps.notifications.services.notify_many') as notify_many:
            notifier_run_pret(self.periode)
        notify_many.assert_called_once()
        args, kwargs = notify_many.call_args
        self.assertEqual(args[1], 'paie_run_pret')
        self.assertEqual(kwargs.get('company'), self.co)

    def test_notification_reelle_persiste_ligne_in_app(self):
        # Bout en bout, aucun mock : la ligne Notification doit exister
        # réellement (preuve que l'EventType est bien enregistré).
        changer_statut(self.periode, PeriodePaie.STATUT_VALIDEE)
        qs = Notification.objects.filter(
            company=self.co, recipient=self.admin,
            event_type='paie_run_pret')
        self.assertEqual(qs.count(), 1)


class RibDivergenceNotificationPersistedTests(TestCase):
    """ARC39 — la ligne in-app RIB divergente (ARC25) est réellement créée."""

    def setUp(self):
        self.co = make_company('arc39-rib')
        ensure_defaults(self.co)
        self.admin = User.objects.create_user(
            username='arc39-rib-admin', password='x', role_legacy='admin',
            company=self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil_divergent(self, mat):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P',
            rib='RIB' + '2' * 20)
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), rib='RIB' + '1' * 20,
            mode_paiement=ProfilPaie.MODE_PAIEMENT_VIREMENT,
            affilie_cnss=True, affilie_amo=True)

    def test_divergence_cree_reellement_une_notification_in_app(self):
        self._profil_divergent('RIBP1')
        controler_coherence_rib(self.periode)
        qs = Notification.objects.filter(
            company=self.co, recipient=self.admin,
            event_type='paie_rib_divergence')
        self.assertEqual(qs.count(), 1)

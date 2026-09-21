"""Tests NTPAY25 — Rappel automatique des échéances déclaratives à venir.

Couvre : les fenêtres J-7 / J-3 / J-0 (et rien en dehors), l'IDEMPOTENCE par
jour-seuil (re-run = zéro doublon) sans jamais recouvrir un autre seuil, le
silence total sur une échéance déjà déposée, le ciblage des titulaires de
``paie_gerer``, et l'isolation société.

``today`` est injecté partout : aucun test ne dépend de l'heure réelle.
"""
from datetime import date, timedelta

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company, CustomUser as User
from apps.notifications.models import Notification
from apps.paie.models import EcheanceDeclarative, PeriodePaie
from apps.paie.tasks import (
    CHAMP_RAPPEL_ECHEANCE,
    EVENEMENT_RAPPEL_ECHEANCE,
    SEUILS_RAPPEL_ECHEANCE,
    _destinataires_paie,
    rappeler_echeances_declaratives_company,
)
from apps.records.models import Activity
from apps.roles.models import Role


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class RappelEcheancesTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay25')
        self.today = date(2026, 7, 15)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        role = Role.objects.create(
            company=self.co, nom='Gestionnaire paie',
            permissions=['paie_voir', 'paie_gerer'])
        self.gestionnaire = User.objects.create_user(
            username='ntpay25-gest', password='x', company=self.co,
            role=role)

    def _echeance(self, jours, statut=EcheanceDeclarative.STATUT_GENEREE,
                  type_echeance=EcheanceDeclarative.TYPE_BDS):
        """Une échéance SUR SA PROPRE période.

        ``EcheanceDeclarative`` est unique par ``(periode, type_echeance)`` :
        chaque appel se donne donc son mois, pour qu'un test puisse en créer
        autant qu'il veut sans collision.
        """
        self._compteur = getattr(self, '_compteur', 0) + 1
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2020 + self._compteur // 12,
            mois=(self._compteur % 12) + 1)
        return EcheanceDeclarative.objects.create(
            company=self.co, periode=periode,
            type_echeance=type_echeance,
            date_limite=self.today + timedelta(days=jours), statut=statut)

    def _lancer(self, today=None):
        return rappeler_echeances_declaratives_company(
            self.co, today=today or self.today)

    def _marqueurs(self, echeance):
        ct = ContentType.objects.get_for_model(EcheanceDeclarative)
        return sorted(
            Activity.objects
            .filter(content_type=ct, object_id=echeance.pk)
            .values_list('field', flat=True))

    # ── Fenêtres ───────────────────────────────────────────────────────────

    def test_les_trois_fenetres_notifient(self):
        self.assertEqual(SEUILS_RAPPEL_ECHEANCE, (7, 3, 0))
        echeances = {seuil: self._echeance(seuil) for seuil in (7, 3, 0)}
        notifies = self._lancer()
        self.assertEqual(len(notifies), 3)
        for seuil, echeance in echeances.items():
            self.assertIn(
                f'{CHAMP_RAPPEL_ECHEANCE}{seuil}', self._marqueurs(echeance))

    def test_hors_fenetre_rien(self):
        for jours in (-1, 1, 2, 4, 6, 8, 30):
            self._echeance(jours)
        self.assertEqual(self._lancer(), [])
        self.assertEqual(
            Notification.objects.filter(company=self.co).count(), 0)

    def test_echeance_deja_deposee_ne_notifie_rien(self):
        self._echeance(3, statut=EcheanceDeclarative.STATUT_DEPOSEE)
        self._echeance(7, statut=EcheanceDeclarative.STATUT_PAYEE)
        self.assertEqual(self._lancer(), [])

    # ── Idempotence ────────────────────────────────────────────────────────

    def test_une_seule_fois_par_jour_seuil(self):
        echeance = self._echeance(3)
        self.assertEqual(len(self._lancer()), 1)
        # Re-run le MÊME jour : aucun doublon.
        self.assertEqual(self._lancer(), [])
        self.assertEqual(self._marqueurs(echeance),
                         [f'{CHAMP_RAPPEL_ECHEANCE}3'])

    def test_chaque_seuil_notifie_a_son_tour(self):
        """La même échéance repasse à J-3 puis J-0 — un marqueur par seuil."""
        limite = self.today + timedelta(days=7)
        echeance = EcheanceDeclarative.objects.create(
            company=self.co, periode=self.periode,
            type_echeance=EcheanceDeclarative.TYPE_BDS, date_limite=limite)

        self.assertEqual(len(self._lancer(today=self.today)), 1)      # J-7
        self.assertEqual(
            len(self._lancer(today=limite - timedelta(days=3))), 1)   # J-3
        self.assertEqual(len(self._lancer(today=limite)), 1)          # J-0
        self.assertEqual(
            self._marqueurs(echeance),
            sorted(f'{CHAMP_RAPPEL_ECHEANCE}{s}'
                   for s in SEUILS_RAPPEL_ECHEANCE))
        # Et aucun des trois jours ne se re-déclenche.
        self.assertEqual(self._lancer(today=limite), [])

    # ── Destinataires ──────────────────────────────────────────────────────

    def test_le_titulaire_de_paie_gerer_est_destinataire(self):
        destinataires = _destinataires_paie(
            self.co, EVENEMENT_RAPPEL_ECHEANCE)
        self.assertIn(self.gestionnaire, destinataires)

    def test_notification_emise_sans_montant(self):
        self._echeance(3)
        self._lancer()
        notifications = Notification.objects.filter(company=self.co)
        self.assertTrue(notifications.exists())
        for notification in notifications:
            texte = f'{notification.title} {notification.body}'
            self.assertIn('Échéance paie', texte)
            self.assertNotIn('MAD', texte)

    # ── Isolation société ──────────────────────────────────────────────────

    def test_isolation_societe(self):
        autre = make_company('ntpay25-autre')
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        echeance_autre = EcheanceDeclarative.objects.create(
            company=autre, periode=periode_autre,
            type_echeance=EcheanceDeclarative.TYPE_BDS,
            date_limite=self.today + timedelta(days=3))
        self._echeance(3)

        notifies = self._lancer()
        self.assertEqual(len(notifies), 1)
        self.assertNotEqual(notifies[0][0].pk, echeance_autre.pk)
        self.assertEqual(self._marqueurs(echeance_autre), [])

"""NTEXT12 — envoi PLANIFIÉ des rapports (abonnements).

Couvre : le matcheur cron PUR (« lundi 8 h »), l'échéance (actif + dû + pas
déjà fait dans l'heure), la résolution des destinataires (users résolus DANS la
société — jamais cross-tenant), le NO-OP propre journalisé quand le canal email
n'est pas configuré, et l'envoi réel avec le rapport en pièce jointe quand il
l'est.
"""
import itertools
from datetime import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from core import data_explorer

from . import rapport_abonnements as ab
from .models import RapportAbonnement, RapportDefinition, WebVitalMetric

User = get_user_model()

_seq = itertools.count(1)

MODULE = 'apps.reporting.rapport_abonnements'


def make_company(nom=None):
    return Company.objects.create(nom=nom or f'NTEXT12 Co {next(_seq)}')


def make_user(company, username=None, email=''):
    return User.objects.create_user(
        username=username or f'ntext12-u{next(_seq)}', password='x',
        email=email, role_legacy='responsable', company=company)


def _vitals_provider(company, user):
    return WebVitalMetric.objects.filter(company=company)


def aware(annee, mois, jour, heure, minute=0):
    """Datetime AWARE figé (USE_TZ=True) — jamais l'horloge réelle."""
    return timezone.make_aware(datetime(annee, mois, jour, heure, minute))


def lundi_8h():
    """Lundi 5 janvier 2026, 08:15 — « lundi 8 h »."""
    return aware(2026, 1, 5, 8, 15)


class CronMatcherTests(TestCase):
    """Matcheur PUR — aucune base, aucun texte exécuté."""

    def test_lundi_8h_is_due_on_monday_morning_only(self):
        self.assertTrue(ab.cron_du('0 8 * * 1', lundi_8h()))
        # Même heure, mardi → non dû.
        self.assertFalse(ab.cron_du('0 8 * * 1', aware(2026, 1, 6, 8, 15)))
        # Même jour, autre heure → non dû.
        self.assertFalse(ab.cron_du('0 8 * * 1', aware(2026, 1, 5, 9, 0)))

    def test_minute_field_is_ignored_grain_is_the_hour(self):
        self.assertTrue(ab.cron_du('30 8 * * 1', lundi_8h()))
        self.assertTrue(ab.cron_du('0 8 * * 1', aware(2026, 1, 5, 8, 59)))

    def test_wildcards_lists_ranges_and_steps(self):
        self.assertTrue(ab.cron_du('0 * * * *', lundi_8h()))
        self.assertTrue(ab.cron_du('0 6,8,10 * * *', lundi_8h()))
        self.assertTrue(ab.cron_du('0 7-9 * * *', lundi_8h()))
        self.assertTrue(ab.cron_du('0 */4 * * *', lundi_8h()))   # 0,4,8,…
        self.assertFalse(ab.cron_du('0 */5 * * *', lundi_8h()))  # 0,5,10,…

    def test_sunday_accepts_both_0_and_7(self):
        dimanche = aware(2026, 1, 4, 8, 0)
        self.assertTrue(ab.cron_du('0 8 * * 0', dimanche))
        self.assertTrue(ab.cron_du('0 8 * * 7', dimanche))

    def test_day_of_month_and_month_are_honoured(self):
        self.assertTrue(ab.cron_du('0 8 5 1 *', lundi_8h()))
        self.assertFalse(ab.cron_du('0 8 6 1 *', lundi_8h()))
        self.assertFalse(ab.cron_du('0 8 5 2 *', lundi_8h()))

    def test_empty_or_unreadable_cron_is_never_due(self):
        for expression in ('', '   ', 'tous les lundis', '0 8 * *',
                           '0 8 * * *  extra', '0 99 * * *', '0 8 * * a',
                           '0 8-6 * * *', '0 */0 * * *'):
            self.assertFalse(ab.cron_du(expression, lundi_8h()), expression)


class DestinatairesTests(TestCase):
    def setUp(self):
        self.company = make_company('NTEXT12 Dest')
        self.autre = make_company('NTEXT12 Dest Autre')
        self.rd = RapportDefinition.objects.create(
            company=self.company, titre='Pipeline', dataset='vitals_ntext12')

    def _abonnement(self, destinataires):
        return RapportAbonnement.objects.create(
            company=self.company, rapport_def=self.rd, cron='0 8 * * 1',
            destinataires=destinataires)

    def test_resolves_users_and_free_emails_deduplicated(self):
        u1 = make_user(self.company, email='u1@example.com')
        u2 = make_user(self.company, email='u2@example.com')
        abonnement = self._abonnement({
            'users': [u1.pk, u2.pk],
            'emails': ['libre@example.com', 'u1@example.com'],
        })
        self.assertEqual(
            sorted(ab.destinataires_emails(abonnement)),
            ['libre@example.com', 'u1@example.com', 'u2@example.com'])

    def test_plain_list_of_addresses_is_tolerated(self):
        abonnement = self._abonnement(['a@example.com', 'b@example.com'])
        self.assertEqual(ab.destinataires_emails(abonnement),
                         ['a@example.com', 'b@example.com'])

    def test_user_of_another_company_is_never_resolved(self):
        etranger = make_user(self.autre, email='fuite@example.com')
        abonnement = self._abonnement({'users': [etranger.pk]})
        self.assertEqual(ab.destinataires_emails(abonnement), [])

    def test_no_recipient_returns_empty(self):
        self.assertEqual(ab.destinataires_emails(self._abonnement({})), [])


class EcheanceTests(TestCase):
    def setUp(self):
        self.company = make_company('NTEXT12 Echeance')
        self.rd = RapportDefinition.objects.create(
            company=self.company, titre='Pipeline', dataset='vitals_ntext12')
        self.abonnement = RapportAbonnement.objects.create(
            company=self.company, rapport_def=self.rd, cron='0 8 * * 1',
            destinataires={'emails': ['a@example.com', 'b@example.com']})

    def test_active_and_due_subscription_creates_the_echeance(self):
        self.assertTrue(ab.est_du(self.abonnement, lundi_8h()))

    def test_inactive_subscription_is_never_due(self):
        self.abonnement.actif = False
        self.assertFalse(ab.est_du(self.abonnement, lundi_8h()))

    def test_already_run_in_the_same_hour_is_not_due_again(self):
        now = lundi_8h()
        self.abonnement.derniere_execution_le = now.replace(minute=2)
        self.assertFalse(ab.est_du(self.abonnement, now))
        # L'heure suivante d'un lundi 8 h n'est de toute façon plus due,
        # mais une exécution de la SEMAINE précédente ne bloque pas.
        self.abonnement.derniere_execution_le = aware(2025, 12, 29, 8, 0)
        self.assertTrue(ab.est_du(self.abonnement, now))


class ExecutionTests(TestCase):
    def setUp(self):
        self.company = make_company('NTEXT12 Exec')
        self.owner = make_user(self.company, email='owner@example.com')
        data_explorer.register_dataset(
            'vitals_ntext12', 'Vitals (test NTEXT12)',
            ['id', 'route', 'metric', 'value'], _vitals_provider)
        WebVitalMetric.objects.create(
            company=self.company, route='/devis', metric='LCP', value=12)
        self.rd = RapportDefinition.objects.create(
            company=self.company, owner=self.owner, titre='Pipeline',
            dataset='vitals_ntext12',
            spec={'group_by': ['route'],
                  'aggregates': [{'alias': 'total', 'fn': 'sum',
                                  'field': 'value'}]})
        self.abonnement = RapportAbonnement.objects.create(
            company=self.company, rapport_def=self.rd, cron='0 8 * * 1',
            destinataires={'emails': ['a@example.com', 'b@example.com']})

    def test_noop_clean_run_is_logged_when_email_is_not_configured(self):
        with mock.patch(f'{MODULE}._email_configure', return_value=False):
            statut = ab.executer_abonnement(self.abonnement, lundi_8h())
        self.assertEqual(statut, RapportAbonnement.Statut.NON_CONFIGURE)
        self.assertEqual(mail.outbox, [])
        self.abonnement.refresh_from_db()
        self.assertEqual(self.abonnement.dernier_statut,
                         RapportAbonnement.Statut.NON_CONFIGURE)
        self.assertEqual(self.abonnement.dernier_detail['destinataires'], 2)
        self.assertIsNotNone(self.abonnement.derniere_execution_le)

    def test_without_recipient_it_is_logged_and_nothing_is_sent(self):
        self.abonnement.destinataires = {}
        self.abonnement.save(update_fields=['destinataires'])
        with mock.patch(f'{MODULE}._email_configure', return_value=True):
            statut = ab.executer_abonnement(self.abonnement, lundi_8h())
        self.assertEqual(statut, RapportAbonnement.Statut.SANS_DESTINATAIRE)
        self.assertEqual(mail.outbox, [])

    def test_configured_channel_sends_the_report_to_both_recipients(self):
        with mock.patch(f'{MODULE}._email_configure', return_value=True):
            statut = ab.executer_abonnement(self.abonnement, lundi_8h())
        self.assertEqual(statut, RapportAbonnement.Statut.OK)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(sorted(message.to),
                         ['a@example.com', 'b@example.com'])
        self.assertIn('Pipeline', message.subject)
        self.assertEqual(len(message.attachments), 1)
        nom, contenu, _type = message.attachments[0]
        if isinstance(contenu, bytes):
            contenu = contenu.decode('utf-8')
        self.assertTrue(nom.endswith('.csv'))
        self.assertIn('route', contenu)
        self.assertIn('12', contenu)

    def test_a_broken_report_is_logged_as_error_and_never_raises(self):
        self.rd.dataset = 'dataset-inexistant'
        self.rd.save(update_fields=['dataset'])
        with mock.patch(f'{MODULE}._email_configure', return_value=True):
            statut = ab.executer_abonnement(self.abonnement, lundi_8h())
        self.assertEqual(statut, RapportAbonnement.Statut.ERREUR)
        self.abonnement.refresh_from_db()
        self.assertTrue(self.abonnement.dernier_detail['detail'])

    def test_pivot_report_is_rendered_as_a_crossed_table(self):
        self.rd.spec = {
            'group_by': ['route', 'metric'],
            'aggregates': [{'alias': 'total', 'fn': 'sum', 'field': 'value'}],
        }
        self.rd.pivot_spec = {'rows': ['route'], 'columns': ['metric'],
                              'measure': 'total', 'agg': 'sum'}
        self.rd.save(update_fields=['spec', 'pivot_spec'])
        _nom, contenu, _type = ab.rendre_abonnement(self.abonnement)
        texte = contenu.decode('utf-8')
        self.assertIn('Ligne', texte)
        self.assertIn('LCP', texte)
        self.assertIn('/devis', texte)


class BeatTaskTests(TestCase):
    def setUp(self):
        self.company = make_company('NTEXT12 Beat')
        self.autre = make_company('NTEXT12 Beat Autre')
        data_explorer.register_dataset(
            'vitals_ntext12', 'Vitals (test NTEXT12)',
            ['id', 'route', 'metric', 'value'], _vitals_provider)
        self.rd = RapportDefinition.objects.create(
            company=self.company, titre='Pipeline', dataset='vitals_ntext12')

    def _abonnement(self, company=None, **kwargs):
        rd = self.rd
        if company is not None and company != self.company:
            rd = RapportDefinition.objects.create(
                company=company, titre='Pipeline', dataset='vitals_ntext12')
        kwargs.setdefault('cron', '0 8 * * 1')
        kwargs.setdefault('destinataires', {'emails': ['x@example.com']})
        return RapportAbonnement.objects.create(
            company=company or self.company, rapport_def=rd, **kwargs)

    def test_task_runs_only_due_subscriptions(self):
        du = self._abonnement()
        pas_du = self._abonnement(cron='0 8 * * 2')
        inactif = self._abonnement(actif=False)
        with mock.patch(f'{MODULE}._now_casablanca', return_value=lundi_8h()), \
                mock.patch(f'{MODULE}._email_configure', return_value=False):
            traites = ab.envoyer_rapports_planifies()
        self.assertEqual(traites, 1)
        du.refresh_from_db()
        pas_du.refresh_from_db()
        inactif.refresh_from_db()
        self.assertEqual(du.dernier_statut,
                         RapportAbonnement.Statut.NON_CONFIGURE)
        self.assertEqual(pas_du.dernier_statut, '')
        self.assertEqual(inactif.dernier_statut, '')

    def test_task_is_idempotent_within_the_same_hour(self):
        self._abonnement()
        with mock.patch(f'{MODULE}._now_casablanca', return_value=lundi_8h()), \
                mock.patch(f'{MODULE}._email_configure', return_value=False):
            self.assertEqual(ab.envoyer_rapports_planifies(), 1)
            self.assertEqual(ab.envoyer_rapports_planifies(), 0)

    def test_each_subscription_runs_in_its_own_company(self):
        mien = self._abonnement()
        autre = self._abonnement(company=self.autre)
        with mock.patch(f'{MODULE}._now_casablanca', return_value=lundi_8h()), \
                mock.patch(f'{MODULE}._email_configure', return_value=False):
            self.assertEqual(ab.envoyer_rapports_planifies(), 2)
        mien.refresh_from_db()
        autre.refresh_from_db()
        self.assertEqual(mien.company_id, self.company.id)
        self.assertEqual(autre.company_id, self.autre.id)
        self.assertEqual(autre.rapport_def.company_id, self.autre.id)

    def test_no_active_subscription_is_a_full_noop(self):
        with mock.patch(f'{MODULE}._now_casablanca', return_value=lundi_8h()):
            self.assertEqual(ab.envoyer_rapports_planifies(), 0)
        self.assertEqual(mail.outbox, [])

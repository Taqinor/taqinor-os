"""Tests des gabarits e-mail du cycle de vie d'une idée (NTIDE52).

Couvre : « idée reçue » (bienvenue, à la création NON brouillon), « idée
retenue » et « idée réalisée » (aux transitions de statut) — gabarit par
défaut (``models.EMAIL_IDEE_DEFAULTS``) tant que la société n'a rien
personnalisé, gabarit personnalisé via ``InnovationSettings``/Paramètres
sinon, aucune notification pour un brouillon ni pour une idée sans auteur.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import services
from apps.innovation.models import Idee, InnovationSettings
from apps.notifications.models import EventType, Notification

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class EmailIdeeRecueTests(TestCase):
    BASE = '/api/django/innovation/idees/'

    def setUp(self):
        self.co_a = make_company('innov-ntide52-a', 'A')
        self.author = make_user(self.co_a, 'ntide52-author')

    def test_notification_fires_on_non_draft_creation(self):
        resp = auth(self.author).post(
            self.BASE, {'titre': 'Une idée', 'draft': False}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        notifs = Notification.objects.filter(
            recipient=self.author, event_type=EventType.IDEA_RECEIVED)
        self.assertEqual(notifs.count(), 1)
        self.assertIn('Une idée', notifs.first().title)

    def test_no_notification_on_draft_creation(self):
        resp = auth(self.author).post(
            self.BASE, {'titre': 'Brouillon', 'draft': True}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.author, event_type=EventType.IDEA_RECEIVED).count(),
            0)

    def test_custom_template_used_when_configured(self):
        InnovationSettings.objects.create(
            company=self.co_a,
            email_recue_sujet='Merci {titre} !',
            email_recue_corps='Corps personnalisé pour {titre}.')
        auth(self.author).post(
            self.BASE, {'titre': 'Export PDF'}, format='json')
        notif = Notification.objects.get(
            recipient=self.author, event_type=EventType.IDEA_RECEIVED)
        self.assertEqual(notif.title, 'Merci Export PDF !')
        self.assertEqual(notif.body, 'Corps personnalisé pour Export PDF.')


class EmailIdeeTransitionsTests(TestCase):
    BASE = '/api/django/innovation/idees/'

    def setUp(self):
        self.co_a = make_company('innov-ntide52-tr-a', 'A')
        self.author = make_user(self.co_a, 'ntide52-tr-author')
        self.resp_a = make_user(
            self.co_a, 'ntide52-tr-resp', role='responsable')
        self.idee = Idee.objects.create(
            company=self.co_a, titre='Une idée', auteur=self.author,
            statut=Idee.Statut.EXAMINEE)

    def test_retenir_notifies_idea_retained(self):
        resp = auth(self.resp_a).post(f'{self.BASE}{self.idee.id}/retenir/')
        self.assertEqual(resp.status_code, 200, resp.data)
        notifs = Notification.objects.filter(
            recipient=self.author, event_type=EventType.IDEA_RETAINED)
        self.assertEqual(notifs.count(), 1)
        self.assertIn('Une idée', notifs.first().title)

    def test_realiser_notifies_idea_realized(self):
        self.idee.statut = Idee.Statut.RETENUE
        self.idee.save(update_fields=['statut'])
        resp = auth(self.resp_a).post(f'{self.BASE}{self.idee.id}/realiser/')
        self.assertEqual(resp.status_code, 200, resp.data)
        notifs = Notification.objects.filter(
            recipient=self.author, event_type=EventType.IDEA_REALIZED)
        self.assertEqual(notifs.count(), 1)

    def test_examiner_does_not_notify_retained_or_realized(self):
        self.idee.statut = Idee.Statut.OUVERT
        self.idee.save(update_fields=['statut'])
        auth(self.resp_a).post(f'{self.BASE}{self.idee.id}/examiner/')
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.author,
                event_type__in=[EventType.IDEA_RETAINED, EventType.IDEA_REALIZED],
            ).count(),
            0)

    def test_no_error_when_idee_has_no_author(self):
        idee = Idee.objects.create(
            company=self.co_a, titre='Sans auteur', statut=Idee.Statut.EXAMINEE)
        resp = auth(self.resp_a).post(f'{self.BASE}{idee.id}/retenir/')
        self.assertEqual(resp.status_code, 200, resp.data)


class TemplateEmailIdeeHelperTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide52-helper-a', 'A')

    def test_default_when_unconfigured(self):
        tpl = services.template_email_idee(self.co_a, 'recue')
        self.assertIn('{titre}', tpl['sujet'])

    def test_custom_overrides_default(self):
        InnovationSettings.objects.create(
            company=self.co_a, email_realisee_sujet='Sujet perso')
        tpl = services.template_email_idee(self.co_a, 'realisee')
        self.assertEqual(tpl['sujet'], 'Sujet perso')
        # Le corps reste le défaut : seul le sujet a été personnalisé.
        self.assertTrue(tpl['corps'])


class InnovationSettingsEmailFieldsApiTests(TestCase):
    BASE = '/api/django/innovation/parametres/'

    def setUp(self):
        self.co_a = make_company('innov-ntide52-set-a', 'A')
        self.admin_a = make_user(self.co_a, 'ntide52-set-admin', role='admin')

    def test_patch_email_fields(self):
        resp = auth(self.admin_a).patch(
            self.BASE,
            {
                'email_recue_sujet': 'Sujet',
                'email_recue_corps': 'Corps',
            },
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        obj = InnovationSettings.objects.get(company=self.co_a)
        self.assertEqual(obj.email_recue_sujet, 'Sujet')
        self.assertEqual(obj.email_recue_corps, 'Corps')

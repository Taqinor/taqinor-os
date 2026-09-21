"""Tests XRH19 — Emails candidats automatiques par étape.

Couvre :
* passer un candidat en « rejeté » avec gabarit ACTIF envoie (console-logue)
  l'email substitué + journalise dans le chatter ;
* sans gabarit, rien ne part ;
* opt-out par candidature (``emails_auto=False``) ;
* jamais d'exception si la config email est cassée (best-effort).
"""
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import (
    Candidature,
    CandidatureActivity,
    GabaritEmailRecrutement,
    OuverturePoste,
)

User = get_user_model()

CANDIDATURES = '/api/django/rh/candidatures/'

LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


@override_settings(EMAIL_BACKEND=LOCMEM)
class EmailCandidatTests(TestCase):
    def setUp(self):
        self.co = make_company('email-a', 'A')
        self.rh = make_user(self.co, 'email-rh')
        self.ouverture = OuverturePoste.objects.create(
            company=self.co, intitule='Technicien SAV')
        self.cand = Candidature.objects.create(
            company=self.co, ouverture=self.ouverture, nom='Yassine Kabbaj',
            email='yassine@example.com')
        mail.outbox = []

    def test_transition_avec_gabarit_actif_envoie_email(self):
        GabaritEmailRecrutement.objects.create(
            company=self.co, etape=Candidature.Etape.REJETE,
            objet='Réponse à votre candidature — {poste}',
            corps='Bonjour {nom}, votre candidature pour {poste} n\'a '
                  'malheureusement pas été retenue.',
            actif=True)

        resp = auth(self.rh).patch(
            f'{CANDIDATURES}{self.cand.id}/',
            {'etape': Candidature.Etape.REJETE})
        self.assertEqual(resp.status_code, 200, resp.data)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Technicien SAV', mail.outbox[0].subject)
        self.assertIn('Yassine Kabbaj', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ['yassine@example.com'])

        notes = CandidatureActivity.objects.filter(
            candidature=self.cand, type='note')
        self.assertTrue(
            any('Email automatique' in n.message for n in notes))

    def test_sans_gabarit_rien_nest_envoye(self):
        resp = auth(self.rh).patch(
            f'{CANDIDATURES}{self.cand.id}/',
            {'etape': Candidature.Etape.REJETE})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(mail.outbox), 0)

    def test_gabarit_inactif_rien_nest_envoye(self):
        GabaritEmailRecrutement.objects.create(
            company=self.co, etape=Candidature.Etape.REJETE,
            objet='X', corps='Y', actif=False)
        resp = auth(self.rh).patch(
            f'{CANDIDATURES}{self.cand.id}/',
            {'etape': Candidature.Etape.REJETE})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(mail.outbox), 0)

    def test_opt_out_emails_auto(self):
        GabaritEmailRecrutement.objects.create(
            company=self.co, etape=Candidature.Etape.REJETE,
            objet='X', corps='Y', actif=True)
        self.cand.emails_auto = False
        self.cand.save(update_fields=['emails_auto'])

        resp = auth(self.rh).patch(
            f'{CANDIDATURES}{self.cand.id}/',
            {'etape': Candidature.Etape.REJETE})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(mail.outbox), 0)

    def test_jamais_dexception_si_envoi_casse(self):
        GabaritEmailRecrutement.objects.create(
            company=self.co, etape=Candidature.Etape.REJETE,
            objet='X', corps='Y', actif=True)
        with mock.patch(
                'django.core.mail.send_mail',
                side_effect=RuntimeError('SMTP down')):
            resp = auth(self.rh).patch(
                f'{CANDIDATURES}{self.cand.id}/',
                {'etape': Candidature.Etape.REJETE})
        # La transition d'étape réussit MALGRÉ l'échec d'envoi (best-effort).
        self.assertEqual(resp.status_code, 200, resp.data)
        self.cand.refresh_from_db()
        self.assertEqual(self.cand.etape, Candidature.Etape.REJETE)

"""ADEP34 — ``is_email_configured()`` répond selon le backend RÉELLEMENT chargé
(clé d'envoi posée ET backend qui envoie) et ``payload_conditions`` lit la même
fonction : une seule règle.

Avant : la clé seule suffisait (``BREVO_API_KEY`` + backend console ⇒
« configuré ») alors que ``send_mail`` imprimait le message sur stdout, et la
page publique disait l'inverse (« backend sans envoi »).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_adep_email_configure -v 2
"""
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

CONSOLE = 'django.core.mail.backends.console.EmailBackend'
DUMMY = 'django.core.mail.backends.dummy.EmailBackend'
LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'
BREVO = 'anymail.backends.sendinblue.EmailBackend'
SMTP = 'django.core.mail.backends.smtp.EmailBackend'

CLE = {'SENDINBLUE_API_KEY': 'brevo-probe-key', 'SENDGRID_API_KEY': ''}
SANS_CLE = {'SENDINBLUE_API_KEY': '', 'SENDGRID_API_KEY': ''}


def _devis_avec_adresse():
    return SimpleNamespace(client=SimpleNamespace(email='client@example.ma'))


class EmailConfigureTests(SimpleTestCase):

    def _deux_reponses(self):
        from apps.ventes.email_service import is_email_configured
        from apps.ventes.public.payload_conditions import (
            _confirmation_email_publique,
        )
        return (is_email_configured(),
                _confirmation_email_publique(_devis_avec_adresse()))

    def test_console_avec_cle_faux_partout(self):
        with override_settings(EMAIL_BACKEND=CONSOLE, ANYMAIL=CLE):
            self.assertEqual(self._deux_reponses(), (False, False))

    def test_dummy_avec_cle_faux_partout(self):
        with override_settings(EMAIL_BACKEND=DUMMY, ANYMAIL=CLE):
            self.assertEqual(self._deux_reponses(), (False, False))

    def test_locmem_avec_cle_vrai_partout(self):
        with override_settings(EMAIL_BACKEND=LOCMEM, ANYMAIL=CLE):
            self.assertEqual(self._deux_reponses(), (True, True))

    def test_anymail_avec_cle_vrai_partout(self):
        with override_settings(EMAIL_BACKEND=BREVO, ANYMAIL=CLE):
            self.assertEqual(self._deux_reponses(), (True, True))

    def test_sans_cle_faux_partout(self):
        for backend in (CONSOLE, LOCMEM, BREVO, SMTP):
            with self.subTest(backend=backend), override_settings(
                    EMAIL_BACKEND=backend, ANYMAIL=SANS_CLE):
                self.assertEqual(self._deux_reponses(), (False, False))

    def test_cle_sendgrid_compte_aussi(self):
        with override_settings(
                EMAIL_BACKEND=BREVO,
                ANYMAIL={'SENDINBLUE_API_KEY': '', 'SENDGRID_API_KEY': 'sg'}):
            self.assertEqual(self._deux_reponses(), (True, True))

    def test_meme_regle_dans_les_trois_cas(self):
        """``payload_conditions`` ne garde aucune règle propre : pour un client
        qui a une adresse, sa réponse égale ``is_email_configured``."""
        for backend in (CONSOLE, LOCMEM, BREVO):
            with self.subTest(backend=backend), override_settings(
                    EMAIL_BACKEND=backend, ANYMAIL=CLE):
                configure, promesse = self._deux_reponses()
                self.assertEqual(configure, promesse)

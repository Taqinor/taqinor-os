"""ADEP31 (C-ADEP-002) — ``core.W_EMAIL`` / ``core.E_EMAIL``.

Une clé d'envoi (BREVO_API_KEY / SENDGRID_API_KEY) posée avec un backend qui
n'envoie rien (console, dummy) donnait une configuration qui SEMBLE prête alors
que tout part dans les logs ; à l'inverse un backend réel avec l'expéditeur par
défaut ``noreply@erp.local`` ne peut être vérifié par aucun fournisseur. Les
deux états sont signalés : avertissement au démarrage (jamais bloquant), erreur
sous ``check --deploy``. L'état sain reste silencieux.

Test-du-test : retirer la branche « clé + console » de ``contradictions_email``
⇒ ``test_cle_avec_console_signalee`` échoue.
"""
from django.test import SimpleTestCase, override_settings

from core import checks

CONSOLE = 'django.core.mail.backends.console.EmailBackend'
DUMMY = 'django.core.mail.backends.dummy.EmailBackend'
BREVO = 'anymail.backends.sendinblue.EmailBackend'
SANS_CLE = {'SENDGRID_API_KEY': '', 'SENDINBLUE_API_KEY': ''}
CLE_BREVO = {'SENDGRID_API_KEY': '', 'SENDINBLUE_API_KEY': 'xkeysib-test'}


def _ids():
    return ([m.id for m in checks.verifier_email_au_demarrage()],
            [m.id for m in checks.verifier_email_deploiement()])


class CheckEmailTests(SimpleTestCase):
    @override_settings(ANYMAIL=CLE_BREVO, EMAIL_BACKEND=CONSOLE,
                       DEFAULT_FROM_EMAIL='contact@taqinor.ma')
    def test_cle_avec_console_signalee(self):
        demarrage, deploiement = _ids()
        self.assertEqual(demarrage, [checks.ID_W_EMAIL])
        self.assertEqual(deploiement, [checks.ID_E_EMAIL])
        message = checks.verifier_email_au_demarrage()[0].msg
        self.assertIn('BREVO_API_KEY', message)
        self.assertNotIn('xkeysib-test', message)  # jamais la valeur du secret

    @override_settings(ANYMAIL=CLE_BREVO, EMAIL_BACKEND=DUMMY,
                       DEFAULT_FROM_EMAIL='contact@taqinor.ma')
    def test_cle_avec_dummy_signalee(self):
        demarrage, deploiement = _ids()
        self.assertEqual(demarrage, [checks.ID_W_EMAIL])
        self.assertEqual(deploiement, [checks.ID_E_EMAIL])

    @override_settings(ANYMAIL=SANS_CLE, EMAIL_BACKEND=CONSOLE,
                       DEFAULT_FROM_EMAIL='noreply@erp.local')
    def test_sans_cle_console_silencieux(self):
        self.assertEqual(_ids(), ([], []))

    @override_settings(ANYMAIL=CLE_BREVO, EMAIL_BACKEND=BREVO,
                       DEFAULT_FROM_EMAIL='contact@taqinor.ma')
    def test_cle_backend_reel_expediteur_verifiable_silencieux(self):
        self.assertEqual(_ids(), ([], []))

    @override_settings(ANYMAIL=CLE_BREVO, EMAIL_BACKEND=BREVO,
                       DEFAULT_FROM_EMAIL='noreply@erp.local')
    def test_backend_reel_expediteur_local_signale(self):
        demarrage, deploiement = _ids()
        self.assertEqual(demarrage, [checks.ID_W_EMAIL])
        self.assertEqual(deploiement, [checks.ID_E_EMAIL])

    def test_predicat_source_unique(self):
        self.assertFalse(checks.backend_email_envoie(CONSOLE))
        self.assertFalse(checks.backend_email_envoie(DUMMY))
        self.assertTrue(checks.backend_email_envoie(BREVO))
        self.assertTrue(checks.backend_email_envoie(
            'django.core.mail.backends.smtp.EmailBackend'))
        self.assertTrue(checks.expediteur_non_verifiable('noreply@erp.local'))
        self.assertTrue(checks.expediteur_non_verifiable('ERP <a@b.local>'))
        self.assertFalse(checks.expediteur_non_verifiable('contact@taqinor.ma'))

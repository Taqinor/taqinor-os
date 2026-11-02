SONDE = {"constat": "C-ADEP-VER2-201", "sha": "1dfa7986c",
         "attendu": "ADEP34 (non-régression) : clé Brevo seule + backend console -> is_email_configured()=False "
                    "et payload_conditions ne promet pas l'e-mail ; clé + anymail -> True des deux côtés ; "
                    "sans clé -> False des deux côtés. repro=True seulement si une réponse diverge (écart réel).",
         "modeles": ["authentication.Company"]}


def sonde(ctx):
    from types import SimpleNamespace
    from django.test import override_settings
    from apps.ventes.email_service import is_email_configured
    from apps.ventes.public.payload_conditions import _confirmation_email_publique

    console = 'django.core.mail.backends.console.EmailBackend'
    brevo = 'anymail.backends.sendinblue.EmailBackend'
    cle = {'SENDINBLUE_API_KEY': 'cle-sonde', 'SENDGRID_API_KEY': ''}
    sans = {'SENDINBLUE_API_KEY': '', 'SENDGRID_API_KEY': ''}
    devis = SimpleNamespace(client=SimpleNamespace(email='client@example.ma'))
    cas = {
        'console+cle': (console, cle, False),
        'anymail+cle': (brevo, cle, True),
        'console sans cle': (console, sans, False),
        'anymail sans cle': (brevo, sans, False),
    }
    obs = {}
    ecart = False
    for nom, (backend, anymail, attendu) in cas.items():
        with override_settings(EMAIL_BACKEND=backend, ANYMAIL=anymail):
            a = is_email_configured()
            b = _confirmation_email_publique(devis)
        obs[nom] = {'is_email_configured': a, 'payload_conditions': b, 'attendu': attendu}
        if a != attendu or b != attendu:
            ecart = True
    print('observé', obs)
    return {'repro': ecart, 'observe': obs}

# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K23 — balayages beat hors des modules scannés par `check_beat_active_companies.py` : la tâche
`reporting.email_saved_reports` (`apps/reporting/scheduled_reports.py::email_saved_reports`) parcourt
`SavedReport.objects.filter(schedule__in=due)` sans `active_companies()` : une société SUSPENDUE (actif=False,
SCA18) continue d'envoyer ses rapports planifiés, avec ses données, à des destinataires EXTERNES.
Témoin : le même rapport d'une société active part aussi (le mécanisme d'envoi fonctionne)."""
SONDE = {"constat": "C-APFS-063", "sha": "c9e72d5b20",
         "attendu": "repro si un e-mail part vers le destinataire externe du rapport de B suspendue (et celui de A active)",
         "modeles": ["reporting.SavedReport", "authentication.Company"]}


def sonde(ctx):
    from unittest import mock
    from django.core import mail
    from authentication.models import Company
    from authentication.selectors import active_companies
    from apps.reporting.models import SavedReport
    from apps.reporting import scheduled_reports as sr
    coA = Company.objects.create(nom='Sonde APFS 063 A', slug='sonde-apfs-063-a')
    coB = Company.objects.create(nom='Sonde APFS 063 B', slug='sonde-apfs-063-b')
    coB.actif = False
    coB.save()
    coB.refresh_from_db()
    rA = SavedReport.objects.create(company=coA, name='Ventes A 063', schedule='daily',
                                    recipients='externe-a-063@example.invalid')
    rB = SavedReport.objects.create(company=coB, name='Ventes B 063', schedule='daily',
                                    recipients='externe-b-063@example.invalid')
    mail.outbox = []
    with mock.patch.object(sr, '_is_email_configured', return_value=True):
        n = sr.email_saved_reports()
    dest = [a for m in mail.outbox for a in (m.to or [])]
    rA.refresh_from_db()
    rB.refresh_from_db()
    obs = {'B_actif': coB.actif, 'B_statut': coB.statut,
           'B_dans_active_companies': active_companies().filter(pk=coB.pk).exists(),
           'envois_total': n, 'mail_vers_B_externe': 'externe-b-063@example.invalid' in dest,
           'mail_vers_A_externe': 'externe-a-063@example.invalid' in dest,
           'B_last_sent_at_pose': rB.last_sent_at is not None, 'A_last_sent_at_pose': rA.last_sent_at is not None,
           'sujets_B': [m.subject for m in mail.outbox if 'externe-b-063@example.invalid' in (m.to or [])][:2]}
    print(obs)
    obs['repro'] = bool(obs['mail_vers_A_externe'] and obs['mail_vers_B_externe']
                        and not obs['B_dans_active_companies'])
    return obs

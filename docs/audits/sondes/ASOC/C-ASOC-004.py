# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K20 — `EventType.DIGEST` fourre-tout. Société R : l'admin a coupé « Récapitulatif » (préférence digest
in_app/email/push = False, grille Préférences). Puis (1) l'auditeur de cohérence trouve 1 nouvelle violation
non-info -> `notifier_nouvelles_violations` ; (2) une demande portail sur un contrat de maintenance ->
`sav.services._notifier_demande_contrat_maintenance`. Relevé : notifications créées, e-mails.
(T) société témoin, préférence absente : mêmes appels -> 1 ligne digest chacun ; `is_action('digest')`."""
SONDE = {"constat": "C-ASOC-004", "sha": "c514bd8ba",
         "attendu": "repro si R : 0 notification pour les deux alertes ; T : 2 lignes digest ; is_action False",
         "modeles": ["notifications.Notification", "notifications.NotificationPreference"]}


def sonde(ctx):
    from types import SimpleNamespace
    from django.contrib.auth import get_user_model
    from django.core import mail
    from django.test import TestCase, override_settings
    from authentication.models import Company
    from apps.notifications.models import Notification, NotificationPreference
    from apps.notifications.severity import is_action
    from apps.sav.services import _notifier_demande_contrat_maintenance
    from apps.ventes.coherence.notification import notifier_nouvelles_violations
    U = get_user_model()
    obs = {}

    def scenario(tag, couper):
        c = Company.objects.create(nom=f'Sonde ASOC 004 {tag}', slug=f'sonde-asoc-004-{tag.lower()}')
        adm = U.objects.create_user(username=f'sonde-asoc-004-{tag.lower()}', password='x', role_legacy='admin',
                                    company=c, email=f'asoc004-{tag.lower()}@example.invalid')
        if couper:
            NotificationPreference.objects.create(user=adm, event_type='digest', in_app=False, email=False,
                                                  push=False, whatsapp=False)
        v = SimpleNamespace(regle='TTC_LIGNES', gravite='erreur', company_id=c.pk, reference='DEV-ASOC004',
                            object_type='devis', object_id=1)
        contrat = SimpleNamespace(pk=0, company=c, client_id=1, client='Client Portail K20')
        n0 = len(getattr(mail, 'outbox', []))
        with override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=False):
            with TestCase.captureOnCommitCallbacks(execute=True):
                emises = notifier_nouvelles_violations(SimpleNamespace(new=[v]))
                n_coh = Notification.objects.filter(company=c, recipient=adm).count()
                _notifier_demande_contrat_maintenance(contrat, 'Demande de visite')
        return {'emises_coherence': emises, 'notif_coherence': n_coh,
                'notif_total': Notification.objects.filter(company=c, recipient=adm).count(),
                'types': sorted(set(Notification.objects.filter(company=c).values_list('event_type', flat=True))),
                'mails': len(getattr(mail, 'outbox', [])) - n0}

    obs['R'] = scenario('R', True)
    obs['T'] = scenario('T', False)
    obs['is_action_digest'] = is_action('digest')
    print(obs)
    r, t = obs['R'], obs['T']
    temoin_ok = t['notif_total'] == 2 and t['types'] == ['digest']
    defaut = r['notif_total'] == 0 and r['mails'] == 0
    obs['repro'] = bool(temoin_ok and defaut and obs['is_action_digest'] is False)
    return obs

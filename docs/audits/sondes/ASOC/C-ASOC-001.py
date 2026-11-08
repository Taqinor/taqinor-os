# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K01 = K25 — `notify()` immédiat ne teste pas `is_active` (la livraison différée N1 le teste).
(R1) A inactif, préférences devis_expired e-mail+push ON : `notify(A, 'devis_expired')` hors heures calmes,
rappels on_commit exécutés -> appels `_dispatch_email` / `_dispatch_webpush` comptés (attendu 0).
(T) témoin : même A, même type, passé par le report N1 puis livré par `_livrer_differee` (cœur du balayage N1) -> 0 appel.
(R2) bus : `devis_expired.send` sur un devis created_by=A (inactif), lead.owner=B (actif) -> destinataires.
(R3) `_notify_user_or_managers(A, …)` (balayages SLA / facture) -> lignes au manager M (attendu >= 1)."""
SONDE = {"constat": "C-ASOC-001", "sha": "c514bd8ba",
         "attendu": "repro si R1 : >=1 appel hors-app vers A inactif ; T : 0 appel ; R2 : notification à A, 0 à B ; "
                    "R3 : 0 notification au manager",
         "modeles": ["notifications.Notification", "notifications.NotificationPreference", "ventes.Devis"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.test import TestCase, override_settings
    from django.utils import timezone
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.notifications import services as ns
    from apps.notifications import sweeps
    from apps.notifications.models import Notification, NotificationPreference
    from apps.ventes.models import Devis
    from core.events import devis_expired
    U = get_user_model()
    co = Company.objects.create(nom='Sonde ASOC 001', slug='sonde-asoc-001')
    a = U.objects.create_user(username='sonde-asoc-001-a', password='x', company=co, role_legacy='normal',
                              email='a-ex-salarie@example.invalid')
    b = U.objects.create_user(username='sonde-asoc-001-b', password='x', company=co, role_legacy='normal',
                              email='b@example.invalid')
    m = U.objects.create_user(username='sonde-asoc-001-m', password='x', company=co, role_legacy='admin',
                              email='m@example.invalid')
    a.is_active = False
    a.save(update_fields=['is_active'])
    for et in ('devis_expired', 'sav_ticket_breaching'):
        NotificationPreference.objects.create(user=a, event_type=et, in_app=True, email=True, push=True,
                                              whatsapp=False)
    appels = []

    def rec(canal):
        def _f(user, *args, **kw):
            appels.append((canal, user.username))
            return True
        return _f

    obs = {'email_configure_reel': ns._is_email_configured()}
    with mock.patch.object(ns, '_dispatch_email', rec('email')), \
            mock.patch.object(ns, '_dispatch_webpush', rec('push')), \
            mock.patch.object(ns, '_is_email_configured', lambda: True):
        # R1 — envoi immédiat (heures calmes coupées pour forcer le chemin immédiat)
        with override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=False):
            with TestCase.captureOnCommitCallbacks(execute=True):
                n1 = ns.notify(a, 'devis_expired', 'Devis expiré', body='DEV-X client Dupont', company=co)
        obs['R1'] = {'ligne_creee': n1 is not None, 'appels': list(appels)}
        # T — même notification passée par le report N1 puis livrée
        del appels[:]
        passe = timezone.now() - timedelta(minutes=1)
        with mock.patch.object(ns, '_report_hors_fenetre', lambda *x, **k: passe):
            with TestCase.captureOnCommitCallbacks(execute=True):
                nd = ns.notify(a, 'devis_expired', 'Devis expiré (différé)', body='DEV-X', company=co)
        # livraison de CETTE ligne seulement (la base locale porte d'autres différées)
        livrees = 1 if (nd is not None and ns._livrer_differee(nd.pk, timezone.now())) else 0
        obs['T'] = {'livrees': livrees, 'appels': list(appels)}
        # R2 — bus devis_expired : created_by=A inactif, lead.owner=B actif
        del appels[:]
        cl = Client.objects.create(company=co, nom='Dupont', prenom='K01', email='k01@example.invalid')
        lead = Lead.objects.create(company=co, nom='Dupont', prenom='K01', telephone='+212600000901',
                                   email='k01@example.invalid', owner=b)
        d = Devis.objects.create(company=co, reference='DEV-ASOC001', client=cl, lead=lead, statut='expire',
                                 taux_tva=Decimal('20'), created_by=a)
        avant = set(Notification.objects.filter(company=co).values_list('pk', flat=True))
        with override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=False):
            with TestCase.captureOnCommitCallbacks(execute=True):
                devis_expired.send(sender=Devis, devis=d, ancien_statut='envoye')
        nouvelles = Notification.objects.filter(company=co, event_type='devis_expired').exclude(pk__in=avant)
        obs['R2'] = {'vers_A': nouvelles.filter(recipient=a).count(), 'vers_B': nouvelles.filter(recipient=b).count(),
                     'appels': list(appels)}
        # R3 — repli managers des balayages
        del appels[:]
        avant = set(Notification.objects.filter(company=co).values_list('pk', flat=True))
        with override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=False):
            with TestCase.captureOnCommitCallbacks(execute=True):
                sweeps._notify_user_or_managers(a, co, 'sav_ticket_breaching', 'SLA', 'Ticket SAV-1 en dépassement')
        nv = Notification.objects.filter(company=co, event_type='sav_ticket_breaching').exclude(pk__in=avant)
        obs['R3'] = {'vers_A': nv.filter(recipient=a).count(), 'vers_M': nv.filter(recipient=m).count(),
                     'appels': list(appels), 'm_est_manager': ns.est_manager(m)}
    print(obs)
    r1 = len(obs['R1']['appels']) >= 1
    t_ok = obs['T']['livrees'] >= 1 and len(obs['T']['appels']) == 0
    r2 = obs['R2']['vers_A'] >= 1 and obs['R2']['vers_B'] == 0
    r3 = obs['R3']['vers_M'] == 0 and obs['R3']['m_est_manager']
    obs['repro'] = bool(t_ok and r1 and r2 and r3)
    return obs

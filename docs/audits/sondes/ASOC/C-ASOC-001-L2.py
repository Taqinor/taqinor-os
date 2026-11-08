# flake8: noqa  (seconde lentille PF2 « Socle » sur C-ASOC-001, rejouable par scripts/sonde.py — METHODE §B.5)
"""K01 — seconde lentille : les VRAIS déclencheurs d'un devis ouvert dont l'auteur est INACTIF, préférences PAR DÉFAUT
(aucune ligne NotificationPreference), heures calmes ALLUMÉES (défaut prod), horloge des beats réels.
(E) `expire_stale_devis` à 01:00 (beat `ventes-expire-stale-devis`) -> `devis_expired_receiver` -> notify(A) REPORTÉ,
    puis `_livrer_differee` à 08:31 -> canaux hors-app appelés ? (attendu par le garde N1 : 0) ; B (responsable du lead) ?
(N) `send_devis_followup_nudges` à 08:15 (beat `ventes-devis-followup-nudges`) : e-mail DIRECT `_send_nudge_email` vers
    `created_by.email` (hors notify, hors préférences, hors heures calmes) -> mail.outbox vers A (inactif) ?
(Nt) témoin : même relance avec `is_email_configured()` faux -> chemin notify -> REPORTÉ -> livré sans hors-app.
(P) `engagement_followup_engine` à 09:05 (beat toutes les 3 h, fenêtre OUVERTE) -> notify(A, devis_nudge_due) IMMÉDIAT
    -> canaux hors-app appelés avec les préférences par défaut (push=True, email=False)."""
SONDE = {"constat": "C-ASOC-001", "sha": "c514bd8ba",
         "attendu": "E : notification reportée à A, 0 hors-app à la livraison, 0 à B ; N : >= 1 e-mail direct à A "
                    "inactif (nom client + lien de proposition) si e-mail configuré ; Nt : 0 hors-app ; P : push vers A "
                    "appelé, e-mail non",
         "modeles": ["notifications.Notification", "notifications.NotificationPreference", "ventes.Devis",
                     "ventes.DevisNudgeLog", "ventes.ShareLink"]}


def sonde(ctx):
    import datetime as dt
    from decimal import Decimal
    from unittest import mock
    from zoneinfo import ZoneInfo
    from django.contrib.auth import get_user_model
    from django.core import mail
    from django.test import TestCase, override_settings
    from authentication.models import Company
    import authentication.selectors as auth_sel
    from apps.crm.models import Client, Lead
    from apps.notifications import services as ns
    from apps.notifications.models import Notification, NotificationPreference
    from apps.ventes import email_service
    from apps.ventes.models import Devis, DevisNudgeLog
    from apps.ventes.domain.recouvrement import expire_stale_devis, send_devis_followup_nudges
    from apps.ventes.scheduled import engagement_followup_engine
    CASA = ZoneInfo('Africa/Casablanca')
    U = get_user_model()

    def societe(suffixe):
        co = Company.objects.create(nom=f'Sonde ASOC 001 L2 {suffixe}', slug=f'sonde-asoc-001-l2-{suffixe}')
        a = U.objects.create_user(username=f'sonde-asoc-001l2-a-{suffixe}', password='x', company=co,
                                  role_legacy='normal', email=f'ex-salarie-{suffixe}@example.invalid')
        a.is_active = False
        a.save(update_fields=['is_active'])
        b = U.objects.create_user(username=f'sonde-asoc-001l2-b-{suffixe}', password='x', company=co,
                                  role_legacy='normal', email=f'b-{suffixe}@example.invalid')
        return co, a, b

    def devis(co, a, ref, **kw):
        cl = Client.objects.create(company=co, nom='Bennani', prenom='K01L2', email=f'{ref.lower()}@example.invalid',
                                   telephone='+212600000911')
        return Devis.objects.create(company=co, client=cl, reference=ref, statut=Devis.Statut.ENVOYE,
                                    taux_tva=Decimal('20'), created_by=a, **kw)

    appels = []

    def rec(canal):
        def _f(user, *args, **kw):
            appels.append((canal, user.username, bool(user.is_active)))
            return True
        return _f

    def a_heure(y, m, d, h, mi):
        t = dt.datetime(y, m, d, h, mi, tzinfo=CASA)
        return mock.patch('django.utils.timezone.now', lambda: t), t

    obs = {'is_email_configured_reel': email_service.is_email_configured(),
           'webpush_configure_reel': ns._is_webpush_configured()}
    co, a, b = societe('e')
    obs['prefs_lignes_A'] = NotificationPreference.objects.filter(user=a).count()
    obs['defaut_devis_expired'] = ns.default_prefs_for('devis_expired')
    obs['defaut_devis_nudge_due'] = ns.default_prefs_for('devis_nudge_due')
    with mock.patch.object(ns, '_dispatch_email', rec('email')), \
            mock.patch.object(ns, '_dispatch_webpush', rec('push')), \
            override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=True):
        # (E) expiration de nuit
        lead = Lead.objects.create(company=co, nom='Bennani', prenom='K01L2', telephone='+212600000912',
                                   email='k01l2-lead@example.invalid', owner=b)
        d_e = devis(co, a, 'DEV-ASOC001L2-E', lead=lead, date_validite=dt.date(2026, 11, 9))
        horloge, t = a_heure(2026, 11, 10, 1, 0)
        with mock.patch.object(auth_sel, 'active_companies', lambda: Company.objects.filter(pk=co.pk)), horloge:
            with TestCase.captureOnCommitCallbacks(execute=True):
                res_e = expire_stale_devis()
        d_e.refresh_from_db()
        ne = Notification.objects.filter(company=co, event_type='devis_expired')
        n_a = ne.filter(recipient=a).first()
        obs['E'] = {'res': res_e, 'statut': d_e.statut, 'vers_A': ne.filter(recipient=a).count(),
                    'vers_B': ne.filter(recipient=b).count(),
                    'reportee_a': str(n_a.programmee_pour.astimezone(CASA)) if n_a and n_a.programmee_pour else None,
                    'appels_a_l_emission': list(appels)}
        del appels[:]
        livree = False
        if n_a is not None:
            horloge, t = a_heure(2026, 11, 10, 8, 31)
            with horloge, TestCase.captureOnCommitCallbacks(execute=True):
                livree = ns._livrer_differee(n_a.pk, t)
        obs['E']['livree'] = livree
        obs['E']['appels_a_la_livraison'] = list(appels)
        del appels[:]

        # (N) relance cadencée de 08:15, e-mail configuré tel quel
        co_n, a_n, _b = societe('n')
        d_n = devis(co_n, a_n, 'DEV-ASOC001L2-N', date_validite=dt.date(2026, 12, 7),
                    date_envoi=dt.datetime(2026, 11, 7, 10, 0, tzinfo=CASA))
        mail.outbox = []
        horloge, t = a_heure(2026, 11, 10, 8, 15)
        with mock.patch.object(auth_sel, 'active_companies', lambda: Company.objects.filter(pk=co_n.pk)), horloge:
            with TestCase.captureOnCommitCallbacks(execute=True):
                nb_n = send_devis_followup_nudges()
        vers_a = [m for m in mail.outbox if a_n.email in m.to]
        obs['N'] = {'nudges': nb_n,
                    'logs': list(DevisNudgeLog.objects.filter(devis=d_n).values_list('niveau', 'canal')),
                    'emails_vers_A_inactif': len(vers_a),
                    'sujet': vers_a[0].subject if vers_a else None,
                    'corps_nomme_client': bool(vers_a and 'Bennani' in vers_a[0].body),
                    'corps_porte_lien_proposition': bool(vers_a and '/proposition/' in vers_a[0].body),
                    'notif_A': Notification.objects.filter(recipient=a_n).count(),
                    'appels_notify': list(appels)}
        del appels[:]

        # (Nt) témoin : e-mail NON configuré -> chemin notify (reporté à 08:30)
        co_t, a_t, _b = societe('t')
        devis(co_t, a_t, 'DEV-ASOC001L2-T', date_validite=dt.date(2026, 12, 7),
              date_envoi=dt.datetime(2026, 11, 7, 10, 0, tzinfo=CASA))
        mail.outbox = []
        horloge, t = a_heure(2026, 11, 10, 8, 15)
        with mock.patch.object(auth_sel, 'active_companies', lambda: Company.objects.filter(pk=co_t.pk)), \
                mock.patch.object(email_service, 'is_email_configured', lambda: False), horloge:
            with TestCase.captureOnCommitCallbacks(execute=True):
                nb_t = send_devis_followup_nudges()
        nt = Notification.objects.filter(recipient=a_t, event_type='devis_nudge_due').first()
        livree_t = False
        if nt is not None and nt.programmee_pour:
            horloge, t = a_heure(2026, 11, 10, 8, 31)
            with horloge, TestCase.captureOnCommitCallbacks(execute=True):
                livree_t = ns._livrer_differee(nt.pk, t)
        obs['Nt'] = {'nudges': nb_t, 'emails': len(mail.outbox), 'notif_A': bool(nt),
                     'reportee': bool(nt and Notification.objects.filter(pk=nt.pk).exists()), 'livree': livree_t,
                     'appels': list(appels)}
        del appels[:]

        # (P) moteur d'engagement à 09:05 (fenêtre ouverte) sur le devis N (lien jamais ouvert, envoyé > 24 h)
        avant = set(Notification.objects.filter(recipient=a_n).values_list('pk', flat=True))
        horloge, t = a_heure(2026, 11, 10, 9, 5)
        with mock.patch.object(auth_sel, 'active_companies', lambda: Company.objects.filter(pk=co_n.pk)), horloge:
            with TestCase.captureOnCommitCallbacks(execute=True):
                nb_p = engagement_followup_engine()
        np_ = Notification.objects.filter(recipient=a_n).exclude(pk__in=avant)
        obs['P'] = {'posees': nb_p, 'notif_A': list(np_.values_list('event_type', flat=True)),
                    'reportees': np_.filter(programmee_pour__isnull=False).count(), 'appels': list(appels)}
    print(obs)
    e_ok = obs['E']['vers_A'] >= 1 and obs['E']['vers_B'] == 0 and not obs['E']['appels_a_la_livraison']
    n_rep = obs['N']['emails_vers_A_inactif'] >= 1
    p_rep = any(c[0] == 'push' and c[1] == a_n.username for c in obs['P']['appels'])
    obs['repro'] = bool(e_ok and (n_rep or p_rep))
    return obs

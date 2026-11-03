SONDE = {"constat": "C-ASAV-VER3-21", "sha": "9ad3b8eb3",
         "attendu": "société au SLA activé, un manager, un ticket SANS technicien en retard SLA (échéance J-2) ; "
                    "le scan au quart d'heure (scan_sla_breaches, beat 15 min) passe AVANT le balayage quotidien "
                    "_sweep_sav_breaching : attendu 1 notification SAV_TICKET_BREACHING (managers) pour l'épisode "
                    "(repro = 0 : le scan pose sla_breach sans notifier faute de technicien, le balayage ne voit "
                    "plus le ticket) ; témoin : ticket AVEC technicien = 1 notification",
         "modeles": ["sav.Ticket", "notifications.Notification"]}


def sonde(ctx):
    from datetime import timedelta
    from unittest.mock import patch
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.notifications.models import Notification
    from apps.notifications.sweeps import _sweep_sav_breaching
    from apps.notifications.types_evenements import EventType
    from apps.sav.models import SavSlaSettings, Ticket
    from apps.sav.tasks import scan_sla_breaches
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde ASAV VER3-21', slug='sonde-asav-ver3-21')
    U = get_user_model()
    mgr = U.objects.create_user(username='sonde-asav-ver3-21-mgr', password='x', company=co, role_legacy='admin')
    tech = U.objects.create_user(username='sonde-asav-ver3-21-tech', password='x', company=co,
                                 role_legacy='technicien')
    reglage = SavSlaSettings.get(co)
    reglage.sla_breach_enabled = True
    reglage.save()
    cl = Client.objects.create(company=co, nom='Client', prenom='VER321')
    sans = Ticket.objects.create(company=co, client=cl, reference='SAV-SONDE-321-SANS',
                                 statut=Ticket.Statut.EN_COURS, created_by=mgr,
                                 date_ouverture=today - timedelta(days=8), sla_due_at=today - timedelta(days=2))
    avec = Ticket.objects.create(company=co, client=cl, reference='SAV-SONDE-321-AVEC',
                                 statut=Ticket.Statut.EN_COURS, created_by=mgr, technicien_responsable=tech,
                                 date_ouverture=today - timedelta(days=8), sla_due_at=today - timedelta(days=2))

    def notifs(t):
        return Notification.objects.filter(company=co, event_type=EventType.SAV_TICKET_BREACHING).filter(
            link__in=[f'/sav?id={t.pk}', f'/sav/tickets/{t.pk}']).count()

    # Borne le scan multi-sociétés à la société de la sonde (le beat parcourt toutes les sociétés actives).
    with patch('authentication.selectors.active_company_ids', return_value=[co.pk]):
        scan_sla_breaches()
    sans.refresh_from_db()
    avec.refresh_from_db()
    apres_scan = (notifs(sans), notifs(avec), sans.sla_breach, avec.sla_breach)
    _sweep_sav_breaching(co)
    _sweep_sav_breaching(co)
    finaux = (notifs(sans), notifs(avec))
    print(f'après scan : sans_tech={apres_scan[0]} avec_tech={apres_scan[1]} '
          f'sla_breach sans={apres_scan[2]} avec={apres_scan[3]} ; après 2 balayages : '
          f'sans_tech={finaux[0]} avec_tech={finaux[1]} (attendu 1 et 1)')
    return {'repro': finaux[0] == 0, 'sans_technicien': finaux[0], 'avec_technicien': finaux[1],
            'sla_breach_sans_apres_scan': apres_scan[2]}

SONDE = {"constat": "C-ASAV-VER2-411", "sha": "56d5b623a",
         "attendu": "ASAV21 : un ticket au SLA en heures ouvrées dont sla_echeance_at est dépassée de 1 h (sla_due_at = aujourd'hui) est signalé en retard par scan_sla_breaches le MÊME jour (sla_breach=True, 1 notification)"}


def sonde(ctx):
    from datetime import timedelta
    from django.utils import timezone
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.notifications.models import Notification
    from apps.sav.models import SavSlaSettings, Ticket
    from apps.sav.tasks import scan_sla_breaches
    from django.contrib.auth import get_user_model
    co = Company.objects.create(nom='Sonde ASAV VER2-411', slug='sonde-asav-ver2-411')
    reglage = SavSlaSettings.get(co)
    reglage.sla_breach_enabled = True
    reglage.save()
    tech = get_user_model().objects.create_user(username='sonde-asav-ver2-411', password='x', company=co)
    cl = Client.objects.create(company=co, nom='Client', prenom='VER2411')
    today = timezone.localdate()
    t = Ticket.objects.create(company=co, reference='SAV-SONDE-411', client=cl, type=Ticket.Type.CORRECTIF,
                              statut=Ticket.Statut.EN_COURS, date_ouverture=today,
                              technicien_responsable=tech)
    Ticket.objects.filter(pk=t.pk).update(
        sla_due_at=today, sla_echeance_at=timezone.now() - timedelta(hours=1))
    scan_sla_breaches()
    t.refresh_from_db()
    n = Notification.objects.filter(company=co).count()
    print(f'sla_breach={t.sla_breach} notifications={n} (attendu True / 1 ; bug si False / 0)')
    return {'repro': not t.sla_breach, 'sla_breach': t.sla_breach, 'notifications': n}

# flake8: noqa  (sonde d'audit de parcours PA7, rejouable par scripts/sonde.py — METHODE §C.4)
"""K32 : (1) POST core/sla/credits/<pk>/statut/ {statut:'emis'} sur un snapshot `non_applicable` (aucun crédit dû)
est-il accepté, et le crédit « émis » sans montant apparaît-il dans la liste ? (2) Un crédit de septembre « refusé »
à 5 % ignore-t-il le recalcul NTOBS25 (recalculer_sla_perimes) après un incident tardif qui le porte à 25 %, sans
notification ? Témoin : août, même scénario mais crédit resté « a_emettre » → recalculé + notifié. Vraie route."""
SONDE = {"constat": "C-AMON-032", "sha": "39313d48e",
         "attendu": "repro si (1) 200 et ligne emis sans montant ; (2) sept reste 5 % refuse ; témoin août recalculé 25 % ; notif de recalcul relevée à part",
         "modeles": ["core.SlaSnapshot", "statuspage.IncidentPublic", "notifications.Notification"]}


def sonde(ctx):
    from datetime import date, datetime
    from decimal import Decimal
    from django.apps import apps as dj
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from core.sla import SlaSnapshot, SlaCreditPolicy, generer_snapshot_societe, recalculer_sla_perimes
    Facture = dj.get_model('facturation', 'Facture')
    Incident = dj.get_model('statuspage', 'IncidentPublic')
    Notification = dj.get_model('notifications', 'Notification')
    H = {'HTTP_HOST': 'localhost'}
    tz = timezone.get_current_timezone()
    co = Company.objects.create(nom='Sonde AMON 032', slug='sonde-amon-032')
    SlaCreditPolicy.objects.create(company=co)
    u = get_user_model().objects.create_user('amon032_adm', password='x', company=co, role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON032', email='amon032@example.invalid')

    def dt(y, m, d, h):
        return timezone.make_aware(datetime(y, m, d, h, 0), tz)

    def incident(y, m, d, heures):
        return Incident.objects.create(company=co, titre='Panne sonde', severite='critique', statut='resolved',
                                       debute_le=dt(y, m, d, 0), resolu_le=dt(y, m, d, 0) + timezone.timedelta(hours=heures))
    for m in (8, 9):
        Facture.objects.create(company=co, reference=f'FAC-AMON032-{m}', client=cl, statut='emise',
                               taux_tva=Decimal('20'), montant_ht=Decimal('8333.33'), montant_tva=Decimal('1666.67'),
                               montant_ttc=Decimal('10000'), date_emission=date(2026, m, 15))
    # (1) juillet : aucun incident → non_applicable
    juil = generer_snapshot_societe(co, date(2026, 7, 1))
    r1 = api.post(f'/api/django/core/sla/credits/{juil.id}/statut/', {'statut': 'emis'}, format='json', **H)
    juil.refresh_from_db()
    liste = api.get('/api/django/core/sla/credits/', **H).json()
    ligne_juil = next((x for x in liste if x.get('id') == juil.id), None)
    # (2) août (témoin, a_emettre) et septembre (refusé), 5 h d'incident chacun → 5 %
    incident(2026, 8, 10, 5)
    incident(2026, 9, 10, 5)
    aout = generer_snapshot_societe(co, date(2026, 8, 1))
    sept = generer_snapshot_societe(co, date(2026, 9, 1))
    avant = {'aout': (str(aout.credit_du_pct), str(aout.credit_du_montant), aout.credit_statut),
             'sept': (str(sept.credit_du_pct), str(sept.credit_du_montant), sept.credit_statut)}
    r2 = api.post(f'/api/django/core/sla/credits/{sept.id}/statut/', {'statut': 'refuse'}, format='json', **H)
    # incidents tardifs de 48 h sur août et septembre
    incident(2026, 8, 20, 48)
    incident(2026, 9, 20, 48)
    n0 = Notification.objects.filter(company=co).count()
    regen = recalculer_sla_perimes()
    notifs = list(Notification.objects.filter(company=co).values_list('title', flat=True))[:20]
    aout.refresh_from_db()
    sept.refresh_from_db()
    obs = {'1_non_applicable_vers_emis_http': r1.status_code, '1_statut': juil.credit_statut,
           '1_ligne_liste': ligne_juil, 'avant': avant, 'refuse_http': r2.status_code,
           'regeneres_co': sorted(s.periode.isoformat() for s in regen if s.company_id == co.id),
           'apres': {'aout': (str(aout.uptime_pct), str(aout.credit_du_pct), str(aout.credit_du_montant), aout.credit_statut),
                     'sept': (str(sept.uptime_pct), str(sept.credit_du_pct), str(sept.credit_du_montant), sept.credit_statut)},
           'notifications_co': notifs}
    # Témoin = le recalcul NTOBS25 marche pour un crédit NON décidé (août 5 % -> 25 %). La notification
    # « crédit recalculé » est relevée à part : `notifications_co` (attendu 1 pour août).
    temoin_ok = aout.credit_du_pct is not None and float(aout.credit_du_pct) == 25.0
    obs['notif_recalcul_morte'] = len(notifs) == 0
    obs['temoin_ok'] = temoin_ok
    d1 = r1.status_code == 200 and juil.credit_statut == 'emis'
    d2 = float(sept.credit_du_pct) == 5.0 and sept.credit_statut == 'refuse'
    obs['repro'] = bool(temoin_ok and d1 and d2)
    return obs

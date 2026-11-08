# flake8: noqa  (sonde d'audit de parcours PA7, critique T6, rejouable par scripts/sonde.py — METHODE §B.5)
"""T6 : `monitoring` est dans `APPS_SANS_MODULE` sans aucun code au registre. Rôle canonique « Admin RH » (aucun code
sav/monitoring, mais des codes d'écriture rh/paie → `is_responsable`) sur les VRAIES routes monitoring : émettre un
certificat carbone, résilier un abonnement de supervision, supprimer un relevé, régler le seuil + l'auto-ticket
société, envoyer le rapport O&M à une adresse tierce. Témoins : le même Admin RH sur une écriture SAV gouvernée
(POST sav/tickets/) → 403 ; un compte « normal » (palier utilisateur) sur les écritures monitoring → 403."""
SONDE = {"constat": "C-AMON-045", "sha": "51dac387b",
         "attendu": "repro si Admin RH : certificat 201, résilier 200, DELETE relevé 204, settings 200, email-om-report "
                    "200 vers un tiers (1 mail) ; témoins : sav/tickets 403 pour Admin RH, normal 403 sur monitoring",
         "modeles": ["monitoring.CertificatCarbone", "monitoring.AbonnementMonitoring", "monitoring.ProductionReading",
                     "monitoring.MonitoringSettings", "roles.Role"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.core import mail
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import AbonnementMonitoring, MonitoringConfig, MonitoringSettings, ProductionReading
    from apps.monitoring.services import creer_abonnement_monitoring
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AMON 045', slug='sonde-amon-045')
    r_rh = Role.objects.create(company=co, nom=reg.ROLE_ADMIN_RH, permissions=list(reg.ADMIN_RH_PERMISSIONS),
                               est_systeme=True, perimetre=reg.PERIMETRE_RH)
    rh = User.objects.create_user(username='sonde-amon045-rh', password='x', company=co, role=r_rh)
    normal = User.objects.create_user(username='sonde-amon045-norm', password='x', company=co, role_legacy='normal')
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON045', email='amon045@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-AMON045', client=cl,
                                       puissance_installee_kwc=Decimal('4.00'), date_mise_en_service=date(2024, 12, 1))
    cfg = MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('6000'))
    ProductionReading.objects.bulk_create([
        ProductionReading(company=co, installation=inst, date=date(2025, m, 1), energy_kwh=Decimal('500'), period_days=28)
        for m in range(1, 13)])
    ab = creer_abonnement_monitoring(co, installation_id=inst.id, periodicite='mensuel', montant=Decimal('150'),
                                     date_debut=date(2026, 1, 1))
    lecture_rh = {'is_responsable': rh.is_responsable, 'codes_sav': [c for c in r_rh.permissions if c.startswith('sav')]}

    def jeu(user, tag):
        api = APIClient()
        api.force_authenticate(user)
        out = {}
        r = api.post('/api/django/monitoring/certificats-carbone/', {
            'installation_id': inst.id, 'periode_debut': '2025-01-01', 'periode_fin': '2025-03-31'}, format='json', **H)
        out['certificat'] = r.status_code
        r = api.post(f'/api/django/monitoring/abonnements/{ab.id}/resilier/', {'motif': f'sonde {tag}'},
                     format='json', **H)
        out['resilier'] = r.status_code
        rel = ProductionReading.objects.filter(installation=inst).order_by('-date').first()
        r = api.delete(f'/api/django/monitoring/readings/{rel.id}/', **H)
        out['delete_releve'] = r.status_code
        r = api.post('/api/django/monitoring/settings/', {'auto_create_ticket': True, 'underperf_threshold_pct': '90'},
                     format='json', **H)
        out['settings'] = r.status_code
        n0 = len(getattr(mail, 'outbox', []))
        r = api.post(f'/api/django/monitoring/configs/{cfg.id}/email-om-report/',
                     {'recipient': 'tiers@example.invalid', 'period': 'monthly'}, format='json', **H)
        out['email_om_report'] = r.status_code
        out['mails_partis'] = [m.to for m in getattr(mail, 'outbox', [])[n0:]]
        r = api.post('/api/django/sav/tickets/', {}, format='json', **H)
        out['temoin_sav_tickets_post'] = r.status_code
        return out

    obs = {'lecture_rh': lecture_rh, 'normal': jeu(normal, 'normal')}
    ab.refresh_from_db()
    obs['abonnement_statut_apres_normal'] = ab.statut
    obs['admin_rh'] = jeu(rh, 'rh')
    ab.refresh_from_db()
    st = MonitoringSettings.objects.filter(company=co).values('auto_create_ticket', 'underperf_threshold_pct').first()
    obs['abonnement_statut_final'] = ab.statut
    obs['settings_final'] = {k: str(v) for k, v in (st or {}).items()}
    n, a = obs['normal'], obs['admin_rh']
    temoin_ok = (a['temoin_sav_tickets_post'] == 403
                 and all(n[k] == 403 for k in ('certificat', 'resilier', 'delete_releve', 'settings', 'email_om_report')))
    defaut = (a['certificat'] == 201 and a['resilier'] == 200 and a['delete_releve'] == 204 and a['settings'] == 200
              and a['email_om_report'] == 200 and a['mails_partis'] == [['tiers@example.invalid']])
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs

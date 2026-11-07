# flake8: noqa  (sonde d'audit de parcours PA7, rejouable par scripts/sonde.py — METHODE §C.4)
"""K22 : un système SAIN dont les relevés mensuels (750 kWh, attendu 9 000 kWh/an) n'ont été importés que jusqu'à
il y a 3 mois est-il évalué en sous-performance (attendu jusqu'à aujourd'hui, réel limité aux relevés reçus) ?
(R) relevés mensuels du 1er de M-12 au 1er de M-3 → evaluate_underperformance (fonction du beat
balayage_quotidien / de l'import) → ratio, drapeau, ticket ; puis la VRAIE route portail
`client/ma-consommation/` du client. (T) témoin : même profil, relevés jusqu'au 1er du mois courant."""
SONDE = {"constat": "C-AMON-022", "sha": "39313d48e",
         "attendu": "repro si R : ratio ≈75 %, drapeau ouvert, ticket préventif créé, portail alertes_ouvertes=1 ; T : pas de drapeau",
         "modeles": ["monitoring.UnderperformanceFlag", "monitoring.ProductionReading", "sav.Ticket"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company, CustomUser
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import (MonitoringConfig, MonitoringSettings, ProductionReading,
                                        UnderperformanceFlag)
    from apps.monitoring.services import evaluate_underperformance
    from apps.roles.models import Role
    from apps.roles.permissions_registre import PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde AMON 022', slug='sonde-amon-022')
    st = MonitoringSettings.get(co)
    st.auto_create_ticket = True
    st.underperf_threshold_pct = Decimal('20')
    st.save()
    role, _ = Role.objects.get_or_create(company=co, nom=ROLE_PORTAIL_CLIENT,
                                         defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS), 'est_systeme': True})

    def mois(k):  # 1er du mois courant - k
        y, m = today.year, today.month - k
        while m <= 0:
            m += 12
            y -= 1
        return date(y, m, 1)

    def cas(tag, dernier_k):
        cl = Client.objects.create(company=co, nom='Client', prenom=f'AMON022{tag}', email=f'amon022{tag}@example.invalid')
        inst = Installation.objects.create(company=co, reference=f'CHT-AMON022-{tag}', client=cl,
                                           puissance_installee_kwc=Decimal('5.00'))
        MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('9000'))
        for k in range(12, dernier_k - 1, -1):
            ProductionReading.objects.create(company=co, installation=inst, date=mois(k),
                                             energy_kwh=Decimal('750'), period_days=30)
        res = evaluate_underperformance(inst, today=today)
        u = CustomUser.objects.create_user(username=f'amon022_portail_{tag}', password='motdepasse-test-1234',
                                           company=co, role=role)
        u.portee = CustomUser.PORTEE_PORTAIL_CLIENT
        u.portail_client_id = cl.id
        u.save()
        api = APIClient()
        api.force_authenticate(u)
        r = api.get('/api/django/portail/client/ma-consommation/', **H)
        rj = r.json() if r.status_code == 200 else {}
        tk = res.get('ticket')
        return {'releves': ProductionReading.objects.filter(installation=inst).count(),
                'ratio_pct': str(res.get('ratio_pct')), 'data_status': res.get('data_status'),
                'underperforming': res.get('underperforming'),
                'drapeau_ouvert': UnderperformanceFlag.objects.filter(installation=inst, is_open=True).exists(),
                'ticket': None if tk is None else {'type': getattr(tk, 'type_ticket', getattr(tk, 'type', None)),
                                                   'priorite': getattr(tk, 'priorite', None),
                                                   'desc': (getattr(tk, 'description', '') or '')[:90]},
                'portail_http': r.status_code, 'portail_alertes_ouvertes': rj.get('alertes_ouvertes'),
                'portail_provider_configure': rj.get('provider_configure')}

    obs = {'today': today.isoformat(), 'R_import_en_retard': cas('R', 3), 'T_temoin_a_jour': cas('T', 0)}
    r, t = obs['R_import_en_retard'], obs['T_temoin_a_jour']
    temoin_ok = t['data_status'] == 'evaluated' and not t['drapeau_ouvert']
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and r['drapeau_ouvert'] and r['ticket'] is not None
                        and r['portail_alertes_ouvertes'] == 1)
    return obs

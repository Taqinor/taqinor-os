# flake8: noqa  (sonde d'audit de parcours PA7, seconde lentille, rejouable par scripts/sonde.py — METHODE §B.5)
"""K22 seconde lentille — RÉGLAGES PAR DÉFAUT (auto-ticket éteint, seuil 20 %) et cadence ORDINAIRE de saisie à l'écran,
au lieu d'un import en retard de 3 mois avec auto-ticket forcé. Corps exact de `ProductionPage.addReading` (défaut 30 j),
compte au rôle système « Technicien ». (Y) système JEUNE, mis en service il y a 75 j : relevés mensuels sains du jour de
mise en service puis +30 j ; le 3e mois (fini il y a 15 j) n'est pas encore saisi — l'évaluation tourne dans le POST
même (`perform_create`) ; puis le 3e relevé est saisi. (O) témoin ANCIEN (400 j), même retard de 15 j, 12 relevés.
Mesure : drapeau ouvert, ticket (aucun attendu : auto-ticket éteint), alerte au portail client (vraie route)."""
SONDE = {"constat": "C-AMON-022", "sha": "39313d48e",
         "attendu": "repro si Y (sain, 15 j de retard ordinaire) est drapeauté sous 80 % au défaut et que le portail du "
                    "client affiche l'alerte, le drapeau tombant dès la saisie du relevé manquant ; témoin O : pas de drapeau",
         "modeles": ["monitoring.UnderperformanceFlag", "monitoring.ProductionReading", "sav.Ticket"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company, CustomUser
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import MonitoringConfig, MonitoringSettings, ProductionReading, UnderperformanceFlag
    from apps.monitoring.services import evaluate_underperformance
    from apps.roles.models import Role
    from apps.roles.permissions_registre import (PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT,
                                                 TECHNICIEN_PERMISSIONS)
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde AMON 022 L2', slug='sonde-amon-022-l2')
    st = MonitoringSettings.get(co)
    reglages = {'auto_create_ticket': st.auto_create_ticket, 'underperf_threshold_pct': str(st.underperf_threshold_pct)}
    tech = CustomUser.objects.create_user('amon022l2_tech', password='x', company=co,
                                          role=Role.objects.create(company=co, nom='Technicien', est_systeme=True,
                                                                   permissions=list(TECHNICIEN_PERMISSIONS)))
    api = APIClient()
    api.force_authenticate(tech)
    role_portail, _ = Role.objects.get_or_create(company=co, nom=ROLE_PORTAIL_CLIENT,
                                                 defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                                                           'est_systeme': True})
    kwh_mois = '739.73'  # 9 000 kWh/an attendus → 24,66 kWh/j × 30 j : production nominale

    def systeme(tag, age):
        cl = Client.objects.create(company=co, nom='Client', prenom=f'AMON022L2{tag}',
                                   email=f'amon022l2{tag}@example.invalid')
        inst = Installation.objects.create(company=co, reference=f'CHT-AMON022L2-{tag}', client=cl,
                                           puissance_installee_kwc=Decimal('5.00'),
                                           date_mise_en_service=today - timedelta(days=age))
        MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('9000'))
        p = CustomUser.objects.create_user(f'amon022l2_portail_{tag}', password='x', company=co, role=role_portail)
        p.portee = CustomUser.PORTEE_PORTAIL_CLIENT
        p.portail_client_id = cl.id
        p.save()
        return inst, p

    def ecran(inst, jour):
        r = api.post('/api/django/monitoring/readings/', {'installation': inst.id, 'date': jour.isoformat(),
                                                           'energy_kwh': kwh_mois, 'period_days': 30, 'note': ''},
                     format='json', **H)
        return r.status_code

    def etat(inst, p):
        c = APIClient()
        c.force_authenticate(p)
        r = c.get('/api/django/portail/client/ma-consommation/', **H)
        fl = UnderperformanceFlag.objects.filter(installation=inst, is_open=True).first()
        return {'drapeau_ouvert': fl is not None, 'ratio_drapeau': None if fl is None else str(fl.ratio_pct),
                'tickets_sav': _tickets(inst), 'portail_http': r.status_code,
                'portail_alertes_ouvertes': r.json().get('alertes_ouvertes') if r.status_code == 200 else None}

    def _tickets(inst):
        from django.apps import apps as dj
        Ticket = dj.get_model('sav', 'Ticket')
        try:
            return Ticket.objects.filter(company=co, client=inst.client).count()
        except Exception as exc:  # champ client absent : compte société
            return f'n/a ({type(exc).__name__})'

    # (Y) jeune : mise en service J-75, relevés J-75 et J-45 (couvrent jusqu'à J-15)
    y, py = systeme('Y', 75)
    c0 = today - timedelta(days=75)
    http_y = [ecran(y, c0), ecran(y, c0 + timedelta(days=30))]
    ev_y = evaluate_underperformance(y, today=today)  # = beat balayage_quotidien
    y_avant = dict(etat(y, py), ratio_beat=str(ev_y['ratio_pct']), data_status=ev_y['data_status'])
    http_y.append(ecran(y, c0 + timedelta(days=60)))  # le relevé manquant (couvre jusqu'à J+15)
    y_apres = etat(y, py)
    y_apres['ratio_apres'] = str(evaluate_underperformance(y, today=today)['ratio_pct'])
    # (O) ancien : 12 relevés mensuels sains, le dernier couvrant jusqu'à J-15
    o, po = systeme('O', 400)
    http_o = [ecran(o, today - timedelta(days=15 + 30 * k)) for k in range(12, 0, -1)]
    ev_o = evaluate_underperformance(o, today=today)
    o_etat = dict(etat(o, po), ratio_beat=str(ev_o['ratio_pct']))
    obs = {'today': today.isoformat(), 'reglages_defaut': reglages,
           'Y_jeune_75j_retard_15j': {'http': http_y, 'avant_saisie_manquante': y_avant,
                                      'apres_saisie_manquante': y_apres},
           'O_temoin_400j_retard_15j': {'http': sorted(set(http_o)), **o_etat}}
    temoin_ok = not o_etat['drapeau_ouvert'] and set(http_o) == {201}
    defaut = (y_avant['drapeau_ouvert'] and y_avant['portail_alertes_ouvertes'] == 1
              and not y_apres['drapeau_ouvert'])
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs

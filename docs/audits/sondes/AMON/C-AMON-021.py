# flake8: noqa  (sonde d'audit de parcours PA7, rejouable par scripts/sonde.py — METHODE §C.4)
"""K21 : l'indice de disponibilité (om_metrics) est divisé par 365 jours fixes, sans borne de mise en service.
(N) système mis en service il y a 60 j, 60 relevés journaliers sains → GET sla-disponibilite/<id>/ecart/ et
GET configs/<id>/om-report/?period=monthly. (V) même système sans aucun relevé. (T) témoin : système en service
depuis > 1 an, 366 relevés journaliers → 100 %, aucune pénalité. Vraies routes, compte admin de la société."""
SONDE = {"constat": "C-AMON-021", "sha": "39313d48e",
         "attendu": "repro si N : mesurée ≈16.44, pénalité ≈59 538, rapport mensuel 16.44 ; V : mesurée 0.00 et pénalité ≈71 540",
         "modeles": ["monitoring.ProductionReading", "monitoring.SlaDisponibilite", "monitoring.MonitoringConfig"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import MonitoringConfig, ProductionReading, SlaDisponibilite
    from apps.parametres.models import CompanyProfile
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde AMON 021', slug='sonde-amon-021')
    prof, _ = CompanyProfile.objects.get_or_create(company=co)
    prof.garantie_production_autorisee = True
    prof.save()
    u = get_user_model().objects.create_user('amon021_adm', password='x', company=co, role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON021', email='amon021@example.invalid')

    def systeme(ref, mes_jours, nb_releves):
        inst = Installation.objects.create(company=co, reference=ref, client=cl,
                                           puissance_installee_kwc=Decimal('5.00'),
                                           date_mise_en_service=today - timedelta(days=mes_jours))
        cfg = MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('9000'))
        for i in range(nb_releves):
            ProductionReading.objects.create(company=co, installation=inst,
                                             date=today - timedelta(days=nb_releves - 1 - i),
                                             energy_kwh=Decimal('24.66'), period_days=1)
        sla = SlaDisponibilite.objects.create(company=co, installation=inst,
                                              disponibilite_garantie_pct=Decimal('98'),
                                              compensation_mad_par_jour_indispo=Decimal('200'))
        e = api.get(f'/api/django/monitoring/sla-disponibilite/{sla.id}/ecart/', **H)
        r = api.get(f'/api/django/monitoring/configs/{cfg.id}/om-report/?period=monthly', **H)
        ej = e.json() if e.status_code == 200 else {'err': str(e.content)[:150]}
        rj = r.json() if r.status_code == 200 else {'err': str(r.content)[:150]}
        return {'ecart_http': e.status_code, 'mesuree': str(ej.get('disponibilite_mesuree_pct')),
                'ecart_pct': str(ej.get('ecart_pct')), 'jours_exc': str(ej.get('jours_indisponibilite_excedentaire')),
                'sous_garantie': ej.get('sous_garantie'), 'penalite_mad': str(ej.get('penalite_mad')),
                'rapport_http': r.status_code, 'rapport_period_days': rj.get('period_days'),
                'rapport_availability_pct': str(rj.get('availability_pct')), 'rapport_pr_pct': str(rj.get('pr_pct'))}

    obs = {'N_neuf_60j': systeme('CHT-AMON021-N', 60, 60),
           'V_sans_releve': systeme('CHT-AMON021-V', 60, 0),
           'T_temoin_400j': systeme('CHT-AMON021-T', 400, 366)}
    n, v, t = obs['N_neuf_60j'], obs['V_sans_releve'], obs['T_temoin_400j']
    def f(x):
        try:
            return float(x)
        except Exception:
            return None
    temoin_ok = t['ecart_http'] == 200 and f(t['mesuree']) == 100.0 and f(t['penalite_mad']) == 0.0
    defaut_n = f(n['mesuree']) is not None and f(n['mesuree']) < 20 and (f(n['penalite_mad']) or 0) > 50000
    defaut_v = v['mesuree'] not in ('None',) and (f(v['penalite_mad']) or 0) > 0
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut_n and defaut_v)
    return obs

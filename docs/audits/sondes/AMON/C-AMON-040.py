# flake8: noqa  (sonde d'audit de parcours PA7, critique T1, rejouable par scripts/sonde.py — METHODE §B.5)
"""T1 : garantie de production 12 000 kWh/an (dégradation 0, start_year 2026, franchise 5 %, 1,10 MAD/kWh).
(N) système mis en service le 08/09/2026, relevés journaliers SAINS 32,88 kWh (= 12 000/365) du 08/09 au 07/11
(61 j). Le garanti est-il proraté sur l'année CIVILE (311/365 au 07/11) au lieu de la période couverte → compensation
≈ 8 478,72 MAD « hors tolérance » pour un système à 100 % ? Et l'année 2025 (antérieure à start_year) reçoit-elle
le garanti plein de l'an 1 → pénalité « définitive » 12 540 MAD dans le rapport contractuel ? (T) témoin en service
depuis le 01/01/2026, mêmes relevés sains sur toute l'année → 0. Services réels (today figé) + vraie route `status`
et `rapport-garantie-pdf?annee=2025` (réglage `garantie_production_autorisee` = vrai)."""
SONDE = {"constat": "C-AMON-040", "sha": "51dac387b",
         "attendu": "repro si N : compensation ≈ 8478.72 et within_tolerance False ; rapport 2025 : penalite 12540, "
                    "year_in_progress False, route PDF 200 ; témoin T : compensation 0",
         "modeles": ["monitoring.ProductionWarranty", "monitoring.ProductionReading"]}


def sonde(ctx):
    from datetime import date, timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import MonitoringConfig, ProductionReading
    from apps.monitoring.models_warranty import ProductionWarranty
    from apps.monitoring.services import production_warranty_status
    from apps.monitoring.report_warranty import build_warranty_report_data
    from apps.parametres.models import CompanyProfile
    H = {'HTTP_HOST': 'localhost'}
    J = date(2026, 11, 7)
    co = Company.objects.create(nom='Sonde AMON 040', slug='sonde-amon-040')
    prof, _ = CompanyProfile.objects.get_or_create(company=co)
    prof.garantie_production_autorisee = True
    prof.save()
    u = get_user_model().objects.create_user('amon040_resp', password='x', company=co, role_legacy='responsable')
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON040', email='amon040@example.invalid')

    def systeme(ref, mes):
        inst = Installation.objects.create(company=co, reference=ref, client=cl,
                                           puissance_installee_kwc=Decimal('7.00'), date_mise_en_service=mes)
        cfg = MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('12000'))
        n = (J - mes).days + 1
        ProductionReading.objects.bulk_create([
            ProductionReading(company=co, installation=inst, date=mes + timedelta(days=i),
                              energy_kwh=Decimal('32.88'), period_days=1) for i in range(n)])
        w = ProductionWarranty.objects.create(company=co, installation=inst, guaranteed_year1_kwh=Decimal('12000'),
                                              degradation_pct_per_year=Decimal('0'), start_year=2026,
                                              compensation_mad_per_kwh=Decimal('1.10'), tolerance_pct=Decimal('5'))
        st = production_warranty_status(inst, today=J)
        r25 = build_warranty_report_data(inst, year=2025, today=J)
        r26 = build_warranty_report_data(inst, year=2026, today=J)
        route = api.get(f'/api/django/monitoring/warranties/{w.id}/status/', **H)
        pdf25 = api.get(f'/api/django/monitoring/configs/{cfg.id}/rapport-garantie-pdf/', {'annee': '2025'}, **H)
        rj = route.json() if route.status_code == 200 else {'err': str(route.content)[:150]}
        return {'releves': n, 'mise_en_service': mes.isoformat(),
                'status_service': {k: str(v) for k, v in st.items()},
                'status_route': {'http': route.status_code, 'year': rj.get('year'),
                                 'guaranteed_kwh': str(rj.get('guaranteed_kwh')), 'actual_kwh': str(rj.get('actual_kwh')),
                                 'compensation_mad': str(rj.get('compensation_mad')),
                                 'within_tolerance': rj.get('within_tolerance')},
                'rapport_2025': {'year_in_progress': r25.get('year_in_progress'),
                                 'guaranteed_year_kwh': str(r25.get('guaranteed_year_kwh')),
                                 'total_actual_kwh': str(r25.get('total_actual_kwh')),
                                 'total_penalite_mad': str(r25.get('total_penalite_mad'))},
                'rapport_2026_mois': [(m['month_label'], str(m['production_kwh']), str(m['penalite_cumulee_mad']))
                                      for m in r26.get('monthly', [])],
                'pdf_2025_http': pdf25.status_code, 'pdf_2025_type': pdf25.get('Content-Type')}

    obs = {'N_mes_08_09': systeme('CHT-AMON040-N', date(2026, 9, 8)),
           'T_temoin_01_01': systeme('CHT-AMON040-T', date(2026, 1, 1))}
    n, t = obs['N_mes_08_09'], obs['T_temoin_01_01']
    temoin_ok = Decimal(t['status_service']['compensation_mad']) == 0
    defaut_courant = (abs(Decimal(n['status_service']['compensation_mad']) - Decimal('8478.72')) < Decimal('5')
                      and n['status_service']['within_tolerance'] == 'False')
    defaut_2025 = (n['rapport_2025']['year_in_progress'] is False
                   and Decimal(n['rapport_2025']['total_penalite_mad']) == Decimal('12540.00')
                   and n['pdf_2025_http'] == 200)
    obs['temoin_ok'] = temoin_ok
    obs['defaut_courant'] = defaut_courant
    obs['defaut_2025'] = defaut_2025
    obs['repro'] = bool(temoin_ok and defaut_courant and defaut_2025)
    return obs

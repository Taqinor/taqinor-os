# flake8: noqa  (sonde d'audit de parcours PA7, critique T3, rejouable par scripts/sonde.py — METHODE §B.5)
"""T3 : registre carbone. Site S (seul site du client), 12 relevés mensuels de 500 kWh en 2025 (= 4,860 t à 0,81) +
un relevé de janvier 2026. Vraie route POST certificats-carbone : (A) site 2025 entier, (B) site juin 2025, (C) client
consolidé 2025 entier, (D) site 01/01/2026 → 31/12/2027 (fin FUTURE). L'anti-double-comptage ne refuse-t-il que le
doublon EXACT (registre 10,125 t pour 4,860 t réelles) ? Puis DELETE (vraie route) du relevé de juin : B garde 0,405 t,
une ré-émission de juin → 409, l'attestation de juin dit « aucune production ». L'attestation imprime-t-elle une
référence de certificat ? Témoin : ré-émission EXACTE de A → 409."""
SONDE = {"constat": "C-AMON-042", "sha": "51dac387b",
         "attendu": "repro si A,B,C,D = 201 (somme 2025 = 10.125 t), témoin A bis 409, après DELETE juin : B 0.405 inchangé, "
                    "ré-émission juin 409, attestation juin sans donnée, aucune référence dans le HTML de l'attestation",
         "modeles": ["monitoring.CertificatCarbone", "monitoring.ProductionReading"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import CertificatCarbone, MonitoringConfig, ProductionReading
    from apps.monitoring.report_carbon import build_carbon_report_data_site, _build_html
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AMON 042', slug='sonde-amon-042')
    u = get_user_model().objects.create_user('amon042_resp', password='x', company=co, role_legacy='responsable')
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON042', email='amon042@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-AMON042', client=cl,
                                       puissance_installee_kwc=Decimal('4.00'), date_mise_en_service=date(2024, 12, 1))
    MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('6000'))
    ProductionReading.objects.bulk_create(
        [ProductionReading(company=co, installation=inst, date=date(2025, m, 1), energy_kwh=Decimal('500'),
                           period_days=28 if m == 2 else (30 if m in (4, 6, 9, 11) else 31)) for m in range(1, 13)]
        + [ProductionReading(company=co, installation=inst, date=date(2026, 1, 1), energy_kwh=Decimal('500'),
                             period_days=31)])

    def emettre(cible, debut, fin):
        corps = {'periode_debut': debut, 'periode_fin': fin}
        corps.update(cible)
        r = api.post('/api/django/monitoring/certificats-carbone/', corps, format='json', **H)
        j = r.json() if r.status_code in (200, 201) else {}
        return {'http': r.status_code, 'tco2': j.get('tco2_evitees'), 'id': j.get('id'), 'reference': j.get('reference'),
                'detail': None if r.status_code < 400 else str(r.content.decode('utf-8', 'replace'))[:120]}

    site, client = {'installation_id': inst.id}, {'client_id': cl.id}
    obs = {'A_site_2025': emettre(site, '2025-01-01', '2025-12-31'),
           'B_site_juin': emettre(site, '2025-06-01', '2025-06-30'),
           'C_client_2025': emettre(client, '2025-01-01', '2025-12-31'),
           'D_site_fin_future': emettre(site, '2026-01-01', '2027-12-31'),
           'temoin_A_bis': emettre(site, '2025-01-01', '2025-12-31')}
    somme_2025 = sum(Decimal(str(obs[k]['tco2'])) for k in ('A_site_2025', 'B_site_juin', 'C_client_2025')
                     if obs[k]['tco2'] is not None)
    obs['registre_somme_2025_t'] = str(somme_2025)
    juin = ProductionReading.objects.get(installation=inst, date=date(2025, 6, 1))
    rd = api.delete(f'/api/django/monitoring/readings/{juin.id}/', **H)
    obs['delete_releve_juin_http'] = rd.status_code
    b_id = obs['B_site_juin']['id']
    obs['B_apres_suppression_tco2'] = str(CertificatCarbone.objects.get(pk=b_id).tco2_evitees) if b_id else None
    obs['reemission_juin'] = emettre(site, '2025-06-01', '2025-06-30')
    d_juin = build_carbon_report_data_site(inst, since=date(2025, 6, 1), until=date(2025, 6, 30))
    obs['attestation_juin_has_data'] = d_juin.get('has_data')
    d_an = build_carbon_report_data_site(inst, since=date(2025, 1, 1), until=date(2025, 12, 31))
    html = _build_html(d_an, entreprise_nom='Sonde')
    obs['attestation_2025_tonnes_apres'] = str(d_an.get('co2_tonnes'))
    obs['attestation_html_contient_reference'] = bool(obs['A_site_2025']['reference']
                                                       and obs['A_site_2025']['reference'] in html)
    obs['attestation_html_contient_CERT'] = 'CERT-CO2' in html
    obs['fichier_key_A'] = (CertificatCarbone.objects.filter(pk=obs['A_site_2025']['id'])
                            .values_list('fichier_key', flat=True).first() if obs['A_site_2025']['id'] else None)
    temoin_ok = obs['temoin_A_bis']['http'] == 409
    defaut = (all(obs[k]['http'] == 201 for k in ('A_site_2025', 'B_site_juin', 'C_client_2025', 'D_site_fin_future'))
              and somme_2025 == Decimal('10.125') and rd.status_code == 204
              and obs['B_apres_suppression_tco2'] in ('0.405', '0.41', '0.4050')
              and obs['reemission_juin']['http'] == 409 and not obs['attestation_juin_has_data']
              and not obs['attestation_html_contient_CERT'])
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs

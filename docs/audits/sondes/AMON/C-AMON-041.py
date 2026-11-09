# flake8: noqa  (sonde d'audit de parcours PA7, critique T2, rejouable par scripts/sonde.py — METHODE §B.5)
"""T2 : la société règle son facteur réseau sourcé (CompanyProfile.facteur_co2_reseau_g_kwh = 630, source, date —
AMOT100 / D-ACI-19, lu par le devis C&I). Site : 12 relevés mensuels de 500 kWh en 2025 (6 000 kWh). Le certificat du
registre (vraie route POST certificats-carbone) et l'attestation (données + route PDF) prennent-ils 0,81 kg/kWh codé en
dur (4,860 t) au lieu de 0,630 (3,780 t), méthodologie sans source ? (B) société SANS facteur réglé : certificat chiffré
quand même (le devis, lui, n'imprime rien). Témoin : `facteur_co2_societe` (devis) lit bien 630 + source."""
SONDE = {"constat": "C-AMON-041", "sha": "51dac387b",
         "attendu": "repro si A : tco2 4.860 (attendu 3.780), co2_kg_par_kwh 0.81, methodologie sans la source ; "
                    "B : certificat 201 chiffré sans facteur réglé ; témoin devis : 630 + source",
         "modeles": ["monitoring.CertificatCarbone", "monitoring.ProductionReading"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from types import SimpleNamespace
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import MonitoringConfig, ProductionReading
    from apps.monitoring.report_carbon import build_carbon_report_data_site
    from apps.parametres.models import CompanyProfile
    from apps.ventes.quote_engine.reglages_societe import facteur_co2_societe
    H = {'HTTP_HOST': 'localhost'}

    def societe(slug, facteur):
        co = Company.objects.create(nom=f'Sonde {slug}', slug=slug)
        prof, _ = CompanyProfile.objects.get_or_create(company=co)
        if facteur:
            prof.facteur_co2_reseau_g_kwh = Decimal(facteur)
            prof.facteur_co2_reseau_source = 'ONEE — rapport annuel 2025'
            prof.facteur_co2_reseau_date = date(2026, 1, 15)
            prof.save()
        u = get_user_model().objects.create_user(f'{slug}-resp', password='x', company=co, role_legacy='responsable')
        api = APIClient()
        api.force_authenticate(u)
        cl = Client.objects.create(company=co, nom='Client', prenom=slug, email=f'{slug}@example.invalid')
        inst = Installation.objects.create(company=co, reference=f'CHT-{slug}', client=cl,
                                           puissance_installee_kwc=Decimal('4.00'), date_mise_en_service=date(2024, 12, 1))
        cfg = MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('6000'))
        ProductionReading.objects.bulk_create([
            ProductionReading(company=co, installation=inst, date=date(2025, m, 1), energy_kwh=Decimal('500'),
                              period_days=28 if m == 2 else (30 if m in (4, 6, 9, 11) else 31)) for m in range(1, 13)])
        r = api.post('/api/django/monitoring/certificats-carbone/', {
            'installation_id': inst.id, 'periode_debut': '2025-01-01', 'periode_fin': '2025-12-31'}, format='json', **H)
        d = build_carbon_report_data_site(inst, since=date(2025, 1, 1), until=date(2025, 12, 31))
        pdf = api.get(f'/api/django/monitoring/configs/{cfg.id}/attestation-carbone-pdf/',
                      {'since': '2025-01-01', 'until': '2025-12-31'}, **H)
        devis_facteur = facteur_co2_societe(SimpleNamespace(company=co))
        rj = r.json() if r.status_code in (200, 201) else {'err': str(r.content)[:150]}
        return {'certificat_http': r.status_code, 'tco2_evitees': str(rj.get('tco2_evitees')),
                'reference': rj.get('reference'),
                'attestation_co2_kg_par_kwh': str(d.get('co2_kg_par_kwh')), 'attestation_co2_tonnes': str(d.get('co2_tonnes')),
                'methodologie_cite_source': 'ONEE' in (d.get('methodologie') or ''),
                'methodologie_extrait': (d.get('methodologie') or '')[:170],
                'pdf_http': pdf.status_code, 'devis_facteur_co2_societe': devis_facteur}

    obs = {'A_facteur_630': societe('sonde-amon-041-a', '630'), 'B_sans_facteur': societe('sonde-amon-041-b', None)}
    a, b = obs['A_facteur_630'], obs['B_sans_facteur']
    temoin_ok = bool(a['devis_facteur_co2_societe'] and a['devis_facteur_co2_societe'].get('g_kwh') == 630.0
                     and b['devis_facteur_co2_societe'] is None)
    defaut_a = (a['certificat_http'] == 201 and a['tco2_evitees'] in ('4.860', '4.86')
                and a['attestation_co2_kg_par_kwh'] == '0.81' and not a['methodologie_cite_source'])
    defaut_b = b['certificat_http'] == 201 and b['tco2_evitees'] in ('4.860', '4.86')
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut_a and defaut_b)
    return obs

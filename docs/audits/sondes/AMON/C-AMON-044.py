# flake8: noqa  (sonde d'audit de parcours PA7, critique T5, rejouable par scripts/sonde.py — METHODE §B.5)
"""T5 : système sain à production SAISONNIÈRE (2025, attendu plat 12 000 kWh/an) — relevés mensuels 700 … 1 350 (juin)
… 650 (décembre). Au 31/12/2025 : `soiling_assessment` lit-il la saison comme de l'encrassement (perte ≥ 60 points,
nettoyage recommandé « chute de PR significative »), `pertes_categorisees.soiling_pct` idem, et le rapport O&M mensuel
client recommande-t-il « Nettoyage des panneaux recommandé. » ? Puis `CleaningEvent` le 20/12 : la base est-elle remise
(attendu : oui) ou la recommandation persiste-t-elle ? Témoin : même système produisant exactement l'attendu au prorata des jours (PR 100 % chaque mois) → aucune reco."""
SONDE = {"constat": "C-AMON-044", "sha": "51dac387b",
         "attendu": "repro si S : perte ≥ 60, recommend True, soiling_pct ≥ 60, reco rapport présente ; après nettoyage "
                    "20/12 : perte inchangée et recommend True ; témoin plat : recommend False",
         "modeles": ["monitoring.ProductionReading", "monitoring.CleaningEvent"]}


def sonde(ctx):
    import calendar
    from datetime import date
    from decimal import Decimal
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import CleaningEvent, MonitoringConfig, ProductionReading
    from apps.monitoring.analytics import pertes_categorisees, soiling_assessment
    from apps.monitoring.report import build_om_report_data
    J = date(2025, 12, 31)
    co = Company.objects.create(nom='Sonde AMON 044', slug='sonde-amon-044')
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON044', email='amon044@example.invalid')
    saison = [700, 800, 1000, 1150, 1300, 1350, 1350, 1250, 1100, 950, 750, 650]

    def systeme(ref, serie):
        inst = Installation.objects.create(company=co, reference=ref, client=cl,
                                           puissance_installee_kwc=Decimal('7.00'), date_mise_en_service=date(2024, 12, 1))
        MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('12000'))
        ProductionReading.objects.bulk_create([
            ProductionReading(company=co, installation=inst, date=date(2025, m, 1), energy_kwh=Decimal(str(serie[m - 1])),
                              period_days=calendar.monthrange(2025, m)[1]) for m in range(1, 13)])
        s = soiling_assessment(inst, today=J)
        p = pertes_categorisees(inst, today=J)
        r = build_om_report_data(inst, period='monthly', today=J)
        avant = {'baseline_pr': str(s['baseline_pr_pct']), 'current_pr': str(s['current_pr_pct']),
                 'perte': str(s['estimated_soiling_loss_pct']), 'recommend': s['recommend_cleaning'],
                 'reasons': s['reasons'], 'soiling_pct_pertes': str(p.get('soiling_pct')),
                 'reco_rapport': r.get('recommendations')}
        CleaningEvent.objects.create(company=co, installation=inst, date=date(2025, 12, 20), note='Nettoyage sonde')
        s2 = soiling_assessment(inst, today=J)
        apres = {'perte': str(s2['estimated_soiling_loss_pct']), 'recommend': s2['recommend_cleaning'],
                 'reasons': s2['reasons'], 'last_cleaning_date': s2['last_cleaning_date']}
        return {'avant_nettoyage': avant, 'apres_nettoyage_20_12': apres}

    obs = {'S_saisonnier': systeme('CHT-AMON044-S', saison), 'T_plat': systeme('CHT-AMON044-T', [round(12000 * calendar.monthrange(2025, m)[1] / 365, 2)
                                                          for m in range(1, 13)])}
    s, t = obs['S_saisonnier'], obs['T_plat']
    temoin_ok = t['avant_nettoyage']['recommend'] is False
    defaut = (float(s['avant_nettoyage']['perte']) >= 60 and s['avant_nettoyage']['recommend'] is True
              and float(s['avant_nettoyage']['soiling_pct_pertes']) >= 60
              and 'Nettoyage des panneaux recommandé.' in (s['avant_nettoyage']['reco_rapport'] or [])
              and s['apres_nettoyage_20_12']['perte'] == s['avant_nettoyage']['perte']
              and s['apres_nettoyage_20_12']['recommend'] is True)
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs

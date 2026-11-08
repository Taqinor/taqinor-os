# flake8: noqa  (sonde d'audit de parcours PA7, critique T4, rejouable par scripts/sonde.py — METHODE §B.5)
"""T4 : onduleur du chantier immobilisé du 01/10 au 16/10/2026 00:00 (SAV `ouvrir_downtime`, XSAV16) + alarme onduleur
critique `escaladee` (FG280). Relevés mensuels CSV-like (un relevé daté du 1er, period_days = jours du mois) sur
les 12 derniers mois, dont octobre. Au 31/10 : SAV dit-il ≈ 51,6 % de disponibilité en octobre pendant que monitoring
(`om_metrics` / `disponibilite_vs_garantie`, SLA 98 % · 200 MAD/j, garantie autorisée) dit 100 %, écart 0, pénalité 0,
et que le rapport O&M mensuel client imprime « Disponibilité 100 % », 0 alarme ouverte, « Aucune action requise » ?
Témoin : `disponibilite_equipement` sans immobilisation → 100 %."""
SONDE = {"constat": "C-AMON-043", "sha": "51dac387b",
         "attendu": "repro si SAV octobre ≈ 51.6 %, monitoring 100 %, sous_garantie False, pénalité 0, rapport client "
                    "availability 100 / open_alarms 0 avec alarme escaladée ; témoin SAV 100 %",
         "modeles": ["monitoring.SlaDisponibilite", "monitoring.ProductionReading", "sav.EquipementDowntime",
                     "sav.AlarmeOnduleur", "sav.Equipement"]}


def sonde(ctx):
    import calendar
    from datetime import date, datetime
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import MonitoringConfig, ProductionReading, SlaDisponibilite
    from apps.monitoring.analytics import om_metrics
    from apps.monitoring.selectors import disponibilite_vs_garantie
    from apps.monitoring.report import build_om_report_data
    from apps.parametres.models import CompanyProfile
    from apps.sav.models import AlarmeOnduleur, Equipement
    from apps.sav.services import disponibilite_equipement, ouvrir_downtime
    from apps.stock.models import Produit
    tz = timezone.get_current_timezone()
    J = date(2026, 10, 31)
    co = Company.objects.create(nom='Sonde AMON 043', slug='sonde-amon-043')
    prof, _ = CompanyProfile.objects.get_or_create(company=co)
    prof.garantie_production_autorisee = True
    prof.save()
    u = get_user_model().objects.create_user('amon043_resp', password='x', company=co, role_legacy='responsable')
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON043', email='amon043@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-AMON043', client=cl,
                                       puissance_installee_kwc=Decimal('7.00'), date_mise_en_service=date(2025, 6, 1))
    MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('12000'))
    mois = [(2025, m) for m in range(10, 13)] + [(2026, m) for m in range(1, 11)]
    ProductionReading.objects.bulk_create([
        ProductionReading(company=co, installation=inst, date=date(y, m, 1), energy_kwh=Decimal('1000'),
                          period_days=calendar.monthrange(y, m)[1]) for y, m in mois])
    SlaDisponibilite.objects.create(company=co, installation=inst, disponibilite_garantie_pct=Decimal('98'),
                                    compensation_mad_par_jour_indispo=Decimal('200'))
    p = Produit.objects.create(company=co, nom='Onduleur sonde', sku='SONDE-AMON-043', prix_vente=Decimal('9000'),
                               quantite_stock=0)
    eq = Equipement.objects.create(company=co, produit=p, installation=inst, numero_serie='OND-043',
                                   date_pose=date(2025, 6, 1))
    eq_t = Equipement.objects.create(company=co, produit=p, installation=inst, numero_serie='OND-043-T',
                                     date_pose=date(2025, 6, 1))
    d0 = timezone.make_aware(datetime(2026, 10, 1, 0, 0), tz)
    d1 = timezone.make_aware(datetime(2026, 10, 16, 0, 0), tz)
    fin_mois = timezone.make_aware(datetime(2026, 11, 1, 0, 0), tz)
    dt = ouvrir_downtime(company=co, equipement=eq, debut=d0, motif='Onduleur HS', created_by=u)
    dt.fin = d1
    dt.save()
    AlarmeOnduleur.objects.create(company=co, equipement=eq, code='E07', gravite='critique',
                                  libelle='Défaut isolement', date_detection=d0, statut='escaladee')
    sav = disponibilite_equipement(eq, debut_periode=d0, fin_periode=fin_mois)
    sav_t = disponibilite_equipement(eq_t, debut_periode=d0, fin_periode=fin_mois)
    om31 = om_metrics(inst, window_days=31, today=J)
    sla = disponibilite_vs_garantie(inst, window_days=31, today=J)
    rap = build_om_report_data(inst, period='monthly', today=J)
    obs = {'sav_octobre': sav, 'sav_temoin': sav_t,
           'monitoring_availability_31j': str(om31.get('availability_pct')),
           'sla': {k: str(v) for k, v in sla.items()},
           'rapport_client': {'availability_pct': str(rap.get('availability_pct')), 'open_alarms': rap.get('open_alarms'),
                              'recommendations': rap.get('recommendations'), 'period_days': rap.get('period_days')}}
    temoin_ok = sav_t['disponibilite_pct'] == 100.0
    defaut = (abs(sav['disponibilite_pct'] - 51.61) < 0.2 and str(om31.get('availability_pct')) in ('100', '100.00')
              and sla.get('sous_garantie') is False and str(sla.get('penalite_mad')) in ('0', '0.00')
              and str(rap.get('availability_pct')) in ('100', '100.00') and rap.get('open_alarms') == 0)
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs

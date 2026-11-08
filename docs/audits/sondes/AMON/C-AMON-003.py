# flake8: noqa  (sonde d'audit de parcours PA7, rejouable par scripts/sonde.py — METHODE §C.4)
"""K03 — convention de date d'un relevé. Le serveur lit un relevé comme couvrant [date, date + période)
(analytics.jours_couverts_par_releves) ; l'écran (ProductionPage) pré-remplit « Date = aujourd'hui,
Période 30 j » sous le seul libellé « Date ». Mêmes 12 relevés mensuels (mêmes kWh) saisis datés du DÉBUT
de mois (système A) ou de la FIN de mois (système B, le geste « relevé du compteur lu ce jour ») :
la disponibilité mesurée et la pénalité SLA diffèrent alors que chaque jour a son relevé.
Vraie route pour le geste écran (POST readings/ avec date du jour + 30 j) ; om_metrics / disponibilite_vs_garantie
appelés en direct (mécanisme interne, `today` fixé au 31/10/2026)."""
SONDE = {"constat": "C-AMON-003", "sha": "3007f3f04",
         "attendu": "repro si A (début de mois) ≈ 100 % et B (fin de mois) < 98 % avec pénalité/écart alors que les "
                    "relevés sont identiques ; et le geste écran par défaut (aujourd'hui, 30 j) est accepté 201",
         "modeles": ["monitoring.ProductionReading", "monitoring.SlaDisponibilite", "installations.Installation"]}


def sonde(ctx):
    import calendar
    from datetime import date, timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import MonitoringConfig, ProductionReading, SlaDisponibilite
    from apps.monitoring.analytics import om_metrics, jours_couverts_par_releves
    from apps.monitoring.selectors import disponibilite_vs_garantie
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AMON 003', slug='sonde-amon-003')
    profil_ok = None
    try:
        from apps.parametres.models import CompanyProfile
        p, _ = CompanyProfile.objects.get_or_create(company=co)
        p.garantie_production_autorisee = True
        p.save()
        profil_ok = True
    except Exception as exc:  # noqa
        profil_ok = f'profil non posé : {exc!r}'[:120]
    u = get_user_model().objects.create_user(username='sonde_amon_003', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)

    def systeme(ref):
        cl = Client.objects.create(company=co, nom='Client', prenom=ref, email=f'{ref.lower()}@example.invalid')
        inst = Installation.objects.create(company=co, reference=ref, client=cl, puissance_installee_kwc=Decimal('4'))
        MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('6000'))
        SlaDisponibilite.objects.create(company=co, installation=inst, disponibilite_garantie_pct=Decimal('98'),
                                        compensation_mad_par_jour_indispo=Decimal('100'))
        return inst

    A, B = systeme('CH-AMON-003A'), systeme('CH-AMON-003B')
    mois = [(2025, 11), (2025, 12)] + [(2026, m) for m in range(1, 11)]
    for (y, m) in mois:
        nj = calendar.monthrange(y, m)[1]
        ProductionReading.objects.create(company=co, installation=A, date=date(y, m, 1), period_days=nj,
                                         energy_kwh=Decimal('500'))
        ProductionReading.objects.create(company=co, installation=B, date=date(y, m, nj), period_days=nj,
                                         energy_kwh=Decimal('500'))
    today = date(2026, 10, 31)
    out = {}
    for nom, inst in (('A_debut_de_mois', A), ('B_fin_de_mois', B)):
        mtr = om_metrics(inst, today=today)
        dv = disponibilite_vs_garantie(inst, today=today)
        out[nom] = {'production_kwh': str(mtr['production_kwh']), 'pr_pct': str(mtr['pr_pct']),
                    'availability_pct': str(mtr['availability_pct']),
                    'ecart_pct': str(dv.get('ecart_pct')), 'sous_garantie': dv.get('sous_garantie'),
                    'penalite_mad': str(dv.get('penalite_mad'))}
    # Geste écran par défaut : date = aujourd'hui, période 30 (ProductionPage.jsx l. 55/159)
    C = systeme('CH-AMON-003C')
    jour = timezone.localdate()
    r = api.post('/api/django/monitoring/readings/', {
        'installation': C.id, 'date': jour.isoformat(), 'period_days': 30, 'energy_kwh': '450'}, format='json', **H)
    couverts_futurs = jours_couverts_par_releves([(jour, 30)], jour + timedelta(days=1), jour + timedelta(days=60))
    out['geste_ecran_defaut'] = {'http': r.status_code, 'date': jour.isoformat(),
                                 'jours_couverts_APRES_aujourdhui_par_ce_releve': couverts_futurs}
    out['profil_garantie_autorisee'] = profil_ok
    a, b = out['A_debut_de_mois'], out['B_fin_de_mois']
    defaut = (Decimal(a['availability_pct']) >= Decimal('99') and Decimal(b['availability_pct']) < Decimal('98')
              and a['production_kwh'] == b['production_kwh'] and r.status_code == 201)
    out['repro'] = bool(defaut)
    return out

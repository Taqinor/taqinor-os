# flake8: noqa  (sonde d'audit de parcours PA7, seconde lentille, rejouable par scripts/sonde.py — METHODE §B.5)
"""K21 seconde lentille — RÉGLAGE PAR DÉFAUT de la société et gestes exacts de l'écran.
La sonde d'origine forçait `garantie_production_autorisee=True` ; ici le profil société garde son défaut (False),
le SLA est créé par le corps exact de `SlaDisponibiliteSection.jsx::enregistrer` (compensation vide → '0', puis 200
tapé) et l'écart est lu par l'appel exact de `calculer` (GET ecart SANS paramètre). Relevés saisis par le corps de
`ProductionPage.addReading` (défaut 30 j). Cas : (M) système en service depuis 400 j dont la supervision n'a démarré
qu'il y a 90 j (3 relevés mensuels sains) ; (N) neuf, en service depuis 60 j, 2 relevés mensuels sains ;
(T) témoin 400 j, 13 relevés mensuels sains. Mesure aussi la carte « Disponibilité » du rapport O&M mensuel (client)."""
SONDE = {"constat": "C-AMON-021", "sha": "39313d48e",
         "attendu": "repro si, au réglage par défaut, M et N sortent « sous la garantie » (mesurée << 98) et le rapport "
                    "mensuel client imprime cette disponibilité ; témoin T ≈ 100 ; pénalité attendue None (réglage éteint)",
         "modeles": ["monitoring.SlaDisponibilite", "monitoring.ProductionReading"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import MonitoringConfig
    from apps.monitoring.selectors import _garantie_production_autorisee
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde AMON 021 L2', slug='sonde-amon-021-l2')
    u = get_user_model().objects.create_user('amon021l2_resp', password='x', company=co, role_legacy='responsable')
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON021L2', email='amon021l2@example.invalid')

    def systeme(ref, mes_jours, nb_mois, compensation):
        inst = Installation.objects.create(company=co, reference=ref, client=cl,
                                           puissance_installee_kwc=Decimal('5.00'),
                                           date_mise_en_service=today - timedelta(days=mes_jours))
        cfg = MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('9000'))
        codes = []
        for k in range(nb_mois, 0, -1):  # relevés mensuels contigus, le dernier se termine aujourd'hui
            jour = today - timedelta(days=30 * k - 1)
            r = api.post('/api/django/monitoring/readings/', {
                'installation': inst.id, 'date': jour.isoformat(), 'energy_kwh': '739.73',
                'period_days': 30, 'note': ''}, format='json', **H)
            codes.append(r.status_code)
        s = api.post('/api/django/monitoring/sla-disponibilite/', {
            'installation': inst.id, 'disponibilite_garantie_pct': '98',
            'compensation_mad_par_jour_indispo': compensation or '0'}, format='json', **H)
        sid = s.json().get('id') if s.status_code in (200, 201) else None
        e = api.get(f'/api/django/monitoring/sla-disponibilite/{sid}/ecart/', **H)
        r = api.get(f'/api/django/monitoring/configs/{cfg.id}/om-report/', {'period': 'monthly'}, **H)
        ej = e.json() if e.status_code == 200 else {'err': str(e.content)[:150]}
        rj = r.json() if r.status_code == 200 else {'err': str(r.content)[:150]}
        return {'releves_http': sorted(set(codes)), 'sla_http': s.status_code, 'ecart_http': e.status_code,
                'window_days': ej.get('window_days'), 'mesuree': str(ej.get('disponibilite_mesuree_pct')),
                'sous_garantie': ej.get('sous_garantie'), 'jours_exc': str(ej.get('jours_indisponibilite_excedentaire')),
                'penalite_mad': str(ej.get('penalite_mad')), 'libelle': ej.get('libelle_indicateur'),
                'rapport_period_days': rj.get('period_days'), 'rapport_availability_pct': str(rj.get('availability_pct')),
                'rapport_pr_pct': str(rj.get('pr_pct'))}

    obs = {'today': today.isoformat(),
           'reglage_garantie_production_autorisee': None,
           'M_supervision_tardive_400j_90j': systeme('CHT-AMON021L2-M', 400, 3, ''),
           'N_neuf_60j_comp200': systeme('CHT-AMON021L2-N', 60, 2, '200'),
           'T_temoin_400j': systeme('CHT-AMON021L2-T', 400, 13, '')}
    inst0 = Installation.objects.filter(company=co).first()
    obs['reglage_garantie_production_autorisee'] = _garantie_production_autorisee(inst0)

    def f(x):
        try:
            return float(x)
        except Exception:
            return None
    m, n, t = obs['M_supervision_tardive_400j_90j'], obs['N_neuf_60j_comp200'], obs['T_temoin_400j']
    temoin_ok = t['ecart_http'] == 200 and (f(t['mesuree']) or 0) >= 98 and t['sous_garantie'] is False
    defaut = all(x['sous_garantie'] is True and (f(x['mesuree']) or 100) < 30
                 and (f(x['rapport_availability_pct']) or 100) < 30 for x in (m, n))
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs

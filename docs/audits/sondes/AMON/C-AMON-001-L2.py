# flake8: noqa  (sonde d'audit de parcours PA7, seconde lentille, rejouable par scripts/sonde.py — METHODE §B.5)
"""K01 seconde lentille — chemin ÉCRAN seul (aucun import CSV : la route import-releves n'a aucun appelant front).
Corps exact de `frontend/src/pages/monitoring/ProductionPage.jsx::addReading` : {installation, date, energy_kwh,
period_days (défaut du formulaire = 30), note}, posté par un compte au rôle système « Technicien ».
(A) deux relevés « mensuels » au défaut 30 j, datés 01/10 et 15/10 (15 jours de recouvrement) ;
(B) un journalier (période 1) le 05/09 puis la même date resaisie au défaut 30 j (le cas « date déjà saisie »
d'ASAV66, mais avec la période que l'écran envoie vraiment). Témoin : le double clic exact → 409."""
SONDE = {"constat": "C-AMON-001", "sha": "39313d48e",
         "attendu": "repro si les relevés chevauchants de l'écran sont acceptés (201) et que l'énergie est sommée deux fois "
                    "(année 2026 / CO2 > énergie réelle, disponibilité = union) ; témoin : double clic exact 409",
         "modeles": ["monitoring.ProductionReading", "monitoring.UnderperformanceFlag"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import MonitoringConfig, ProductionReading
    from apps.monitoring.selectors import co2_for_installation
    from apps.monitoring.services import production_for_calendar_year
    from apps.monitoring.analytics import jours_couverts_par_releves
    from apps.roles.models import Role
    from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AMON 001 L2', slug='sonde-amon-001-l2')
    role = Role.objects.create(company=co, nom='Technicien', permissions=list(TECHNICIEN_PERMISSIONS), est_systeme=True)
    u = get_user_model().objects.create_user(username='amon001l2_tech', password='x', company=co, role=role)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON1L2', email='amon1l2@example.invalid')
    inst = Installation.objects.create(company=co, reference='CH-AMON-001-L2', client=cl,
                                       puissance_installee_kwc=Decimal('4'))
    MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('6000'))

    def ecran(jour, kwh, periode=30, note=''):  # = ProductionPage.addReading
        r = api.post('/api/django/monitoring/readings/', {
            'installation': inst.id, 'date': jour, 'energy_kwh': kwh, 'period_days': periode, 'note': note},
            format='json', **H)
        return r.status_code if r.status_code != 201 else 201

    a1 = ecran('2026-10-01', '450', note='relevé octobre')
    a2 = ecran('2026-10-15', '450', note='relevé mi-mois')
    a_dup = ecran('2026-10-15', '450', note='double clic')
    b1 = ecran('2026-09-05', '15', periode=1)
    b2 = ecran('2026-09-05', '450', note='mensuel resaisi au défaut 30 j')
    rel = list(ProductionReading.objects.filter(installation=inst).values_list('date', 'period_days', 'energy_kwh'))
    jours_union = jours_couverts_par_releves([(d, p) for d, p, _ in rel], date(2026, 9, 1), date(2026, 11, 7))
    jours_lignes = sum(int(p) for _, p, _ in rel)
    obs = {'role_http': {'A_01_10': a1, 'A_15_10': a2, 'A_double_clic': a_dup, 'B_journalier_05_09': b1,
                         'B_mensuel_meme_date': b2},
           'releves': [(d.isoformat(), p, str(e)) for d, p, e in rel],
           'jours_couverts_union': jours_union, 'jours_couverts_somme_lignes': jours_lignes,
           'annee_2026_kwh': str(production_for_calendar_year(inst, 2026)),
           'co2_octobre_kwh': str(co2_for_installation(inst, since=date(2026, 10, 1),
                                                       until=date(2026, 10, 31))['production_kwh'])}
    temoin_ok = a1 == 201 and a_dup == 409
    defaut = (a2 == 201 and b2 == 201 and jours_lignes > jours_union
              and Decimal(obs['co2_octobre_kwh']) >= Decimal('900'))
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs

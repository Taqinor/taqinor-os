# flake8: noqa  (sonde d'audit de parcours PA7, rejouable par scripts/sonde.py — METHODE §C.4)
"""K26 : (A) rattrapage à l'écran — auto-ticket actif, système sain (750 kWh/mois, attendu 9 000/an) mis en service
il y a 371 j ; on saisit ses 12 relevés mensuels UN PAR UN par la vraie route POST readings/ (chaque saisie
ré-évalue). Un ticket « sous-performance » naît-il au 1er relevé et reste-t-il ouvert quand le drapeau se ferme ?
(B) l'épisode suivant (relevés qui s'arrêtent, beat daté J+100) crée-t-il un 2e ticket alors que le 1er est
toujours ouvert ?"""
SONDE = {"constat": "C-AMON-026", "sha": "39313d48e",
         "attendu": "repro si A : ticket créé au 1er relevé (ratio ≈8.89) puis drapeau fermé et ticket ouvert ; B : 2 tickets préventifs ouverts",
         "modeles": ["monitoring.UnderperformanceFlag", "monitoring.ProductionReading", "sav.Ticket"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.apps import apps as dj
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import MonitoringConfig, MonitoringSettings, UnderperformanceFlag
    from apps.monitoring.services import evaluate_underperformance
    Ticket = dj.get_model('sav', 'Ticket')
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde AMON 026', slug='sonde-amon-026')
    st = MonitoringSettings.get(co)
    st.auto_create_ticket = True
    st.save()
    u = get_user_model().objects.create_user('amon026_adm', password='x', company=co, role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON026', email='amon026@example.invalid')
    mes = today - timedelta(days=371)
    inst = Installation.objects.create(company=co, reference='CHT-AMON026', client=cl,
                                       puissance_installee_kwc=Decimal('5.00'), date_mise_en_service=mes)
    MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('9000'))

    def tickets():
        return list(Ticket.objects.filter(installation=inst, type=Ticket.Type.PREVENTIF)
                    .values_list('id', 'statut'))

    def drapeau():
        f = UnderperformanceFlag.objects.filter(installation=inst, is_open=True).first()
        return None if f is None else str(f.ratio_pct)
    trace = []
    for i in range(1, 13):
        jour = mes + timedelta(days=30 * i)
        r = api.post('/api/django/monitoring/readings/', {'installation': inst.id, 'date': jour.isoformat(),
                                                           'period_days': 30, 'energy_kwh': '750'}, format='json', **H)
        trace.append({'i': i, 'date': jour.isoformat(), 'http': r.status_code, 'drapeau': drapeau(),
                      'n_tickets': len(tickets())})
    fermes = list(UnderperformanceFlag.objects.filter(installation=inst, is_open=False)
                  .values_list('motif_cloture', flat=True))
    obs = {'A_saisie_une_par_une': trace, 'A_drapeaux_fermes': fermes, 'A_tickets': tickets()}
    # B — plus aucun relevé ; nouvelle évaluation à J+100.
    res = evaluate_underperformance(inst, today=today + timedelta(days=100))
    obs['B_ratio'] = str(res.get('ratio_pct'))
    obs['B_drapeau'] = drapeau()
    obs['B_tickets'] = tickets()
    t_ok = trace[0]['http'] == 201
    a = trace[0]['n_tickets'] == 1 and trace[-1]['drapeau'] is None and len(obs['A_tickets']) == 1
    b = len(obs['B_tickets']) == 2
    obs['repro'] = bool(t_ok and a and b)
    return obs

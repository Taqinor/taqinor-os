# flake8: noqa  (sonde d'audit de parcours PA7, rejouable par scripts/sonde.py — METHODE §C.4)
"""K04 — équipement remplacé (étape PA7 `monitoring_suit_remplacement`, MANQUANTE). Système sous-performant :
drapeau + ticket préventif T1 (auto-ticket actif). Sur T1 l'onduleur est retiré par le VRAI service
`sav.services.retirer_piece` (équipement « Remplacé », événement `equipement_remplace` émis), puis T1 est résolu.
Question : le monitoring clôt-il l'épisode ? Sinon le drapeau reste ouvert, lié à T1 résolu, le portail compte
« 1 alerte ouverte », et une réévaluation toujours basse n'ouvre AUCUN nouveau ticket."""
SONDE = {"constat": "C-AMON-004", "sha": "3007f3f04",
         "attendu": "repro si après retrait + T1 résolu + réévaluation : drapeau toujours ouvert, ticket_id == T1, "
                    "1 seul ticket sur le système, aucun récepteur monitoring de equipement_remplace",
         "modeles": ["monitoring.UnderperformanceFlag", "sav.Ticket", "sav.Equipement", "sav.PieceRetiree"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import MonitoringConfig, MonitoringSettings, ProductionReading, UnderperformanceFlag
    from apps.monitoring.services import evaluate_underperformance
    from apps.monitoring.selectors import underperformance_flags_client_portail
    from apps.sav.models import Equipement, Ticket
    from apps.sav.services import retirer_piece
    from apps.stock.models import Produit
    from core.events import equipement_remplace
    co = Company.objects.create(nom='Sonde AMON 004', slug='sonde-amon-004')
    u = get_user_model().objects.create_user(username='sonde_amon_004', password='x', role_legacy='admin', company=co)
    s = MonitoringSettings.get(co)
    s.auto_create_ticket = True
    s.underperf_threshold_pct = Decimal('20')
    s.save()
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON4', email='amon4@example.invalid')
    inst = Installation.objects.create(company=co, reference='CH-AMON-004', client=cl,
                                       puissance_installee_kwc=Decimal('4'))
    MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('6000'))
    today = timezone.localdate()
    for i in range(90, 0, -1):  # 90 jours à ~8 kWh/j quand ~16,4 attendus : ratio ~50 %
        ProductionReading.objects.create(company=co, installation=inst, date=today - timedelta(days=i),
                                         period_days=1, energy_kwh=Decimal('8'))
    r1 = evaluate_underperformance(inst, user=u)
    flag = UnderperformanceFlag.objects.filter(installation=inst, is_open=True).first()
    t1 = flag.ticket if flag else None
    onduleur = Produit.objects.create(company=co, nom='Onduleur AMON4', sku='OND-AMON4', prix_achat=1000,
                                      prix_vente=2000, quantite_stock=Decimal('0'))
    eq = Equipement.objects.create(company=co, produit=onduleur, installation=inst, numero_serie='SN-AMON4-1',
                                   created_by=u)
    retrait = None
    try:
        retirer_piece(company=co, ticket=t1, produit=onduleur, quantite=Decimal('1'), numero_serie='SN-AMON4-1',
                      destination='rebut', user=u)
        retrait = 'ok'
    except Exception as exc:  # noqa
        retrait = f'echec {exc!r}'[:160]
    eq.refresh_from_db()
    Ticket.objects.filter(pk=t1.pk).update(statut=Ticket.Statut.RESOLU)
    flag.refresh_from_db()
    apres_retrait = {'flag_ouvert': flag.is_open, 'ticket_id': flag.ticket_id, 'motif_cloture': flag.motif_cloture}
    r2 = evaluate_underperformance(inst, user=u)
    flag2 = UnderperformanceFlag.objects.filter(installation=inst, is_open=True).first()
    receveurs = []
    for entree in equipement_remplace.receivers:
        ref = entree[1]
        fn = ref() if callable(ref) else ref
        receveurs.append(getattr(fn, '__module__', '?') + '.' + getattr(fn, '__name__', '?'))
    obs = {'evaluation_1': {'ratio_pct': str(r1['ratio_pct']), 'underperforming': r1['underperforming']},
           'ticket_T1': t1 and t1.reference, 'retrait_piece': retrait, 'equipement_statut': eq.statut,
           'apres_retrait_et_T1_resolu': apres_retrait,
           'evaluation_2': {'ratio_pct': str(r2['ratio_pct']), 'underperforming': r2['underperforming']},
           'drapeau_ouvert_apres_reeval': bool(flag2), 'drapeau_ticket_id': flag2 and flag2.ticket_id,
           'T1_id': t1 and t1.pk, 'T1_statut': Ticket.objects.get(pk=t1.pk).statut,
           'tickets_sur_systeme': Ticket.objects.filter(installation=inst).count(),
           'alertes_portail_client': underperformance_flags_client_portail(co, cl.id).count(),
           'receveurs_equipement_remplace': receveurs}
    defaut = (t1 is not None and retrait == 'ok' and eq.statut == Equipement.Statut.REMPLACE and flag2 is not None
              and flag2.ticket_id == t1.pk and obs['tickets_sur_systeme'] == 1
              and not any('monitoring' in x for x in receveurs))
    obs['repro'] = bool(defaut)
    return obs

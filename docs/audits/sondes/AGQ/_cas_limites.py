import json, traceback
from decimal import Decimal
from datetime import date
from django.db import transaction
from django.contrib.auth import get_user_model


def P(*a):
    print('##', *a, flush=True)


def J(o, n=1200):
    return json.dumps(o, default=str, ensure_ascii=False)[:n]


with transaction.atomic():
    from apps.crm.models import Lead
    from apps.stock.models import Produit, FicheTechnique
    from apps.ventes.domain.pompage import etudier_pompage
    from apps.ventes.services import build_devis_auto, AutoDevisError
    from apps.crm.selectors import champs_devis_auto_manquants
    from apps.crm.services import visite_point_eau_requise
    from authentication.models import Company
    co = Company.objects.get(pk=4)
    User = get_user_model()
    user = User.objects.filter(company=co, is_active=True).exclude(role_legacy='').order_by('id').first()
    P('garantie_mois seeded:', [(p.nom[:30], p.garantie_mois) for p in Produit.objects.filter(company=co, pk__in=(311, 303, 268, 295))])
    # catalogue complet
    prix = {311: 28000, 312: 32000, 313: 36000, 314: 40000, 315: 44000, 316: 46000, 317: 52000, 318: 54000, 319: 60000, 320: 62000, 321: 75000}
    for pid, pv in prix.items():
        Produit.objects.filter(pk=pid).update(prix_vente=Decimal(pv), prix_achat=Decimal(int(pv * 0.8)))
    FicheTechnique.objects.create(company=co, produit_id=268, type_fiche='module', pmax_wc=Decimal('710'), vmp_v=Decimal('40.3'), voc_v=Decimal('48.6'), isc_a=Decimal('18.6'), imp_a=Decimal('17.6'))
    for pid, imax in ((298, 13), (299, 13), (300, 40), (301, 40), (302, 40), (303, 40), (304, 45), (305, 55), (306, 70), (307, 90)):
        FicheTechnique.objects.create(company=co, produit_id=pid, type_fiche='variateur_pompage', ond_mppt_v_min=Decimal('250'), ond_mppt_v_max=Decimal('750'), ond_v_max_abs=Decimal('800'), ond_i_max_mppt_a=Decimal(imax), ond_phases=3, var_v_sortie_v=Decimal('380'))
    base = dict(company=co, nom='Sonde AGQ L2', telephone='0600000002', type_installation='agricole', ville='Marrakech', gps_lat=Decimal('31.63'), gps_lng=Decimal('-8.0'), source_eau='forage', niveau_statique_m=Decimal('45'), niveau_statique_source='declare', debit_forage_m3h=Decimal('25'), debit_forage_source='foreur', profondeur_forage_m=Decimal('120'), raccordement='triphase', pompe_hmt_m=Decimal('70'), pompe_hmt_source='declaree')
    # L2 : seulement le debit souhaite (pompe_debit_m3h), pas de besoin
    l2 = Lead.objects.create(**dict(base, pompe_debit_m3h=Decimal('20')))
    P('L2 manquants', champs_devis_auto_manquants(l2), 'visite', visite_point_eau_requise(l2))
    s = etudier_pompage(co, {'alim': 'tri'}, lead=l2)
    P('L2 etude pompe', (s.get('pompe') or {}).get('nom'), 'conception', s.get('conception'), 'alertes', [a['code'] for a in s['alertes']])
    try:
        d = build_devis_auto(lead=l2, user=user, company=co, journal_auto={})
        P('L2 auto OK', d.reference)
    except AutoDevisError as e:
        P('L2 auto REFUS', e.message, '| field', e.field)
    # L3 : raccordement inconnu (alim absente)
    l3 = Lead.objects.create(**dict(base, nom='Sonde AGQ L3', raccordement='inconnu', besoin_eau_m3j=Decimal('120'), mois_irrigation=[4, 5, 6, 7, 8, 9, 10]))
    s = etudier_pompage(co, {}, lead=l3)
    P('L3 alim inconnue: pompe', (s.get('pompe') or {}).get('nom'), 'alertes', [(a['code'], a['message'][:90]) for a in s['alertes']])
    # L4 : mois_irrigation absents (besoin toute l'annee ?)
    l4 = Lead.objects.create(**dict(base, nom='Sonde AGQ L4', besoin_eau_m3j=Decimal('120')))
    s = etudier_pompage(co, {'alim': 'tri'}, lead=l4)
    P('L4 sans mois: besoin serie', (s.get('besoin') or {}).get('m3_jour_mois'), 'mois_critique', (s.get('conception') or {}).get('mois_critique'), 'champ', (s.get('champ') or {}).get('nb_panneaux'), 'couv', s.get('couverture_pct_mois'))
    # L1b again : journal complet + lignes + options kit cochees
    l1b = Lead.objects.create(**dict(base, nom='Sonde AGQ HMT70', besoin_eau_m3j=Decimal('120'), besoin_eau_source='client', culture='olivier', surface_irriguee_ha=Decimal('5'), irrigation_methode='goutte', region_agricole='haouz', mois_irrigation=[4, 5, 6, 7, 8, 9, 10], distance_forage_champ_m=Decimal('30'), pompe_alim_actuelle='butane', butane_bouteilles_jour=Decimal('2'), carburant_prix_unitaire_mad=Decimal('50'), carburant_prix_declare_le=date.today()))
    s = etudier_pompage(co, {'alim': 'tri'}, lead=l1b)
    P('L1b heures_pic vs equiv: mois_critique', s['conception']['mois_critique'], 'debit_conception', s['conception']['debit_conception_m3h'], 'heq', (s.get('production') or {}).get('heures_equivalentes_mois'), 'couv', s.get('couverture_pct_mois'), 'controle', (s.get('controle_conception') or {}).get('statut'))
    journal = {}
    try:
        devis = build_devis_auto(lead=l1b, user=user, company=co, journal_auto=journal)
        P('L1b journal codes', [(a.get('code'), a.get('message')[:110]) for a in journal.get('alertes', [])])
        from rest_framework.test import APIClient
        api = APIClient(HTTP_HOST='127.0.0.1')
        api.force_authenticate(user=user)
        from apps.ventes.models import ShareLink
        link = ShareLink.for_devis(devis)
        for path in ('/api/django/ventes/proposal/%s/' % link.token, '/api/django/ventes/public/proposal/%s/' % link.token, '/api/django/ventes/proposition/%s/' % link.token):
            r = api.get(path)
            if r.status_code == 200:
                dd = r.data if hasattr(r, 'data') else {}
                P('PUBLIC', path, 'keys', sorted(dd.keys())[:40] if isinstance(dd, dict) else type(dd))
                sa = dd.get('synthese_agricole') if isinstance(dd, dict) else None
                P('PUBLIC synthese_agricole keys', sorted(sa.keys()) if isinstance(sa, dict) else sa)
                break
            P('PUBLIC', path, r.status_code)
    except AutoDevisError as e:
        P('L1b auto REFUS', e.message)
    except Exception:
        P('EXC')
        traceback.print_exc()
    transaction.set_rollback(True)
P('FIN')

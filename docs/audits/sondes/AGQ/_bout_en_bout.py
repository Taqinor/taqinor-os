import json, time, traceback, os
from decimal import Decimal
from datetime import date
from django.db import transaction
from django.contrib.auth import get_user_model
os.makedirs('/tmp/agq', exist_ok=True)


def P(*a):
    print('##', *a, flush=True)


def J(o, n=900):
    return json.dumps(o, default=str, ensure_ascii=False)[:n]


def resume(s):
    out = {}
    out['hmt'] = s.get('hmt')
    out['besoin_nature'] = (s.get('besoin') or {}).get('nature')
    out['besoin_serie'] = (s.get('besoin') or {}).get('m3_jour_mois')
    out['conception'] = {k: (s.get('conception') or {}).get(k) for k in ('mois_critique', 'debit_conception_m3h')}
    p = s.get('pompe') or {}
    out['pompe'] = {k: p.get(k) for k in ('nom', 'placeholder', 'kw', 'debit_a_hmt_m3h', 'prix_connu', 'etiquette')}
    v = s.get('variateur') or {}
    out['variateur'] = {k: v.get(k) for k in ('nom', 'motif', 'kw')}
    out['puissance'] = s.get('puissance_retenue')
    out['prix_a_renseigner'] = s.get('prix_a_renseigner')
    c = s.get('champ') or {}
    out['champ'] = {k: c.get(k) for k in ('kwc', 'nb_panneaux', 'ratio', 'motif')}
    out['chaines'] = c.get('chaines')
    pr = s.get('production') or {}
    out['production'] = {k: pr.get(k) for k in ('mode', 'source_irradiation', 'm3_jour_mois')}
    out['couverture'] = s.get('couverture_pct_mois')
    out['controle'] = s.get('controle_conception')
    out['ha'] = s.get('ha_irrigables')
    out['tailles'] = [{k: t.get(k) for k in ('cle', 'pompe_nom', 'puissance_kw', 'champ_kwc', 'nb_panneaux', 'couverture_mois_critique_pct', 'total_ttc', 'prix_connu', 'motif')} for t in s.get('tailles') or []]
    out['tailles_omises'] = s.get('tailles_omises')
    k = s.get('kit') or {}
    out['kit_inclus'] = [(x.get('cle'), x.get('designation'), x.get('quantite'), x.get('prix_connu')) for x in k.get('inclus') or []]
    out['kit_options'] = [(o.get('cle'), o.get('cochee'), o.get('prix_connu'), o.get('motif')) for o in k.get('options') or []]
    out['kit_total_ttc'] = k.get('total_ttc')
    out['alertes'] = [(a.get('code'), a.get('message')) for a in s.get('alertes') or []]
    out['methode'] = s.get('methode')
    return out


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
    P('user', user.id, user.username, getattr(user, 'role_legacy', None))
    # ---- L0 : lead prod-like 1038
    l0 = Lead.objects.get(pk=1038)
    P('L0 manquants', champs_devis_auto_manquants(l0), 'visite_requise', visite_point_eau_requise(l0))
    t = time.time()
    s0 = etudier_pompage(co, {'taille': 'recommandee'}, lead=l0)
    P('L0 etude %.1fs' % (time.time() - t))
    P('L0', J(resume(s0), 2500))
    try:
        d = build_devis_auto(lead=l0, user=user, company=co, journal_auto={})
        P('L0 auto OK', d.reference)
    except AutoDevisError as e:
        P('L0 auto REFUS', e.message, '| field', e.field)
    # ---- L1 : lead realiste
    base = dict(company=co, nom='Sonde AGQ Haouz', telephone='0600000001', type_installation='agricole', ville='Marrakech', gps_lat=Decimal('31.63'), gps_lng=Decimal('-8.0'), region_agricole='haouz', source_eau='forage', niveau_statique_m=Decimal('45'), niveau_statique_source='declare', debit_forage_m3h=Decimal('25'), debit_forage_source='foreur', profondeur_forage_m=Decimal('120'), besoin_eau_m3j=Decimal('120'), besoin_eau_source='client', culture='olivier', surface_irriguee_ha=Decimal('5'), irrigation_methode='goutte', raccordement='triphase', pompe_actuelle_type='immergee', pompe_actuelle_cv=Decimal('7.5'), pompe_actuelle_debit_m3h=Decimal('18'), pompage_heures_jour=Decimal('6'), pompe_alim_actuelle='butane', butane_bouteilles_jour=Decimal('2'), carburant_prix_unitaire_mad=Decimal('50'), carburant_prix_declare_le=date.today(), mois_irrigation=[4, 5, 6, 7, 8, 9, 10], distance_forage_champ_m=Decimal('30'))
    l1 = Lead.objects.create(**base)
    P('L1 (sans HMT declaree) manquants', champs_devis_auto_manquants(l1), 'visite_requise', visite_point_eau_requise(l1))
    s1 = etudier_pompage(co, {'taille': 'recommandee', 'alim': 'tri'}, lead=l1)
    P('L1 as-is', J(resume(s1), 2500))
    try:
        d = build_devis_auto(lead=l1, user=user, company=co, journal_auto={})
        P('L1 auto OK', d.reference)
    except AutoDevisError as e:
        P('L1 auto REFUS', e.message, '| field', e.field)
    l1b = Lead.objects.create(**dict(base, nom='Sonde AGQ HMT70', pompe_hmt_m=Decimal('70'), pompe_hmt_source='declaree'))
    s1b = etudier_pompage(co, {'taille': 'recommandee', 'alim': 'tri'}, lead=l1b)
    P('L1b as-is (HMT 70)', J(resume(s1b), 2500))
    try:
        d = build_devis_auto(lead=l1b, user=user, company=co, journal_auto={})
        P('L1b auto OK', d.reference)
    except AutoDevisError as e:
        P('L1b auto REFUS', e.message, '| field', e.field)
    # ---- S1 : catalogue complet (prix OSP + fiches), rollback a la fin
    prix = {311: 28000, 312: 32000, 313: 36000, 314: 40000, 315: 44000, 316: 46000, 317: 52000, 318: 54000, 319: 60000, 320: 62000, 321: 75000}
    for pid, pv in prix.items():
        Produit.objects.filter(pk=pid).update(prix_vente=Decimal(pv), prix_achat=Decimal(int(pv * 0.8)))
    FicheTechnique.objects.create(company=co, produit_id=268, type_fiche='module', pmax_wc=Decimal('710'), vmp_v=Decimal('40.3'), voc_v=Decimal('48.6'), isc_a=Decimal('18.6'), imp_a=Decimal('17.6'))
    for pid, imax in ((298, 13), (299, 13), (300, 20), (301, 20), (302, 32), (303, 40), (304, 45), (305, 55), (306, 70), (307, 90)):
        FicheTechnique.objects.create(company=co, produit_id=pid, type_fiche='variateur_pompage', ond_mppt_v_min=Decimal('250'), ond_mppt_v_max=Decimal('750'), ond_v_max_abs=Decimal('800'), ond_i_max_mppt_a=Decimal(imax), ond_phases=3, var_v_sortie_v=Decimal('380'))
    t = time.time()
    s2 = etudier_pompage(co, {'taille': 'recommandee', 'alim': 'tri'}, lead=l1b)
    P('S1 etude %.1fs' % (time.time() - t))
    P('S1 L1b catalogue complet', J(resume(s2), 4000))
    s2e = etudier_pompage(co, {'taille': 'recommandee', 'alim': 'tri', 'mode_pompe': 'existante', 'plaque': {'kw': 5.5, 'tension_v': 380, 'phases': 'tri'}, 'besoin': {'mode': 'pompe_actuelle', 'debit_actuel_m3h': 18, 'heures_actuelles_jour': 6}}, lead=l1b)
    P('S1 existante', J(resume(s2e), 2000))
    journal = {}
    try:
        t = time.time()
        devis = build_devis_auto(lead=l1b, user=user, company=co, journal_auto=journal)
        P('S1 auto OK %.1fs' % (time.time() - t), devis.reference, 'journal', J(journal, 800))
        for lg in devis.lignes.order_by('ordre', 'id'):
            P('  LIGNE', lg.designation[:60], '| q', lg.quantite, '| PU', lg.prix_unitaire, '| tva', lg.taux_tva, '| role', lg.role_devis, '| prod', lg.produit_id)
        P('  TOTAUX ht', devis.total_ht, 'ttc', devis.total_ttc, 'tva', devis.taux_tva)
        ep = devis.etude_params or {}
        P('  EP keys', sorted(ep.keys()))
        P('  EP m3_jour', ep.get('m3_jour'), 'hmt_m', ep.get('hmt_m'), 'debit_hmt', ep.get('debit_hmt_m3h'), 'champ_kwc', ep.get('champ_kwc'), 'pompe_kw', ep.get('pompe_kw'), 'heures', ep.get('heures_pompage'), 'nature', (ep.get('besoin_mensuel') or {}).get('nature'))
        P('  EP saisies_eco', J(ep.get('saisies_economie_pompage'), 600))
        P('  EP production', J(ep.get('production'), 500))
        from rest_framework.test import APIClient
        api = APIClient(HTTP_HOST='127.0.0.1')
        api.force_authenticate(user=user)
        r = api.get('/api/django/ventes/devis/%d/economie-pompage/' % devis.id)
        P('ECO status', r.status_code, J(r.data if hasattr(r, 'data') else r.content, 2500))
        from apps.ventes.quote_engine import clean_pdf_options
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.agricole.synthese import synthese_agricole
        data = build_quote_data(devis, clean_pdf_options({'pdf_mode': 'full'}))
        syn = synthese_agricole(data)
        P('SYNTHESE eau', J(syn.get('eau')), 'champ', J(syn.get('champ')), 'pompe', J(syn.get('pompe')))
        P('SYNTHESE omissions', J(syn.get('omissions'), 1500))
        P('SYNTHESE economies?', 'economies' in syn, 'garanties', J(syn.get('garanties'), 500), 'a_confirmer', syn.get('a_confirmer_par_visite'), 'provenance', J(syn.get('provenance'), 600))
        import fitz
        for nom, q in (('full', ''), ('note', '?include_note_calcul=1'), ('onepage', '?pdf_mode=onepage'), ('ar', '?langue=ar')):
            t = time.time()
            r = api.get('/api/django/ventes/devis/%d/proposal/%s' % (devis.id, q))
            dt = time.time() - t
            if r.status_code != 200:
                P('PDF', nom, 'status', r.status_code, (r.content or b'')[:300])
                continue
            b = r.content
            open('/tmp/agq/%s.pdf' % nom, 'wb').write(b)
            doc = fitz.open(stream=b, filetype='pdf')
            P('PDF', nom, 'pages', len(doc), 'bytes', len(b), '%.1fs' % dt)
            for i, page in enumerate(doc):
                page.get_pixmap(dpi=80).save('/tmp/agq/%s_p%d.png' % (nom, i + 1))
                if nom == 'full':
                    open('/tmp/agq/%s_p%d.txt' % (nom, i + 1), 'w').write(page.get_text())
    except AutoDevisError as e:
        P('S1 auto REFUS', e.message, '| field', e.field)
    except Exception:
        P('EXC')
        traceback.print_exc()
    transaction.set_rollback(True)
P('FIN (rollback)')

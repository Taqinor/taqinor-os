# flake8: noqa  (sonde d'audit PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K20 — un devis ENVOYÉ (règles >= 3) lié à un calepinage simulé avec ombrage : ses chiffres client
bougent-ils après (1) un PUT des réglages société calepinage (écran Réglages, route réelle) puis
(2) une re-simulation (POST simuler accepté sur l'atelier « verrouillé ») ?
Mesures à chaque état : perte_ombrage_du_devis, GET /proposal (vraie route, données passées au rendu
PDF capturées par espion sur build_quote_data), GET proposition publique (lien client tokenisé,
JSON), et le moteur horaire qu'un ré-enregistrement du devis rangerait (etude_horaire_pour_devis).
Simulation : vraie chaîne simuler_calepinage, météo rejouée (_ClientParOrientation), fiches
module/onduleur injectées (resoudre_materiel patché, comme les tests du module). Transaction annulée."""
SONDE = {"constat": "C-ACON-020", "sha": "33cba7f5d",
         "attendu": "repro si la perte d'ombrage (et un chiffre client) d'un devis envoye change apres un PUT reglages, et si simuler/recalculer ne sont pas refuses (409) sur le calepinage d'un devis envoye",
         "modeles": ["ventes.Devis", "calepinage.Calepinage", "calepinage.ParametresCalepinage"]}


def sonde(ctx):
    import copy
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, ShareLink
    from apps.calepinage.models import Calepinage
    from apps.calepinage.services.liens import lier_devis
    from apps.calepinage.services.simulation import simuler_calepinage
    from apps.calepinage.tests.test_acal_multi_pans import _ClientParOrientation, _layout, _zone
    from apps.calepinage.tests.test_calx5_simulation import MATERIEL, REGLAGES
    from apps.ventes.horaire.ombrage import perte_ombrage_du_devis
    from apps.ventes.etude_horaire import etude_horaire_pour_devis
    from apps.ventes.domain.etudes import rafraichir_etudes_du_devis
    import apps.ventes.quote_engine.builder as builder

    H = {'HTTP_HOST': 'localhost'}
    patch_mat = mock.patch('apps.calepinage.services.electrique.resoudre_materiel', return_value=MATERIEL)
    patch_mat.start()
    obs = {}
    try:
        co = Company.objects.create(nom='Sonde ACON 020', slug='sonde-acon-020')
        u = get_user_model().objects.create_user(username='sonde_acon_020', password='x',
                                                 role_legacy='admin', company=co)
        api = APIClient()
        api.force_authenticate(u)
        # Réglages simulation posés par la VRAIE route (écran Réglages).
        sim0 = copy.deepcopy(REGLAGES['simulation'])
        for _v in sim0.values():
            _v['source'] = 'societe'
        r = api.put('/api/django/calepinage/parametres/', {'simulation': sim0}, format='json', **H)
        obs['put_reglages_initial'] = r.status_code
        if r.status_code != 200:
            return 'PUT initial refuse : %s %s' % (r.status_code, r.content[:600])
        from apps.calepinage.selectors import parametres_de_societe
        obs['simulation_lue'] = str((parametres_de_societe(co) or {}).get('simulation'))[:300]
        cl = Client.objects.create(company=co, nom='Client K20')
        lead_kw = dict(company=co, nom='Lead K20', facture_hiver=Decimal('900'))
        if any(f.name == 'ville' for f in Lead._meta.fields):
            lead_kw['ville'] = 'Casablanca'
        lead = Lead.objects.create(**lead_kw)
        d = Devis.objects.create(company=co, reference='DEV-K20-01', client=cl, lead=lead,
                                 taux_tva=Decimal('20'), statut='brouillon', created_by=u,
                                 mode_installation='residentiel',
                                 etude_params={'factures_mensuelles_reelles': [900] * 12,
                                               'distributeur': 'onee', 'ville': 'casablanca'})
        for i, (nom, qte, pu) in enumerate((('Panneau Canadien Solar 710W', '8', '1166.67'),
                                            ('Onduleur réseau Huawei 5kW Monophasé', '1', '9000.00'))):
            p = Produit.objects.create(company=co, nom=nom, sku=f'k20-{i}', prix_vente=Decimal(pu),
                                       quantite_stock=50)
            LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=Decimal(qte),
                                      prix_unitaire=Decimal(pu), remise=Decimal('0'), ordre=i)
        layout = _layout(_zone(1, 16, 90.0), _zone(2, 8, 270.0))
        for zone in layout['zones']:
            zone['geometry']['solarAccess'] = {
                'values': [0.9] * zone['geometry']['count'],
                'method': {'horizon': False, 'rangees': False, 'resolution': 'annuelle',
                           'description': 'Accès solaire annuel'},
                'assumptions': {'periode': 'annee'}, 'computedAt': '2026-10-01T10:00:00Z'}
        c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='K20', roof_layout=layout)
        lier_devis(c, d.pk)
        simuler_calepinage(c, client=_ClientParOrientation(), materiel=MATERIEL, enregistrer=True)
        c.refresh_from_db()
        d.refresh_from_db()
        obs['perte_apres_simulation'] = perte_ombrage_du_devis(d)
        hash_avant = (c.resultat or {}).get('simulation', {}).get('hash_entree')
        entree_avant = str((c.resultat or {}).get('entree_electrique'))[:120]
        rafraichir_etudes_du_devis(d)
        c.refresh_from_db()
        obs['perte_apres_rafraichir_etudes'] = perte_ombrage_du_devis(Devis.objects.get(pk=d.pk))
        obs['entree_electrique_change_par_rafraichir'] = entree_avant != str((c.resultat or {}).get('entree_electrique'))[:120]
        obs['hash_sim_inchange'] = hash_avant == (c.resultat or {}).get('simulation', {}).get('hash_entree')  # ce qu'un enregistrement du devis brouillon range
        Devis.objects.filter(pk=d.pk).update(statut='envoye')  # envoi (statut seul, aucun effet de bord)
        d.refresh_from_db()
        obs['regles_calcul'] = d.regles_calcul
        obs['statut'] = d.statut
        link = ShareLink.objects.create(company=co, devis=d)

        captures = []
        vrai_build = builder.build_quote_data

        def espion(*a, **k):
            data = vrai_build(*a, **k)
            captures.append(data)
            return data

        def chiffres(data):
            return data or {}

        def mesurer(etiquette):
            dd = Devis.objects.get(pk=d.pk)
            m = {'perte_ombrage_pct': perte_ombrage_du_devis(dd)}
            bloc = etude_horaire_pour_devis(dd, kwc=5.68)
            m['horaire_live_production_kwh'] = ((bloc or {}).get('annuel') or {}).get('production_kwh')
            m['horaire_live_economie_sans'] = ((bloc or {}).get('annuel') or {}).get('economie_sans_mad')
            stocke = (dd.etude_params or {}).get('etude_horaire') or {}
            m['horaire_range_production_kwh'] = (stocke.get('annuel') or {}).get('production_kwh')
            captures.clear()
            with mock.patch.object(builder, 'build_quote_data', side_effect=espion):
                rp = api.get(f'/api/django/ventes/devis/{d.pk}/proposal/', **H)
            m['proposal_http'] = rp.status_code
            m['proposal_ctype'] = rp.get('Content-Type')
            m['_proposal_chiffres'] = chiffres(captures[0]) if captures else None
            with mock.patch('apps.ventes.public_views._notify_open'):
                rpub = APIClient().get(f'/api/django/public/proposal/{link.token}/data/', **H)
            m['public_http'] = rpub.status_code
            m['_public'] = rpub.json() if rpub.status_code == 200 else str(rpub.content[:200])
            return m

        def aplatir(x, pref=''):
            out = {}
            if isinstance(x, dict):
                for k, v in x.items():
                    out.update(aplatir(v, f'{pref}.{k}' if pref else str(k)))
            elif isinstance(x, list):
                for i, v in enumerate(x[:40]):
                    out.update(aplatir(v, f'{pref}[{i}]'))
            elif isinstance(x, (int, float)) and not isinstance(x, bool):
                out[pref] = x
            return out

        def diff(a, b, n=12):
            fa, fb = aplatir(a), aplatir(b)
            ch = [(k, fa.get(k), fb.get(k)) for k in sorted(set(fa) | set(fb)) if fa.get(k) != fb.get(k)]
            return {'nb': len(ch), 'exemples': ch[:n]}

        m0 = mesurer('frais')
        # (1) un réglage société change (incertitude σ — n'a rien à voir avec l'ombrage ni le devis)
        sim = copy.deepcopy(sim0)
        sim['sigma_modele_pct'] = {'valeur': 7, 'source': 'societe', 'reference': 'sonde'}
        r = api.put('/api/django/calepinage/parametres/', {'simulation': sim}, format='json', **H)
        obs['put_reglages_sigma'] = r.status_code
        if r.status_code != 200:
            obs['put_detail'] = str(r.content[:300])
        m1 = mesurer('apres_reglage')
        # (2) re-simulation : la route accepte-t-elle sur le calepinage d'un devis ENVOYÉ ?
        with mock.patch('core.jobs.submit', side_effect=lambda *a, **k: type('J', (), {'pk': 1, 'id': 1, 'statut': 'en_attente', 'status': 'pending', 'kind': 'calepinage'})()), \
                mock.patch('apps.calepinage.views.simulation.accuse_de_simulation', side_effect=lambda job: {'job_id': 1}):
            rs = api.post(f'/api/django/calepinage/calepinages/{c.pk}/simuler/', {'forcer': True}, format='json', **H)
        obs['simuler_http'] = rs.status_code
        obs['simuler_corps'] = str(rs.content[:200])
        with mock.patch('core.jobs.submit', side_effect=lambda *a, **k: type('J', (), {'pk': 2, 'id': 2})()):
            rr = api.post('/api/django/calepinage/parametres/recalculer-simulations/', {}, format='json', **H)
        obs['recalculer_http'] = rr.status_code
        obs['recalculer_corps'] = str(rr.content[:300])
        # le travail de fond (même service), météo rejouée, crête différente (autre année météo)
        c.refresh_from_db()
        simuler_calepinage(c, forcer=True, client=_ClientParOrientation(crete=760.0), materiel=MATERIEL,
                           enregistrer=True)
        m2 = mesurer('apres_resimulation')
        # (3) depuis l'état FRAIS (m2), un second changement de réglage société
        sim3 = copy.deepcopy(sim)
        sim3['sigma_modele_pct'] = {'valeur': 8, 'source': 'societe', 'reference': 'sonde'}
        r3 = api.put('/api/django/calepinage/parametres/', {'simulation': sim3}, format='json', **H)
        obs['put_reglages_sigma_2'] = r3.status_code
        m3 = mesurer('apres_second_reglage')

        for nom, m in (('m0_frais', m0), ('m1_apres_put_reglage', m1), ('m2_apres_resimulation', m2), ('m3_apres_second_reglage', m3)):
            obs[nom] = {k: v for k, v in m.items() if not k.startswith('_')}
        obs['diff_proposal_m0_m1'] = diff(m0['_proposal_chiffres'], m1['_proposal_chiffres'])
        obs['diff_public_m0_m1'] = diff(m0['_public'], m1['_public'])
        obs['diff_public_m0_m2'] = diff(m0['_public'], m2['_public'])
        obs['diff_proposal_m0_m2'] = diff(m0['_proposal_chiffres'], m2['_proposal_chiffres'])
        obs['diff_public_m2_m3'] = diff(m2['_public'], m3['_public'], 6)
        obs['diff_proposal_m2_m3'] = diff(m2['_proposal_chiffres'], m3['_proposal_chiffres'], 6)
        p2, p3 = m2['perte_ombrage_pct'], m3['perte_ombrage_pct']
        change_perte = p2 is not None and p2 > 0 and p3 != p2
        client_bouge = obs['diff_public_m2_m3']['nb'] > 0 or obs['diff_proposal_m2_m3']['nb'] > 0
        obs['repro'] = bool(d.statut == 'envoye' and change_perte and client_bouge
                            and obs['simuler_http'] != 409)
    finally:
        patch_mat.stop()
    for cle in ('diff_public_m0_m1', 'diff_proposal_m0_m1'):
        obs.pop(cle, None)
    obs['diff_public_m0_m2']['exemples'] = obs['diff_public_m0_m2']['exemples'][:7]
    obs['nb_chiffres_proposal_compares'] = len(aplatir(m0['_proposal_chiffres']))
    print(json.dumps(obs, default=str, ensure_ascii=False)[:5900])
    return {'repro': obs.get('repro', False)}

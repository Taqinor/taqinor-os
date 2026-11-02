# flake8: noqa  (sonde de vérification C-L6-1, rejouable par scripts/sonde.py)
"""C-L6-1 — une ligne « Câble batterie DC 25 mm² » (role_devis figé `cable_dc` par classer_produit) : le PDF /
la page publique (`builder._repartir_options`, rôle d'abord) la mettent dans l'option « sans batterie », le noyau
monnaie (`utils/options.filter_lines_for_option`, mots-clés seuls → `is_battery`) l'exclut. Rejeu : devis résidentiel
« Les deux » créé par POST devis/atomic/ (porte du générateur), puis TTC « sans » lu par build_quote_data, par
GET /public/proposal/<token>/data/ (option_totals) et par option_totaux / next_tranche après acceptation interne
« sans_batterie ». Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-040", "sha": "1dfa7986c",
         "attendu": "TTC « sans batterie » du PDF/page publique = TTC « sans batterie » de l'acompte/serveur (défaut : écart = câble × 1,2)",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "ventes.ShareLink"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, ShareLink
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 040', slug='sonde-advs-040')
    u = U.objects.create_user(username='sonde-advs-040', password='x', role_legacy='admin', company=c)
    cl = Client.objects.create(company=c, nom='Option', prenom='Cable', email='sonde-advs-040@example.invalid')

    def prod(nom, sku, pv):
        return Produit.objects.create(company=c, nom=nom, sku=sku, prix_vente=Decimal(pv), prix_achat=Decimal('1'),
                                      tva=Decimal('20'), quantite_stock=100)
    pan = prod('Panneau Canadien Solar 710W', 'A40-P', '1000')
    res = prod('Onduleur réseau Huawei 5kW Monophasé', 'A40-R', '8000')
    hyb = prod('Onduleur hybride Deye 5kW Monophasé', 'A40-H', '12000')
    bat = prod('Batterie Dyness 5 kWh', 'A40-B', '15000')
    cab = prod('Câble batterie DC 25 mm²', 'A40-C', '150')
    obs = {}

    def appel(api, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt)
            except Exception:
                return r.status_code, {'_brut': txt[:300]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    api = APIClient()
    api.force_authenticate(u)

    def L(p, q, pu):
        return {'produit': p.id, 'designation': p.nom, 'quantite': str(q), 'prix_unitaire': pu, 'taux_tva': '20'}
    s, cree = appel(api, 'post', '/api/django/ventes/devis/atomic/', {
        'client': cl.id, 'taux_tva': '20.00', 'mode_installation': 'residentiel',
        'etude_params': {'scenario': 'Les deux (Sans + Avec)'},
        'lignes': [L(pan, 8, '1000.00'), L(res, 1, '8000.00'), L(hyb, 1, '12000.00'), L(bat, 1, '15000.00'),
                   L(cab, 6, '150.00')]})
    obs['atomic'] = [s, '' if s < 400 else str(cree)[:300]]
    dv = Devis.objects.filter(company=c).first()
    if dv is None:
        obs['erreur'] = 'aucun devis'
        return {'repro': False, 'observe': obs}
    obs['scenario'] = (dv.etude_params or {}).get('scenario')
    obs['lignes'] = [(l.designation, l.role_devis, getattr(l, 'variante', ''), str(l.quantite), str(l.prix_unitaire))
                     for l in dv.lignes.all().order_by('id')]
    from apps.ventes.quote_engine.builder import build_quote_data
    from apps.ventes.utils.options import option_totaux, deux_options_declarees, option_effective
    obs['deux_options'] = deux_options_declarees(dv)
    obs['option_effective'] = option_effective(dv)
    try:
        data = build_quote_data(dv)
        obs['pdf_totaux_sans_ttc'] = str((data.get('totaux_sans') or {}).get('ttc'))
        obs['pdf_totaux_avec_ttc'] = str((data.get('totaux_avec') or {}).get('ttc'))
        obs['pdf_sans_items'] = [it.get('designation') for it in (data.get('sans_items') or [])]
    except Exception as e:
        obs['pdf_err'] = repr(e)[:300]
    ot_s = option_totaux(dv, 'sans_batterie')
    ot_a = option_totaux(dv, 'avec_batterie')
    obs['serveur_sans_ttc'] = str(ot_s['ttc'])
    obs['serveur_avec_ttc'] = str(ot_a['ttc'])
    obs['total_ttc_devis'] = str(dv.total_ttc)
    with mock.patch('apps.ventes.public_views._notify_open'), \
            mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
        s, sl = appel(api, 'post', f'/api/django/ventes/devis/{dv.id}/share-link/', {'envoi': True})
        obs['share_link'] = s
        link = ShareLink.objects.filter(devis=dv, revoque_le__isnull=True).order_by('-id').first()
        if link is not None:
            pub = APIClient()
            s, lu = appel(pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
            ot = (lu.get('option_totals') or {}) if isinstance(lu, dict) else {}
            obs['public_status'] = s
            obs['public_option_totals_sans'] = json.dumps(ot.get('sans_batterie'), default=str)[:200]
        s, acc = appel(api, 'post', f'/api/django/ventes/devis/{dv.id}/accepter/',
                       {'nom': 'Client Sonde', 'option': 'sans_batterie'})
        obs['accepter'] = [s, '' if s < 400 else str(acc)[:300]]
    dv.refresh_from_db()
    obs['statut'] = dv.statut
    obs['option_acceptee'] = getattr(dv, 'option_acceptee', None) or getattr(dv, 'accepted_option', None)
    obs['total_ttc_apres_accept'] = str(dv.total_ttc)
    try:
        from apps.ventes.utils.echeancier import next_tranche
        t = next_tranche(dv)
        obs['next_tranche'] = json.dumps(t, default=str)[:300]
    except Exception as e:
        obs['next_tranche_err'] = repr(e)[:200]
    try:
        from apps.ventes.vente_facturation import plan_facturation
        obs['prix_convenu_ttc'] = str(plan_facturation(dv).get('prix_convenu_ttc'))
    except Exception as e:
        obs['plan_err'] = repr(e)[:200]
    try:
        ecart = Decimal(obs['pdf_totaux_sans_ttc']) - Decimal(obs['serveur_sans_ttc'])
    except Exception:
        ecart = None
    obs['ecart_pdf_moins_serveur_sans'] = str(ecart)
    return {'repro': bool(ecart), 'observe': obs}

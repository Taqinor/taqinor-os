# flake8: noqa  (sonde de vérification C8-3, rejouable par scripts/sonde.py)
"""C8-3 — portée « soi » (rôle Commercial, SCOPE_SELF) non appliquée aux références `lead` du CORPS des portes de
création : A (Commercial) ne voit pas le lead LB de B (GET /crm/leads/LB/ → 404 témoin) mais POST devis/atomic/,
devis/auto/ et devis/from-layout/ sur LB ; et from-layout rend le brouillon de B (même empreinte) à A (dédup QJ17)
avec id/référence/jeton. Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-042", "sha": "1dfa7986c",
         "attendu": "lead hors portée dans le corps → 404, 0 devis écrit, aucun brouillon d'autrui rendu (défaut : 201/200)",
         "modeles": ["ventes.Devis", "crm.Lead", "roles.Role"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
    from apps.stock.models import Produit
    from apps.ventes.models import Devis
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 042', slug='sonde-advs-042')
    r = Role.objects.create(company=c, nom='Commercial sonde 042', permissions=list(COMMERCIAL_PERMISSIONS))
    ua = U.objects.create_user(username='sonde-advs-042-a', password='x', company=c, role=r)
    ub = U.objects.create_user(username='sonde-advs-042-b', password='x', company=c, role=r)
    lb = Lead.objects.create(company=c, nom='Collegue', prenom='LeadB', email='sonde-advs-042@example.invalid',
                             telephone='+212600004042', ville='Casablanca', owner=ub,
                             conso_mensuelle_kwh=500, facture_hiver=Decimal('700'))
    prods = {}
    for nom, sku, prix in (('Panneau Jinko 550W', 'A042-PAN', '1100'),
                           ('Onduleur réseau Huawei 5kW Monophasé', 'A042-OND', '14000'),
                           ('Onduleur hybride Deye 5kW Monophasé', 'A042-HYB', '17000'),
                           ('Batterie Dyness 5 kWh', 'A042-BAT', '16000')):
        prods[sku] = Produit.objects.create(company=c, nom=nom, sku=sku, prix_vente=Decimal(prix),
                                            prix_achat=Decimal('1'), tva=Decimal('20'), quantite_stock=100)

    def appel(api, meth, url, corps=None):
        try:
            with transaction.atomic():
                rr = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            txt = rr.content.decode('utf-8', 'replace')
            try:
                return rr.status_code, json.loads(txt)
            except Exception:
                return rr.status_code, {'_brut': txt[:200]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    A, B = APIClient(), APIClient()
    A.force_authenticate(ua)
    B.force_authenticate(ub)
    obs = {'scope_A': [p for p in COMMERCIAL_PERMISSIONS if p.startswith('records_scope')]}
    s, _ = appel(A, 'get', f'/api/django/crm/leads/{lb.id}/')
    obs['A_lit_lead_B'] = s
    s, _ = appel(B, 'get', f'/api/django/crm/leads/{lb.id}/')
    obs['B_lit_son_lead'] = s

    def compte():
        return Devis.objects.filter(company=c, lead=lb).count()
    # 1. atomic
    n0 = compte()
    s, rep = appel(A, 'post', '/api/django/ventes/devis/atomic/', {
        'lead': lb.id, 'taux_tva': '20.00',
        'lignes': [{'produit': prods['A042-PAN'].id, 'designation': 'Panneau Jinko 550W', 'quantite': '8',
                    'prix_unitaire': '1100.00', 'taux_tva': '20'},
                   {'produit': prods['A042-OND'].id, 'designation': 'Onduleur réseau Huawei 5kW Monophasé',
                    'quantite': '1', 'prix_unitaire': '14000.00', 'taux_tva': '20'}]})
    obs['A_atomic_sur_LB'] = [s, compte() - n0, '' if s < 400 else str(rep)[:200]]
    # 2. auto
    n0 = compte()
    s, rep = appel(A, 'post', '/api/django/ventes/devis/auto/', {'lead': lb.id})
    obs['A_auto_sur_LB'] = [s, compte() - n0, {k: rep.get(k) for k in ('total_ttc', 'kwc', 'detail', 'field')}
                            if isinstance(rep, dict) else str(rep)[:200]]
    # 3. from-layout : B d'abord (son brouillon), puis A avec la même empreinte
    layout = {'scenario': 'reseau', 'panelWatt': 550,
              'result': {'panels': 8, 'kwc': 4.4, 'annualKwh': 7200, 'savings': 6000}}
    s, rb = appel(B, 'post', '/api/django/ventes/devis/from-layout/', {'layout': layout, 'lead': lb.id})
    obs['B_from_layout'] = [s, {k: rb.get(k) for k in ('id', 'reference', 'statut', 'detail')} if isinstance(rb, dict) else '']
    n0 = compte()
    s, ra = appel(A, 'post', '/api/django/ventes/devis/from-layout/', {'layout': layout, 'lead': lb.id})
    obs['A_from_layout'] = [s, compte() - n0, {k: ra.get(k) for k in ('id', 'reference', 'deduplicated', 'detail')}
                            if isinstance(ra, dict) else '', bool(isinstance(ra, dict) and ra.get('proposal_token'))]
    id_b = rb.get('id') if isinstance(rb, dict) else None
    if id_b:
        s, _ = appel(A, 'get', f'/api/django/ventes/devis/{id_b}/')
        obs['A_lit_brouillon_B_par_fiche'] = s
        obs['brouillon_B_rendu_a_A'] = bool(isinstance(ra, dict) and ra.get('id') == id_b)
    obs['devis_sur_LB'] = [(d.reference, d.created_by.username if d.created_by_id else None, d.statut)
                           for d in Devis.objects.filter(company=c, lead=lb).order_by('id')]
    ecrit_par_A = Devis.objects.filter(company=c, lead=lb, created_by=ua).count()
    obs['devis_crees_par_A_sur_LB'] = ecrit_par_A
    repro = obs['A_lit_lead_B'] == 404 and (ecrit_par_A > 0 or obs.get('brouillon_B_rendu_a_A'))
    return {'repro': bool(repro), 'observe': obs}

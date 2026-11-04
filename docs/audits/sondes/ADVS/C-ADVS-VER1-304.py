# flake8: noqa  (sonde de verification VER1, rejouable par scripts/sonde.py)
"""VER1-304 (ADVS44) — from-layout : A (Commercial, portée « soi ») POST sur le lead LB de son collègue B → 404 « Lead inconnu. »,
aucun id ni jeton du brouillon de B servi, 0 devis écrit ; B rejoue → 200 dédupliqué ; un lead que A possède → 201/200 ; lead d'une
autre société → 404. repro=True = l'écart existe encore. Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-042", "sha": "06ced8b1a",
         "attendu": "lead d'un collègue / d'une autre société : 404 sans id ni jeton ; B dédupliqué ; A sur son lead OK",
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
    c = Company.objects.create(nom='Sonde VER1 304', slug='sonde-ver1-304')
    c2 = Company.objects.create(nom='Sonde VER1 304 bis', slug='sonde-ver1-304-bis')
    r = Role.objects.create(company=c, nom='Commercial sonde 304', permissions=list(COMMERCIAL_PERMISSIONS))
    ua = U.objects.create_user(username='sonde-ver1-304-a', password='x', company=c, role=r)
    ub = U.objects.create_user(username='sonde-ver1-304-b', password='x', company=c, role=r)
    lb = Lead.objects.create(company=c, nom='Collegue', prenom='LeadB', email='v304b@example.invalid',
                             telephone='+212600004304', ville='Casablanca', owner=ub,
                             conso_mensuelle_kwh=500, facture_hiver=Decimal('700'))
    la = Lead.objects.create(company=c, nom='Moi', prenom='LeadA', email='v304a@example.invalid',
                             telephone='+212600004305', ville='Casablanca', owner=ua,
                             conso_mensuelle_kwh=500, facture_hiver=Decimal('700'))
    lx = Lead.objects.create(company=c2, nom='Autre', prenom='Soc', email='v304x@example.invalid',
                             telephone='+212600004306', ville='Rabat')
    for nom, sku, prix in (('Panneau Jinko 550W', 'V304-PAN', '1100'),
                           ('Onduleur réseau Huawei 5kW Monophasé', 'V304-OND', '14000'),
                           ('Onduleur hybride Deye 5kW Monophasé', 'V304-HYB', '17000'),
                           ('Batterie Dyness 5 kWh', 'V304-BAT', '16000')):
        Produit.objects.create(company=c, nom=nom, sku=sku, prix_vente=Decimal(prix),
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
    obs = {}
    s, _ = appel(A, 'get', f'/api/django/crm/leads/{lb.id}/')
    obs['temoin_A_lit_LB'] = s
    layout = {'scenario': 'reseau', 'panelWatt': 550,
              'result': {'panels': 8, 'kwc': 4.4, 'annualKwh': 7200, 'savings': 6000}}
    url = '/api/django/ventes/devis/from-layout/'
    s, rb = appel(B, 'post', url, {'layout': layout, 'lead': lb.id})
    obs['B_cree'] = [s, rb.get('id'), rb.get('reference')]
    n0 = Devis.objects.filter(company=c, lead=lb).count()
    s, ra = appel(A, 'post', url, {'layout': layout, 'lead': lb.id})
    obs['A_sur_LB'] = {'status': s, 'corps': ra, 'devis_ajoutes': Devis.objects.filter(company=c, lead=lb).count() - n0,
                       'jeton_ou_id_servi': bool(ra.get('proposal_token') or ra.get('id') or ra.get('reference'))}
    s, rb2 = appel(B, 'post', url, {'layout': layout, 'lead': lb.id})
    obs['B_rejoue'] = {'status': s, 'meme_id': rb2.get('id') == rb.get('id'), 'deduplicated': rb2.get('deduplicated')}
    s, rm = appel(A, 'post', url, {'layout': layout, 'lead': la.id})
    obs['A_sur_son_lead'] = {'status': s, 'id': rm.get('id'), 'detail': rm.get('detail')}
    s, rx = appel(A, 'post', url, {'layout': layout, 'lead': lx.id})
    obs['A_lead_autre_societe'] = {'status': s, 'corps': rx}
    obs['devis_crees_par_A_sur_LB'] = Devis.objects.filter(company=c, lead=lb, created_by=ua).count()
    ecart = not (obs['temoin_A_lit_LB'] == 404 and obs['B_cree'][0] == 201
                 and obs['A_sur_LB']['status'] == 404 and obs['A_sur_LB']['corps'] == {'detail': 'Lead inconnu.'}
                 and obs['A_sur_LB']['devis_ajoutes'] == 0 and not obs['A_sur_LB']['jeton_ou_id_servi']
                 and obs['B_rejoue']['status'] == 200 and obs['B_rejoue']['meme_id'] and obs['B_rejoue']['deduplicated']
                 and obs['A_sur_son_lead']['status'] in (200, 201)
                 and obs['A_lead_autre_societe']['status'] == 404)
    return {'repro': bool(ecart), 'observe': obs}

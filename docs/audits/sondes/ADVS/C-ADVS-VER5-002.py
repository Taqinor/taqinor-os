# flake8: noqa  (sonde de verification VER5, rejouable par scripts/sonde.py)
"""VER5-002 (ADVS3, D-ADVS-4) — 3 lignes (2 panneaux + 1 onduleur) a 1 000 TTC (HT 833,33, TVA 20 %) creees par POST devis/atomic/ :
total TTC stocke 3 000,00 (jamais 2 900), ht_net + tva == ttc, aucune ligne repricee ; le /proposal annonce le meme
total ; temoins : 2 957 TTC -> 2 900, 3 000 pile inchange. repro=True = l'ecart existe encore (2 900 ou divergence).
Societe neuve, transaction annulee."""
SONDE = {"constat": "C-ADVS-001", "sha": "2781a2049",
         "attendu": "total_ttc 3000.00 au serveur, /proposal = noyau ; 2 957 -> 2 900 ; 3 000 -> 3 000",
         "modeles": ["ventes.Devis", "ventes.LigneDevis"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS VER5 002', slug='sonde-advs-ver5-002')
    u = U.objects.create_user(username='sonde-advs-ver5-002', password='x', role_legacy='admin', company=c)
    cl = Client.objects.create(company=c, nom='Centaine', prenom='Test', email='client-ver5-002@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Jinko 550W', sku='VER5002-PAN', prix_vente=Decimal('833.33'),
                                 prix_achat=Decimal('1'), tva=Decimal('20'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 5kW Monophasé', sku='VER5002-OND',
                                 prix_vente=Decimal('833.33'), prix_achat=Decimal('1'), tva=Decimal('20'),
                                 quantite_stock=100)
    api = APIClient()
    api.force_authenticate(u)
    obs = {}

    def creer(nom, lignes):
        try:
            with transaction.atomic():
                r = api.post('/api/django/ventes/devis/atomic/',
                             {'client': cl.id, 'taux_tva': '20.00', 'lignes': lignes},
                             format='json', HTTP_HOST='localhost')
            data = json.loads(r.content.decode('utf-8', 'replace') or '{}')
        except Exception as e:
            obs[nom] = {'_exc': repr(e)[:300]}
            return None
        did = data.get('id') if isinstance(data, dict) else None
        dv = Devis.objects.filter(pk=did).first() if did else None
        o = {'http': r.status_code}
        if dv is not None:
            o.update(total_ttc=str(dv.total_ttc), total_ht=str(getattr(dv, 'total_ht', None)),
                     total_tva=str(getattr(dv, 'total_tva', None)), regles=getattr(dv, 'regles_calcul', None),
                     prix_lignes=[str(li.prix_unitaire) for li in dv.lignes.all()])
        else:
            o['reponse'] = {k: data.get(k) for k in list(data)[:6]} if isinstance(data, dict) else str(data)[:200]
        obs[nom] = o
        return dv

    une = {'produit': pan.id, 'designation': pan.nom, 'quantite': '1', 'prix_unitaire': '833.33', 'taux_tva': '20'}
    onduleur = {'produit': ond.id, 'designation': ond.nom, 'quantite': '1', 'prix_unitaire': '833.33',
                'taux_tva': '20'}
    # 2 panneaux + 1 onduleur reseau a 1 000 TTC chacun (le moteur PDF refuse un devis sans onduleur).
    dv = creer('trois_fois_1000', [dict(une), dict(une), onduleur])
    creer('temoin_2957', [{'produit': pan.id, 'designation': pan.nom, 'quantite': '1', 'prix_unitaire': '2464.17',
                           'taux_tva': '20'}])
    creer('temoin_3000', [{'produit': pan.id, 'designation': pan.nom, 'quantite': '1', 'prix_unitaire': '2500.00',
                           'taux_tva': '20'}])
    pdf_ttc = None
    if dv is not None:
        try:
            from apps.ventes.quote_engine.builder import build_quote_data
            with transaction.atomic():
                d = build_quote_data(dv)
            t = d.get('totaux') or d.get('totaux_all') or {}
            obs['proposal'] = {k: (str(v) if not isinstance(v, (dict, list)) else None)
                               for k, v in d.items() if 'total' in k.lower() and not isinstance(v, (dict, list))}
            obs['proposal_totaux'] = {k: str(v) for k, v in t.items()} if isinstance(t, dict) else str(t)[:120]
            pdf_ttc = (t.get('ttc') if isinstance(t, dict) else None) or d.get('total_ttc')
        except Exception as e:
            obs['proposal'] = repr(e)[:200]
    ok_serveur = obs.get('trois_fois_1000', {}).get('total_ttc') == '3000.00'
    ok_pdf = pdf_ttc is not None and Decimal(str(pdf_ttc)) == Decimal('3000')
    ok_temoins = (obs.get('temoin_2957', {}).get('total_ttc') == '2900.00'
                  and obs.get('temoin_3000', {}).get('total_ttc') == '3000.00')
    obs['bilan'] = {'serveur_3000': ok_serveur, 'proposal_3000': ok_pdf, 'temoins': ok_temoins}
    return {'repro': not (ok_serveur and ok_pdf and ok_temoins), 'observe': obs}

# flake8: noqa  (sonde de vérification F2 (lane 7), rejouable par scripts/sonde.py)
"""F2 — POST /devis/<id>/renouveler/ (api-only QJR667) re-tarife au `prix_vente` de la fiche (`_prix_courant` →
`prix_applicable`) des lignes dont le prix ne vient PAS de la fiche et qui ne portent pas `prix_manuel` :
(a) prestation C&I au forfait société (article du rôle à prix_vente 0), (b) forfait « Installation » au barème
prix_fixe_ht + prix_par_panneau_ht (prix_vente 0). Devis EXPIRÉ (seul statut renouvelable). Société neuve,
transaction annulée."""
SONDE = {"constat": "C-ADVS-045", "sha": "1dfa7986c",
         "attendu": "ligne prestation / forfait de la copie = prix de la source (défaut : 0)",
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
    from apps.ventes.models import Devis, LigneDevis
    U = get_user_model()
    co = Company.objects.create(nom='Sonde ADVS 045', slug='sonde-advs-045')
    u = U.objects.create_user(username='sonde-advs-045', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Renouv', prenom='Prix', email='sonde-advs-045@example.invalid')
    pan = Produit.objects.create(company=co, nom='Panneau Jinko 710W', sku='A045-P', prix_vente=Decimal('1300'),
                                 prix_achat=Decimal('1'), tva=Decimal('20'), quantite_stock=100)
    etu = Produit.objects.create(company=co, nom='Études et ingénierie', sku='A045-E', prix_vente=Decimal('0'),
                                 prix_achat=Decimal('0'), tva=Decimal('20'), role_devis='etudes_ingenierie')
    ins = Produit.objects.create(company=co, nom='Installation et mise en service', sku='A045-I',
                                 prix_vente=Decimal('0'), prix_achat=Decimal('0'), tva=Decimal('20'),
                                 prix_fixe_ht=Decimal('2000'), prix_par_panneau_ht=Decimal('250'))
    obs = {'role_etudes_valide': None}
    try:
        from core.product_roles import role_declare
        obs['role_etudes_valide'] = role_declare('etudes_ingenierie')
    except Exception as e:
        obs['role_etudes_valide'] = repr(e)[:100]
    res = {}
    for mode, lignes in (('commercial', [(pan, 70, '1300'), (etu, 1, '5000')]),
                         ('agricole', [(pan, 10, '1300'), (ins, 1, str(2000 + 250 * 10))])):
        dv = Devis.objects.create(company=co, reference=f'DEV-A045-{mode[:3].upper()}', client=cl, statut='expire',
                                  taux_tva=Decimal('20.00'), remise_globale=Decimal('0'), created_by=u,
                                  mode_installation=mode)
        for i, (p, q, pu) in enumerate(lignes):
            LigneDevis.objects.create(devis=dv, produit=p, designation=p.nom, quantite=Decimal(q),
                                      prix_unitaire=Decimal(pu), remise=Decimal('0'), ordre=i, prix_manuel=False)
        api = APIClient()
        api.force_authenticate(u)
        try:
            with transaction.atomic():
                r = api.post(f'/api/django/ventes/devis/{dv.id}/renouveler/', {}, format='json', HTTP_HOST='localhost')
            st = r.status_code
            body = json.loads(r.content.decode('utf-8', 'replace') or '{}')
        except Exception as e:
            st, body = 599, {'_exc': repr(e)[:300]}
        nid = body.get('id') if isinstance(body, dict) else None
        neuf = Devis.objects.filter(pk=nid).first() if nid else None
        res[mode] = {'http': st, 'detail': '' if st < 400 else str(body)[:200],
                     'source': [(l.designation, str(l.prix_unitaire)) for l in dv.lignes.order_by('ordre')],
                     'source_ttc': str(dv.total_ttc),
                     'copie': [(l.designation, str(l.prix_unitaire), l.prix_manuel) for l in neuf.lignes.order_by('ordre')] if neuf else None,
                     'copie_ttc': str(neuf.total_ttc) if neuf else None,
                     'copie_statut': neuf.statut if neuf else None}
    obs['res'] = res
    zero = any(c and any(Decimal(p) == 0 for (_, p, _) in c) for c in (res[m]['copie'] for m in res))
    return {'repro': bool(zero), 'observe': obs}

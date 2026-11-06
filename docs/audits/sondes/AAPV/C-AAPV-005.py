# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K47 — ligne « sur commande » (ZPUR1) : la facture naît AVANT la réception (`facturer_bcf_sur_commande`),
le lettrage GR/IR ne tourne qu'à la création / au lien d'une facture, et `provisionner_gr_ir_reception`
provisionne toute ligne entrée sans regarder `_politique_ligne`. Vraies routes : produit sur_commande,
BCF 10 × 2 000 HT envoyé, POST bons-commande-fournisseur/<id>/facturer/ (FF 20 000 HT), REC 10 confirmée,
puis « Facturer » la réception (FG56, refusée : rien à facturer).
Attendu sain : provision absente ou lettrée par la facture ZPUR1 (GR/IR ouvert 0)."""
SONDE = {"constat": "C-AAPV-005", "sha": "5f603acce0",
         "attendu": "repro si apres FF sur commande 20000 HT puis reception confirmee : provision 20000 ouverte (lettre=False) et facturer reception refuse",
         "modeles": ["stock.Produit", "stock.MouvementStock", "stock.ReceptionFournisseur",
                     "stock.FactureFournisseur", "installations.ReceptionNonFacturee"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import (Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur, Produit)
    from apps.installations.models_gr_ir import ReceptionNonFacturee
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 005', slug='sonde-aapv-005')
    u = get_user_model().objects.create_user(username='sonde_aapv_005', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    p = Produit.objects.create(company=co, nom='Panneau import AAPV5', sku='AAPV-005', prix_vente=Decimal('3000'),
                               quantite_stock=0,
                               politique_facturation_achat=Produit.PolitiqueFacturationAchat.SUR_COMMANDE)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV5')
    bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference='BCF-AAPV-005',
                                               statut=BonCommandeFournisseur.Statut.ENVOYE)
    lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=10,
                                                    prix_achat_unitaire=Decimal('2000'))
    rfb = api.post(f'/api/django/stock/bons-commande-fournisseur/{bc.id}/facturer/', {}, format='json', **H)
    obs = {'facturer_bcf': rfb.status_code, 'ff_ht': rfb.data.get('montant_ht') if rfb.status_code == 201 else str(rfb.data)[:160]}
    url = '/api/django/stock/receptions-fournisseur/'
    r = api.post(url, {'bon_commande': bc.id, 'lignes': [{'ligne_commande': lc.id, 'quantite': 10}]},
                 format='json', **H)
    rec_id = r.data['id']
    rc = api.post(f'{url}{rec_id}/confirmer/', {}, format='json', **H)
    p.refresh_from_db()
    rfr = api.post(f'{url}{rec_id}/facturer/', {}, format='json', **H)
    provs = [{k: str(v) for k, v in d.items()} for d in ReceptionNonFacturee.objects.filter(
        company=co, bon_commande=bc).values('montant_provision', 'lettre', 'facture_id')]
    obs.update({'confirmer': rc.status_code, 'stock': p.quantite_stock,
                'facturer_reception': rfr.status_code,
                'facturer_reception_detail': None if rfr.status_code < 400 else str(rfr.data)[:160],
                'gr_ir': provs})
    ouvert = sum(Decimal(d['montant_provision']) for d in provs if d['lettre'] == 'False')
    obs['gr_ir_ouvert'] = str(ouvert)
    print(obs)
    temoin_ok = rfb.status_code == 201 and rc.status_code == 200 and p.quantite_stock == 10
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and ouvert == Decimal('20000.00') and rfr.status_code >= 400)
    return obs

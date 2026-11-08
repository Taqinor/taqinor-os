# flake8: noqa  (sonde PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K03 — devis (A x10 + B x1, stock 0) accepté par l'API -> chantier « Signé » ; BCF de la ligne A créé par le
service de `generer-bcf` (`creer_bcf_depuis_lignes`, chantier_origine), ENVOYÉ par l'API puis REÇU en totalité par
l'API (`bons-commande-fournisseur/<id>/recevoir/`) -> BCF « recu », B toujours en manque. Puis le lead sort de
« Signé » (PATCH confirme_recul). (T) témoin = C-ADVS-027 : même chaîne arrêtée au BCF envoyé -> 409."""
SONDE = {"constat": "C-ACSV-003", "sha": "f57951e87",
         "attendu": "repro si R : 200, chantier annulé avec un BCF « recu » du chantier ; T : 409 nommant le BCF envoyé",
         "modeles": ["ventes.Devis", "installations.Installation", "achats.BonCommandeFournisseur", "crm.Lead",
                     "installations.StockReservation"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Client, Lead
    from apps.installations.models import Installation, StockReservation
    from apps.stock.models import Fournisseur, Produit
    from apps.stock.services import creer_bcf_depuis_lignes
    from apps.ventes.models import Devis, LigneDevis
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACSV 003', slug='sonde-acsv-003')
    u = U.objects.create_user(username='sonde-acsv-003', password='x', role_legacy='admin', company=c)
    pa = Produit.objects.create(company=c, nom='Panneau 710W', sku='ACSV003-A', prix_vente=Decimal('1166.67'),
                                prix_achat=Decimal('700'), tva=Decimal('20'), quantite_stock=0)
    pb = Produit.objects.create(company=c, nom='Onduleur réseau 10kW', sku='ACSV003-B', prix_vente=Decimal('14000'),
                                prix_achat=Decimal('9000'), tva=Decimal('20'), quantite_stock=0)
    f = Fournisseur.objects.create(company=c, nom='Fournisseur Sonde ACSV 003')
    api = APIClient()
    api.force_authenticate(u)

    def appel(meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            try:
                return r.status_code, json.loads(r.content.decode('utf-8', 'replace') or '{}')
            except Exception:
                return r.status_code, {}
        except Exception as e:
            return repr(e)[:200], {}

    def cas(suffixe, recevoir):
        lead = Lead.objects.create(company=c, nom='Achats', prenom=suffixe, telephone='+21260000030' + suffixe[-1],
                                   ville='Casablanca', email=f'acsv003-{suffixe}@example.invalid')
        cl = Client.objects.create(company=c, nom='Achats', prenom=suffixe, email=f'acsv003-{suffixe}@example.invalid')
        d = Devis.objects.create(company=c, reference=f'DEV-ACSV003-{suffixe}', client=cl, lead=lead, statut='envoye',
                                 date_envoi=timezone.now(), taux_tva=Decimal('20'), created_by=u)
        LigneDevis.objects.create(devis=d, produit=pa, designation=pa.nom, quantite=Decimal('10'),
                                  prix_unitaire=pa.prix_vente, remise=Decimal('0'), ordre=0)
        LigneDevis.objects.create(devis=d, produit=pb, designation=pb.nom, quantite=Decimal('1'),
                                  prix_unitaire=pb.prix_vente, remise=Decimal('0'), ordre=1)
        o = {'accepter': appel('post', f'/api/django/ventes/devis/{d.id}/accepter/', {'nom': 'Client'})[0]}
        inst = Installation.objects.filter(devis=d, annule=False).first()
        if inst is None:
            return o, None
        with transaction.atomic():
            bon = creer_bcf_depuis_lignes(company=c, user=u, fournisseur=f,
                                          lignes=[(pa.id, pa.nom, Decimal('10'), Decimal('700'))],
                                          note='Sonde ACSV 003', chantier_origine=inst)
        o['envoyer'] = appel('post', f'/api/django/stock/bons-commande-fournisseur/{bon.id}/envoyer/')[0]
        if recevoir:
            ligne = bon.lignes.first()
            s, rr = appel('post', f'/api/django/stock/bons-commande-fournisseur/{bon.id}/recevoir/',
                          {'receptions': [{'ligne': ligne.id, 'quantite': 10}]})
            o['recevoir'] = [s, None if s == 200 else str(rr)[:200]]
        bon.refresh_from_db()
        inst.refresh_from_db()
        pa.refresh_from_db()
        o['avant_sortie'] = {'bcf': bon.statut, 'chantier': inst.statut, 'stock_A': pa.quantite_stock,
                             'resa_A_actives': sum(StockReservation.objects.filter(
                                 installation=inst, produit=pa, active=True).values_list('quantite', flat=True))}
        s, rl = appel('patch', f'/api/django/crm/leads/{lead.id}/', {'stage': stages.CONTACTED, 'confirme_recul': True})
        o['sortie_signe'] = [s, rl.get('detail') if isinstance(rl, dict) else None]
        d.refresh_from_db()
        inst.refresh_from_db()
        bon.refresh_from_db()
        lead.refresh_from_db()
        o['final'] = {'devis': d.statut, 'chantier_annule': inst.annule, 'bcf': bon.statut, 'lead': lead.stage,
                      'resa_A_actives': sum(StockReservation.objects.filter(
                          installation=inst, produit=pa, active=True).values_list('quantite', flat=True))}
        return o, inst

    obs = {}
    obs['T'], _ = cas('T1', recevoir=False)
    obs['R'], _ = cas('R1', recevoir=True)
    t, r = obs['T'], obs['R']
    temoin_ok = bool(t.get('sortie_signe', [None])[0] == 409)
    defaut = bool(r.get('avant_sortie', {}).get('bcf') == 'recu' and r.get('avant_sortie', {}).get('chantier') == 'signe'
                  and r.get('sortie_signe', [None])[0] == 200 and r['final']['chantier_annule'])
    obs['temoin_ok'] = temoin_ok
    return {'repro': bool(temoin_ok and defaut), 'observe': obs}

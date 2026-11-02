# flake8: noqa  (sonde de vérification C-L5-2, rejouable par scripts/sonde.py)
"""C-L5-2 — dés-acceptation alors qu'un BCF du chantier est ENVOYÉ au fournisseur : devis (A ×10 + B ×1, stock 0)
accepté par l'API → chantier « Signé » ; BCF créé par le service que `generer-bcf` appelle
(`stock.services.creer_bcf_depuis_lignes`, ligne A seule, `chantier_origine`=chantier) puis ENVOYÉ par l'API
(`bons-commande-fournisseur/<id>/envoyer/`) → B encore en manque ⇒ chantier reste « Signé » ; puis le commercial sort
le lead de « Signé » (PATCH crm/leads/<id>/ stage=CONTACTED). Relevé : réponse, chantier annulé ?, BCF toujours
envoyé ? La DA (chaîne d'approbation) n'est PAS rejouée ici. Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-027", "sha": "1dfa7986c",
         "attendu": "BCF envoyé pour le chantier = suite réelle → 409 nommant le BCF (défaut : 200, chantier annulé, BCF envoyé orphelin)",
         "modeles": ["ventes.Devis", "installations.Installation", "stock.BonCommandeFournisseur", "crm.Lead"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Client, Lead
    from apps.installations.models import Installation
    from apps.stock.models import BonCommandeFournisseur, Fournisseur, Produit
    from apps.stock.services import creer_bcf_depuis_lignes
    from apps.ventes.models import Devis, LigneDevis
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 027', slug='sonde-advs-027')
    u = U.objects.create_user(username='sonde-advs-027', password='x', role_legacy='admin', company=c)
    lead = Lead.objects.create(company=c, nom='Achats', prenom='Desaccept', telephone='+212600002700',
                               ville='Casablanca', email='sonde-advs-027@example.invalid')
    cl = Client.objects.create(company=c, nom='Achats', prenom='Desaccept', email='sonde-advs-027@example.invalid')
    pa = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS027-A',
                                prix_vente=Decimal('1166.67'), prix_achat=Decimal('700'), tva=Decimal('20'), quantite_stock=0)
    pb = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 10kW Monophasé', sku='ADVS027-B',
                                prix_vente=Decimal('14000'), prix_achat=Decimal('9000'), tva=Decimal('20'), quantite_stock=0)
    d = Devis.objects.create(company=c, reference='DEV-ADVS027-01', client=cl, lead=lead, statut='envoye',
                             taux_tva=Decimal('20'), created_by=u)
    LigneDevis.objects.create(devis=d, produit=pa, designation=pa.nom, quantite=Decimal('10'),
                              prix_unitaire=pa.prix_vente, remise=Decimal('0'), ordre=0)
    LigneDevis.objects.create(devis=d, produit=pb, designation=pb.nom, quantite=Decimal('1'),
                              prix_unitaire=pb.prix_vente, remise=Decimal('0'), ordre=1)
    api = APIClient()
    api.force_authenticate(u)
    obs = {}

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

    s, _ = appel('post', f'/api/django/ventes/devis/{d.id}/accepter/', {'nom': 'Client'})
    obs['accepter'] = s
    lead.refresh_from_db()
    inst = Installation.objects.filter(devis=d, annule=False).first()
    obs['apres_acceptation'] = {'lead': lead.stage, 'chantier': getattr(inst, 'statut', None)}
    if inst is None:
        return {'repro': False, 'observe': obs}
    f = Fournisseur.objects.create(company=c, nom='Fournisseur Sonde 027')
    try:
        with transaction.atomic():
            bon = creer_bcf_depuis_lignes(company=c, user=u, fournisseur=f,
                                          lignes=[(pa.id, pa.nom, Decimal('10'), Decimal('700'))],
                                          note='Sonde 027', chantier_origine=inst)
    except Exception as e:
        obs['bcf_err'] = repr(e)[:200]
        return {'repro': False, 'observe': obs}
    s, rb = appel('post', f'/api/django/stock/bons-commande-fournisseur/{bon.id}/envoyer/')
    bon.refresh_from_db()
    inst.refresh_from_db()
    obs['bcf_envoi'] = [s, bon.statut, rb.get('detail') if isinstance(rb, dict) else None]
    obs['chantier_apres_envoi_bcf'] = inst.statut
    s, rl = appel('patch', f'/api/django/crm/leads/{lead.id}/', {'stage': stages.CONTACTED, 'confirme_recul': True})
    obs['sortie_signe'] = [s, (rl.get('detail') or rl.get('stage')) if isinstance(rl, dict) else None]
    d.refresh_from_db()
    inst.refresh_from_db()
    bon.refresh_from_db()
    lead.refresh_from_db()
    obs['final'] = {'devis': d.statut, 'chantier_annule': inst.annule, 'chantier_statut': inst.statut,
                    'bcf_statut': bon.statut, 'bcf_chantier_origine': bon.chantier_origine_id == inst.id,
                    'lead': lead.stage}
    repro = bool(obs['sortie_signe'][0] == 200 and inst.annule and bon.statut == 'envoye')
    return {'repro': repro, 'observe': obs}

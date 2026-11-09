# flake8: noqa  (sonde PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K07 — devis (A x10 + B x1, stock 0) accepté par l'API -> chantier « Signé » ; BCF de A créé
(`creer_bcf_depuis_lignes`, chantier_origine) et ENVOYÉ par l'API -> suite réelle. (T) témoin : sortie de « Signé »
-> 409 (ADVS40). (R) « Annuler le chantier » par l'API (`chantiers/<id>/annuler/`, motif « client parti ») puis
sortie de « Signé » (PATCH confirme_recul). Relevé : code, devis, BCF, lead ; puis ré-acceptation par l'API : le
chantier (motif manuel) est-il réactivé ?"""
SONDE = {"constat": "C-ACSV-007", "sha": "f57951e87",
         "attendu": "repro si T = 409 puis R = 200 (devis « envoyé », BCF « envoyé » orphelin) après annulation manuelle du chantier",
         "modeles": ["ventes.Devis", "installations.Installation", "achats.BonCommandeFournisseur", "crm.Lead"]}


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
    from apps.installations.models import Installation
    from apps.stock.models import Fournisseur, Produit
    from apps.stock.services import creer_bcf_depuis_lignes
    from apps.ventes.models import Devis, LigneDevis
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACSV 007', slug='sonde-acsv-007')
    u = U.objects.create_user(username='sonde-acsv-007', password='x', role_legacy='admin', company=c)
    pa = Produit.objects.create(company=c, nom='Panneau 710W', sku='ACSV007-A', prix_vente=Decimal('1166.67'),
                                prix_achat=Decimal('700'), tva=Decimal('20'), quantite_stock=0)
    pb = Produit.objects.create(company=c, nom='Onduleur réseau 10kW', sku='ACSV007-B', prix_vente=Decimal('14000'),
                                prix_achat=Decimal('9000'), tva=Decimal('20'), quantite_stock=0)
    f = Fournisseur.objects.create(company=c, nom='Fournisseur Sonde ACSV 007')
    lead = Lead.objects.create(company=c, nom='Contour', prenom='K07', telephone='+212600000707', ville='Casablanca',
                               email='acsv007@example.invalid')
    cl = Client.objects.create(company=c, nom='Contour', prenom='K07', email='acsv007@example.invalid')
    d = Devis.objects.create(company=c, reference='DEV-ACSV007-1', client=cl, lead=lead, statut='envoye',
                             date_envoi=timezone.now(), taux_tva=Decimal('20'), created_by=u)
    LigneDevis.objects.create(devis=d, produit=pa, designation=pa.nom, quantite=Decimal('10'),
                              prix_unitaire=pa.prix_vente, remise=Decimal('0'), ordre=0)
    LigneDevis.objects.create(devis=d, produit=pb, designation=pb.nom, quantite=Decimal('1'),
                              prix_unitaire=pb.prix_vente, remise=Decimal('0'), ordre=1)
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

    def sortir():
        s, r = appel('patch', f'/api/django/crm/leads/{lead.id}/', {'stage': stages.CONTACTED, 'confirme_recul': True})
        return [s, r.get('detail') if isinstance(r, dict) else None]

    obs = {'accepter': appel('post', f'/api/django/ventes/devis/{d.id}/accepter/', {'nom': 'Client'})[0]}
    inst = Installation.objects.filter(devis=d, annule=False).first()
    if inst is None:
        return {'repro': False, 'observe': obs}
    with transaction.atomic():
        bon = creer_bcf_depuis_lignes(company=c, user=u, fournisseur=f,
                                      lignes=[(pa.id, pa.nom, Decimal('10'), Decimal('700'))],
                                      note='Sonde ACSV 007', chantier_origine=inst)
    obs['envoyer_bcf'] = appel('post', f'/api/django/stock/bons-commande-fournisseur/{bon.id}/envoyer/')[0]
    inst.refresh_from_db()
    obs['chantier_avant'] = inst.statut
    obs['T_sortie'] = sortir()
    s, r = appel('post', f'/api/django/installations/chantiers/{inst.id}/annuler/', {'motif': 'client parti'})
    inst.refresh_from_db()
    obs['annuler_chantier'] = [s, inst.annule, inst.motif_annulation]
    obs['R_sortie'] = sortir()
    d.refresh_from_db()
    bon.refresh_from_db()
    lead.refresh_from_db()
    obs['R_final'] = {'devis': d.statut, 'bcf': bon.statut, 'bcf_chantier': bon.chantier_origine_id == inst.id,
                      'lead': lead.stage}
    # ré-acceptation : le chantier annulé à la main n'est pas réactivé (motif != marqueur)
    obs['reaccepter'] = appel('post', f'/api/django/ventes/devis/{d.id}/accepter/', {'nom': 'Client'})[0]
    inst.refresh_from_db()
    obs['apres_reacceptation'] = {'annule': inst.annule, 'motif': inst.motif_annulation,
                                  'chantiers_du_devis': Installation.objects.filter(devis=d).count()}
    repro = bool(obs['T_sortie'][0] == 409 and obs['annuler_chantier'][0] == 200 and obs['R_sortie'][0] == 200
                 and d.statut == 'envoye' and bon.statut == 'envoye')
    return {'repro': repro, 'observe': obs}

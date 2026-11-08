# flake8: noqa  (sonde PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K02 — devis PAN x10 accepté par l'API -> chantier (10 réservés) ; lead sorti de « Signé » (PATCH confirme_recul)
-> devis « envoyé », chantier annulé avec le motif-marqueur, réservations libérées. Puis un responsable clique
« Réactiver » : POST `installations/chantiers/<id>/reactiver/`. Relevé : code HTTP, chantier actif ?, réservations
actives, statut du devis, étape du lead."""
SONDE = {"constat": "C-ACSV-002", "sha": "f57951e87",
         "attendu": "repro si 200 + chantier actif + réservations réamorcées alors que le devis est « envoyé » (attendu : 409)",
         "modeles": ["ventes.Devis", "installations.Installation", "installations.StockReservation", "crm.Lead"]}


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
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACSV 002', slug='sonde-acsv-002')
    u = U.objects.create_user(username='sonde-acsv-002', password='x', role_legacy='admin', company=c)
    pan = Produit.objects.create(company=c, nom='Panneau 710W', sku='ACSV002-PAN', prix_vente=Decimal('1000'),
                                 prix_achat=Decimal('600'), tva=Decimal('20'), quantite_stock=50)
    lead = Lead.objects.create(company=c, nom='Affaire', prenom='K02', telephone='+212600000202', ville='Rabat',
                               email='acsv002@example.invalid', type_installation='residentiel')
    cl = Client.objects.create(company=c, nom='Affaire', prenom='K02', email='acsv002@example.invalid')
    d = Devis.objects.create(company=c, reference='DEV-ACSV002-1', client=cl, lead=lead, statut='envoye',
                             date_envoi=timezone.now(), taux_tva=Decimal('20'), mode_installation='residentiel',
                             created_by=u)
    LigneDevis.objects.create(devis=d, produit=pan, designation=pan.nom, quantite=Decimal('10'),
                              prix_unitaire=pan.prix_vente, remise=Decimal('0'), ordre=0)
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

    def actives(inst):
        return sum(StockReservation.objects.filter(installation=inst, active=True).values_list('quantite', flat=True))

    obs = {'accepter': appel('post', f'/api/django/ventes/devis/{d.id}/accepter/', {'nom': 'Client'})[0]}
    inst = Installation.objects.filter(devis=d).first()
    if inst is None:
        return {'repro': False, 'observe': obs}
    obs['resa_apres_acceptation'] = actives(inst)
    obs['sortie_signe'] = appel('patch', f'/api/django/crm/leads/{lead.id}/',
                                {'stage': stages.FOLLOW_UP, 'confirme_recul': True})[0]
    inst.refresh_from_db()
    d.refresh_from_db()
    obs['apres_sortie'] = {'devis': d.statut, 'annule': inst.annule, 'motif': inst.motif_annulation,
                           'resa': actives(inst)}
    s, r = appel('post', f'/api/django/installations/chantiers/{inst.id}/reactiver/')
    inst.refresh_from_db()
    d.refresh_from_db()
    lead.refresh_from_db()
    obs['reactiver'] = {'http': s, 'detail': r.get('detail') if isinstance(r, dict) else None,
                        'annule': inst.annule, 'statut': inst.statut, 'resa_actives': actives(inst),
                        'devis': d.statut, 'lead': lead.stage}
    repro = bool(obs['apres_sortie']['annule'] and s == 200 and not inst.annule and d.statut == 'envoye'
                 and actives(inst) > 0)
    return {'repro': repro, 'observe': obs}

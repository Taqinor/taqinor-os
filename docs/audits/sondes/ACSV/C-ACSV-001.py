# flake8: noqa  (sonde PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K01 — V1 (PAN x10) envoyée, acceptée par l'API -> chantier ; lead sorti de « Signé » (PATCH confirme_recul) ->
chantier annulé avec le motif-marqueur ; V1 révisée par l'API (`devis/<id>/reviser/`), V2 PAN x12 passée « envoyé »
puis acceptée par l'API. Relevé : chantier de l'affaire (annule, motif, devis, bom), réservations actives.
(T) témoin : même aller-retour SANS révision (ré-acceptation du même devis, ACHT114) -> chantier réactivé."""
SONDE = {"constat": "C-ACSV-001", "sha": "f57951e87",
         "attendu": "repro si R : chantier rattaché à V2 mais annule=True (motif désacceptation), 0 réservation active ; T : réactivé",
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
    c = Company.objects.create(nom='Sonde ACSV 001', slug='sonde-acsv-001')
    u = U.objects.create_user(username='sonde-acsv-001', password='x', role_legacy='admin', company=c)
    pan = Produit.objects.create(company=c, nom='Panneau 710W', sku='ACSV001-PAN', prix_vente=Decimal('1000'),
                                 prix_achat=Decimal('600'), tva=Decimal('20'), quantite_stock=50)
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

    def affaire(suffixe):
        lead = Lead.objects.create(company=c, nom='Affaire', prenom=suffixe, telephone='+2126000010' + suffixe[-1],
                                   ville='Rabat', email=f'acsv001-{suffixe}@example.invalid',
                                   type_installation='residentiel')
        cl = Client.objects.create(company=c, nom='Affaire', prenom=suffixe, email=f'acsv001-{suffixe}@example.invalid')
        d = Devis.objects.create(company=c, reference=f'DEV-ACSV001-{suffixe}', client=cl, lead=lead, statut='envoye',
                                 date_envoi=timezone.now(), taux_tva=Decimal('20'), mode_installation='residentiel',
                                 created_by=u)
        LigneDevis.objects.create(devis=d, produit=pan, designation=pan.nom, quantite=Decimal('10'),
                                  prix_unitaire=pan.prix_vente, remise=Decimal('0'), ordre=0)
        return lead, d

    def etat(inst):
        inst.refresh_from_db()
        return {'id': inst.id, 'annule': inst.annule, 'motif': inst.motif_annulation, 'devis_id': inst.devis_id,
                'bom': {str(li.get('produit_id')): li.get('quantite') for li in (inst.bom or [])},
                'resa_actives': sum(StockReservation.objects.filter(installation=inst, active=True)
                                    .values_list('quantite', flat=True))}

    obs = {}
    # R — avec révision
    lead, v1 = affaire('R1')
    obs['R_accepter_v1'] = appel('post', f'/api/django/ventes/devis/{v1.id}/accepter/', {'nom': 'Client'})[0]
    inst = Installation.objects.filter(devis=v1).first()
    if inst is None:
        return {'repro': False, 'observe': obs, 'raison': 'pas de chantier à l\'acceptation V1'}
    obs['R_apres_acceptation'] = etat(inst)
    s, rl = appel('patch', f'/api/django/crm/leads/{lead.id}/', {'stage': stages.FOLLOW_UP, 'confirme_recul': True})
    obs['R_sortie_signe'] = [s, rl.get('detail') if isinstance(rl, dict) else None]
    v1.refresh_from_db()
    obs['R_apres_sortie'] = {'v1': v1.statut, 'chantier': etat(inst)}
    s, rr = appel('post', f'/api/django/ventes/devis/{v1.id}/reviser/')
    v1.refresh_from_db()
    obs['R_reviser'] = [s, v1.superseded_by_id]
    if not v1.superseded_by_id:
        obs['R_reviser_detail'] = str(rr)[:200]
        return {'repro': False, 'observe': obs}
    v2 = Devis.objects.get(pk=v1.superseded_by_id)
    LigneDevis.objects.filter(devis=v2, produit=pan).update(quantite=Decimal('12'))
    Devis.objects.filter(pk=v2.pk).update(statut='envoye', date_envoi=timezone.now())
    s, ra = appel('post', f'/api/django/ventes/devis/{v2.id}/accepter/', {'nom': 'Client'})
    v2.refresh_from_db()
    lead.refresh_from_db()
    obs['R_accepter_v2'] = [s, v2.statut, lead.stage, None if s == 200 else str(ra)[:200]]
    chantiers = list(Installation.objects.filter(company=c, lead=lead).values_list('id', flat=True))
    obs['R_chantiers_affaire'] = chantiers
    obs['R_final'] = etat(inst)
    # T — témoin ACHT114 : ré-acceptation du même devis
    leadT, dT = affaire('T1')
    appel('post', f'/api/django/ventes/devis/{dT.id}/accepter/', {'nom': 'Client'})
    instT = Installation.objects.filter(devis=dT).first()
    sT = appel('patch', f'/api/django/crm/leads/{leadT.id}/', {'stage': stages.FOLLOW_UP, 'confirme_recul': True})[0]
    LigneDevis.objects.filter(devis=dT, produit=pan).update(quantite=Decimal('12'))
    sT2 = appel('post', f'/api/django/ventes/devis/{dT.id}/accepter/', {'nom': 'Client'})[0]
    obs['T'] = {'sortie': sT, 'reaccepter': sT2, 'final': etat(instT) if instT else None}
    f = obs['R_final']
    temoin_ok = bool(obs['T']['final'] and obs['T']['final']['annule'] is False
                     and obs['T']['final']['resa_actives'] == 12)
    defaut = bool(obs['R_accepter_v2'][0] == 200 and f['devis_id'] == v2.id and f['annule'] is True
                  and f['resa_actives'] == 0)
    obs['temoin_ok'] = temoin_ok
    return {'repro': bool(temoin_ok and defaut), 'observe': obs}

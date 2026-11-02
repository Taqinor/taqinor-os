# flake8: noqa  (sonde du parcours PA4 « Argent », rejouable par scripts/sonde.py — AMET93)
"""K20 : `apps/ventes/domain/facturation_vente.py::retirer_acompte_automatique` tient pour « automatique » TOUT
brouillon d'acompte du devis à référence provisoire sans paiement compté — or « Facturer l'acompte » saisi à la main
(`facturer_vente(nature='acompte', emettre=False)` → `creer_brouillon_tranche` / `_editer_brouillon`) produit le
même « BROUILLON-<id> ». `cycle_vie.py::annuler_acceptation` l'annule AVANT `raison_blocage_annulation_acceptation`.
Chaîne réelle : POST accepter, POST facturer (acompte 35 000 TTC, brouillon), PATCH lead SIGNED → FOLLOW_UP.
Deux devis : A (acompte automatique créé par l'acceptation puis ressaisi), B (accepté sans échéancier figé : le
brouillon n'existe QUE par la saisie). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-020", "sha": "56d5b623a",
         "attendu": "Lead sorti de « Signé » → 200 ; brouillon d'acompte saisi à la main (35 000 TTC) ANNULÉ, devis "
                    "« envoyé », échéancier réécrit gardé ; attendu sain : 409 nommant le brouillon, ou brouillon gardé",
         "modeles": ["authentication.Company", "crm.Lead", "ventes.Devis", "ventes.Facture"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    import apps.crm.stages as stages
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, Facture
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AARG-020', slug='sonde-aarg-020')
    u = get_user_model().objects.create_user(username='sonde-aarg-020', password='x', company=co,
                                             role_legacy='responsable')
    api = APIClient()
    api.force_authenticate(u)
    p = Produit.objects.create(company=co, nom='Centrale', sku='SONDE-AARG-020', prix_vente=Decimal('100000'),
                               prix_achat=Decimal('0'), quantite_stock=50)
    out = {}
    for cas in ('A_route_accepter', 'B_sans_auto'):
        cl = Client.objects.create(company=co, nom='K20', prenom=cas, email=f'sonde-aarg-020-{cas}@example.invalid')
        lead = Lead.objects.create(company=co, nom=f'Lead K20 {cas}', stage=stages.FOLLOW_UP)
        d = Devis.objects.create(company=co, reference=f"DEV-{timezone.now():%Y%m}-92{len(out)}0", client=cl,
                                 lead=lead, statut=Devis.Statut.ENVOYE, date_envoi=timezone.now(),
                                 taux_tva=Decimal('20'))
        LigneDevis.objects.create(devis=d, produit=p, designation='Centrale', quantite=Decimal('1'),
                                  prix_unitaire=Decimal('100000'))
        etapes = {}
        if cas == 'A_route_accepter':
            r = api.post(f'/api/django/ventes/devis/{d.id}/accepter/', {'nom': 'M. Client'}, format='json', **H)
            etapes['accepter'] = r.status_code
        else:
            Devis.objects.filter(pk=d.pk).update(statut=Devis.Statut.ACCEPTE, date_acceptation=timezone.now())
        Lead.objects.filter(pk=lead.pk).update(stage=stages.SIGNED)
        auto = list(Facture.objects.filter(devis=d).values_list('id', 'reference', 'statut', 'montant_ttc'))
        r = api.post(f'/api/django/ventes/devis/{d.id}/facturer/',
                     {'nature': 'acompte', 'montant_ttc': '35000.00', 'emettre': False}, format='json', **H)
        etapes['facturer'] = (r.status_code, r.data.get('facture') if r.status_code < 300 else r.data)
        fid = (r.data.get('facture') or {}).get('id') if r.status_code < 300 else None
        d.refresh_from_db()
        ech_avant = d.echeancier
        r = api.patch(f'/api/django/crm/leads/{lead.id}/', {'stage': stages.FOLLOW_UP, 'confirme_recul': True},
                      format='json', **H)
        etapes['sortie_signe'] = (r.status_code, None if r.status_code < 300 else r.data)
        d.refresh_from_db()
        lead.refresh_from_db()
        f = Facture.objects.filter(pk=fid).first() if fid else None
        out[cas] = {'etapes': etapes, 'brouillon_auto_avant_saisie': [(a, b, c, str(t)) for a, b, c, t in auto],
                    'facture': (f.id, f.reference, f.statut, str(f.total_ttc)) if f else None,
                    'devis_statut': d.statut, 'lead_stage': lead.stage,
                    'echeancier_avant': ech_avant, 'echeancier_apres': d.echeancier}
        if cas == 'A_route_accepter':  # ré-acceptation : le montant saisi revient-il par l'échéancier ?
            r = api.post(f'/api/django/ventes/devis/{d.id}/accepter/', {'nom': 'M. Client'}, format='json', **H)
            out[cas]['reacceptation'] = (r.status_code, list(
                Facture.objects.filter(devis=d).exclude(pk=fid).values_list('reference', 'statut', 'montant_ttc')))
    print(out)
    repro = {k: bool(v['facture']) and v['facture'][2] == Facture.Statut.ANNULEE
             and v['etapes']['sortie_signe'][0] == 200 and v['devis_statut'] == Devis.Statut.ENVOYE
             for k, v in out.items()}
    return {'repro': any(repro.values()), 'repro_par_cas': repro, 'detail': out}

# flake8: noqa  (sonde de critique de complétude PA1 — Fable B.6, rejouable par scripts/sonde.py)
"""C-ACVI-192 — étape PA1.08 « lead → devis », lentille ARGENT : aucun constat du dossier ne porte sur le
chiffre client que PA1 transmet à PA3. Règle fondateur du 30/09/2026 (kwh-declare-vs-factures) : un kWh
mensuel tapé qui contredit les factures déclarées (ratio hors [0,5 ; 2], `ventes.horaire.conso.
coherence_kwh_declare_factures`) BLOQUE l'enregistrement du devis « jusqu'à correction de la fiche ». Côté
PA1 : la fiche accepte-t-elle la contradiction sans un mot (PATCH, questionnaire public), et la porte de
passage `POST crm/leads/<id>/devis-auto/` répond-elle « Lead prêt pour le devis automatique » sur des
chiffres que PA3 refusera ? Le panneau d'appel et la fiche servie portent-ils un avertissement ?
Lead réel de la démo (résidentiel, devis existant), transaction annulée."""
SONDE = {"constat": "C-ACVI-192", "sha": "352ae5455",
         "attendu": "fiche ou passage lead→devis signale la contradiction (409 ou champ d'avertissement) ; "
                    "défaut supposé : PATCH 200 muet, questionnaire 200, devis-auto 200 « prêt »",
         "modeles": ["crm.Lead", "crm.LeadActivity", "ventes.Devis"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from apps.crm.models import Lead, LeadActivity
    from apps.crm.questionnaire import mint_lien
    from apps.crm.devis_auto import champs_manquants
    from apps.ventes.horaire.conso import coherence_kwh_declare_factures
    from apps.ventes.models import Devis
    U = get_user_model()
    ua = U.objects.filter(username='demo_admin', is_active=True).first()
    c = ua.company
    api, pub = APIClient(), APIClient()
    api.force_authenticate(ua)

    def appel(cl, meth, u, corps=None):
        try:
            with transaction.atomic():
                r = getattr(cl, meth)(u, corps or {}, format='json', HTTP_HOST='localhost')
            t = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(t), t
            except Exception:
                return r.status_code, {}, t
        except Exception as e:
            return 599, {'_exc': repr(e)[:200]}, ''

    # un lead résidentiel réel, déjà « prêt » (devis existant)
    lead = None
    for dv in Devis.objects.filter(company=c, lead__isnull=False, is_active=True).select_related('lead').order_by('-id')[:60]:
        l = dv.lead
        if (l.type_installation or 'residentiel') == 'residentiel' and not l.perdu and not l.is_archived \
                and not champs_manquants(l) and l.facture_hiver:
            lead = l
            break
    if lead is None:
        return 'STATIQUE : aucun lead résidentiel prêt pour le devis dans la démo'
    lead.owner = ua
    lead.save(update_fields=['owner'])
    L = f'/api/django/crm/leads/{lead.id}/'
    obs = {'lead': lead.id, 'facture_hiver': str(lead.facture_hiver), 'facture_ete': str(lead.facture_ete),
           'kwh_avant': str(lead.conso_mensuelle_kwh)}
    # témoin : devis-auto avant toute contradiction
    s0, r0, _ = appel(api, 'post', L + 'devis-auto/')
    obs['devis_auto_temoin'] = (s0, r0.get('detail') if isinstance(r0, dict) else None)
    # 1. PATCH : facture 300 MAD, 5 000 kWh/mois (×30 contradictoire)
    n0 = LeadActivity.objects.filter(lead=lead).count()
    s, r, t = appel(api, 'patch', L, {'facture_hiver': '300', 'facture_ete': '300', 'conso_mensuelle_kwh': '5000'})
    lead.refresh_from_db()
    coh = coherence_kwh_declare_factures(lead.conso_mensuelle_kwh, [lead.facture_hiver, lead.facture_ete])
    obs['patch'] = {'statut': s, 'kwh': str(lead.conso_mensuelle_kwh), 'facture': str(lead.facture_hiver),
                    'coherence_pa3': ({k: (str(v) if k != 'ratios' else [round(float(x), 2) for x in v])
                                       for k, v in coh.items()} if coh else None),
                    'avertissement_dans_la_reponse': any(m in t.lower() for m in ('incoh', 'contrad', 'avertis')),
                    'chatter_delta': LeadActivity.objects.filter(lead=lead).count() - n0}
    # 2. la fiche servie et le panneau d'appel disent-ils quelque chose ?
    s1, r1, t1 = appel(api, 'get', L)
    s2, r2, t2 = appel(api, 'get', L + 'panneau-appel/')
    obs['fiche'] = {'statut': s1, 'mots': [m for m in ('incoh', 'contrad', 'kwh') if m in t1.lower()],
                    'incoherence_segment': r1.get('incoherence_segment') if isinstance(r1, dict) else None}
    obs['panneau_appel'] = {'statut': s2, 'mots': [m for m in ('incoh', 'contrad', 'facture') if m in t2.lower()],
                            'cles': sorted(r2.keys())[:20] if isinstance(r2, dict) else None}
    # 3. passage PA1.08 : devis-auto
    s3, r3, _ = appel(api, 'post', L + 'devis-auto/')
    obs['devis_auto'] = (s3, r3.get('detail') if isinstance(r3, dict) else None)
    # 4. le client lui-même, par le questionnaire public : kWh 5 000 sur facture 300
    lien, _, _ = mint_lien(lead, user=ua)
    s4, r4, _ = appel(pub, 'post', f'/api/django/crm/public/questionnaire/{lien.token}/',
                      {'section': 'energie', 'reponses': {'conso_mensuelle_kwh': 6000, 'facture_hiver': 250}})
    lead.refresh_from_db()
    obs['questionnaire_public'] = {'statut': s4, 'corps': r4, 'kwh': str(lead.conso_mensuelle_kwh),
                                   'facture': str(lead.facture_hiver)}
    s5, r5, _ = appel(api, 'post', L + 'devis-auto/')
    obs['devis_auto_apres_client'] = (s5, r5.get('detail') if isinstance(r5, dict) else None)
    repro = bool(coh and not coh['coherent'] and s == 200 and s3 == 200
                 and not obs['patch']['avertissement_dans_la_reponse'])
    return {'repro': repro, 'observe': obs}

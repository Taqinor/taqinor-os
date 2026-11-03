# flake8: noqa  (sonde de parcours PA1, rejouable par scripts/sonde.py — AMET93)
"""PA1 bout en bout (C19) sur UN enregistrement, par l'API réelle, société démo : POST /crm/leads/ (saisie
manuelle) → cadence « contact » démarrée (touches) → PATCH qualification (chatter old→new, score, relecture
identique) → touche « fait » (suivante matérialisée, jamais deux échues) → POST /visites/ (planifiée ; recalage
cadence) → terminer (gate de complétude : contournée par le service si des pièces manquent, dit dans l'observé)
→ valider (feu vert ; récap sur la fiche, `visite_effectuee`) → négatifs : société B 404 partout, visite doublée
déplacée et non doublée, valider avant terminer 409, terminer bis idempotent, PATCH sans changement muet,
`company` / `owner` étrangers refusés. Oracles : aucune ≥ 500 ; `prix_achat` absent ; chaque étape 2xx ou le
refus attendu. Transaction annulée."""
SONDE = {"constat": "parcours-PA1", "sha": "352ae5455",
         "attendu": "chaque étape 2xx ; cadence contact née (≥ 1 touche, ≤ 1 échue) ; PATCH relu identique ; "
                    "visite planifiée → terminée → validée ; B → 404 ; aucun 5xx ; aucun prix_achat",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "visites.VisiteTerrain"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.urls import reverse
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm.models import Lead, LeadActivity
    from apps.crm.models_cadence import RelanceEtape
    from apps.visites.models import VisiteTerrain
    from apps.visites import services as vs
    U = get_user_model()
    ua = U.objects.filter(username='demo_admin', is_active=True).first()
    if ua is None:
        ua = U.objects.filter(username__startswith='demo_resp', is_active=True).order_by('id').first()
    ub = U.objects.filter(is_active=True).exclude(company=ua.company).exclude(company=None).order_by('id').first()
    api, apib = APIClient(), APIClient()
    api.force_authenticate(ua)
    if ub is not None:
        apib.force_authenticate(ub)
    etapes, fuites = [], []

    def appel(nom, client, meth, url, corps=None, attendu=None):
        try:
            with transaction.atomic():
                r = getattr(client, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
        except Exception as e:
            import traceback
            etapes.append((nom, 599, ''.join(traceback.format_exception_only(type(e), e))[:300]))
            return 599, {}
        txt = r.content.decode('utf-8', 'replace') if hasattr(r, 'content') else ''
        ok = r.status_code < 400 or attendu == r.status_code
        etapes.append((nom, r.status_code, '' if ok else txt[:220]))
        if 'prix_achat' in txt:
            fuites.append(nom)
        try:
            return r.status_code, json.loads(txt)
        except Exception:
            return r.status_code, {}

    leads_url = reverse('lead-list')
    visites_url = reverse('visites-visite-list')
    touches_url = reverse('relance-etape-list')
    obs = {'utilisateur_A': ua.username, 'societe_A': ua.company_id,
           'utilisateur_B': getattr(ub, 'username', None), 'societe_B': getattr(ub, 'company_id', None)}

    # 1. arrivée : saisie manuelle
    corps = {'nom': 'Parcours', 'prenom': 'PA1', 'telephone': '+212600001001', 'email': 'sonde-acvi-pa1@example.invalid',
             'ville': 'Casablanca', 'facture_hiver': '900', 'facture_ete': '700'}
    s, cree = appel('creer lead', api, 'post', leads_url, corps)
    lead = Lead.objects.filter(company=ua.company, email='sonde-acvi-pa1@example.invalid').order_by('-id').first()
    if lead is None:
        obs['etapes'] = etapes
        return {'repro': True, 'observe': obs}
    url_lead = f'{leads_url}{lead.id}/'

    def touches():
        qs = RelanceEtape.objects.filter(lead=lead).order_by('ordre', 'id')
        return [(t.cadence, t.ordre, t.canal, str(t.due_date), t.statut) for t in qs]

    def chatter():
        return LeadActivity.objects.filter(lead=lead).count()

    obs['creation'] = {'stage': lead.stage, 'owner': getattr(lead.owner, 'username', None), 'score': getattr(lead, 'score', None),
                       'source': lead.source, 'chatter': chatter(), 'touches': touches()}
    echues = [t for t in touches() if t[4] not in ('fait', 'annulee', 'sautee') and t[3] <= str(timezone.localdate())]
    obs['touches_echues_apres_creation'] = len(echues)

    # 2. qualification : PATCH, relecture, PATCH identique muet
    avant = chatter()
    s, _ = appel('patch ville', api, 'patch', url_lead, {'ville': 'Rabat', 'conso_mensuelle_kwh': '450'})
    lead.refresh_from_db()
    s, lu = appel('relire', api, 'get', url_lead)
    obs['qualification'] = {'ville': lead.ville, 'kwh': str(lead.conso_mensuelle_kwh), 'score': getattr(lead, 'score', None),
                            'chatter_delta': chatter() - avant, 'ville_api': lu.get('ville')}
    avant = chatter()
    s, _ = appel('patch identique', api, 'patch', url_lead, {'ville': 'Rabat', 'conso_mensuelle_kwh': '450'})
    obs['patch_identique_chatter_delta'] = chatter() - avant
    s, _ = appel('patch company etrangere', api, 'patch', url_lead, {'company': getattr(ub, 'company_id', 0) or 0})
    lead.refresh_from_db()
    obs['company_apres_patch'] = lead.company_id
    if ub is not None:
        s, _ = appel('patch owner etranger', api, 'patch', url_lead, {'owner': ub.id}, attendu=404)
        lead.refresh_from_db()
        obs['owner_apres_patch_etranger'] = (s, getattr(lead.owner, 'username', None))

    # 3. cadence : première touche faite → suivante
    t0 = RelanceEtape.objects.filter(lead=lead).exclude(statut='fait').order_by('ordre', 'id').first()
    if t0 is not None:
        s, r = appel('touche fait', api, 'post', f'{touches_url}{t0.id}/fait/', {'outcome': 'non_joint', 'note': 'sonde PA1'})
        obs['touche_fait'] = {'statut': s, 'touches': touches()}
    else:
        obs['touche_fait'] = 'aucune touche (cadence non démarrée)'

    # 4. visite planifiée (deux fois : déplacée, jamais doublée)
    demain = (timezone.localdate() + dt.timedelta(days=2)).isoformat()
    s, v = appel('planifier visite', api, 'post', visites_url, {'lead': lead.id, 'date_prevue': demain, 'notes': 'sonde PA1'})
    s2, v2 = appel('planifier visite bis', api, 'post', visites_url,
                   {'lead': lead.id, 'date_prevue': (timezone.localdate() + dt.timedelta(days=3)).isoformat()})
    visites = list(VisiteTerrain.objects.filter(lead=lead).order_by('id'))
    obs['visite'] = {'nb': len(visites), 'statuts': [x.statut for x in visites], 'dates': [str(x.date_prevue) for x in visites],
                     'touches_apres': touches(), 'chatter': chatter()}
    if not visites:
        obs['etapes'] = etapes
        return {'repro': True, 'observe': obs}
    vis = visites[-1]
    url_v = f'{visites_url}{vis.id}/'
    # B : lecture / écriture du lead et de la visite
    if ub is not None:
        sb = [appel('B lit lead', apib, 'get', url_lead, attendu=404)[0],
              appel('B patch lead', apib, 'patch', url_lead, {'ville': 'Fuite'}, attendu=404)[0],
              appel('B lit visite', apib, 'get', url_v, attendu=404)[0],
              appel('B visite sur lead A', apib, 'post', visites_url, {'lead': lead.id, 'date_prevue': demain}, attendu=404)[0]]
        obs['societe_B_codes'] = sb
        obs['visites_apres_B'] = VisiteTerrain.objects.filter(lead=lead).count()
    # 5. valider avant terminer → 409 ; terminer (gate) ; terminer bis
    s, _ = appel('valider avant terminer', api, 'post', f'{url_v}valider/', attendu=409)
    s, r = appel('terminer incomplete', api, 'post', f'{url_v}terminer/', attendu=409)
    obs['terminer_incomplete'] = {'statut': s, 'nb_manquants': len(r.get('manquants') or []) if isinstance(r, dict) else None}
    # pièces : mesures par l'API (3 catégories du gabarit toiture), photos par l'ORM (le stockage objet est hors sonde)
    mesures = {'toiture': {'longueur_m': '8', 'largeur_m': '5', 'pente_deg': '20', 'orientation': 'sud',
                           'type_couverture': 'beton', 'etat_couverture': 'bon'},
               'tableau': {'calibre_disjoncteur_a': '40', 'type_alimentation': 'mono', 'emplacements_libres': '4'},
               'local_onduleur': {'largeur_mur_cm': '120', 'hauteur_mur_cm': '150', 'profondeur_degagement_cm': '80',
                                  'distance_tableau_m': '3', 'local_abrite': True, 'local_ventile': True}}
    for cat, val in mesures.items():
        appel(f'mesures {cat}', api, 'patch', f'{url_v}mesures/', {'categorie': cat, 'valeurs': val})
    from django.contrib.contenttypes.models import ContentType
    from apps.records.models import Attachment
    from apps.visites.models import VisiteMedia
    ct = ContentType.objects.get(app_label='crm', model='lead')
    for slot in ('toiture_vue_generale', 'toiture_vue_generale', 'toiture_obstacles', 'tableau_ouvert', 'onduleur_mur', 'general_facade'):
        att = Attachment.objects.create(company=ua.company, content_type=ct, object_id=lead.id, uploaded_by=ua,
                                        filename=f'{slot}.png', file_key=f'sonde/{slot}', mime='image/png', size=64)
        VisiteMedia.objects.create(company=ua.company, visite=vis, attachment=att, slot_code=slot, commentaire='sonde')
    s, r = appel('terminer', api, 'post', f'{url_v}terminer/')
    obs['terminer'] = {'statut': s, 'manquants': (r.get('manquants') if isinstance(r, dict) else None)}
    vis.refresh_from_db()
    s, _ = appel('terminer bis', api, 'post', f'{url_v}terminer/')
    lead.refresh_from_db()
    obs['apres_terminee'] = {'touches': touches(), 'chatter': chatter(), 'visite_effectuee': lead.visite_effectuee}
    # 6. revue : valider
    s, r = appel('valider', api, 'post', f'{url_v}valider/')
    vis.refresh_from_db()
    lead.refresh_from_db()
    s2, _ = appel('valider bis', api, 'post', f'{url_v}valider/', attendu=409)
    s3, _ = appel('patch visite validee', api, 'patch', url_v, {'notes': 'après feu vert'}, attendu=400)
    obs['revue'] = {'statut_http': s, 'statut_visite': vis.statut, 'validee_le': str(vis.validee_le), 'visite_effectuee': lead.visite_effectuee,
                    'stage': lead.stage, 'chatter': chatter(), 'touches': touches(), 'valider_bis': s2, 'patch_apres_feu_vert': s3}
    erreurs = [e for e in etapes if e[1] >= 500 or (e[1] >= 400 and e[2])]
    repro = bool(erreurs or fuites or vis.statut != 'validee')
    obs['etapes'] = etapes
    obs['fuites_prix_achat'] = fuites
    obs['erreurs'] = erreurs
    return {'repro': repro, 'observe': obs}

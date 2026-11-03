# flake8: noqa  (constat C-ACVI-133 : copie rejouable de la sonde groupée C-ACVI-126, sa clé dans `observe`)
"""G-7 + G-14 (vérificateur frais). Société démo, API réelle, transaction annulée.
G-7 (C-ACVI-126) : PATCH /visites/visites/<id>/ sur un BROUILLON : {date_prevue:'2020-01-01'} → code ? ;
      {commercial: <compte INACTIF de la même société>} → code ? (témoin : POST /visites/visites/ avec ce
      même commercial inactif → planifier_visite le refuse ?)
G-14 (C-ACVI-133) : PATCH /crm/leads/<id>/ {stage} sur un lead PERDU → code et forme du corps (`stage` sans `detail` ?)."""
SONDE = {"constat": "C-ACVI-126+133", "sha": "352ae5455",
         "attendu": "G-7 : date passée refusée (409) ; commercial inactif refusé comme à la création ; "
                    "G-14 : 409 dont le corps porte un `detail` lisible par l'écran",
         "modeles": ["crm.Lead", "crm.LeadActivity", "visites.VisiteTerrain", "authentication.CustomUser"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.urls import reverse
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm.models import Lead
    from apps.visites.models import VisiteTerrain
    U = get_user_model()
    ua = U.objects.filter(username='demo_admin', is_active=True).first()
    api = APIClient()
    api.force_authenticate(ua)
    leads_url = reverse('lead-list')
    visites_url = reverse('visites-visite-list')
    today = timezone.localdate()
    obs = {}

    def appel(meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt)
            except Exception:
                return r.status_code, txt[:300]
        except Exception as e:
            return 599, repr(e)[:300]

    def creer(suffixe):
        appel('post', leads_url, {'nom': 'SondeG7', 'prenom': suffixe, 'telephone': '+2126000126' + suffixe,
                                  'email': f'sonde-acvi-126-{suffixe}@example.invalid', 'ville': 'Casablanca'})
        return Lead.objects.filter(email=f'sonde-acvi-126-{suffixe}@example.invalid').order_by('-id').first()

    # G-7
    l1 = creer('01')
    s, v = appel('post', visites_url, {'lead': l1.id, 'date_prevue': (today + dt.timedelta(days=5)).isoformat()})
    vis = VisiteTerrain.objects.filter(lead_id=l1.id).order_by('-id').first()
    obs['G7_creation'] = {'statut': s, 'visite_statut': getattr(vis, 'statut', None)}
    url_v = f'{visites_url}{vis.id}/'
    s, r = appel('patch', url_v, {'date_prevue': '2020-01-01'})
    vis.refresh_from_db()
    obs['G7_patch_date_passee'] = {'statut': s, 'corps': r, 'date_apres': str(vis.date_prevue)}
    inactif = U.objects.create_user(username='sonde-acvi-126-inactif', password='x', company=ua.company,
                                    role=getattr(ua, 'role', None), is_active=False)
    avant = vis.commercial_id
    s, r = appel('patch', url_v, {'commercial': inactif.id})
    vis.refresh_from_db()
    obs['G7_patch_commercial_inactif'] = {'statut': s, 'corps': r if s >= 400 else None,
                                          'commercial_avant': avant, 'commercial_apres': vis.commercial_id,
                                          'inactif_id': inactif.id}
    l2 = creer('02')
    s, r = appel('post', visites_url, {'lead': l2.id, 'date_prevue': (today + dt.timedelta(days=6)).isoformat(),
                                       'commercial': inactif.id})
    obs['G7_temoin_post_commercial_inactif'] = {'statut': s, 'corps': r if s >= 400 else None}
    repro_g7 = vis.commercial_id == inactif.id

    # G-14
    l3 = creer('03')
    appel('patch', f'{leads_url}{l3.id}/', {'perdu': True, 'motif_perte': 'Prix trop élevé'})
    l3.refresh_from_db()
    choix = [c[0] for c in Lead._meta.get_field('stage').choices]
    cible = next(c for c in choix if c != l3.stage)
    s, r = appel('patch', f'{leads_url}{l3.id}/', {'stage': cible})
    l3.refresh_from_db()
    obs['G14_patch_stage_perdu'] = {'perdu': l3.perdu, 'stage_cible': cible, 'statut': s, 'corps': r,
                                    'cles_corps': sorted(r.keys()) if isinstance(r, dict) else None,
                                    'stage_apres': l3.stage}
    repro_g14 = s == 409 and isinstance(r, dict) and 'detail' not in r
    obs['repro_G7_commercial_inactif_accepte'] = repro_g7
    obs['repro_G14_sans_detail'] = repro_g14
    return {'repro': bool(repro_g7 or repro_g14), 'observe': obs}

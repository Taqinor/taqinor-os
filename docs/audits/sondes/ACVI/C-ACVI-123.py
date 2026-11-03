# flake8: noqa  (sonde de vérification PA1, rejouable par scripts/sonde.py)
"""G-4 (vérificateur frais) — `Lead.visite_prevue_le` a deux écrivains (humain via PATCH fiche, automatique via
`cadence_visite.appliquer_visite_planifiee` et `annuler_rendez_vous_du_lead`).
(A) date future saisie à la main → lead PERDU avec motif : date vidée ? ligne MODIFICATION old→new au chatter ?
(B) date future saisie à la main (marquée `saisies_humaines`) → POST /visites/visites/ à une autre date : la saisie
    est-elle écrasée (pas d'`ecrire_si_libre`) ? tracée old→new ?
(C) témoin : date PASSÉE saisie à la main → perdu : gardée (vider_date_passee=False).
Société démo (demo_admin), API réelle, transaction annulée."""
SONDE = {"constat": "C-ACVI-123", "sha": "352ae5455",
         "attendu": "toute écriture automatique de visite_prevue_le respecte la saisie humaine ou la trace old→new",
         "modeles": ["crm.Lead", "crm.LeadActivity", "visites.VisiteTerrain"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.urls import reverse
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm.models import Lead, LeadActivity
    U = get_user_model()
    ua = U.objects.filter(username='demo_admin', is_active=True).first()
    api = APIClient()
    api.force_authenticate(ua)
    leads_url = reverse('lead-list')
    visites_url = reverse('visites-visite-list')
    today = timezone.localdate()
    obs = {'utilisateur': ua.username}

    def appel(client, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(client, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt)
            except Exception:
                return r.status_code, txt[:200]
        except Exception as e:
            return 599, repr(e)[:200]

    def creer(suffixe):
        s, _ = appel(api, 'post', leads_url, {'nom': 'SondeG4', 'prenom': suffixe, 'telephone': '+2126000123' + suffixe,
                                              'email': f'sonde-acvi-123-{suffixe}@example.invalid', 'ville': 'Casablanca'})
        return Lead.objects.filter(email=f'sonde-acvi-123-{suffixe}@example.invalid').order_by('-id').first(), s

    def activites(lead, depuis_id):
        return [(a.kind, a.field, a.old_value, a.new_value, (a.body or '')[:120], a.user_id)
                for a in LeadActivity.objects.filter(lead=lead, id__gt=depuis_id).order_by('id')]

    def dernier_id(lead):
        x = LeadActivity.objects.filter(lead=lead).order_by('-id').first()
        return x.id if x else 0

    # (A) futur manuel → perdu
    la, s = creer('01')
    d_future = (today + dt.timedelta(days=30)).isoformat()
    s1, r1 = appel(api, 'patch', f'{leads_url}{la.id}/', {'visite_prevue_le': d_future})
    la.refresh_from_db()
    obs['A_patch_date'] = {'statut': s1, 'visite_prevue_le': str(la.visite_prevue_le),
                           'saisies_humaines': la.saisies_humaines,
                           'ligne_modif_humaine': LeadActivity.objects.filter(lead=la, field='visite_prevue_le', kind='modification', user__isnull=False).count()}
    depuis = dernier_id(la)
    s2, r2 = appel(api, 'patch', f'{leads_url}{la.id}/', {'perdu': True, 'motif_perte': 'Prix trop élevé'})
    la.refresh_from_db()
    acts = activites(la, depuis)
    obs['A_perdu'] = {'statut': s2, 'corps': r2 if s2 >= 400 else None, 'visite_prevue_le_apres': str(la.visite_prevue_le),
                      'activites': acts,
                      'ligne_modif_visite_prevue_le': [a for a in acts if a[1] == 'visite_prevue_le']}
    repro_A = la.visite_prevue_le is None and not [a for a in acts if a[1] == 'visite_prevue_le']

    # (B) futur manuel → planification ERP à une autre date
    lb, s = creer('02')
    appel(api, 'patch', f'{leads_url}{lb.id}/', {'visite_prevue_le': d_future})
    lb.refresh_from_db()
    avant = str(lb.visite_prevue_le)
    marque = 'visite_prevue_le' in (lb.saisies_humaines or [])
    depuis = dernier_id(lb)
    d_visite = (today + dt.timedelta(days=5)).isoformat()
    s3, r3 = appel(api, 'post', visites_url, {'lead': lb.id, 'date_prevue': d_visite})
    lb.refresh_from_db()
    acts = activites(lb, depuis)
    obs['B_planif'] = {'statut': s3, 'corps': r3 if s3 >= 400 else None, 'avant': avant, 'marque_humaine': marque,
                       'apres': str(lb.visite_prevue_le), 'activites': acts,
                       'ligne_modif_visite_prevue_le': [a for a in acts if a[1] == 'visite_prevue_le']}
    repro_B = marque and str(lb.visite_prevue_le) == d_visite and not [a for a in acts if a[1] == 'visite_prevue_le']

    # (C) témoin : passée manuelle → perdu
    lc, s = creer('03')
    d_passee = (today - dt.timedelta(days=3)).isoformat()
    s4, r4 = appel(api, 'patch', f'{leads_url}{lc.id}/', {'visite_prevue_le': d_passee})
    appel(api, 'patch', f'{leads_url}{lc.id}/', {'perdu': True, 'motif_perte': 'Prix trop élevé'})
    lc.refresh_from_db()
    obs['C_temoin_passee'] = {'patch': s4, 'apres_perdu': str(lc.visite_prevue_le)}

    obs['repro_A_vide_sans_old_new'] = repro_A
    obs['repro_B_ecrase_saisie_sans_old_new'] = repro_B
    return {'repro': bool(repro_A or repro_B), 'observe': obs}

# flake8: noqa  (sonde de vérification PA1, rejouable par scripts/sonde.py — AMET93)
"""B-4 (= C-3, jumeau E-8/C-ACVI-167) + B-15 (= C-2) + B-3(b) — portes d'arrêt et de restauration, par l'API
réelle, société démo. Chaque lead naît par POST /crm/leads/ (cadence contact démarrée) et reçoit une visite par
POST /visites/ (J+4). Témoin : PATCH perdu+motif (annule le RDV, SUIVI E21). Portes vérifiées : lot `set_perdu`,
lot `archive`, action `archiver`. Puis restauration : `restaurer` unitaire vs lot `unarchive` (touches À FAIRE).
Enfin lot `prepare_whatsapp` et `archiver` sur un lead jamais contacté : `first_contacted_at`.
Transaction annulée."""
SONDE = {"constat": "C-ACVI-023+022+034+201+202", "sha": "352ae5455",
         "attendu": "défaut : visite gardée (date_prevue non vidée) après lot set_perdu / lot archive / archiver, alors "
                    "que le témoin PATCH l'annule ; restaurer = 0 touche, unarchive >= 1 ; first_contacted_at posé "
                    "par prepare_whatsapp / archiver",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "visites.VisiteTerrain"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.urls import reverse
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm.models import Lead
    from apps.crm.models_cadence import RelanceEtape
    from apps.visites.models import VisiteTerrain
    U = get_user_model()
    ua = U.objects.filter(username='demo_admin', is_active=True).first()
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    leads_url = reverse('lead-list')
    visites_url = reverse('visites-visite-list')
    etapes = []

    def appel(nom, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
        except Exception as e:
            etapes.append((nom, 599, repr(e)[:300]))
            return 599, {}
        txt = r.content.decode('utf-8', 'replace')
        etapes.append((nom, r.status_code, txt[:200] if r.status_code >= 400 else ''))
        try:
            return r.status_code, json.loads(txt)
        except Exception:
            return r.status_code, {}

    n = [0]

    def nouveau(nom):
        n[0] += 1
        appel('creer ' + nom, 'post', leads_url,
              {'nom': nom, 'prenom': 'ACVI023', 'telephone': '+2126000230%02d' % n[0], 'ville': 'Rabat',
               'email': 'acvi023-%d@example.invalid' % n[0]})
        return Lead.objects.filter(company=c, email='acvi023-%d@example.invalid' % n[0]).order_by('-id').first()

    j4 = (timezone.localdate() + dt.timedelta(days=4)).isoformat()

    def avec_visite(lead):
        appel('visite ' + lead.nom, 'post', visites_url, {'lead': lead.id, 'date_prevue': j4, 'notes': 'sonde 023'})

    def etat(lead):
        lead.refresh_from_db()
        vs = list(VisiteTerrain.objects.filter(lead=lead).values_list('statut', 'date_prevue'))
        return {'perdu': lead.perdu, 'archive': lead.is_archived, 'visite_prevue_le': str(lead.visite_prevue_le),
                'visites': [(s, str(d)) for s, d in vs],
                'touches_a_faire': RelanceEtape.objects.filter(lead=lead, statut=RelanceEtape.Statut.A_FAIRE).count()}

    obs = {}
    # témoin : PATCH perdu
    t = nouveau('Temoin')
    avec_visite(t)
    obs['temoin_avant'] = etat(t)
    appel('PATCH perdu', 'patch', '%s%d/' % (leads_url, t.id), {'perdu': True, 'motif_perte': 'prix'})
    obs['temoin_patch_perdu'] = etat(t)
    # lot set_perdu
    l1 = nouveau('LotPerdu')
    avec_visite(l1)
    appel('lot set_perdu', 'post', leads_url + 'bulk/', {'action': 'set_perdu', 'ids': [l1.id], 'motif': 'prix'})
    obs['lot_set_perdu'] = etat(l1)
    # lot archive
    l2 = nouveau('LotArchive')
    avec_visite(l2)
    appel('lot archive', 'post', leads_url + 'bulk/', {'action': 'archive', 'ids': [l2.id]})
    obs['lot_archive'] = etat(l2)
    # archiver unitaire
    l3 = nouveau('Archiver')
    avec_visite(l3)
    appel('archiver', 'post', '%s%d/archiver/' % (leads_url, l3.id))
    obs['archiver'] = etat(l3)
    # C-2 / B-15 : restaurer unitaire vs lot unarchive
    l4 = nouveau('Restaurer')
    Lead.objects.filter(pk=l4.pk).update(first_contacted_at=None)
    a4 = etat(l4)
    appel('archiver l4', 'post', '%s%d/archiver/' % (leads_url, l4.id))
    l4.refresh_from_db()
    fca_apres_archiver = str(l4.first_contacted_at)
    b4 = etat(l4)
    appel('restaurer l4', 'post', '%s%d/restaurer/' % (leads_url, l4.id))
    obs['restaurer_unitaire'] = {'avant': a4, 'archive': b4, 'restaure': etat(l4),
                                 'first_contacted_at_apres_archiver': fca_apres_archiver}
    l5 = nouveau('Unarchive')
    a5 = etat(l5)
    appel('lot archive l5', 'post', leads_url + 'bulk/', {'action': 'archive', 'ids': [l5.id]})
    b5 = etat(l5)
    appel('lot unarchive l5', 'post', leads_url + 'bulk/', {'action': 'unarchive', 'ids': [l5.id]})
    obs['lot_unarchive'] = {'avant': a5, 'archive': b5, 'restaure': etat(l5)}
    # B-3 (b) : prepare_whatsapp sur un lead jamais contacté
    l6 = nouveau('Whatsapp')
    Lead.objects.filter(pk=l6.pk).update(first_contacted_at=None)
    s, r = appel('lot prepare_whatsapp', 'post', leads_url + 'bulk/',
                 {'action': 'prepare_whatsapp', 'ids': [l6.id], 'body': 'Bonjour'})
    l6.refresh_from_db()
    obs['prepare_whatsapp'] = {'http': s, 'file': (r.get('count') if isinstance(r, dict) else None),
                               'first_contacted_at': str(l6.first_contacted_at), 'stage': l6.stage}
    obs['etapes'] = etapes

    def garde(e):
        return any(d != 'None' for _, d in e['visites'])
    obs['defauts'] = {
        'temoin_annule_rdv': not garde(obs['temoin_patch_perdu']),
        'B4_lot_set_perdu_garde_visite': garde(obs['lot_set_perdu']),
        'B4_lot_archive_garde_visite': garde(obs['lot_archive']),
        'B4_archiver_garde_visite': garde(obs['archiver']),
        'C2_restaurer_sans_touche': obs['restaurer_unitaire']['restaure']['touches_a_faire'] == 0,
        'C2_unarchive_avec_touche': obs['lot_unarchive']['restaure']['touches_a_faire'] >= 1,
        'B3b_first_contacted_par_prepare_whatsapp': obs['prepare_whatsapp']['first_contacted_at'] != 'None',
        'B3b_first_contacted_par_archiver': fca_apres_archiver != 'None',
    }
    d = obs['defauts']
    return {'repro': bool(d['B4_lot_set_perdu_garde_visite'] or d['B4_lot_archive_garde_visite']
                          or d['B4_archiver_garde_visite'] or d['C2_restaurer_sans_touche']
                          or d['B3b_first_contacted_par_prepare_whatsapp']),
            'observe': obs}

# flake8: noqa  (constat C-ACVI-168 : copie rejouable de la sonde groupée C-ACVI-167, sa clé dans `observe`)
"""E-8 / D-12 / E-9 / E-19 (C-ACVI-167, 071, 168, 178) — compensation de la visite planifiée, société démo 1,
demo_admin, visites assignées à demo_tech, transaction annulée. E-8 : perdu EN MASSE et archivage EN MASSE
laissent la visite datée + Lead.visite_prevue_le + aucune notification ; témoin : perdu par PATCH de la fiche.
D-12 : « Perdu — Locataire » (clore_locataire_sans_proprietaire) idem. E-9 : PATCH date_prevue:null → fiche et
étapes gardent l'ancienne date ; DELETE d'une visite terminée → visite_effectuee reste. E-19 : visite annulée
(annuler_rendez_vous) puis « terminer » (complétude simulée) → 200 et visite_effectuee."""
SONDE = {"constat": "C-ACVI-167+071+168+178", "sha": "352ae5455",
         "attendu": "défauts : date de visite gardée après perdu en masse / archive / locataire ; date null sans "
                    "compensation ; DELETE sans compensation ; visite annulée terminable",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "visites.VisiteTerrain",
                     "notifications.Notification"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm.models import Lead, MotifPerte
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm.fiche_bulk import apply_bulk_action
    from apps.crm.cadence_reponses import clore_locataire_sans_proprietaire
    from apps.notifications.models import Notification
    from apps.visites import selectors as vsel
    from apps.visites import services as vs
    from apps.visites.models import VisiteTerrain
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
    tech = U.objects.get(username='demo_tech')
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    today = timezone.localdate()
    motif = MotifPerte.objects.filter(company=c).values_list('nom', flat=True).first() or 'Prix'
    obs = {'motif': motif}

    def appel(meth, url, corps=None):
        try:
            with transaction.atomic():
                if meth in ('get', 'delete'):
                    r = getattr(api, meth)(url, HTTP_HOST='localhost')
                else:
                    r = getattr(api, meth)(url, corps if corps is not None else {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace') if r.content else ''
            try:
                return r.status_code, json.loads(txt) if txt else {}
            except Exception:
                return r.status_code, {'_brut': txt[:120]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:200]}

    def nouveau(n, jours):
        L = Lead.objects.create(company=c, nom=f'Visite{n}', prenom='Sonde', telephone=f'06123493{n:02d}',
                                email=f'sonde-acvi-167-{n}@example.invalid', ville='Casablanca', owner=ua)
        V, err = vs.planifier_visite(L, ua, today + dt.timedelta(days=jours), commercial=tech)
        L.refresh_from_db()
        return L, V

    def etat(L, V):
        L.refresh_from_db()
        V.refresh_from_db()
        return {'perdu': L.perdu, 'archive': L.is_archived, 'visite_date': str(V.date_prevue),
                'visite_statut': V.statut, 'lead_visite_prevue_le': str(L.visite_prevue_le),
                'touches_ouvertes': list(RelanceEtape.objects.filter(lead=L, statut='a_faire').values_list('libelle', 'due_date')),
                }

    def notifs():
        return Notification.objects.filter(recipient=tech).count()

    # ---------- E-8 : perdu en masse ----------
    L1, V1 = nouveau(1, 3)
    avant1 = etat(L1, V1)
    n0 = notifs()
    rep = apply_bulk_action(company=c, user=ua, lead_ids=[L1.id], op='set_perdu', params={'motif': motif})
    obs['E8_perdu_masse'] = {'avant': avant1, 'bulk': {k: rep.get(k) for k in ('updated', 'skipped')},
                             'apres': etat(L1, V1), 'notifs_tech_delta': notifs() - n0}
    # archivage en masse
    L2, V2 = nouveau(2, 3)
    n0 = notifs()
    apply_bulk_action(company=c, user=ua, lead_ids=[L2.id], op='archive', params={})
    obs['E8_archive_masse'] = {'apres': etat(L2, V2), 'notifs_tech_delta': notifs() - n0}
    # témoin : perdu par la fiche
    L3, V3 = nouveau(3, 3)
    n0 = notifs()
    s, r = appel('patch', f'/api/django/crm/leads/{L3.id}/', {'perdu': True, 'motif_perte': motif})
    obs['E8_temoin_patch_fiche'] = {'http': s, 'err': r if s >= 400 else '', 'apres': etat(L3, V3), 'notifs_tech_delta': notifs() - n0}
    e8 = (str(V1.date_prevue) != 'None' and obs['E8_perdu_masse']['apres']['perdu']
          and obs['E8_temoin_patch_fiche']['apres']['visite_date'] == 'None')

    # ---------- D-12 : Perdu — Locataire ----------
    L4, V4 = nouveau(4, 3)
    n0 = notifs()
    passe = clore_locataire_sans_proprietaire(L4, ua)
    obs['D12_locataire'] = {'passe_perdu': passe, 'apres': etat(L4, V4), 'notifs_tech_delta': notifs() - n0}
    d12 = passe and obs['D12_locataire']['apres']['visite_date'] != 'None'

    # ---------- E-9 (b) : PATCH date_prevue null ----------
    L5, V5 = nouveau(5, 4)
    avant5 = etat(L5, V5)
    s, r = appel('patch', f'/api/django/visites/visites/{V5.id}/', {'date_prevue': None})
    obs['E9b_date_null'] = {'avant': avant5, 'http': s, 'apres': etat(L5, V5)}
    e9b = s == 200 and obs['E9b_date_null']['apres']['visite_date'] == 'None' and \
        obs['E9b_date_null']['apres']['lead_visite_prevue_le'] != 'None'

    orig = vsel.visite_terrain_manquants
    vsel.visite_terrain_manquants = lambda visite: []
    try:
        # ---------- E-9 (a) : DELETE d'une visite terminée ----------
        L6, V6 = nouveau(6, 1)
        s_t, _ = appel('post', f'/api/django/visites/visites/{V6.id}/terminer/')
        L6.refresh_from_db()
        eff_avant = L6.visite_effectuee
        s_d, _ = appel('delete', f'/api/django/visites/visites/{V6.id}/')
        L6.refresh_from_db()
        obs['E9a_delete_terminee'] = {'terminer': s_t, 'visite_effectuee_avant': eff_avant, 'delete': s_d,
                                      'visite_existe': VisiteTerrain.objects.filter(pk=V6.pk).exists(),
                                      'visite_effectuee_apres': L6.visite_effectuee,
                                      'touches_ouvertes': list(RelanceEtape.objects.filter(lead=L6, statut='a_faire').values_list('libelle', flat=True))}
        e9a = s_d in (200, 204) and L6.visite_effectuee is True

        # ---------- E-19 : visite annulée puis terminée ----------
        L7, V7 = nouveau(7, 2)
        n_ann = vs.annuler_rendez_vous(L7, ua)
        V7.refresh_from_db()
        apres_ann = {'annules': n_ann, 'statut': V7.statut, 'date': str(V7.date_prevue), 'notes': V7.notes[-80:]}
        s19, _ = appel('post', f'/api/django/visites/visites/{V7.id}/terminer/')
        L7.refresh_from_db()
        V7.refresh_from_db()
        obs['E19'] = {'apres_annulation': apres_ann, 'terminer': s19, 'statut_final': V7.statut,
                      'visite_effectuee': L7.visite_effectuee,
                      'touches_ouvertes': list(RelanceEtape.objects.filter(lead=L7, statut='a_faire').values_list('libelle', flat=True))}
        e19 = s19 == 200 and L7.visite_effectuee is True
    finally:
        vsel.visite_terrain_manquants = orig
    obs['repro_par_constat'] = {'E8': bool(e8), 'D12': bool(d12), 'E9b': bool(e9b), 'E9a': bool(e9a), 'E19': bool(e19)}
    return {'repro': bool(e8 and d12 and e9b and e9a and e19), 'observe': obs}

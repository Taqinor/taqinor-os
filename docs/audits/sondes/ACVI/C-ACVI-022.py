# flake8: noqa  (constat C-ACVI-022 : copie rejouable de la sonde groupée C-ACVI-020, sa clé dans `observe`)
"""B-1 + B-2 + B-3(a) + B-16 — fusion de fiches par l'API réelle (POST /crm/leads/<B>/merge/ {others:[A]}),
société démo. Fusion 1 : A (même téléphone) porte une visite planifiée par l'API Visites + un RDV crm.Appointment,
puis passe `ne_plus_contacter=True` ; B est NEW, jamais contacté. Fusion 2 : A2 SIGNED → B2 NEW.
Oracles : B hérite de l'opposition et n'a aucune touche À FAIRE ; visites/RDV suivent B ; `first_contacted_at` de
B reste vide (aucun contact réel) ; B2 harmonisé SIGNED. Transaction annulée."""
SONDE = {"constat": "C-ACVI-020+021+022+035", "sha": "352ae5455",
         "attendu": "défaut : B.ne_plus_contacter False + touche À FAIRE posée ; visite/RDV restés sur A archivé ; "
                    "B.first_contacted_at horodaté par la note de fusion ; B2.stage NEW",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "crm.Appointment", "visites.VisiteTerrain"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.urls import reverse
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm.models import Lead, LeadActivity, Appointment
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

    def touches(lead):
        return [(t.cadence, t.ordre, t.libelle[:40] if getattr(t, 'libelle', None) else '', t.statut)
                for t in RelanceEtape.objects.filter(lead=lead).order_by('id')]

    # ── Fusion 1 ──
    tel = '+212600020020'
    a = Lead.objects.create(company=c, nom='Absorbe', prenom='ACVI020', telephone=tel, ville='Casablanca',
                            email='acvi020-a@example.invalid', owner=ua)
    b = Lead.objects.create(company=c, nom='Survivant', prenom='ACVI020', telephone=tel, ville='Casablanca',
                            owner=ua)
    j5 = (timezone.localdate() + dt.timedelta(days=5)).isoformat()
    s_vis, v = appel('planifier visite sur A', 'post', visites_url, {'lead': a.id, 'date_prevue': j5, 'notes': 'sonde 020'})
    Appointment.objects.create(company=c, lead=a, scheduled_at=timezone.now() + dt.timedelta(days=5), created_by=ua)
    Lead.objects.filter(pk=a.pk).update(ne_plus_contacter=True)
    RelanceEtape.objects.filter(lead=b).delete()  # B sans touche avant la fusion (isoler celle que pose la fusion)
    Lead.objects.filter(pk=b.pk).update(first_contacted_at=None)
    b.refresh_from_db()
    avant = {'b_first_contacted_at': str(b.first_contacted_at), 'b_touches': touches(b),
             'a_visites': VisiteTerrain.objects.filter(lead=a).count(), 'a_rdv': Appointment.objects.filter(lead=a).count(),
             'a_ne_plus_contacter': Lead.objects.get(pk=a.pk).ne_plus_contacter}
    t0 = timezone.now()
    s_m, _ = appel('fusion A dans B', 'post', f'{leads_url}{b.id}/merge/', {'others': [a.id]})
    a.refresh_from_db(); b.refresh_from_db()
    notes_signees = list(LeadActivity.objects.filter(lead=b, user__isnull=False, created_at__gte=t0)
                         .values_list('kind', 'body'))
    apres = {'http': s_m, 'a_archive': a.is_archived, 'b_ne_plus_contacter': b.ne_plus_contacter,
             'b_touches': touches(b),
             'b_touches_a_faire': RelanceEtape.objects.filter(lead=b, statut=RelanceEtape.Statut.A_FAIRE).count(),
             'b_visites': VisiteTerrain.objects.filter(lead=b).count(), 'a_visites': VisiteTerrain.objects.filter(lead=a).count(),
             'visites_a_detail': list(VisiteTerrain.objects.filter(lead=a).values_list('statut', 'date_prevue')),
             'b_rdv': Appointment.objects.filter(lead=b).count(), 'a_rdv': Appointment.objects.filter(lead=a).count(),
             'b_visite_prevue_le': str(b.visite_prevue_le), 'a_visite_prevue_le': str(a.visite_prevue_le),
             'b_first_contacted_at': str(b.first_contacted_at),
             'notes_signees_creees_sur_b': [(k, (x or '')[:90]) for k, x in notes_signees]}
    # ── Fusion 2 : stage ──
    a2 = Lead.objects.create(company=c, nom='Absorbe2', prenom='ACVI035', telephone='+212600020035', owner=ua)
    b2 = Lead.objects.create(company=c, nom='Survivant2', prenom='ACVI035', telephone='+212600020035', owner=ua)
    Lead.objects.filter(pk=a2.pk).update(stage='SIGNED')
    s_m2, _ = appel('fusion A2 (SIGNED) dans B2 (NEW)', 'post', f'{leads_url}{b2.id}/merge/', {'others': [a2.id]})
    b2.refresh_from_db()
    fusion2 = {'http': s_m2, 'a2_stage_avant': 'SIGNED', 'b2_stage_apres': b2.stage}
    obs = {'avant': avant, 'apres_fusion1': apres, 'fusion2': fusion2, 'etapes': etapes, 'visite_api': s_vis}
    obs['defauts'] = {
        'B1_opposition_perdue': apres['b_ne_plus_contacter'] is False,
        'B1_touche_posee_sur_survivant': apres['b_touches_a_faire'] > 0,
        'B2_visite_restee_sur_archive': apres['a_visites'] > 0 and apres['b_visites'] == 0,
        'B2_rdv_reste_sur_archive': apres['a_rdv'] > 0 and apres['b_rdv'] == 0,
        'B3a_first_contacted_pose_par_fusion': apres['b_first_contacted_at'] != 'None',
        'B16_stage_non_harmonise': b2.stage != 'SIGNED',
    }
    return {'repro': any(obs['defauts'].values()), 'observe': obs}

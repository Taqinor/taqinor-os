# flake8: noqa  (sonde de contre-visite ACVI71, rejouable par scripts/sonde.py)
"""ACVI71 — vérificateur frais : le PATCH/PUT d'une visite applique les gardes de `planifier_visite`.
(a) PATCH {commercial: <compte inactif de la société>} -> 400 nommant `commercial`, visite inchangée en base ;
(b) PATCH {date_prevue: +8 j} -> 200 et une ligne « Rendez-vous du … déplacé au … » aux notes, relue en base ;
(c) PUT {date_prevue, commercial inactif} -> même refus ; (d) PATCH {commercial: <autre société>} -> 400 ;
(e) PATCH {commercial: actif, date_prevue: nouvelle} dans le même corps -> 200, une seule ligne « déplacé » ;
(f) PATCH date passée -> refus, aucune écriture ; (g) témoin POST avec commercial inactif -> 400 comme avant."""
SONDE = {"constat": "C-ACVI-126", "sha": "06ced8b1a",
         "attendu": "repro: False — commercial inactif 400, date déplacée tracée aux notes, relecture base conforme",
         "modeles": ["crm.Lead", "visites.VisiteTerrain", "authentication.CustomUser"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.visites import services as vs
    from apps.visites.models import VisiteTerrain
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
    tech = U.objects.get(username='demo_tech')
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    today = timezone.localdate()
    obs = {}

    def appel(meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(url, corps if corps is not None else {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace') if r.content else ''
            try:
                return r.status_code, json.loads(txt) if txt else {}
            except Exception:
                return r.status_code, {'_brut': txt[:120]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:200]}

    def nouveau(n, jours):
        L = Lead.objects.create(company=c, nom=f'Patch{n}', prenom='Ver1', telephone=f'06123471{n:02d}',
                                email=f'sonde-ver1-71-{n}@example.invalid', ville='Casablanca', owner=ua)
        V, err = vs.planifier_visite(L, ua, today + dt.timedelta(days=jours), commercial=tech)
        return L, V

    def relu(V):
        V = VisiteTerrain.objects.get(pk=V.pk)
        return {'commercial': V.commercial_id, 'date': str(V.date_prevue), 'notes': V.notes}

    inactif = U.objects.create_user(username='sonde-ver1-71-inactif', password='x', company=c,
                                    role=getattr(ua, 'role', None), is_active=False)
    autre_soc = Company.objects.exclude(pk=c.pk).first()
    etranger = None
    if autre_soc is not None:
        etranger = U.objects.create_user(username='sonde-ver1-71-etranger', password='x', company=autre_soc,
                                         role=getattr(ua, 'role', None), is_active=True)

    # (a)
    L, V = nouveau(1, 5)
    avant = relu(V)
    url = f'/api/django/visites/visites/{V.id}/'
    sa, ra = appel('patch', url, {'commercial': inactif.id})
    apres_a = relu(V)
    obs['a_patch_commercial_inactif'] = {'http': sa, 'corps': ra, 'inchange': apres_a == avant}
    ok_a = sa == 400 and 'commercial' in json.dumps(ra) and apres_a == avant

    # (b)
    sb, rb = appel('patch', url, {'date_prevue': (today + dt.timedelta(days=8)).isoformat()})
    apres_b = relu(V)
    d_ancienne = (today + dt.timedelta(days=5)).strftime('%d/%m/%Y')
    d_nouvelle = (today + dt.timedelta(days=8)).strftime('%d/%m/%Y')
    ligne = f'Rendez-vous du {d_ancienne} déplacé au {d_nouvelle}.'
    obs['b_patch_date'] = {'http': sb, 'date_relue': apres_b['date'], 'notes_relues': apres_b['notes'][-100:],
                           'ligne_attendue': ligne, 'ligne_presente': ligne in apres_b['notes'],
                           'notes_dans_reponse': (rb.get('notes') or '')[-100:] if isinstance(rb, dict) else None}
    ok_b = sb == 200 and apres_b['date'] == str(today + dt.timedelta(days=8)) and ligne in apres_b['notes']

    # (c) PUT
    L2, V2 = nouveau(2, 5)
    avant2 = relu(V2)
    sc, rc = appel('put', f'/api/django/visites/visites/{V2.id}/', {'commercial': inactif.id,
                                                                    'date_prevue': (today + dt.timedelta(days=6)).isoformat()})
    apres_c = relu(V2)
    obs['c_put_commercial_inactif'] = {'http': sc, 'corps': rc, 'inchange': apres_c == avant2}
    ok_c = sc in (400, 409) and apres_c == avant2

    # (d) commercial d'une autre société
    L3, V3 = nouveau(3, 5)
    avant3 = relu(V3)
    if etranger is not None:
        sd, rd = appel('patch', f'/api/django/visites/visites/{V3.id}/', {'commercial': etranger.id})
        obs['d_commercial_autre_societe'] = {'http': sd, 'corps': rd, 'inchange': relu(V3) == avant3}
        ok_d = sd in (400, 404) and relu(V3) == avant3  # 404 : pk hors société (queryset scopé)
    else:
        obs['d_commercial_autre_societe'] = 'aucune autre société en base : non joué'
        ok_d = True

    # (e) commercial actif + date dans le même corps
    L4, V4 = nouveau(4, 5)
    autre_actif = U.objects.filter(company=c, is_active=True).exclude(pk=tech.pk).first()
    se, re_ = appel('patch', f'/api/django/visites/visites/{V4.id}/',
                    {'commercial': autre_actif.id, 'date_prevue': (today + dt.timedelta(days=9)).isoformat()})
    apres_e = relu(V4)
    obs['e_commercial_et_date'] = {'http': se, 'relu': apres_e, 'nb_lignes_deplace': apres_e['notes'].count('déplacé')}
    ok_e = se == 200 and apres_e['commercial'] == autre_actif.id and apres_e['notes'].count('déplacé') == 1

    # (f) date passée
    L5, V5 = nouveau(5, 5)
    avant5 = relu(V5)
    sf, rf = appel('patch', f'/api/django/visites/visites/{V5.id}/', {'date_prevue': (today - dt.timedelta(days=2)).isoformat()})
    obs['f_date_passee'] = {'http': sf, 'inchange': relu(V5) == avant5}
    ok_f = sf in (400, 409) and relu(V5) == avant5

    # (g) témoin POST commercial inactif
    L6 = Lead.objects.create(company=c, nom='Patch6', prenom='Ver1', telephone='0612347106',
                             email='sonde-ver1-71-6@example.invalid', ville='Casablanca', owner=ua)
    sg, rg = appel('post', '/api/django/visites/visites/', {'lead': L6.id, 'commercial': inactif.id,
                                                            'date_prevue': (today + dt.timedelta(days=5)).isoformat()})
    obs['g_temoin_post'] = {'http': sg, 'corps': rg}
    ok_g = sg == 400

    obs['verifs'] = {k: bool(v) for k, v in dict(a=ok_a, b=ok_b, c=ok_c, d=ok_d, e=ok_e, f=ok_f, g=ok_g).items()}
    return {'repro': not all([ok_a, ok_b, ok_c, ok_d, ok_e, ok_f, ok_g]), 'observe': obs}

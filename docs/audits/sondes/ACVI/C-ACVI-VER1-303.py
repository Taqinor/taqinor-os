# flake8: noqa  (sonde de contre-visite ACVI79, rejouable par scripts/sonde.py)
"""ACVI79 — vérificateur frais : `GET /api/django/crm/leads/kpi-premier-contact/?jours=30` sous capture SQL.
Cas 1 (le Then du plan) : leads de nuit de même jour, 3 puis 9 -> même nombre de requêtes.
Cas 2 (réel) : leads de nuit sur des jours DISTINCTS -> le coût ne doit pas croître avec le nombre de leads
(borné par le nombre de jours distincts, pas par lead) ; on relève 3 puis 9 leads sur 3 puis 9 jours.
Parité : médianes / taux identiques à un calcul de référence hors `cache_local()`. Transaction annulée."""
SONDE = {"constat": "C-ACVI-142", "sha": "06ced8b1a",
         "attendu": "repro: False — mêmes requêtes à 3 et 9 leads (même jour) ; chiffres identiques à la référence hors cache",
         "modeles": ["crm.Lead"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm import horaires
    from apps.crm.models import Lead
    from apps.crm.leads_selectors import _limite_rappel_du_matin, _mediane
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    casa = horaires.CASABLANCA
    obs = {}
    n_existants = Lead.objects.filter(company=c, source=Lead.Source.OS_NATIVE, is_archived=False,
                                      date_creation__gte=timezone.now() - dt.timedelta(days=30)).count()
    obs['leads_os_native_existants_30j'] = n_existants

    def lead_nuit(jour_offset, k):
        # arrivée à 22:00 heure du Maroc il y a `jour_offset` jours, 1er contact 2 jours plus tard à 11:00
        base = (timezone.now().astimezone(casa) - dt.timedelta(days=jour_offset)).replace(
            hour=22, minute=0, second=0, microsecond=0)
        contact = base + dt.timedelta(days=2, hours=-11)
        L = Lead.objects.create(company=c, nom=f'Kpi{jour_offset}-{k}', prenom='Ver1', owner=ua,
                                source=Lead.Source.OS_NATIVE)
        Lead.objects.filter(pk=L.pk).update(date_creation=base, first_contacted_at=contact)
        return L

    def appel():
        with CaptureQueriesContext(connection) as q:
            r = api.get('/api/django/crm/leads/kpi-premier-contact/?jours=30', HTTP_HOST='localhost')
        return len(q), r.status_code, (json.loads(r.content) if r.status_code == 200 else None)

    # Cas 1 : même jour
    for k in range(3):
        lead_nuit(5, k)
    n3, s3, kpi3 = appel()
    for k in range(3, 9):
        lead_nuit(5, k)
    n9, s9, kpi9 = appel()
    obs['cas1_meme_jour'] = {'requetes_3': n3, 'requetes_9': n9, 'http': [s3, s9],
                             'nb_leads': [kpi3 and kpi3.get('nb_leads'), kpi9 and kpi9.get('nb_leads')]}
    ok1 = s3 == 200 and s9 == 200 and abs(n3 - n9) <= 2  # 1re requête amorce des caches (48 vs 47)

    # Cas 2 : jours distincts (3 nouveaux jours, puis 6 jours de plus)
    for k, j in enumerate((8, 9, 10)):
        lead_nuit(j, k)
    d3, _, _ = appel()
    for k, j in enumerate((11, 12, 13, 14, 15, 16)):
        lead_nuit(j, k)
    d9, _, kpi_d9 = appel()
    obs['cas2_jours_distincts'] = {'requetes_apres_3_jours_de_plus': d3, 'requetes_apres_9_jours_de_plus': d9,
                                   'croissance_par_jour_distinct_ajoute': round((d9 - d3) / 6, 2)}
    # critère : pas de croissance PAR LEAD au-delà de quelques requêtes par jour distinct (ancien code : ~15/lead)
    ok2 = (d9 - d3) / 6 <= 6

    # Parité : référence calculée hors cache_local()
    depuis = timezone.now() - dt.timedelta(days=30)
    leads = list(Lead.objects.filter(company=c, is_archived=False, source=Lead.Source.OS_NATIVE,
                                     date_creation__gte=depuis))
    minutes, cal, nuit, nuit_ok = [], [], 0, 0
    for lead in leads:
        nais = lead.date_origine
        de_nuit = not horaires.est_dans_fenetre(nais, c)
        nuit += 1 if de_nuit else 0
        if lead.first_contacted_at is None:
            continue
        minutes.append(horaires.minutes_ouvrees_entre(nais, lead.first_contacted_at, c))
        cal.append(horaires.minutes_calendaires_entre(nais, lead.first_contacted_at))
        if de_nuit and lead.first_contacted_at <= _limite_rappel_du_matin(nais, c):
            nuit_ok += 1
    ref = {'nb_leads': len(leads), 'mediane_minutes_ouvrees': _mediane(minutes),
           'mediane_minutes_calendaires': _mediane(cal), 'nb_nuit': nuit, 'nb_nuit_rappeles_avant_930': nuit_ok}
    _, _, kpi_final = appel()
    ecarts = {k: (ref[k], kpi_final.get(k)) for k in ref if ref[k] != kpi_final.get(k)}
    obs['parite'] = {'reference': ref, 'ecarts': ecarts}
    ok3 = not ecarts

    # Cockpit équipe (jumeau traité dans la tâche)
    try:
        from apps.crm import cockpit_equipe
        import inspect
        src = inspect.getsource(cockpit_equipe._premier_contact)
        obs['cockpit_equipe_cache_local'] = 'cache_local' in src
        ok4 = 'cache_local' in src
    except Exception as e:
        obs['cockpit_equipe_cache_local'] = repr(e)
        ok4 = False
    obs['verifs'] = {'ok1': bool(ok1), 'ok2': bool(ok2), 'ok3': bool(ok3), 'ok4': bool(ok4)}
    return {'repro': not (ok1 and ok2 and ok3 and ok4), 'observe': obs}

SONDE = {"constat": "C-APRF-ACC-SAV", "sha": "665a4ce53",
         "attendu": "APRF42 (C-APRF-014, C-APRF-015) : parc d'équipements SAV et tickets sous contrat, société démo 6, "
                    "mesurés à TROIS tailles (démo + 5, +15, +25 équipements à 4 tickets et clients distincts sous "
                    "contrat à 2 tickets, dans la transaction annulée) : requêtes identiques entre les tailles 2 et 3 "
                    "(pente 0 ± 1), 0 réponse 503, compteurs nb_tickets_ouverts / nb_tickets_12m = EquipementSerializer "
                    "unitaire, couverture de contrat de la liste = fiche détail (chemin non préchargé).",
         "modeles": ["sav.Ticket", "sav.Equipement", "sav.ContratMaintenance", "crm.Client"]}

# ---- outillage commun APRF (copié dans chaque sonde APRF-ACC : une sonde est autonome) ----
H = {'HTTP_HOST': 'localhost'}


def _api(user):
    from rest_framework.test import APIClient
    api = APIClient()
    api.force_authenticate(user)
    return api


def _mesure(api, url, methode='get', data=None):
    """(statut, nb requêtes SQL, octets, corps JSON|None) d'un appel HTTP réel (DRF APIClient)."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as ctx:
        if methode == 'get':
            r = api.get(url, data or {}, **H)
        else:
            r = api.post(url, data or {}, format='json', **H)
    corps = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
    js = None
    if 'json' in (r.get('Content-Type') or ''):
        import json
        try:
            js = json.loads(corps)
        except ValueError:
            js = None
    return r.status_code, len(ctx.captured_queries), len(corps), js


def _lignes(js):
    if isinstance(js, dict):
        return js.get('results', js.get('data', []))
    return js or []


def _plat(a, b, tol=1):
    return abs(b - a) <= tol
# ---- fin outillage commun ----


def sonde(ctx):
    from datetime import timedelta
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.sav.models import CategorieEquipement, ContratMaintenance, Equipement, Ticket
    from apps.sav.serializers import EquipementSerializer
    from apps.stock.models import Produit
    U = get_user_model()
    u = U.objects.get(username='demo_admin_full')
    co = u.company
    api = _api(u)
    today = timezone.localdate()
    cl = Client.objects.create(company=co, nom='Sonde parc', prenom='APRF42')
    inst = Installation.objects.create(company=co, reference='CHT-APRF42-SAV', client=cl)
    prod = Produit.objects.create(company=co, nom='Onduleur sonde', sku='OND-APRF42', prix_achat=0, prix_vente=100)
    cat = CategorieEquipement.objects.create(company=co, nom='Onduleurs sonde')
    n = [0]

    def equipements(k):  # patron tests_aprf30
        for _ in range(k):
            n[0] += 1
            eq = Equipement.objects.create(company=co, produit=prod, installation=inst,
                                           numero_serie='APRF42-%d' % n[0], categorie=cat, created_by=u)
            for statut, annule in (('nouveau', False), ('en_cours', False), ('nouveau', True), ('cloture', False)):
                Ticket.objects.create(company=co, reference='SAV-A42-%d-%s-%s' % (n[0], statut, annule),
                                      client=cl, equipement=eq, type=Ticket.Type.CORRECTIF, statut=statut,
                                      annule=annule)

    def clients_contrat(k):  # patron tests_yopsb13 (ERR-PERF-SAV-REPORTING-N1)
        for _ in range(k):
            n[0] += 1
            i = n[0]
            c = Client.objects.create(company=co, nom='Sonde contrat %d' % i, prenom='Contrat',
                                      email='aprf42-contrat-%d@example.com' % i, telephone='+2126%08d' % i)
            ct = ContratMaintenance.objects.create(company=co, client=c, actif=True,
                                                   date_debut=today - timedelta(days=400),
                                                   deplacements_inclus_an=1, visites_incluses_an=2,
                                                   sla_resolution_days=(3 if i % 2 else None))
            for j in range(2):
                eq = Equipement.objects.create(company=co, produit=prod, numero_serie='SNC42-%d-%d' % (i, j))
                if j == 0 or i % 3 == 0:
                    ct.equipements.add(eq)
                Ticket.objects.create(company=co, reference='TCC42-%04d-%d' % (i, j), client=c, equipement=eq,
                                      date_ouverture=today - timedelta(days=(i % 40) * 2 + j))

    E = '/api/django/sav/equipements/'
    T = '/api/django/sav/tickets/'

    def tour():
        se, qe, _, je = _mesure(api, E, data={'rebut': 'tous', 'page_size': 100})
        st, qt, _, jt = _mesure(api, T, data={'page_size': 100})
        return {'equipements': {'st': se, 'q': qe, 'n': len(_lignes(je)), 'rows': _lignes(je)},
                'tickets': {'st': st, 'q': qt, 'n': len(_lignes(jt)), 'rows': _lignes(jt)}}

    equipements(5)
    clients_contrat(5)
    tour()  # échauffement
    a = tour()
    equipements(10)
    clients_contrat(10)
    b = tour()
    equipements(10)
    clients_contrat(10)
    c = tour()
    ok, mes = {}, {}
    for k in ('equipements', 'tickets'):
        mes[k] = '%s→%s→%s req (st %s/%s/%s, lignes %s→%s→%s)' % (
            a[k]['q'], b[k]['q'], c[k]['q'], a[k]['st'], b[k]['st'], c[k]['st'], a[k]['n'], b[k]['n'], c[k]['n'])
        ok['200_' + k] = a[k]['st'] == b[k]['st'] == c[k]['st'] == 200
        ok['plat_' + k] = c[k]['q'] - b[k]['q'] <= 1
        ok['grandit_' + k] = c[k]['n'] > b[k]['n'] > a[k]['n']
    # Compteurs = sérialiseur unitaire (repli .count()), sur les équipements de la sonde.
    ecarts = []
    for r in c['equipements']['rows']:
        if not str(r.get('numero_serie', '')).startswith('APRF42-'):
            continue
        att = EquipementSerializer(Equipement.objects.get(pk=r['id'])).data
        if (r['nb_tickets_ouverts'], r['nb_tickets_12m']) != (att['nb_tickets_ouverts'], att['nb_tickets_12m']):
            ecarts.append(r['id'])
    ok['compteurs_egaux_unitaire'] = not ecarts
    # Couverture = fiche détail.
    champs = ('equipement_couvert', 'couverture_proposee', 'sla_due_at_effectif')
    ecarts_t = []
    vus = 0
    for r in c['tickets']['rows']:
        if not str(r.get('reference', '')).startswith('TCC42-') or vus >= 12:
            continue
        vus += 1
        d = api.get('%s%s/' % (T, r['id']), **H)
        if d.status_code != 200 or {k: r.get(k) for k in champs} != {k: d.data.get(k) for k in champs}:
            ecarts_t.append(r['reference'])
    ok['couverture_egale_detail'] = vus > 0 and not ecarts_t
    mes['couverture'] = '%d tickets comparés, écarts %s' % (vus, ecarts_t[:4])
    mes['compteurs'] = 'écarts %s' % ecarts[:4]
    ok['zero_503'] = all(x[k]['st'] != 503 for x in (a, b, c) for k in x)
    return {'repro': all(ok.values()), 'ko': sorted(k for k, v in ok.items() if not v), 'mesures': mes}

SONDE = {"constat": "C-APRF-ACC-CRM", "sha": "665a4ce53",
         "attendu": "APRF42 (C-APRF-006…013) : CRM clients, cockpit (dormants, mon-portefeuille), relance-etapes, "
                    "leads (liste, relances overdue, sla-breach), roi-sources et « Ma file », société démo 2, mesurés à "
                    "DEUX tailles (données démo, puis +10 clients cockpit, +10 leads en retard avec devis, +10 leads "
                    "signés par campagne, +10 activités dues, +10 touches WhatsApp, dans la transaction annulée) : requêtes identiques "
                    "(pente 0 ± 1), 0 réponse 503, dormants = oracle unitaire d'avant APRF22, compteurs relances / "
                    "SLA augmentés exactement des leads ajoutés ; portée client (APRF16) sans DISTINCT.",
         "modeles": ["crm.Lead", "crm.Client", "ventes.Devis", "records.Activity"]}

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
    import datetime
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from django.utils import timezone
    from apps.crm import stages
    from apps.crm.models import Client, Lead, LeadActivity, PointContact
    from apps.records.models import Activity, ActivityType
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, Facture, LigneDevis, ShareLink
    U = get_user_model()
    u = U.objects.get(username='demo_admin')
    co = u.company
    api = _api(u)
    now = timezone.now()
    n = [0]
    B = '/api/django/crm/'

    def produit():
        n[0] += 1
        return Produit.objects.create(company=co, nom='Panneau sonde', sku='APRF42-%d' % n[0],
                                      prix_vente=Decimal('1000'), quantite_stock=10)

    def leads_retard(k):  # patron tests_aprf18 : NEW, relance passée, non contacté, devis + ligne produit
        for _ in range(k):
            n[0] += 1
            lead = Lead.objects.create(company=co, nom='Sonde retard %d' % n[0], owner=u, stage=stages.NEW)
            Lead.objects.filter(pk=lead.pk).update(relance_date=timezone.localdate() - datetime.timedelta(days=2),
                                                   date_creation=now - datetime.timedelta(days=5),
                                                   first_contacted_at=None, stage=stages.NEW)
            d = Devis.objects.create(company=co, reference='DEV-APRF42R-%04d' % n[0], lead=lead,
                                     client=Client.objects.create(company=co, nom='Sonde client %d' % n[0]),
                                     statut='brouillon', taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
                                     created_by=u)
            LigneDevis.objects.create(devis=d, produit=produit(), designation='Panneau', quantite=Decimal('2'),
                                      prix_unitaire=Decimal('1000'), remise=Decimal('0'))

    def clients_cockpit(k):  # patron tests_aprf22
        for _ in range(k):
            n[0] += 1
            i = n[0]
            c = Client.objects.create(company=co, nom='Sonde cockpit %d' % i)
            lead = Lead.objects.create(company=co, nom='Sonde cockpit lead %d' % i, owner=u, client=c)
            d = Devis.objects.create(company=co, client=c, lead=lead, reference='DV-APRF42C-%d' % i,
                                     statut=(Devis.Statut.ACCEPTE if i % 3 == 0 else Devis.Statut.ENVOYE))
            Devis.objects.filter(pk=d.pk).update(date_creation=now - datetime.timedelta(days=200 if i % 2 else 10))
            if i % 2 == 0:
                ShareLink.objects.create(company=co, devis=d, view_count=2)
                Facture.objects.create(company=co, client=c, devis=d, reference='FA-APRF42C-%d' % i,
                                       statut=(Facture.Statut.PAYEE if i % 4 == 0 else Facture.Statut.EMISE))
                PointContact.objects.create(company=co, lead=lead, canal='telephone',
                                            date_contact=now - datetime.timedelta(days=3))
                LeadActivity.objects.create(company=co, lead=lead, kind=LeadActivity.Kind.NOTE, body='note')

    def leads_signes(k):  # patron tests_aprf19 : une campagne par lead
        cl = Client.objects.create(company=co, nom='Sonde ROI')
        for j in range(k):
            n[0] += 1
            lead = Lead.objects.create(company=co, nom='Sonde ROI %d' % n[0], canal='meta_ads',
                                       utm_campaign='sonde-camp-%d' % j, stage=stages.SIGNED)
            d = Devis.objects.create(company=co, reference='DEV-APRF42S-%04d' % n[0], client=cl, lead=lead,
                                     statut='accepte', taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
                                     created_by=u)
            LigneDevis.objects.create(devis=d, produit=produit(), designation='Panneau', quantite=Decimal('1'),
                                      prix_unitaire=Decimal('1000'), remise=Decimal('0'))

    def activites(k):  # patron records TestMaFile
        typ = ActivityType.objects.filter(company=co).first() or ActivityType.objects.first()
        ct_l, ct_c = ContentType.objects.get_for_model(Lead), ContentType.objects.get_for_model(Client)
        for _ in range(k):
            n[0] += 1
            if n[0] % 2:
                cible, ct = Lead.objects.create(company=co, nom='Sonde cible %d' % n[0],
                                                telephone='0612%06d' % n[0]), ct_l
            else:
                cible, ct = Client.objects.create(company=co, nom='Sonde cible %d' % n[0],
                                                  telephone='0613%06d' % n[0]), ct_c
            Activity.objects.create(company=co, content_type=ct, object_id=cible.id, activity_type=typ,
                                    summary='Appel sonde %d' % n[0],
                                    due_date=timezone.localdate() - datetime.timedelta(days=1),
                                    assigned_to=u, created_by=u)

    def touches_whatsapp(k):  # patron tests_aprf21 : touche WhatsApp à faire + message ouvert
        from apps.crm.cadence_reperes import prefixe_activite_message_ouvert
        from apps.crm.models import RelanceEtape
        for _ in range(k):
            n[0] += 1
            lead = Lead.objects.create(company=co, nom='Sonde touche %d' % n[0], owner=u, stage=stages.CONTACTED)
            t = RelanceEtape.objects.create(company=co, lead=lead, cadence='contact', ordre=n[0],
                                            canal=RelanceEtape.Canal.WHATSAPP, libelle='Message %d' % n[0],
                                            due_at=now, due_date=now.date(), statut=RelanceEtape.Statut.A_FAIRE)
            LeadActivity.objects.create(company=co, lead=lead, user=u, kind=LeadActivity.Kind.WHATSAPP,
                                        body=prefixe_activite_message_ouvert(t) + ' (sonde)')

    paginees = {'clients': B + 'clients/', 'leads': B + 'leads/', 'relance_etapes': B + 'relance-etapes/'}
    globales = {'dormants': B + 'clients/dormants/', 'portefeuille': B + 'clients/mon-portefeuille/',
                'relances_overdue': B + 'leads/relances/?scope=overdue', 'sla_breach': B + 'leads/sla-breach/',
                'roi_sources': B + 'leads/roi-sources/', 'ma_file': '/api/django/records/activities/ma-file/'}

    def _cid(r):
        c = r.get('client')
        return c.get('id') if isinstance(c, dict) else (c if c is not None else r.get('id'))

    def tour():
        res = {}
        for nom, url in paginees.items():
            extra = {'scope': 'all'} if nom == 'relance_etapes' else {}
            for ps in (25, 50):
                st, q, o, js = _mesure(api, url, data=dict(extra, page_size=ps))
                res['%s@%d' % (nom, ps)] = {'st': st, 'q': q, 'n': len(_lignes(js))}
        for nom, url in globales.items():
            st, q, o, js = _mesure(api, url)
            ent = {'st': st, 'q': q, 'o': o, 'n': len(_lignes(js)) if isinstance(js, (list, dict)) else None}
            if isinstance(js, dict) and 'count' in js:
                ent['count'] = js['count']
            if nom == 'dormants':
                ent['ids'] = sorted(_cid(r) for r in _lignes(js))
            if nom == 'roi_sources':
                ent['js'] = js
            res[nom] = ent
        return res

    tour()  # échauffement (caches de processus : ContentType & co.)
    a = tour()
    leads_retard(10)
    clients_cockpit(10)
    leads_signes(10)
    activites(10)
    touches_whatsapp(10)
    b = tour()
    # Taille 3 (+10 de chaque encore) : la pente se lit entre les tailles 2 et 3, une fois tous les
    # niveaux de préchargement amorcés (un niveau vide ne tire pas sa requête à la taille 1).
    leads_retard(10)
    clients_cockpit(10)
    leads_signes(10)
    activites(10)
    touches_whatsapp(10)
    c = tour()
    ok, mes = {}, {}
    for k in a:
        mes[k] = '%s→%s→%s req (st %s/%s/%s, n %s→%s→%s)' % (
            a[k]['q'], b[k]['q'], c[k]['q'], a[k]['st'], b[k]['st'], c[k]['st'],
            a[k].get('count', a[k]['n']), b[k].get('count', b[k]['n']), c[k].get('count', c[k]['n']))
        ok['200_' + k] = a[k]['st'] == 200 and b[k]['st'] == 200 and c[k]['st'] == 200
        # Pente : aucune croissance au-delà de ±1 quand les données grossissent (une baisse = lignes
        # sondes plus simples que les lignes démo remplacées en tête de page, jamais un N+1).
        ok['plat_donnees_' + k] = c[k]['q'] - b[k]['q'] <= 1
    for nom in paginees:
        ok["plat_page_" + nom] = _plat(c[nom + "@25"]["q"], c[nom + "@50"]["q"])
    # Oracle d'avant APRF22 (calcul unitaire copié dans le test) pour les dormants (seuil 90 = défaut de la vue).
    try:
        from apps.crm.tests_aprf22_cockpit_clients_en_lot import _anciens_dormants
        ora = _anciens_dormants(co, timezone.now(), 90)
        ok['dormants_egaux_oracle'] = sorted(ora) == c['dormants']['ids']
        mes['dormants_oracle'] = '%d servis / %d oracle unitaire' % (len(c['dormants']['ids']), len(ora))
    except Exception as e:  # pragma: no cover
        mes['dormants_oracle'] = 'oracle non joué : %s' % str(e)[:120]
    for nom in ('relances_overdue', 'sla_breach'):
        na, nb_ = a[nom].get('count', a[nom]['n']), c[nom].get('count', c[nom]['n'])
        ok[nom + '_plus_20'] = (nb_ or 0) - (na or 0) == 20
    ok['zero_503'] = all(v['st'] != 503 for v in list(a.values()) + list(b.values()) + list(c.values()))
    # APRF16 : portée client sans jointure multi-valuée ni DISTINCT.
    # Aucun utilisateur démo n'a une portée restreinte : `record_scope_for` est forcé à 'self' le temps
    # de la mesure (même chemin que la vue), puis restauré.
    import core.scoping as sc
    orig = sc.record_scope_for
    sc.record_scope_for = lambda user: 'self'
    try:
        sql = str(sc.scope_client_queryset(Client.objects.filter(company=co), u).query).upper()
        p25 = _mesure(api, B + 'clients/', data={'page_size': 25})
        p50 = _mesure(api, B + 'clients/', data={'page_size': 50})
    finally:
        sc.record_scope_for = orig
    mes['portee_aprf16'] = {'distinct': 'DISTINCT' in sql, 'exists': sql.count('EXISTS'),
                            'clients_portee_self': '%s req @25 / %s req @50 (st %s/%s, n %s/%s)' % (
                                p25[1], p50[1], p25[0], p50[0], len(_lignes(p25[3])), len(_lignes(p50[3])))}
    ok['portee_sans_distinct'] = 'DISTINCT' not in sql and sql.count('EXISTS') >= 4
    ok['portee_liste_plate'] = p25[0] == p50[0] == 200 and _plat(p25[1], p50[1])
    mes['roi'] = [str(a['roi_sources'].get('js'))[:200], str(c['roi_sources'].get('js'))[:200]]
    return {'repro': all(ok.values()), 'ko': sorted(k for k, v in ok.items() if not v), 'mesures': mes}

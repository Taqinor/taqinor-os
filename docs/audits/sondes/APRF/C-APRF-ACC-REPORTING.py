SONDE = {"constat": "C-APRF-ACC-REPORTING", "sha": "665a4ce53",
         "attendu": "APRF42 (C-APRF-004, 025, 026, 027) : Reporting dashboard, pipeline, commercial/dashboard, "
                    "pipeline/velocity, contrôle d'intégrité factures_payees_avec_solde, CA par client "
                    "(ca_devis_factures_par_clients) et tâches SLA CRM (recyclage + rappels, dry-run), société "
                    "anonymisée 4 (334 devis réels), mesurés à TROIS tailles (factures payées, leads à devis et devis "
                    "signés de commerciaux distincts, dormants déjà escaladés, ajoutés dans la transaction annulée) : "
                    "requêtes identiques entre les tailles 2 et 3 (pente 0 ± 1), 0 réponse 503, chiffres = relecture "
                    "facture par facture / devis par devis sans préchargement.",
         "modeles": ["ventes.Facture", "ventes.Devis", "crm.Lead", "crm.LeadActivity", "ventes.Paiement"]}

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


def _plat(a, b, tol=1):
    return abs(b - a) <= tol
# ---- fin outillage commun ----


def _compte(fn):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as c:
        res = fn()
    return len(c.captured_queries), res


def sonde(ctx):
    import itertools
    from datetime import date, timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from apps.crm import stages
    from apps.crm.management.commands import escalader_rappels_demandes as rappels
    from apps.crm.management.commands import recycler_leads_non_travailles as recyclage
    from apps.crm.models import Client, Lead, LeadActivity
    from apps.reporting.integrity import factures_payees_avec_solde
    from apps.reporting.views import _ht_encaisse
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, Facture, LigneDevis, LigneFacture, Paiement
    from apps.ventes.selectors_facturation import ca_devis_factures_par_clients
    from apps.ventes.utils.options import option_totaux
    U = get_user_model()
    co_id = 4
    u = U.objects.filter(company_id=co_id, is_active=True).order_by('id').first()
    co = u.company
    api = _api(u)
    seq = itertools.count(1)
    now = timezone.now()
    cl = Client.objects.create(company=co, nom='Cli APRF42 reporting')
    prod = Produit.objects.create(company=co, nom='Kit sonde', sku='APRF42R-P', prix_vente=Decimal('1450'),
                                  quantite_stock=0)
    ok, mes, statuts = {}, {}, []

    def facture(statut, part):
        f = Facture.objects.create(company=co, reference='FAC-APRF42R-%d' % next(seq), client=cl, statut=statut)
        LigneFacture.objects.create(facture=f, produit=prod, designation='Kit', quantite=Decimal('1'),
                                    prix_unitaire=Decimal('1000'))
        paye = (Decimal(f.total_ttc) * part).quantize(Decimal('0.01'))
        if paye:
            Paiement.objects.create(company=co, facture=f, client=cl, montant=paye, date_paiement=date.today(),
                                    mode=Paiement.Mode.VIREMENT)
        Facture.objects.filter(pk=f.pk).update(statut=statut)

    def devis(lead=None, statut=Devis.Statut.ENVOYE, client=None):
        n = next(seq)
        d = Devis.objects.create(company=co, reference='DEV-APRF42R-%04d' % n, client=client or cl, lead=lead,
                                 statut=statut, taux_tva=Decimal('20'))
        LigneDevis.objects.create(devis=d, produit=prod, designation=prod.nom, quantite=Decimal(str(1 + n % 9)),
                                  prix_unitaire=Decimal('1450'), remise=Decimal('0'))
        return d

    def croissance(k):
        for i in range(k):  # factures payées (moitié soldées, moitié à reliquat) + une émise réglée en partie
            facture(Facture.Statut.PAYEE, Decimal('1') if i % 2 == 0 else Decimal('0.5'))
        facture(Facture.Statut.EMISE, Decimal('0.1'))
        for _ in range(k):  # leads à devis + changements d'étape (patron tests_aprf14)
            lead = Lead.objects.create(company=co, nom='Lead sonde %d' % next(seq), stage=stages.QUOTE_SENT)
            Lead.objects.filter(pk=lead.pk).update(date_creation=now - timedelta(days=10))
            devis(lead)
            for jours, cle in ((6, stages.CONTACTED), (4, stages.QUOTE_SENT)):
                a = LeadActivity.objects.create(company=co, lead=lead, kind=LeadActivity.Kind.MODIFICATION,
                                                field='stage', new_value=stages.STAGE_LABELS[cle])
                LeadActivity.objects.filter(pk=a.pk).update(created_at=now - timedelta(days=jours))
        for _ in range(k):  # devis signés de commerciaux distincts
            n = next(seq)
            v = U.objects.create_user(username='aprf42_vendeur_%d' % n, password='x', role_legacy='commercial',
                                      company=co)
            lead = Lead.objects.create(company=co, nom='Lead signé %d' % n, stage=stages.SIGNED, owner=v)
            d = devis(lead)
            Devis.objects.filter(pk=d.pk).update(statut=Devis.Statut.ACCEPTE, created_by=v,
                                                 date_acceptation=timezone.localdate())
        for _ in range(k):  # dormants déjà escaladés (patron tests_aprf10)
            for mod, kw in ((recyclage, {}), (rappels, {'contact_preference': 'phone_ok'})):
                lead = Lead.objects.create(company=co, nom='Dormant', stage=stages.NEW, **kw)
                Lead.objects.filter(pk=lead.pk).update(
                    date_creation=now - timedelta(days=10),
                    contact_preference_set_at=(now - timedelta(days=10) if kw else None))
                LeadActivity.objects.create(company=co, lead=lead, user=None, kind=LeadActivity.Kind.NOTE,
                                            body='%s (déjà)' % mod.ESCALATION_MARKER)
        cx = Client.objects.create(company=co, nom='Cli CA %d' % next(seq))
        for _ in range(k):  # CA par client (APRF12)
            d = devis(client=cx, statut=Devis.Statut.ACCEPTE)
            Facture.objects.create(company=co, reference='FAC-APRF42C-%d' % next(seq), client=cx, devis=d,
                                   statut=Facture.Statut.EMISE, montant_ht=Decimal('500'), montant_tva=Decimal('100'),
                                   montant_ttc=Decimal('600'))
        clients_ca.append(cx.id)

    clients_ca = []
    R = '/api/django/reporting/'
    ep = {'dashboard': R + 'dashboard/', 'pipeline': R + 'pipeline/', 'commercial': R + 'commercial/dashboard/',
          'velocity': R + 'pipeline/velocity/'}

    def tour():
        res = {}
        for nom, url in ep.items():
            st, q, o, js = _mesure(api, url)
            res[nom] = {'st': st, 'q': q, 'js': js}
            statuts.append(st)
        res['integrite'] = dict(zip(('q', 'ids'), _compte(lambda: factures_payees_avec_solde(co))))
        res['recyclage'] = {'q': _compte(lambda: recyclage.recycler_leads_non_travailles(now=now, dry_run=True))[0]}
        res['rappels'] = {'q': _compte(lambda: rappels.escalader_rappels_demandes(now=now, dry_run=True))[0]}
        res['ca_clients'] = dict(zip(('q', 'ca'), _compte(lambda: ca_devis_factures_par_clients(co, clients_ca))))
        return res

    croissance(2)
    tour()  # échauffement
    a = tour()
    croissance(10)
    b = tour()
    croissance(10)
    c = tour()
    for k in a:
        mes[k] = '%s→%s→%s req' % (a[k]['q'], b[k]['q'], c[k]['q'])
        if 'st' in a[k]:
            mes[k] += ' (st %s/%s/%s)' % (a[k]['st'], b[k]['st'], c[k]['st'])
            ok['200_' + k] = a[k]['st'] == b[k]['st'] == c[k]['st'] == 200
        ok['plat_' + k] = c[k]['q'] - b[k]['q'] <= 1
    # Chiffres = relecture SANS préchargement.
    payees = list(Facture.objects.filter(company=co, statut=Facture.Statut.PAYEE))
    ca_paye = sum((_ht_encaisse(f) for f in payees), Decimal('0'))
    k_ = (c['dashboard']['js'] or {}).get('kpis') or {}
    ok['dashboard_ca_paye'] = abs(Decimal(str(k_.get('ca_paye', -1))) - ca_paye) <= Decimal('0.01')
    mes['dashboard_ca_paye'] = '%s servi / %s relu' % (k_.get('ca_paye'), ca_paye)
    anomalies = sorted(f.id for f in payees if f.montant_du != 0)
    ok['integrite_egale_unitaire'] = sorted(c['integrite']['ids']) == anomalies
    mes['integrite_ids'] = '%d servis / %d relus' % (len(c['integrite']['ids']), len(anomalies))
    attendu = {d.lead.owner.username: str(Decimal(str(option_totaux(d)['ht'])))
               for d in Devis.objects.filter(company=co, statut=Devis.Statut.ACCEPTE,
                                             lead__owner__username__startswith='aprf42_vendeur_')
               .select_related('lead__owner')}
    servi = {r['commercial']: r['ca_ht'] for r in (c['commercial']['js'] or {}).get('leaderboard', [])
             if str(r.get('commercial', '')).startswith('aprf42_vendeur_')}
    ok['commercial_ca_egal_option_totaux'] = bool(attendu) and servi == attendu
    mes['commercial_classement'] = '%d vendeurs sonde servis / %d relus' % (len(servi), len(attendu))
    ecart_ca = []
    for cid in clients_ca:
        ds = Devis.objects.filter(company=co, client_id=cid)
        att = sum((Decimal(str(d.total_ttc)) for d in ds), Decimal('0'))
        if c['ca_clients']['ca'][cid]['ca_devis'] != att:
            ecart_ca.append(cid)
    ok['ca_clients_egal_unitaire'] = not ecart_ca
    ok['zero_503'] = 503 not in statuts
    return {'repro': all(ok.values()), 'ko': sorted(k for k, v in ok.items() if not v), 'mesures': mes}

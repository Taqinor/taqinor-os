SONDE = {"constat": "C-APRF-ACC-STOCK", "sha": "665a4ce53",
         "attendu": "APRF42 (C-APRF-017, 020, 021, 028, 029) : catalogue produits, bons de commande fournisseur, "
                    "documents GED, valorisation du stock (écran + xlsx) et export des mouvements, société démo 2, "
                    "mesurés à TROIS tailles (données créées dans la transaction annulée selon les patrons des tests "
                    "APRF) : requêtes identiques entre les tailles 2 et 3 (pente 0 ± 1), 0 réponse 503, compteurs de "
                    "versions GED = relecture unitaire, export mouvements 200 sous le seuil NTPLT30 et 202 + job "
                    "au-delà (Celery coupé par la sonde : rien n'est exécuté).",
         "modeles": ["stock.Produit", "stock.BonCommandeFournisseur", "stock.MouvementStock", "ged.Document",
                     "core.Job"]}

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
    import itertools
    import os
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from apps.ged.models import Cabinet, Document, DocumentTag, DocumentTagAssignment, DocumentVersion, FavoriGed, Folder
    from apps.stock.models import (AcompteFournisseur, AnnonceLivraisonFournisseur, BonCommandeFournisseur,
                                   EmplacementStock, Fournisseur, LigneBonCommandeFournisseur, MouvementStock,
                                   Produit, RevalorisationStock, StockEmplacement, TransfertStock)
    from apps.stock.services import ensure_emplacements
    U = get_user_model()
    u = U.objects.get(username='demo_admin')
    co = u.company
    api = _api(u)
    seq = itertools.count(1)
    four = Fournisseur.objects.create(company=co, nom='Four APRF42')
    ensure_emplacements(co)
    principal = EmplacementStock.objects.filter(company=co, is_principal=True).first()
    camion = EmplacementStock.objects.filter(company=co, is_principal=False).first()
    today = timezone.localdate()
    ok, mes, toutes = {}, {}, []

    def trois(nom, creer, appel, tailles=(3, 10, 10)):
        r = []
        creer(tailles[0])
        appel()  # échauffement
        r.append(appel())
        creer(tailles[1])
        r.append(appel())
        creer(tailles[2])
        r.append(appel())
        toutes.extend(r)
        mes[nom] = '%s→%s→%s req (st %s/%s/%s, n %s→%s→%s)' % tuple(
            [x['q'] for x in r] + [x['st'] for x in r] + [x.get('n') for x in r])
        ok[nom + '_200'] = all(x['st'] == 200 for x in r)
        ok[nom + '_plat'] = r[2]['q'] - r[1]['q'] <= 1
        return r

    def get(url, **data):
        def f():
            st, q, o, js = _mesure(api, url, data=data)
            return {'st': st, 'q': q, 'n': len(_lignes(js)), 'rows': _lignes(js)}
        return f

    # ---- produits (C-APRF-017) ----
    def produits(k):
        for _ in range(k):
            Produit.objects.create(company=co, nom='Produit sonde %d' % next(seq), sku='APRF42S-%d' % next(seq),
                                   prix_vente=Decimal('100'), prix_achat=Decimal('70'), quantite_stock=3)
    trois('produits', produits, get('/api/django/stock/produits/', page_size=100), (5, 30, 30))
    # Le catalogue démo remplit déjà la page de 100 : la pente PAR LIGNE se lit aussi à 25 vs 100 lignes.
    p25, p100 = get('/api/django/stock/produits/', page_size=25)(), get('/api/django/stock/produits/', page_size=100)()
    mes['produits_par_page'] = '%s req @25 / %s req @100 (n %s/%s)' % (p25['q'], p100['q'], p25['n'], p100['n'])
    ok['produits_plat_page'] = p25['st'] == p100['st'] == 200 and _plat(p25['q'], p100['q'])

    # ---- BCF (C-APRF-020, patron tests_aprf33) ----
    p0 = Produit.objects.create(company=co, nom='P sonde', sku='APRF42S-P0', prix_vente=Decimal('100'),
                                prix_achat=Decimal('70'), quantite_stock=0)

    def bcf(k):
        for _ in range(k):
            b = BonCommandeFournisseur.objects.create(company=co, reference='BCF-APRF42-%d' % next(seq), fournisseur=four)
            LigneBonCommandeFournisseur.objects.create(bon_commande=b, produit=p0, quantite=2,
                                                       prix_achat_unitaire=Decimal('70'))
            for k2 in range(2):
                AcompteFournisseur.objects.create(company=co, bon_commande=b, montant=Decimal('10') + k2,
                                                  date_versement=date(2026, 1, 1 + k2))
                AnnonceLivraisonFournisseur.objects.create(company=co, bon_commande_fournisseur=b,
                                                           date_expedition=date(2026, 2, 1 + k2), transporteur='T%d' % k2,
                                                           lignes=[{'produit_id': p0.id, 'produit_nom': 'P', 'quantite': 1}])
    trois('bcf', bcf, get('/api/django/stock/bons-commande-fournisseur/', page_size=50))

    # ---- GED (C-APRF-021, patron test_aprf36) ----
    cab = Cabinet.objects.create(company=co, nom='Cab sonde')
    folder = Folder.objects.create(company=co, cabinet=cab, nom='R sonde')
    tag = DocumentTag.objects.create(company=co, nom='Contrats sonde', slug='contrats-sonde')
    nd = [0]

    def docs(k):
        for _ in range(k):
            nd[0] += 1
            d = Document.objects.create(company=co, folder=folder, nom='D%d' % nd[0], created_by=u, proprietaire=u,
                                        locked_by=u)
            for v in range(1, 1 + (nd[0] % 3) + 1):
                DocumentVersion.objects.create(company=co, document=d, version=v, file_key='aprf42-k%d-%d' % (nd[0], v),
                                               mime='application/v%d' % v)
            DocumentTagAssignment.objects.create(company=co, document=d, tag=tag)
            FavoriGed.objects.create(company=co, utilisateur=u, document=d)
    r = trois('ged', docs, get('/api/django/ged/documents/', folder=folder.pk, page_size=100), (5, 14, 14))
    ecarts = []
    for row in r[2]['rows']:
        vs = list(Document.objects.get(pk=row['id']).versions.order_by('-version'))
        if (row.get('version_count'), row.get('derniere_version'), row.get('derniere_mime')) != (
                len(vs), vs[0].version, vs[0].mime):
            ecarts.append(row['id'])
    ok['ged_valeurs_unitaires'] = bool(r[2]['rows']) and not ecarts

    # ---- valorisation (C-APRF-029, patron tests_aprf35) ----
    def recu(p, quantite, prix, il_y_a, frais='0'):
        b = BonCommandeFournisseur.objects.create(company=co, reference='BCF-AP42V-%d' % next(seq), fournisseur=four,
                                                  statut=BonCommandeFournisseur.Statut.RECU)
        jour = today - datetime.timedelta(days=il_y_a)
        BonCommandeFournisseur.objects.filter(pk=b.pk).update(
            date_creation=timezone.make_aware(datetime.datetime.combine(jour, datetime.time(10, 0))))
        LigneBonCommandeFournisseur.objects.create(bon_commande=b, produit=p, quantite=quantite,
                                                   prix_achat_unitaire=Decimal(prix), quantite_recue=quantite,
                                                   frais_annexes=Decimal(frais))

    def valo_produits(k):
        for _ in range(k):
            i = next(seq)
            p = Produit.objects.create(company=co, nom='Produit AP42V %04d' % i, sku='AP42V-%d' % i,
                                       prix_vente=Decimal('500'), prix_achat=Decimal('111.11'), quantite_stock=12)
            g = i % 4
            if g == 0:
                recu(p, 10, '100', 20, frais='30')
                recu(p, 5, '130.33', 3)
            elif g == 1:
                recu(p, 10, '1000', 30)
                RevalorisationStock.objects.create(company=co, produit=p, ancien_cout=Decimal('1000'),
                                                   nouveau_cout=Decimal('600'), quantite_snapshot=10,
                                                   delta_valeur=Decimal('-4000'), motif='Baisse', auteur=u,
                                                   statut=RevalorisationStock.Statut.VALIDEE,
                                                   date_validation=timezone.now() - datetime.timedelta(days=10))
                recu(p, 4, '700', 2)
            elif g == 2:
                m = MouvementStock.objects.create(company=co, produit=p, type_mouvement='entree', quantite=6,
                                                  quantite_avant=6, quantite_apres=12, cout_unitaire=Decimal('87.1234'))
                MouvementStock.objects.filter(pk=m.pk).update(date=timezone.now() - datetime.timedelta(days=1))
                recu(p, 3, '90', 4)
            if camion and i % 3 == 0:
                StockEmplacement.objects.create(company=co, produit=p, emplacement=camion, quantite=4)
            if camion and principal and i % 5 == 0:
                TransfertStock.objects.create(company=co, produit=p, source=principal, destination=camion, quantite=2,
                                              statut=TransfertStock.Statut.EXPEDIE)

    def valo():
        st, q, o, js = _mesure(api, '/api/django/stock/produits/valorisation/')
        st2, q2, o2, _ = _mesure(api, '/api/django/stock/produits/valorisation-xlsx/')
        return {'st': st if st2 == 200 else st2, 'q': q, 'q_xlsx': q2, 'n': o2}
    r = trois('valorisation', valo_produits, valo, (9, 20, 20))
    ok['valorisation_xlsx_plat'] = r[2]['q_xlsx'] - r[1]['q_xlsx'] <= 1
    mes['valorisation_xlsx'] = '%s→%s→%s req' % tuple(x['q_xlsx'] for x in r)

    # ---- export des mouvements (C-APRF-028, APRF34) ----
    nmv = MouvementStock.objects.filter(company=co).count()
    sync = _mesure(api, '/api/django/stock/mouvements/export-xlsx/', 'post')
    ancien = os.environ.get('NTPLT30_EXPORT_ROW_THRESHOLD')
    os.environ['NTPLT30_EXPORT_ROW_THRESHOLD'] = str(max(1, nmv // 2))
    try:
        asy = _mesure(api, '/api/django/stock/mouvements/export-xlsx/', 'post')
    finally:
        if ancien is None:
            os.environ.pop('NTPLT30_EXPORT_ROW_THRESHOLD', None)
        else:
            os.environ['NTPLT30_EXPORT_ROW_THRESHOLD'] = ancien
    mes['export_mouvements'] = 'seuil défaut : %s (%s req) ; seuil abaissé à %s / %s lignes : %s %s' % (
        sync[0], sync[1], max(1, nmv // 2), nmv, asy[0], str(asy[3])[:120])
    ok['export_sync_200'] = sync[0] == 200
    ok['export_async_202_job'] = asy[0] == 202 and isinstance(asy[3], dict) and any('job' in k for k in asy[3])
    mes['celery'] = 'tâches bloquées par la sonde : %s' % ctx['celery']
    ok['zero_503'] = all(x['st'] != 503 for x in toutes) and 503 not in (sync[0], asy[0])
    return {'repro': all(ok.values()), 'ko': sorted(k for k, v in ok.items() if not v), 'mesures': mes}

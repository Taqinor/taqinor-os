SONDE = {"constat": "C-APRF-ACC-INST", "sha": "665a4ce53",
         "attendu": "APRF42 (C-APRF-016, 018, 019, 022, 023, 024) : liste des chantiers, ordres d'assemblage, "
                    "interventions, replanification en masse (simulation), « Chantiers à facturer » et les 11 listes "
                    "d'installations à lignes, société démo 2, mesurés à TROIS tailles (données créées dans la "
                    "transaction annulée selon les patrons des tests APRF) : requêtes identiques entre les tailles 2 "
                    "et 3 (pente 0 ± 1), 0 réponse 503 ; blocs de détail nuls en liste et servis au détail, coût et "
                    "temps des ordres = calcul à la main, tranches dues = tranche_facturee unitaire, propositions du "
                    "lot = suggerer_creneau unitaire.",
         "modeles": ["installations.Installation", "installations.Intervention", "installations.OrdreAssemblage",
                     "installations.JalonProjet", "ventes.Devis", "ventes.Facture"]}

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


def _url_liste(viewset):
    """Chemin de liste d'un viewset, lu dans le résolveur (aucune URL écrite à la main)."""
    from django.urls import get_resolver

    def walk(pats, pre=''):
        for p in pats:
            s = pre + str(p.pattern)
            if hasattr(p, 'url_patterns'):
                r = walk(p.url_patterns, s)
                if r:
                    return r
            else:
                cb = getattr(p, 'callback', None)
                if getattr(cb, 'cls', None) is viewset and 'list' in (getattr(cb, 'actions', None) or {}).values() \
                        and '<' not in s and '(?P' not in s and 'format' not in s:
                    return s
        return None
    s = walk(get_resolver().url_patterns)
    return '/' + s.replace('^', '').replace('$', '').replace('\\Z', '') if s else None


def sonde(ctx):
    import datetime
    import itertools
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from django.utils import timezone
    from apps.crm.models import Client, Lead
    from apps.installations import selectors as isel
    from apps.installations.models import (EtapeAssemblage, EtapeOrdre, Installation, Intervention, JalonProjet,
                                           Kit, KitComposant, OrdreAssemblage, OrdreAssemblageLigne)
    from apps.installations.planification_lot import suggerer_creneaux_lot
    from apps.records.models import Attachment
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, Facture, LigneDevis
    from apps.ventes.selectors import tranche_facturee
    from core.events import devis_accepted
    U = get_user_model()
    u = U.objects.get(username='demo_admin')
    co = u.company
    api = _api(u)
    seq = itertools.count(1)
    today = timezone.localdate()
    B = '/api/django/installations/'
    ok, mes = {}, {}

    def produit(nom, prix_achat=Decimal('0')):
        return Produit.objects.create(company=co, nom=nom, sku='APRF42I-%d' % next(seq), prix_vente=Decimal('100'),
                                      prix_achat=prix_achat, quantite_stock=100)

    # ---- liste des chantiers (patron test_regime APRF37 : devis accepté à 11 lignes -> chantier) ----
    prods = [produit('Produit sonde %d' % i) for i in range(11)]

    def chantiers(k):
        for _ in range(k):
            i = next(seq)
            cl = Client.objects.create(company=co, nom='Site%d' % i, prenom='Sonde', email='aprf42i-%d@example.invalid' % i)
            lead = Lead.objects.create(company=co, nom='Site%d' % i, prenom='Sonde', stage='SIGNED',
                                       type_installation='residentiel')
            d = Devis.objects.create(company=co, reference='DEV-AP42I-%d' % i, client=cl, lead=lead,
                                     statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'), mode_installation='residentiel')
            for p in prods:
                LigneDevis.objects.create(devis=d, produit=p, designation=p.nom, quantite=Decimal('2'),
                                          prix_unitaire=Decimal('100'))
            devis_accepted.send(sender=None, devis=d, user=u, ancien_statut='envoye')

    def liste_chantiers():
        st, q, o, js = _mesure(api, B + 'chantiers/', data={'page_size': 50})
        return {'st': st, 'q': q, 'n': len(_lignes(js)), 'rows': _lignes(js)}

    chantiers(3)
    liste_chantiers()
    ca = liste_chantiers()
    chantiers(5)
    cb = liste_chantiers()
    chantiers(5)
    cc = liste_chantiers()
    mes['chantiers'] = '%s→%s→%s req (st %s/%s/%s, lignes %s→%s→%s)' % (
        ca['q'], cb['q'], cc['q'], ca['st'], cb['st'], cc['st'], ca['n'], cb['n'], cc['n'])
    ok['chantiers_200'] = ca['st'] == cb['st'] == cc['st'] == 200
    ok['chantiers_plat'] = cc['q'] - cb['q'] <= 1
    une = next((r for r in cc['rows'] if str(r.get('reference', '')).startswith('CH') or True), None)
    blocs_nuls = all(r.get(k) is None for r in cc['rows'] for k in ('regime_suggere', 'calepinage', 'dossier_8221_resume'))
    det = api.get('%schantiers/%s/' % (B, une['id']), **H) if une else None
    ok['chantiers_blocs_nuls_liste'] = blocs_nuls
    ok['chantiers_blocs_servis_detail'] = bool(det is not None and det.status_code == 200
                                               and isinstance(det.data.get('dossier_8221_resume'), dict)
                                               and 'regime_suggere' in det.data)

    # ---- ordres d'assemblage (patron tests_xmfg14 APRF39) ----
    pieces = [produit('Piece sonde %d' % i, Decimal('5.00') + i) for i in range(4)]
    kit = Kit.objects.create(company=co, nom='Kit APRF42', produit_compose=produit('Compose sonde'))
    etapes = [EtapeAssemblage.objects.create(kit=kit, ordre=i, libelle='Etape %d' % i, duree_attendue_min=10 * (i + 1))
              for i in range(2)]
    for p in pieces:
        KitComposant.objects.create(kit=kit, produit=p, quantite=3)

    def ordres(k):
        for _ in range(k):
            o = OrdreAssemblage.objects.create(company=co, reference='ASM-APRF42-%d' % next(seq), kit=kit, quantite=2,
                                               responsable=u)
            for p in pieces:
                OrdreAssemblageLigne.objects.create(ordre=o, produit=p, quantite=3)
            for e in etapes:
                EtapeOrdre.objects.create(ordre=o, etape_modele=e, duree_reelle_min=7)

    def liste_ordres():
        st, q, o, js = _mesure(api, B + 'ordres-assemblage/', data={'page_size': 100})
        return {'st': st, 'q': q, 'n': len(_lignes(js)), 'rows': _lignes(js)}
    ordres(2)
    liste_ordres()
    oa_, ob, oc = liste_ordres(), None, None
    ordres(6)
    ob = liste_ordres()
    ordres(6)
    oc = liste_ordres()
    mes['ordres_assemblage'] = '%s→%s→%s req (st %s/%s/%s, lignes %s→%s→%s)' % (
        oa_['q'], ob['q'], oc['q'], oa_['st'], ob['st'], oc['st'], oa_['n'], ob['n'], oc['n'])
    ok['ordres_200'] = oa_['st'] == ob['st'] == oc['st'] == 200
    ok['ordres_plat'] = oc['q'] - ob['q'] <= 1
    cout = sum((Decimal(3) * p.prix_achat for p in pieces), Decimal('0'))
    ok['ordres_valeurs_main'] = all(Decimal(str(r['cout_prevu'])) == cout and r['temps_prevu_min'] == 30
                                    and r['temps_reel_min'] == 14 and len(r['lignes']) == 4
                                    for r in oc['rows'] if str(r.get('reference', '')).startswith('ASM-APRF42-'))

    # ---- interventions (patron tests_aud324 APRF40) ----
    inst = Installation.objects.create(company=co, reference='APRF42-INT', statut=Installation.Statut.EN_COURS)
    ct = ContentType.objects.get_for_model(Intervention)
    ni = [0]

    def interventions(k):
        for _ in range(k):
            ni[0] += 1
            iv = Intervention.objects.create(company=co, installation=inst, type_intervention=Intervention.Type.POSE,
                                             statut=Intervention.Statut.PRETE, technicien=u, date_prevue=str(today))
            if ni[0] % 2 == 0:
                Attachment.objects.create(company=co, content_type=ct, object_id=iv.id, file_key='aprf42/%s' % iv.id,
                                          filename='slot:toiture_apres|toit.jpg')

    def liste_iv():
        st, q, o, js = _mesure(api, B + 'interventions/', data={'page_size': 200})
        return {'st': st, 'q': q, 'n': len(_lignes(js))}
    interventions(5)
    liste_iv()
    ia = liste_iv()
    interventions(20)
    ib = liste_iv()
    interventions(20)
    ic = liste_iv()
    mes['interventions'] = '%s→%s→%s req (st %s/%s/%s, lignes %s→%s→%s)' % (
        ia['q'], ib['q'], ic['q'], ia['st'], ib['st'], ic['st'], ia['n'], ib['n'], ic['n'])
    ok['interventions_200'] = ia['st'] == ib['st'] == ic['st'] == 200
    ok['interventions_plat'] = ic['q'] - ib['q'] <= 1

    # ---- replanification en masse, simulation (patron tests_xfsm2 APRF41) ----
    jour = today + datetime.timedelta(days=3)
    absent = U.objects.create_user(username='aprf42-absent-%d' % next(seq), password='x', role_legacy='technicien',
                                   company=co)
    libres = [U.objects.create_user(username='aprf42-libre-%d' % next(seq), password='x', role_legacy='technicien',
                                    company=co) for _ in range(3)]
    base_inst = Installation.objects.create(company=co, reference='APRF42-R0', statut=Installation.Statut.EN_COURS)
    for k, tech in enumerate(libres):
        for d in range(k + 1):
            Intervention.objects.create(company=co, installation=base_inst, type_intervention=Intervention.Type.POSE,
                                        statut=Intervention.Statut.PRETE, technicien=tech,
                                        date_prevue=jour + datetime.timedelta(days=5 + d))
    a_repl = []

    def a_replanifier(k):
        for _ in range(k):
            i2 = Installation.objects.create(company=co, reference='APRF42-R%d' % next(seq),
                                             statut=Installation.Statut.EN_COURS)
            Intervention.objects.create(company=co, installation=i2, type_intervention=Intervention.Type.POSE,
                                        statut=Intervention.Statut.PRETE, technicien=absent, date_prevue=jour)
            a_repl.append(i2.id)

    def simul():
        st, q, o, js = _mesure(api, B + 'interventions/replanifier-en-masse/', 'post',
                               {'jour': str(jour), 'technicien': absent.id, 'simuler': True})
        return {'st': st, 'q': q, 'n': len((js or {}).get('propositions') or []), 'js': js}
    a_replanifier(2)
    simul()
    ra = simul()
    a_replanifier(4)
    rb = simul()
    a_replanifier(4)
    rc = simul()
    mes['replanification'] = '%s→%s→%s req (st %s/%s/%s, propositions %s→%s→%s)' % (
        ra['q'], rb['q'], rc['q'], ra['st'], rb['st'], rc['st'], ra['n'], rb['n'], rc['n'])
    ok['replanif_200'] = ra['st'] == rb['st'] == rc['st'] == 200
    ok['replanif_plat'] = rc['q'] - rb['q'] <= 1 and (ra['n'], rb['n'], rc['n']) == (2, 6, 10)
    lot = suggerer_creneaux_lot(co, a_repl[:3], n=10)
    ok['replanif_lot_egal_unitaire'] = all(
        lot[cid] == isel.suggerer_creneau(co, chantier_id=cid, type_intervention=Intervention.Type.POSE, n=10)
        for cid in a_repl[:3])

    # ---- « Chantiers à facturer » (patron tests_yserv7 APRF24) ----
    cl24 = Client.objects.create(company=co, nom='Client', prenom='APRF42-24', email='aprf42-24@example.invalid')
    tranches = ('acompte', 'intermediaire', 'solde')
    jalons = []

    def jalons_atteints(k):
        motifs = (None, 'emise', 'annulee', 'brouillon')
        for j in range(k):
            n = next(seq)
            tr = tranches[n % 3]
            d = Devis.objects.create(company=co, reference='DEV-AP42F-%04d' % n, client=cl24,
                                     statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'), mode_installation='residentiel')
            i3 = Installation.objects.create(company=co, reference='CHT-AP42F-%d' % n, client=cl24, devis=d,
                                             statut=Installation.Statut.SIGNE)
            jalons.append(JalonProjet.objects.create(company=co, installation=i3, phase=JalonProjet.Phase.POSE,
                                                     libelle='Pose %d' % n, tranche_echeancier=tr, atteint=True))
            m = motifs[j % 4]
            if m:
                Facture.objects.create(company=co, reference='FAC-AP42F-%04d' % n, devis=d, client=cl24,
                                       type_facture=tr, statut={'emise': Facture.Statut.EMISE,
                                                                'annulee': Facture.Statut.ANNULEE,
                                                                'brouillon': Facture.Statut.BROUILLON}[m])

    def af():
        st, q, o, js = _mesure(api, B + 'chantiers/a-facturer/')
        return {'st': st, 'q': q, 'n': len(_lignes(js)), 'rows': _lignes(js)}
    jalons_atteints(4)
    af()
    fa = af()
    jalons_atteints(8)
    fb = af()
    jalons_atteints(8)
    fc = af()
    mes['a_facturer'] = '%s→%s→%s req (st %s/%s/%s, lignes %s→%s→%s)' % (
        fa['q'], fb['q'], fc['q'], fa['st'], fb['st'], fc['st'], fa['n'], fb['n'], fc['n'])
    ok['a_facturer_200'] = fa['st'] == fb['st'] == fc['st'] == 200
    ok['a_facturer_plat'] = fc['q'] - fb['q'] <= 1
    attendu = sorted(j.id for j in jalons if not tranche_facturee(j.installation.devis, j.tranche_echeancier))
    servis = sorted(r['jalon_id'] for r in fc['rows'] if r.get('jalon_id') in {j.id for j in jalons})
    ok['a_facturer_egal_unitaire'] = servis == attendu
    mes['a_facturer_tranches'] = '%d dues servies / %d unitaire' % (len(servis), len(attendu))

    # ---- les 11 listes à lignes (APRF38) : préchargements déclarés + GET réel (statut, requêtes) ----
    from apps.installations.views.colisage import ColisViewSet
    from apps.installations.views.commande_cadre import CommandeCadreViewSet
    from apps.installations.views.comptage import SessionComptageViewSet
    from apps.installations.views.contrat_prix import ContratPrixFournisseurViewSet
    from apps.installations.views.demande_achat import DemandeAchatViewSet
    from apps.installations.views.kitting import KitViewSet, OrdreDemontageViewSet
    from apps.installations.views.livraison import LivraisonViewSet
    from apps.installations.views.picklist import PickListViewSet
    from apps.installations.views.retour_livraison import RetourLivraisonViewSet
    from apps.installations.views.retour_materiel import RetourMaterielViewSet
    onze = ((PickListViewSet, ('lignes__produit', 'lignes__bin')), (ColisViewSet, ('lignes__produit',)),
            (SessionComptageViewSet, ('lignes__produit',)), (LivraisonViewSet, ('lignes__produit',)),
            (RetourMaterielViewSet, ('lignes__produit',)), (RetourLivraisonViewSet, ('lignes__produit',)),
            (DemandeAchatViewSet, ('lignes__produit',)), (CommandeCadreViewSet, ('lignes__produit',)),
            (ContratPrixFournisseurViewSet, ('lignes__produit',)), (KitViewSet, ('composants__produit',)),
            (OrdreDemontageViewSet, ('lignes__produit',)))
    res11 = {}
    for vs, lk in onze:
        decl = set(vs.queryset._prefetch_related_lookups)
        url = _url_liste(vs)
        st, q, n = (None, None, None)
        if url:
            st, q, o, js = _mesure(api, url)
            n = len(_lignes(js))
        res11[vs.__name__] = {'prefetch': all(x in decl for x in lk), 'url': url, 'st': st, 'q': q, 'n': n}
    ok['onze_prefetch_declares'] = all(v['prefetch'] for v in res11.values())
    ok['onze_get_200'] = all(v['st'] == 200 for v in res11.values())
    # Kits : taille 2 / 3 (composants à produit).

    def kits(k):
        for _ in range(k):
            kk = Kit.objects.create(company=co, nom='Kit sonde %d' % next(seq), produit_compose=produit('Compose k'))
            for p in pieces:
                KitComposant.objects.create(kit=kk, produit=p, quantite=2)
    url_kit = res11['KitViewSet']['url']
    kits(3)
    k2 = _mesure(api, url_kit, data={'page_size': 100})
    kits(6)
    k3 = _mesure(api, url_kit, data={'page_size': 100})
    mes['kits'] = '%s→%s req (st %s/%s, lignes %s→%s)' % (k2[1], k3[1], k2[0], k3[0], len(_lignes(k2[3])),
                                                          len(_lignes(k3[3])))
    ok['kits_plat'] = k2[0] == k3[0] == 200 and k3[1] - k2[1] <= 1
    mes['onze_listes'] = {k: '%s %s req n=%s prefetch=%s' % (v['st'], v['q'], v['n'], v['prefetch'])
                          for k, v in res11.items()}
    toutes = [ca, cb, cc, oa_, ob, oc, ia, ib, ic, ra, rb, rc, fa, fb, fc]
    ok['zero_503'] = all(x['st'] != 503 for x in toutes) and all(v['st'] != 503 for v in res11.values())
    return {'repro': all(ok.values()), 'ko': sorted(k for k, v in ok.items() if not v), 'mesures': mes}

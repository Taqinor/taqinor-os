SONDE = {"constat": "C-AMOT-HXH-ACHAT", "sha": "673ec3f92",
         "attendu": "P3.5 / charte D2 — sur un devis de chaque mode (résidentiel 1121, commercial 1116, industriel "
                    "1112, agricole de la société anonymisée), prix d'achat de toutes les fiches produit posé à la "
                    "valeur-témoin 7 313,17 dans la transaction : la valeur et toute clé prix_achat / marge* / "
                    "cout_achat sont absentes du PDF /proposal (full + une-page) et de /proposal data ; une ligne "
                    "saisie à la main (« Prestation spéciale sonde AMOT », 3 × 1 234,56) est rendue telle quelle "
                    "(désignation, P.U. 1 234,56, total 3 703,68) ; pompage : 0 onduleur, 0 batterie"}


def sonde(ctx):
    import json
    import re
    import fitz
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    H = {'HTTP_HOST': 'localhost'}
    User = get_user_model()
    apis = {}
    for nom in ('demo_admin', 'anon_admin'):
        u = User.objects.get(username=nom)
        a = APIClient()
        a.force_authenticate(u)
        apis[u.company_id] = a
    anon = User.objects.get(username='anon_admin')

    def norm(t):
        return re.sub(r'[   ]', ' ', t or '')

    def lire(dv, qs=''):
        r = apis[dv.company_id].get(f'/api/django/ventes/devis/{dv.id}/proposal/{qs}', **H)
        if r.status_code != 200:
            return r.status_code, '', 0
        body = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
        doc = fitz.open(stream=body, filetype='pdf')
        return 200, norm('\n'.join(p.get_text() for p in doc)), doc.page_count

    def cles_interdites(obj, chemin=''):
        trouve = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                ks = str(k).lower()
                if ks.startswith('prix_achat') or ks.startswith('marge') or ks.startswith('cout_achat'):
                    trouve.append(chemin + '.' + str(k))
                trouve += cles_interdites(v, chemin + '.' + str(k))
        elif isinstance(obj, (list, tuple)):
            for i, v in enumerate(obj):
                trouve += cles_interdites(v, f'{chemin}[{i}]')
        return trouve

    agri = Devis.objects.filter(company=anon.company, mode_installation='agricole').order_by('-id').first()
    cas = [('residentiel', Devis.objects.get(pk=1121)), ('commercial', Devis.objects.get(pk=1116)),
           ('industriel', Devis.objects.get(pk=1112)), ('agricole', agri)]
    out, ok = {}, True
    for nom, dv in cas:
        Produit.objects.filter(pk__in=dv.lignes.exclude(produit__isnull=True).values('produit')).update(
            prix_achat=Decimal('7313.17'))
        LigneDevis.objects.create(devis=dv, designation='Prestation spéciale sonde AMOT', quantite=Decimal('3'),
                                  prix_unitaire=Decimal('1234.56'), taux_tva=Decimal('20'), ordre=999)
        dv.refresh_from_db()
        res = {'reference': dv.reference}
        for fmt, qs in (('full', ''), ('onepage', '?pdf_mode=onepage')):
            st, txt, pages = lire(dv, qs)
            achat = [x for x in ('7 313,17', '7313,17', '7 313.17', '7313.17') if x in txt]
            ligne = {'http': st, 'pages': pages, 'prix_achat_imprime': achat,
                     'mot_marge': txt.lower().count('marge'), 'mot_achat': txt.lower().count("prix d'achat"),
                     'designation_manuelle': 'Prestation spéciale sonde AMOT' in txt,
                     'pu_1234_56': '1 234,56' in txt, 'total_3703_68': '3 703,68' in txt}
            if nom == 'agricole':
                ligne['onduleur'] = txt.lower().count('onduleur')
                ligne['batterie'] = txt.lower().count('batterie')
                ok &= ligne['onduleur'] == 0 and ligne['batterie'] == 0
            res[fmt] = ligne
            ok &= st == 200 and not achat and ligne['mot_achat'] == 0
            if fmt == 'full':
                ok &= ligne['designation_manuelle'] and ligne['pu_1234_56'] and ligne['total_3703_68']
        r = apis[dv.company_id].post(f'/api/django/ventes/devis/{dv.id}/share-link/', {}, format='json', **H)
        if r.status_code in (200, 201):
            rd = apis[dv.company_id].get(f"/api/django/ventes/proposal/{r.data.get('token_interne')}/", **H)
            brut = json.dumps(rd.data, default=str, ensure_ascii=False) if rd.status_code == 200 else ''
            q = (rd.data or {}).get('quote') or {}
            manu = [it for it in q.get('all_items', []) if it.get('designation') == 'Prestation spéciale sonde AMOT']
            res['data'] = {'http': rd.status_code, 'cles_interdites': cles_interdites(rd.data)[:6],
                           'valeur_prix_achat': '7313.17' in brut,
                           'ligne_manuelle': [{k: m.get(k) for k in ('quantite', 'qty', 'pu_ht', 'prix_unitaire_ht',
                                                                    'total_ht') if k in m} for m in manu][:1]}
            ok &= rd.status_code == 200 and not res['data']['cles_interdites'] and '7313.17' not in brut and bool(manu)
        else:
            res['data'] = {'share_link_http': r.status_code}
            ok = False
        out[nom] = res
    out['repro'] = bool(ok)
    return out

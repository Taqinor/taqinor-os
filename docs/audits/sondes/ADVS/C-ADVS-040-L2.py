# flake8: noqa  (seconde lentille C-ADVS-040, reproduction indépendante — rejouable par scripts/sonde.py)
"""Répartition des options « Sans / Avec batterie » : le PDF et la page publique (`quote_engine/builder.py::
_repartir_options`, rôle stocké `LigneDevis.role_devis` d'abord) contre l'argent serveur (`utils/options.py::
filter_lines_for_option` → `option_totaux`, mots-clés seuls). Devis « Les deux (Sans + Avec) » créé par POST
/atomic (rôles posés par le serveur) avec, en plus du kit, trois frères candidats :
  F1 « Câble batterie DC 25 mm² » (rôle dérivé cable_dc, mot « batterie ») ;
  F2 « Dyness BX51100 5,12 kWh » (Produit.role_devis='batterie' déclaré, aucun mot-clé) ;
  F3 « Support mural batterie » (rôle dérivé batterie, mot « batterie » — témoin, doit concorder).
Compare TTC par option : builder.build_quote_data (totaux_sans/avec) vs utils.options.option_totaux, et la page
publique /data. Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-040", "sha": "1dfa7986c",
         "attendu": "TTC sans/avec identiques entre PDF (builder), page publique et option_totaux serveur",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "ventes.ShareLink"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, ShareLink
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 040 L2', slug='sonde-advs-040-l2')
    u = U.objects.create_user(username='sonde-advs-040-l2', password='x', role_legacy='admin', company=c)
    cl = Client.objects.create(company=c, nom='Options', prenom='L2', email='sonde-advs-040-l2@example.invalid')

    def mk(sku, nom, prix, tva, role=None):
        kw = {'role_devis': role} if role else {}
        return Produit.objects.create(company=c, nom=nom, sku=f'ADVS040L2-{sku}', prix_vente=Decimal(prix),
                                      prix_achat=Decimal('1'), quantite_stock=100, tva=Decimal(tva), **kw)
    kit = [(mk('P', 'Panneau Canadian Solar 550W', '1000.00', 10), 10),
           (mk('R', 'Onduleur réseau Huawei 5kW Monophasé', '12000.00', 20), 1),
           (mk('H', 'Onduleur hybride Deye 5kW Monophasé', '15000.00', 20), 1),
           (mk('B', 'Batterie Dyness 5 kWh', '14000.00', 20), 1),
           (mk('F1', 'Câble batterie DC 25 mm²', '250.00', 20), 4),
           (mk('F2', 'Dyness BX51100 5,12 kWh', '13000.00', 20, role='batterie'), 1),
           (mk('F3', 'Support mural batterie', '400.00', 20), 1)]
    api, pub = APIClient(), APIClient()
    api.force_authenticate(u)
    etapes = []

    def appel(nom, cli, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(cli, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
        except Exception as e:
            etapes.append((nom, 599, repr(e)[:300]))
            return 599, {}
        txt = r.content.decode('utf-8', 'replace') if hasattr(r, 'content') else ''
        etapes.append((nom, r.status_code, '' if r.status_code < 400 else txt[:300]))
        try:
            return r.status_code, json.loads(txt)
        except Exception:
            return r.status_code, {}

    s, r = appel('atomic', api, 'post', '/api/django/ventes/devis/atomic/', {
        'client': cl.id, 'statut': 'brouillon', 'taux_tva': '20.00',
        'etude_params': {'scenario': 'Les deux (Sans + Avec)'},
        'lignes': [{'produit': p.id, 'designation': p.nom, 'quantite': str(q), 'prix_unitaire': str(p.prix_vente),
                    'taux_tva': str(p.tva)} for p, q in kit]})
    dv = Devis.objects.filter(company=c).first()
    obs = {'etapes': etapes}
    if dv is None:
        return {'repro': False, 'observe': obs}
    from apps.ventes.utils.options import (
        AVEC_BATTERIE, SANS_BATTERIE, deux_options_declarees, filter_lines_for_option, option_totaux)
    from apps.ventes.quote_engine.builder import _repartir_options, build_quote_data
    lignes = list(dv.lignes.select_related('produit').order_by('ordre', 'id'))
    obs['roles'] = {li.designation: li.role_devis for li in lignes}
    obs['deux_options'] = deux_options_declarees(dv)
    serveur = {o: [li.designation for li in filter_lines_for_option(lignes, o)] for o in (SANS_BATTERIE, AVEC_BATTERIE)}
    s_pdf, a_pdf, contra = _repartir_options([(li, {'designation': li.designation, 'produit_nom': li.produit.nom})
                                              for li in lignes])
    pdf = {SANS_BATTERIE: [li.designation for li, _ in s_pdf], AVEC_BATTERIE: [li.designation for li, _ in a_pdf]}
    obs['paniers_divergents'] = {o: {'pdf_seul': sorted(set(pdf[o]) - set(serveur[o])),
                                     'serveur_seul': sorted(set(serveur[o]) - set(pdf[o]))} for o in pdf}
    try:
        q = build_quote_data(dv)
        obs['pdf_acompte'] = {k: q.get(k) for k in q if 'acompte' in k.lower()}
        obs['pdf_ttc'] = {'sans': str(q['totaux_sans']['ttc']), 'avec': str(q['totaux_avec']['ttc']),
                          'nb_options': q.get('nb_options')}
    except Exception as e:
        obs['pdf_ttc'] = f'err {e!r}'[:300]
    obs['serveur_ttc'] = {'sans': str(option_totaux(dv, SANS_BATTERIE)['ttc']),
                          'avec': str(option_totaux(dv, AVEC_BATTERIE)['ttc'])}
    obs['devis_total_ttc'] = str(dv.total_ttc)
    try:
        from apps.ventes.selectors import acompte_pour_devis
    except Exception:
        acompte_pour_devis = None
    obs['acompte_serveur'] = str(acompte_pour_devis(dv)) if acompte_pour_devis else 'n/a'
    with mock.patch('apps.ventes.public_views._notify_open'):
        appel('share-link', api, 'post', f'/api/django/ventes/devis/{dv.id}/share-link/', {'envoi': True})
        link = ShareLink.objects.filter(devis=dv, revoque_le__isnull=True).order_by('-id').first()
        if link is not None:
            s, lu = appel('public data', pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
            brut = json.dumps(lu, default=str, ensure_ascii=False)
            obs['public_extraits'] = {k: lu.get(k) for k in ('total_sans', 'total_avec', 'total_ttc', 'display_total',
                                                              'acompte', 'nb_options') if k in lu}
            obs['public_cles_total'] = {k: v for k, v in lu.items() if 'total' in k.lower() or 'option' in k.lower()}
            obs['public_cles_total'] = json.dumps(obs['public_cles_total'], default=str, ensure_ascii=False)[:1200]
    pdf_ttc = obs['pdf_ttc'] if isinstance(obs['pdf_ttc'], dict) else {}
    diverge = bool(pdf_ttc) and (pdf_ttc.get('sans') != obs['serveur_ttc']['sans']
                                 or pdf_ttc.get('avec') != obs['serveur_ttc']['avec'])
    return {'repro': diverge, 'observe': obs}

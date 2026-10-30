SONDE = {"constat": "C-AMOT-035", "sha": "673ec3f92",
         "attendu": "P2.4 — curseur batterie de la page client (/proposal data, balayage_stockage) des devis démo 1119 "
                    "et 1121 remisés à 10 % dans la transaction : chaque palier = prix de VENTE (coût catalogue × 0,9, "
                    "arrondi 100) et payback = payback_publiable sur CE prix ; à la quantité offerte (modules du devis), "
                    "prix du palier = totaux_avec.ttc du devis"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.ventes.models import Devis
    from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
    from apps.ventes.quote_engine.pricing import payback_publiable
    H = {'HTTP_HOST': 'localhost'}
    admin = get_user_model().objects.get(username='demo_admin')
    api = APIClient()
    api.force_authenticate(admin)

    def payload(did):
        r = api.post(f'/api/django/ventes/devis/{did}/share-link/', {}, format='json', **H)
        rd = api.get(f"/api/django/ventes/proposal/{r.data.get('token_interne')}/", **H)
        return rd.status_code, (rd.data or {})

    out, ok = {}, True
    for did in (1119, 1121):
        dv = Devis.objects.get(pk=did, company=admin.company)
        r = api.get(f'/api/django/ventes/devis/{did}/offres-tailles/', **H)
        reco = next((o for o in ((r.data or {}).get('offres_tailles') or {}).get('offres', [])
                     if o.get('est_le_devis')), {})
        nb_offert = (reco.get('config') or {}).get('batterie_nb_modules')
        st0, p0 = payload(did)
        Devis.objects.filter(pk=did).update(remise_globale=Decimal('10'))
        dv.refresh_from_db()
        st1, p1 = payload(did)
        tot_avec = float(build_quote_data(dv, clean_pdf_options({}))['totaux_avec']['ttc'])
        av = {x['nb_packs']: x for x in (p0.get('balayage_stockage') or {}).get('paliers', [])}
        ap = {x['nb_packs']: x for x in (p1.get('balayage_stockage') or {}).get('paliers', [])}
        res = {'http': [st0, st1], 'nb_modules_offerts': nb_offert, 'totaux_avec_ttc_remise': tot_avec, 'paliers': {}}
        for n, pal in ap.items():
            brut = (av.get(n) or {}).get('cout_ttc')
            pb = payback_publiable(pal['cout_ttc'], pal.get('economie_mad'), stockage=True)['payback_years']
            ligne = {'cout_sans_remise': brut, 'cout_remise': pal['cout_ttc'], 'payback': pal.get('payback_annees'),
                     'payback_publiable_sur_prix': pb,
                     'remise_appliquee': bool(brut) and abs(pal['cout_ttc'] - brut * 0.9) <= 100,
                     'payback_coherent': pb is not None and pal.get('payback_annees') is not None
                     and abs(pb - pal['payback_annees']) <= 0.05}
            ok &= ligne['remise_appliquee'] and ligne['payback_coherent']
            res['paliers'][n] = ligne
        offert = ap.get(nb_offert) or {}
        res['palier_offert_cout'] = offert.get('cout_ttc')
        res['palier_offert_egal_totaux_avec'] = (offert.get('cout_ttc') is not None
                                                  and abs(float(offert['cout_ttc']) - tot_avec) < 1)
        res['ecart_palier_offert_vs_devis'] = (None if offert.get('cout_ttc') is None
                                               else round(float(offert['cout_ttc']) - tot_avec, 2))
        ech = [(x.get('capacite_kwh'), x.get('nb_panneaux'), x.get('prix_ttc'))
               for x in (p1.get('paliers_batterie') or []) if x.get('retenu')]
        res['echelle_palier_retenu_capacite_panneaux_prix'] = ech
        ok &= st0 == 200 and st1 == 200 and bool(ap) and res['palier_offert_egal_totaux_avec']
        out[dv.reference] = res
    out['repro'] = bool(ok)
    return out

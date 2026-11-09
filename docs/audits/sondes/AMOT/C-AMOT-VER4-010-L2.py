# flake8: noqa  (sonde second regard vérifie AMOT 04/11, rejouable par scripts/sonde.py — AMET93)
"""Second regard C-AMOT-VER4-010 — bout en bout par le VRAI payload public (GET /api/django/public/proposal/<token>/data/).

Devis résidentiel d'un site ISOLÉ (lead raccordement='aucun', Casablanca, table PVGIS — aucun réseau), lignes
panneaux + « Onduleur Off-Grid 5kW » + batterie, catalogue isolé tarifé. On sert le payload deux fois : (A) le code
de main ; (B) le même code où les deux constructeurs de provision des surfaces /proposition
(`offres_tailles._cout_onduleur_ttc`, `dimensionnement_devis._payback_publie_palier`) voient le rôle
`onduleur_offgrid` comme `onduleur_hybride` (= comme le PDF via `is_inverter`). Si les paybacks des cartes Éco/Max
« avec » et des paliers diffèrent entre A et B, la provision de l'onduleur autonome est réellement OMISE sur la page
servie. On relève aussi roi_a / provision du document (build_quote_data). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AMOT-VER4-010", "sha": "ecd7fcf40",
         "attendu": "payload servi : offres_tailles (Éco/Max avec) et/ou paliers_batterie présents ; payback A < payback B "
                    "(provision onduleur autonome omise) ; roi_a du document calculé AVEC provision",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "ventes.ShareLink", "crm.Lead", "stock.Produit",
                     "authentication.Company"]}


def sonde(ctx):
    from decimal import Decimal
    from unittest import mock
    from rest_framework.test import APIClient
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, ShareLink
    from apps.ventes import offres_tailles as ot
    from apps.ventes.domain import dimensionnement_devis as dd
    from apps.ventes.tests._quote_engine_common import make_company
    from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options

    co = make_company(slug='sonde-amot-ver4-010-l2', nom='SONDE VER4 010 L2')
    catalogue = [
        ('Panneau Jinko 550W', 'L2-PAN550', '1100'),
        ('Onduleur Off-Grid 5kW', 'L2-ONDA5', '15000'),
        ('Onduleur Off-Grid 8kW', 'L2-ONDA8', '21000'),
        ('Onduleur Off-Grid 10kW', 'L2-ONDA10', '26000'),
        ('Onduleur réseau Huawei 5kW Monophasé', 'L2-ONDR5', '14000'),
        ('Onduleur hybride Deye 5kW Monophasé', 'L2-ONDH5', '17000'),
        ('Batterie Dyness 5 kWh', 'L2-BAT5', '16000'),
        ('Structures acier', 'L2-STR', '500'),
    ]
    prod = {}
    for nom, sku, prix in catalogue:
        prod[nom] = Produit.objects.create(company=co, nom=nom, sku=f'{sku}-{co.pk}', prix_vente=Decimal(prix),
                                           prix_achat=Decimal('1'), quantite_stock=100)
    cl = Client.objects.create(company=co, nom='Client isole L2')
    lead = Lead.objects.create(company=co, nom='Lead', prenom='isole', telephone='+212600000000', ville='Casablanca',
                               facture_hiver=1800, ete_differente=False, raccordement='aucun')

    def devis(ref):
        dv = Devis.objects.create(company=co, reference=ref, client=cl, lead=lead, statut='envoye',
                                  taux_tva=Decimal('20'), mode_installation='residentiel', etude_params={})
        for nom, q in (('Panneau Jinko 550W', '10'), ('Onduleur Off-Grid 5kW', '1'), ('Batterie Dyness 5 kWh', '2'),
                       ('Structures acier', '10')):
            p = prod[nom]
            LigneDevis.objects.create(devis=dv, produit=p, designation=nom, quantite=Decimal(q),
                                      prix_unitaire=p.prix_vente, remise=Decimal('0'))
        return dv

    def payload(dv):
        link = ShareLink.objects.create(company=co, devis=dv)
        r = APIClient().get(f'/api/django/public/proposal/{link.token}/data/')
        return r.status_code, (r.json() if r.status_code == 200 else None)

    def resume(p):
        if p is None:
            return None
        out = {'mode': p.get('mode'), 'roi_a': p.get('roi_a'), 'roi_s': p.get('roi_s'),
               'variantes_servables': p.get('variantes_servables'),
               'inv_cost': ((p.get('hypotheses') or {}).get('inverter_replace_cost'),
                            (p.get('hypotheses') or {}).get('inverter_replace_cost_avec'))}
        ot_bloc = p.get('offres_tailles')
        out['offres_tailles_present'] = ot_bloc is not None
        if ot_bloc:
            out['cartes'] = {o.get('cle'): {v: ({k: (o.get(v) or {}).get(k) for k in
                                                ('nb_panneaux', 'prix_ttc', 'economie_annuelle_mad', 'payback_annees')}
                                                if o.get(v) else None) for v in ('sans', 'avec')}
                             for o in (ot_bloc.get('offres') or [])}
        pal = p.get('paliers_batterie')
        out['paliers_present'] = pal is not None
        if pal:
            out['paliers'] = [(x.get('capacite_kwh'), x.get('prix_ttc'), x.get('economies_annuelles'),
                               x.get('payback_annees')) for x in pal]
        return out

    dv_a = devis('DEV-SONDE-V4-010-A')
    dv_b = devis('DEV-SONDE-V4-010-B')
    obs = {'regles_calcul': dv_a.regles_calcul}
    try:
        d = build_quote_data(dv_a, clean_pdf_options({}))
        obs['pdf'] = {'scenario': d.get('scenario'), 'roi_a': d.get('roi_a'), 'roi_s': d.get('roi_s'),
                      'inv_cost_avec': (d.get('cashflow_assumptions') or {}).get('inverter_replace_cost'),
                      'nb_options': d.get('nb_options')}
    except Exception as exc:  # noqa
        obs['pdf'] = f'ERREUR {exc!r}'
    sa, pa = payload(dv_a)
    obs['A_status'] = sa
    obs['A'] = resume(pa)

    orig_cout = ot._cout_onduleur_ttc
    orig_pal = dd._payback_publie_palier

    def cout_elargi(lignes, roles, *a, **k):
        roles = ['onduleur_hybride' if r == 'onduleur_offgrid' else r for r in (roles or [])]
        return orig_cout(lignes, roles, *a, **k)

    def pal_elargi(cout, eco, lignes, *a, **k):
        lignes = [({**l, 'role': 'onduleur_hybride'} if (l or {}).get('role') == 'onduleur_offgrid' else l)
                  for l in (lignes or [])]
        return orig_pal(cout, eco, lignes, *a, **k)

    appels = {'cout': [], 'pal': []}

    def cout_trace(lignes, roles, *a, **k):
        appels['cout'].append(list(roles or []))
        return cout_elargi(lignes, roles, *a, **k)

    def pal_trace(cout, eco, lignes, *a, **k):
        appels['pal'].append([(l or {}).get('role') for l in (lignes or [])])
        return pal_elargi(cout, eco, lignes, *a, **k)

    with mock.patch.object(ot, '_cout_onduleur_ttc', cout_trace), \
            mock.patch.object(dd, '_payback_publie_palier', pal_trace):
        sb, pb = payload(dv_b)
    obs['B_status'] = sb
    obs['B'] = resume(pb)
    obs['roles_vus_cartes'] = sorted({r for rs in appels['cout'] for r in rs if r and 'onduleur' in r})
    obs['roles_vus_paliers'] = sorted({r for rs in appels['pal'] for r in rs if r and 'onduleur' in r})
    obs['nb_appels'] = {k: len(v) for k, v in appels.items()}

    ecarts = []
    A, B = obs['A'] or {}, obs['B'] or {}
    for cle, c in (A.get('cartes') or {}).items():
        for v in ('sans', 'avec'):
            pa_ = ((c or {}).get(v) or {}).get('payback_annees')
            pb_ = (((B.get('cartes') or {}).get(cle) or {}).get(v) or {}).get('payback_annees')
            if pa_ != pb_:
                ecarts.append(('carte', cle, v, pa_, pb_))
    for x, y in zip(A.get('paliers') or [], B.get('paliers') or []):
        if x[3] != y[3]:
            ecarts.append(('palier', x[0], x[3], y[3]))
    obs['ecarts'] = ecarts
    print(obs)
    obs['repro'] = bool(ecarts)
    return obs

# flake8: noqa  (sonde de contre-visite de clôture vérifie AGNR 04/11, rejouable par scripts/sonde.py — AMET93)
"""AGNR6 (+ jumeau public AGNR54) : un devis à deux factures tapées à l'écran (`factures_hiver_ete` 500 / 1 200,
été différent) est calculé sur les MARCHES, source `facture_hiver_ete`, 5 779 kWh/an (contrat AGNR5), et les
lecteurs publics (`payload_horaire.conso_publique_du_devis`, `_profil_horaire_pour_devis`,
`payload_economie._monthly_consumption`) lisent la MÊME série — sans lead, puis avec un lead à 1 800 MAD.
PATCH par la vraie route, fonctions réelles, transaction annulée, aucun appel réseau."""
SONDE = {"constat": "C-AGNR-VER4-001", "sha": "4cd568403",
         "attendu": "sans lead et avec lead 1 800 : source facture_hiver_ete, 5 779 kWh/an, marches 310/653, "
                    "série publique = série de l'étude",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "crm.Lead", "crm.Client", "stock.Produit",
                     "authentication.Company"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.etude_horaire import profil_conso_du_devis
    from apps.ventes.public import payload_horaire, payload_economie
    a_agnr54 = hasattr(payload_horaire, 'conso_publique_du_devis')
    co = Company.objects.create(nom='Sonde AGNR VER4-001', slug='sonde-agnr-ver4-001')
    u = get_user_model().objects.create_user(username='sonde-agnr-ver4-001', password='x', company=co,
                                             role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client', prenom='VER4', email='sonde-agnr-ver4-001@example.invalid')
    lead = Lead.objects.create(company=co, nom='Lead VER4', telephone='+212600000001', ville='Casablanca',
                               facture_hiver=1800, ete_differente=False)
    api = APIClient()
    api.force_authenticate(u)
    out = {'code_agnr54': a_agnr54}
    ok = True
    for cas, le_lead in (('sans_lead', None), ('lead_1800', lead)):
        d = Devis.objects.create(company=co, reference=f'DEV-SONDE-AGNR4-{cas}', client=cl, lead=le_lead,
                                 statut='brouillon', taux_tva=Decimal('20'), mode_installation='residentiel',
                                 etude_params={'scenario': 'Sans batterie'})
        for nom, q, pu in (('Panneau Canadien Solar 710W', '6', '1166.67'),
                           ('Onduleur réseau Huawei 3kW Monophasé', '1', '8000.00')):
            p = Produit.objects.create(company=co, nom=f'{nom} {cas}', prix_vente=Decimal(pu), quantite_stock=50)
            LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=Decimal(q),
                                      prix_unitaire=Decimal(pu), remise=Decimal('0'))
        r = api.patch(f'/api/django/ventes/devis/{d.pk}/etude-params/',
                      {'factures_hiver_ete': {'hiver_mad': 500, 'ete_mad': 1200, 'ete_differente': True}},
                      format='json', HTTP_HOST='localhost')
        d.refresh_from_db()
        etude, source, _ = profil_conso_du_devis(d)
        e = [round(v) for v in (etude or [])]
        pub = payload_horaire.conso_publique_du_devis(d) if a_agnr54 else None
        pub = [round(v) for v in (pub or [])]
        res = payload_horaire._profil_horaire_pour_devis(d)
        bloc_pub = [round(v) for v in ((res[1] if isinstance(res, (list, tuple)) and len(res) > 1 else None) or [])]
        mensuel = list(payload_economie._monthly_consumption(d) or [])
        bloc = (d.etude_params or {}).get('etude_horaire') or {}
        print(f'{cas}: patch={r.status_code} regles={getattr(d, "regles_calcul", None)} source={source} '
              f'total={sum(e)} etude={e} publique={pub} blocs={bloc_pub} mensuel_public={mensuel} '
              f'bloc_persiste_source={bloc.get("source_consommation")}')
        cas_ok = (r.status_code == 200 and source == 'facture_hiver_ete' and abs(sum(e) - 5779) <= 2
                  and e[:4] == [310] * 4 and e[4:10] == [653] * 6 and pub == e and bloc_pub == e
                  and (not mensuel or mensuel == e))
        out[cas] = {'patch': r.status_code, 'source': source, 'total': sum(e), 'etude': e, 'publique': pub,
                    'blocs': bloc_pub, 'mensuel_public': mensuel, 'ok': cas_ok}
        ok = ok and cas_ok
    out['repro'] = ok
    return out

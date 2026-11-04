# flake8: noqa  (sonde de contre-visite vérifie AANA du 04/11, rejouable par scripts/sonde.py — AMET93)
"""AANA62 : `apps/reporting/services.py::build_leaderboard` construit LA population de devis signés du classement ;
`commercial.py::commercial_dashboard` et `insights.py::sales_leaderboard` n'en passent plus. Un devis signé SANS lead
(crédité à `created_by`) doit compter dans les deux. Vraies routes, responsable. Transaction annulée."""
SONDE = {"constat": "C-AANA-VER4-011", "sha": "d54c88db3",
         "attendu": "commercial : devis signé à lead 1000 HT + devis signé sans lead 2000 HT : ca_ht 3000 et nb 2 sur /commercial/dashboard ET /insights/sales-leaderboard",
         "modeles": ["authentication.Company", "crm.Lead", "crm.Client", "ventes.Devis", "stock.Produit"]}


def sonde(ctx):
    from datetime import date, timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    U = get_user_model()
    co = Company.objects.create(nom='Sonde AANA VER4-011', slug='sonde-aana-ver4-011')
    resp = U.objects.create_user(username='sonde-aana-ver4-011', password='x', company=co, role_legacy='responsable')
    comm = U.objects.create_user(username='sonde-aana-ver4-011-c', password='x', company=co, role_legacy='responsable')
    to = date.today() - timedelta(days=2)
    frm = to - timedelta(days=5)
    lead = Lead.objects.create(company=co, nom='Signe', stage=stages.SIGNED, owner=comm)
    cl = Client.objects.create(company=co, nom='Cli VER4-011')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-AANA-V4-011', prix_vente=Decimal('1000'), quantite_stock=0)
    a = Devis.objects.create(company=co, reference='DEV-SONDE-V4-011-A', client=cl, lead=lead,
                             statut=Devis.Statut.ACCEPTE, date_acceptation=to, created_by=resp)
    LigneDevis.objects.create(devis=a, produit=p, designation='Kit', quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
    b = Devis.objects.create(company=co, reference='DEV-SONDE-V4-011-B', client=cl,
                             statut=Devis.Statut.ACCEPTE, date_acceptation=to, created_by=comm)
    LigneDevis.objects.create(devis=b, produit=p, designation='Kit', quantite=Decimal('2'), prix_unitaire=Decimal('1000'))
    api = APIClient()
    api.force_authenticate(resp)
    q = f'?from={frm.isoformat()}&to={to.isoformat()}'
    out = {}
    for nom, url, cle in (('tableau', f'/api/django/reporting/commercial/dashboard/{q}', 'leaderboard'),
                          ('export', f'/api/django/reporting/insights/sales-leaderboard/{q}', 'rows')):
        r = api.get(url, HTTP_HOST='localhost')
        d = r.data if isinstance(getattr(r, 'data', None), dict) else {}
        ligne = next((x for x in d.get(cle, []) if x.get('commercial') == comm.username), {})
        out[nom] = {'status': r.status_code, 'ca_ht': ligne.get('ca_ht'),
                    'nb_devis_signes': ligne.get('nb_devis_signes', ligne.get('nb_devis'))}
    print(out)
    ok = all(v['status'] == 200 and v['ca_ht'] is not None and abs(float(v['ca_ht']) - 3000.0) < 0.01
             and v['nb_devis_signes'] == 2 for v in out.values())
    return {'repro': not ok, **out}

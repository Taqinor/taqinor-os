"""Sonde AANA, rejouable par scripts/sonde.py : transaction annulée. Jamais contre la prod.
Rejoue C-AANA-021 (audit analyse du 05/10, §6) : un lead SIGNED mais perdu=True était compté gagné selon l'écran.
"""
SONDE = {
    'constat': 'C-AANA-021',
    'sha': '5908d43bb',
    'attendu': "défaut absent : lead SIGNED perdu exclu partout — rapport ventes SIGNED=1, pipeline gagnés=1, tableau commercial SIGNED=1 et taux 50 %, même taux au classement",
}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.crm import stages
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from authentication.models import Company
    U = get_user_model()
    co = Company.objects.create(nom='Sonde AANA-021', slug='sonde-aana-021')
    adm = U.objects.create_user(username='sonde-aana-021-a', password='x', role_legacy='admin', company=co)
    own = U.objects.create_user(username='sonde-aana-021-c', password='x', role_legacy='responsable', company=co)
    Lead.objects.create(company=co, nom='Perdu signé', stage=stages.SIGNED, perdu=True, owner=own)
    Lead.objects.create(company=co, nom='Nouveau', stage=stages.NEW, owner=own)
    g = Lead.objects.create(company=co, nom='Gagné', stage=stages.SIGNED, owner=own)
    cl = Client.objects.create(company=co, nom='Cli R7')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-AANA-021', prix_vente=Decimal('1000'), quantite_stock=0)
    d = Devis.objects.create(company=co, reference='DEV-SONDE-AANA21', client=cl, lead=g, statut=Devis.Statut.ACCEPTE, date_acceptation=date.today())
    LigneDevis.objects.create(devis=d, produit=p, designation='Kit', quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
    api = APIClient()
    api.force_authenticate(adm)
    B = '/api/django/reporting'
    h = {'HTTP_HOST': 'localhost'}
    rs = api.get(B + '/reports/sales/', **h)
    rp = api.get(B + '/pipeline/', **h)
    rc = api.get(B + '/commercial/dashboard/', **h)
    rl = api.get(B + '/insights/sales-leaderboard/', **h)
    f_sales = {f['stage']: f['count'] for f in rs.data['funnel']}.get(stages.SIGNED)
    f_comm = {f['stage']: f['count'] for f in rc.data['funnel']}.get(stages.SIGNED)
    gagnes = rp.data['gagnes']['count']
    taux = rc.data['win_rate_pct']
    t_lead = rl.data['rows'][0]['win_rate_pct']
    ok = f_sales == 1 and gagnes == 1 and f_comm == 1 and rc.data['total_signes'] == 1 and taux == 50.0 and t_lead == taux
    print('ventes SIGNED=%s pipeline gagnés=%s commercial SIGNED=%s taux=%s classement taux=%s' % (f_sales, gagnes, f_comm, taux, t_lead))
    return {'repro': ok, 'ventes_signed': f_sales, 'pipeline_gagnes': gagnes, 'commercial_signed': f_comm, 'taux': taux, 'taux_classement': t_lead}

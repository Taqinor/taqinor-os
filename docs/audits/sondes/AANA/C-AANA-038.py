"""Sonde AANA, rejouable par scripts/sonde.py : transaction annulée. Jamais contre la prod.
Rejoue C-AANA-038 (audit analyse du 05/10, §6) : classement, deux fenêtres de leads, deux taux de victoire.
"""
SONDE = {
    'constat': 'C-AANA-038',
    'sha': '5908d43bb',
    'attendu': "défaut absent : commercial/dashboard et insights/sales-leaderboard donnent le même win_rate_pct (50.0) avec un 2e lead créé le jour `to` à 15 h",
}


def sonde(ctx):
    from datetime import date, datetime, time, timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm import stages
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from authentication.models import Company
    U = get_user_model()
    co = Company.objects.create(nom='Sonde AANA-038', slug='sonde-aana-038')
    resp_u = U.objects.create_user(username='sonde-aana-038-r', password='x', role_legacy='responsable', company=co)
    own = U.objects.create_user(username='sonde-aana-038-c', password='x', role_legacy='responsable', company=co)
    to = date.today() - timedelta(days=2)
    frm = to - timedelta(days=5)
    signe = Lead.objects.create(company=co, nom='Signé', stage=stages.SIGNED, owner=own)
    tardif = Lead.objects.create(company=co, nom='Créé le jour to à 15 h', stage=stages.NEW, owner=own)
    Lead.objects.filter(pk=signe.pk).update(date_creation=timezone.make_aware(datetime.combine(frm + timedelta(days=1), time(10, 0))))
    Lead.objects.filter(pk=tardif.pk).update(date_creation=timezone.make_aware(datetime.combine(to, time(15, 0))))
    cl = Client.objects.create(company=co, nom='Cli R8')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-AANA-038', prix_vente=Decimal('1000'), quantite_stock=0)
    d = Devis.objects.create(company=co, reference='DEV-SONDE-AANA38', client=cl, lead=signe, statut=Devis.Statut.ACCEPTE, date_acceptation=to)
    LigneDevis.objects.create(devis=d, produit=p, designation='Kit', quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
    api = APIClient()
    api.force_authenticate(resp_u)
    q = '?from=%s&to=%s' % (frm.isoformat(), to.isoformat())
    B = '/api/django/reporting'
    t1 = api.get('%s/commercial/dashboard/%s' % (B, q), HTTP_HOST='localhost').data['leaderboard'][0]['win_rate_pct']
    t2 = api.get('%s/insights/sales-leaderboard/%s' % (B, q), HTTP_HOST='localhost').data['rows'][0]['win_rate_pct']
    print('tableau commercial=%s export classement=%s' % (t1, t2))
    return {'repro': t1 == t2 == 50.0, 'tableau': t1, 'export': t2}

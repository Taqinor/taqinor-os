"""Sonde AANA, rejouable par scripts/sonde.py : transaction annulée. Jamais contre la prod.
Rejoue C-AANA-009 (audit analyse du 05/10, §6) : un rapport planifié SANS société rendait les données de toutes les sociétés.
"""
SONDE = {
    'constat': 'C-AANA-009',
    'sha': '5908d43bb',
    'attendu': "défaut absent : rendre_rapport(SavedReport(company=None)) renvoie (None,)*4, aucune ligne rendue, création sans société refusée (400)",
}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.reporting import scheduled_reports
    from apps.reporting.models import SavedReport
    from apps.stock.models import Produit
    from authentication.models import Company
    for s in ('sonde-aana-009a', 'sonde-aana-009b'):
        co = Company.objects.create(nom=s, slug=s)
        Produit.objects.create(company=co, nom='P ' + s, sku=s, prix_vente=Decimal('10'), quantite_stock=1)
    r = SavedReport.objects.create(company=None, name='Orphelin', target_kind=SavedReport.TargetKind.STOCK)
    rendu = scheduled_reports.rendre_rapport(r)
    _e, lignes = scheduled_reports.render_stock(r)
    su = get_user_model().objects.create_superuser(username='sonde-aana-009', password='x', email='sonde-aana-009@example.invalid')
    api = APIClient()
    api.force_authenticate(su)
    avant = SavedReport.objects.count()
    resp = api.post('/api/django/reporting/saved-reports/', {'name': 'Sans société', 'target_kind': 'stock'}, format='json', HTTP_HOST='localhost')
    cree = SavedReport.objects.count() - avant
    ok = rendu == (None, None, None, None) and not lignes and resp.status_code == 400 and cree == 0
    print('rendu=%s lignes=%s POST=%s créés=%s' % (rendu, len(lignes), resp.status_code, cree))
    return {'repro': ok, 'rendu': str(rendu), 'lignes': len(lignes), 'post': resp.status_code, 'crees': cree}

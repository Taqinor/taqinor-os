"""Sonde AANA, rejouable par scripts/sonde.py : transaction annulée. Jamais contre la prod.
Rejoue C-AANA-020 (audit analyse du 05/10, §6) : le CA en attente du tableau de bord ignorait remise_globale.
"""
SONDE = {
    'constat': 'C-AANA-020',
    'sha': '5908d43bb',
    'attendu': "défaut absent : facture 1×1000, remise_globale 50 % → total_ht 500 et dashboard kpis.ca_attente = 500.0 (créance = montant_du)",
}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture
    from authentication.models import Company
    co = Company.objects.create(nom='Sonde AANA-020', slug='sonde-aana-020')
    u = get_user_model().objects.create_user(username='sonde-aana-020', password='x', role_legacy='responsable', company=co)
    cl = Client.objects.create(company=co, nom='Cli R2')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-AANA-020', prix_vente=Decimal('1000'), quantite_stock=0)
    f = Facture.objects.create(company=co, reference='FAC-SONDE-AANA20', client=cl, statut=Facture.Statut.EMISE, remise_globale=Decimal('50'))
    LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
    api = APIClient()
    api.force_authenticate(u)
    r = api.get('/api/django/reporting/dashboard/', HTTP_HOST='localhost')
    ca = r.data['kpis']['ca_attente']
    cre = [c['montant_total'] for c in r.data['creances']]
    ok = f.total_ht == Decimal('500.00') and ca == 500.0 and cre == [float(f.montant_du)] and 1000.0 not in cre
    print('total_ht=%s ca_attente=%s créances=%s montant_du=%s' % (f.total_ht, ca, cre, f.montant_du))
    return {'repro': ok, 'total_ht': str(f.total_ht), 'ca_attente': ca, 'creances': cre}

"""Sonde AANA, rejouable par scripts/sonde.py : transaction annulée. Jamais contre la prod.
Rejoue C-AANA-039 (audit analyse du 05/10, §6) : la commission MARGE_INTERNE ignorait la remise de ligne.
"""
SONDE = {
    'constat': 'C-AANA-039',
    'sha': '5908d43bb',
    'attendu': "défaut absent : PU 1000, achat 600, remise ligne 20 %, plan MARGE_INTERNE 10 % → base 200, commission 20 (pas 400 / 40)",
}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.crm import stages
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, PlanCommission
    from authentication.models import Company
    U = get_user_model()
    co = Company.objects.create(nom='Sonde AANA-039', slug='sonde-aana-039')
    adm = U.objects.create_user(username='sonde-aana-039-a', password='x', role_legacy='admin', company=co)
    com = U.objects.create_user(username='sonde-aana-039-c', password='x', role_legacy='responsable', company=co)
    PlanCommission.objects.create(company=co, owner=com, base=PlanCommission.Base.MARGE_INTERNE, taux_pct=Decimal('10'), actif=True)
    cl = Client.objects.create(company=co, nom='Cli R9')
    lead = Lead.objects.create(company=co, nom='Lead R9', stage=stages.SIGNED, owner=com)
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-AANA-039', prix_vente=Decimal('1000'), prix_achat=Decimal('600'), quantite_stock=0)
    d = Devis.objects.create(company=co, reference='DEV-SONDE-AANA39', client=cl, lead=lead, statut=Devis.Statut.ACCEPTE, date_acceptation=date.today())
    LigneDevis.objects.create(devis=d, produit=p, designation='Onduleur', quantite=Decimal('1'), prix_unitaire=Decimal('1000'), remise=Decimal('20'))
    api = APIClient()
    api.force_authenticate(adm)
    r = api.get('/api/django/reporting/insights/commissions/', HTTP_HOST='localhost')
    row = r.data['rows'][0]
    base, com_ = Decimal(str(row['base'])), Decimal(str(row['commission']))
    print('base=%s commission=%s (attendu 200 / 20)' % (base, com_))
    return {'repro': base == Decimal('200') and com_ == Decimal('20'), 'base': str(base), 'commission': str(com_)}

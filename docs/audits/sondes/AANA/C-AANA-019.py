"""Sonde AANA, rejouable par scripts/sonde.py : transaction annulée. Jamais contre la prod.
Rejoue C-AANA-019 (audit analyse du 05/10, §6) : devis V1 accepté puis révisé V2 accepté comptés deux fois (commissions doublées).
"""
SONDE = {
    'constat': 'C-AANA-019',
    'sha': '5908d43bb',
    'attendu': "défaut absent : commissions count=1 base=10000 commission=500 ; dashboard nb_acceptes=1 ; classement nb_devis_signes=1",
}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.crm import stages
    from apps.crm.models import Client, Lead
    from apps.parametres.models import CompanyProfile
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from authentication.models import Company
    U = get_user_model()
    co = Company.objects.create(nom='Sonde AANA-019', slug='sonde-aana-019')
    adm = U.objects.create_user(username='sonde-aana-019-a', password='x', role_legacy='admin', company=co)
    com = U.objects.create_user(username='sonde-aana-019-c', password='x', role_legacy='responsable', company=co)
    prof = CompanyProfile.get(co)
    prof.commission_mode = 'pct_devis'
    prof.commission_valeur = Decimal('5')
    prof.save(update_fields=['commission_mode', 'commission_valeur'])
    cl = Client.objects.create(company=co, nom='Cli R1')
    lead = Lead.objects.create(company=co, nom='Lead R1', stage=stages.SIGNED, owner=com)
    p = Produit.objects.create(company=co, nom='Panneau', sku='SONDE-AANA-019', prix_vente=Decimal('1000'), quantite_stock=0)
    v1 = Devis.objects.create(company=co, reference='DEV-SONDE-AANA19-V1', client=cl, lead=lead, statut=Devis.Statut.ACCEPTE, date_acceptation=date.today())
    LigneDevis.objects.create(devis=v1, produit=p, designation='P', quantite=Decimal('10'), prix_unitaire=Decimal('1000'))
    v2 = Devis.objects.create(company=co, reference='DEV-SONDE-AANA19-V2', client=cl, lead=lead, statut=Devis.Statut.ACCEPTE, date_acceptation=date.today(), version=2, version_parent=v1)
    LigneDevis.objects.create(devis=v2, produit=p, designation='P', quantite=Decimal('10'), prix_unitaire=Decimal('1000'))
    Devis.objects.filter(pk=v1.pk).update(is_active=False, superseded_by=v2)
    api = APIClient()
    api.force_authenticate(adm)
    B = '/api/django/reporting'
    rc = api.get(B + '/insights/commissions/', HTTP_HOST='localhost')
    rd = api.get(B + '/dashboard/', HTTP_HOST='localhost')
    rl = api.get(B + '/insights/sales-leaderboard/', HTTP_HOST='localhost')
    row = rc.data['rows'][0] if rc.data.get('rows') else {}
    nb = rd.data['conversion']['nb_acceptes']
    sig = rl.data['rows'][0]['nb_devis_signes'] if rl.data.get('rows') else None
    ok = (len(rc.data['rows']) == 1 and row.get('count') == 1 and Decimal(str(row.get('base'))) == Decimal('10000')
          and Decimal(str(row.get('commission'))) == Decimal('500') and nb == 1 and sig == 1)
    print('commissions count=%s base=%s commission=%s ; nb_acceptes=%s ; nb_devis_signes=%s' % (row.get('count'), row.get('base'), row.get('commission'), nb, sig))
    return {'repro': ok, 'count': row.get('count'), 'base': str(row.get('base')), 'commission': str(row.get('commission')), 'nb_acceptes': nb, 'nb_devis_signes': sig}

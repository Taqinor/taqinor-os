# flake8: noqa  (sonde d'audit — contre-visite AANA du 04/11, rejouable par scripts/sonde.py — AMET93)
"""AANA23 : `apps/reporting/insights.py::_marge_devis` (fonction unique commissions MARGE_INTERNE, job-costing,
rentabilité) somme TOUTES les lignes `compte_dans_totaux` ; un devis à DEUX options (sans/avec batterie) accepté
sur l'option « sans » garde dans la marge les lignes de l'option « avec » (onduleur hybride, batterie), alors que
`Devis.total_ht` (domain.argent, option effective D9) ne compte que le panier accepté. Transaction annulée."""
SONDE = {"constat": "C-AANA-VER4-030", "sha": "d54c88db3",
         "attendu": "devis 2 options accepté « sans » : total_ht = 18 000 ; _marge_devis ca_ht = 50 000, marge 16 000 ; commission MARGE_INTERNE 10 % = 1 600 au lieu de 700 (marge du panier accepté 7 000)",
         "modeles": ["authentication.Company", "ventes.Devis", "ventes.LigneDevis", "ventes.PlanCommission", "crm.Lead", "stock.Produit"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, PlanCommission
    from apps.ventes.utils.options import deux_options_declarees, option_effective, option_totaux
    from apps.reporting.insights import _marge_devis
    User = get_user_model()
    co = Company.objects.create(nom='Sonde AANA VER4-030', slug='sonde-aana-ver4-030')
    admin = User.objects.create_user(username='sonde-aana-030-adm', password='x', role_legacy='admin', company=co)
    comm = User.objects.create_user(username='sonde-aana-030-com', password='x', role_legacy='responsable', company=co)
    PlanCommission.objects.create(company=co, owner=comm, base=PlanCommission.Base.MARGE_INTERNE,
                                  taux_pct=Decimal('10'), actif=True)
    cli = Client.objects.create(company=co, nom='Client 030')
    lead = Lead.objects.create(company=co, nom='Lead 030', stage=stages.SIGNED, owner=comm, client=cli)
    d = Devis.objects.create(company=co, reference='DEV-SONDE-AANA-030', client=cli, lead=lead,
                             statut=Devis.Statut.ACCEPTE, date_acceptation=date.today(),
                             option_acceptee='sans_batterie', taux_tva=Decimal('20'), remise_globale=Decimal('0'),
                             created_by=comm)
    lignes = [
        ('Panneau solaire 550W', 'PAN', '', Decimal('10'), Decimal('1000'), Decimal('600')),
        ('Onduleur réseau 8 kW injection', 'OND-R', 'sans', Decimal('1'), Decimal('8000'), Decimal('5000')),
        ('Onduleur hybride 8 kW', 'OND-H', 'avec', Decimal('1'), Decimal('12000'), Decimal('8000')),
        ('Batterie lithium 10 kWh', 'BAT', 'avec', Decimal('1'), Decimal('20000'), Decimal('15000')),
    ]
    for nom, sku, var, q, pu, pa in lignes:
        p = Produit.objects.create(company=co, nom=nom, sku=f'SONDE-AANA030-{sku}', prix_vente=pu, prix_achat=pa,
                                   quantite_stock=0)
        LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=q, prix_unitaire=pu,
                                  remise=Decimal('0'), variante=var)
    d = Devis.objects.get(pk=d.pk)
    m = _marge_devis(d)
    obs = {'deux_options': deux_options_declarees(d), 'option_effective': option_effective(d),
           'total_ht': str(d.total_ht), 'option_totaux_ht': str(option_totaux(d)['ht']),
           'marge_ca_ht': str(m['ca_ht']), 'marge_cout': str(m['cout']), 'marge': str(m['marge'])}
    api = APIClient()
    api.force_authenticate(admin)
    r = api.get('/api/django/reporting/insights/commissions/', HTTP_HOST='localhost')
    obs['commissions_status'] = r.status_code
    if r.status_code == 200:
        rows = r.data.get('rows') or []
        obs['commissions_rows'] = [{k: str(v) for k, v in row.items() if k in ('commercial', 'base', 'commission')}
                                   for row in rows]
    print(obs)
    repro = bool(obs['deux_options']) and Decimal(obs['marge_ca_ht']) != Decimal(obs['total_ht'])
    return {'repro': repro, **obs}

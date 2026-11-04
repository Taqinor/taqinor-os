# flake8: noqa  (sonde d'audit — contre-visite AANA du 04/11, rejouable par scripts/sonde.py — AMET93)
"""`apps/reporting/insights.py::_marge_devis` (marge UNIQUE : commissions MARGE_INTERNE, job-costing, rentabilité)
somme `ligne.total_ht × (1 − remise globale)` et `prix_achat × quantite` des lignes d'UNE villa : ni le ×N
multivilla (`apps/ventes/multivilla.py::nombre_proprietes`, appliqué par `domain/argent.py::_totaux_canoniques` →
`noyau_totaux.totaux_multi_proprietes`) ni le palier de 100 MAD (ARRONDI-100). Le chantier, lui, gèle N × les
lignes (`installations/services.py::_freeze_bom`) et `_bom_material_cost` coûte N villas. Devis UNE option accepté,
`etude_params.nombre_proprietes = 3`. Transaction annulée."""
SONDE = {"constat": "C-AANA-VER4-031", "sha": "d54c88db3",
         "attendu": "N=3 : total_ht ≈ 3 × 18 333 (palier compris) ; _marge_devis ca_ht = 18 333 et cout = 11 000 (une villa) ; _bom_material_cost du chantier = 33 000 ; job-costing cost_estimate = 11 000",
         "modeles": ["authentication.Company", "ventes.Devis", "ventes.LigneDevis", "crm.Lead", "crm.Client",
                     "stock.Produit", "installations.Installation"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.multivilla import nombre_proprietes
    from apps.ventes.domain.argent import totaux, Vue
    from apps.ventes.utils.options import deux_options_declarees
    from apps.reporting.insights import _marge_devis
    User = get_user_model()
    co = Company.objects.create(nom='Sonde AANA VER4-031', slug='sonde-aana-ver4-031')
    admin = User.objects.create_user(username='sonde-aana-031-adm', password='x', role_legacy='admin', company=co)
    cli = Client.objects.create(company=co, nom='Client 031')
    lead = Lead.objects.create(company=co, nom='Lead 031', stage=stages.SIGNED, owner=admin, client=cli)
    d = Devis.objects.create(company=co, reference='DEV-SONDE-AANA-031', client=cli, lead=lead,
                             statut=Devis.Statut.ACCEPTE, date_acceptation=date.today(),
                             taux_tva=Decimal('20'), remise_globale=Decimal('0'), created_by=admin,
                             etude_params={'nombre_proprietes': 3})
    lignes = [
        ('Panneau solaire 550W', 'PAN', Decimal('10'), Decimal('1000'), Decimal('600')),
        ('Onduleur réseau 8 kW injection', 'OND', Decimal('1'), Decimal('8333'), Decimal('5000')),
    ]
    for nom, sku, q, pu, pa in lignes:
        p = Produit.objects.create(company=co, nom=nom, sku=f'SONDE-AANA031-{sku}', prix_vente=pu, prix_achat=pa,
                                   quantite_stock=0)
        LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=q, prix_unitaire=pu,
                                  remise=Decimal('0'), variante='')
    d = Devis.objects.get(pk=d.pk)
    m = _marge_devis(d)
    t_villa = totaux(d, vue=Vue.NET, unitaire=True)
    obs = {'nombre_proprietes': nombre_proprietes(d), 'deux_options': bool(deux_options_declarees(d)),
           'total_ht': str(d.total_ht), 'total_ttc': str(d.total_ttc),
           'ht_une_villa_palier': str(t_villa.ht_net), 'ttc_une_villa_palier': str(t_villa.ttc),
           'arrondi_une_villa': str(t_villa.arrondi),
           'marge_ca_ht': str(m['ca_ht']), 'marge_cout': str(m['cout']), 'marge': str(m['marge'])}
    # chantier
    ch = None
    try:
        from apps.installations.services import create_installation_from_devis, _bom_material_cost, compute_chantier_cout
        ch, created = create_installation_from_devis(d, admin, co)
        obs['chantier_cree'] = bool(ch)
    except Exception as e:  # noqa
        obs['chantier_erreur'] = repr(e)[:300]
    if ch is not None:
        ch.refresh_from_db()
        bom_cout, _det = _bom_material_cost(ch)
        obs['bom_quantites'] = [(l.get('designation'), l.get('quantite')) for l in (ch.bom or [])]
        obs['bom_material_cost'] = str(bom_cout)
        cc = compute_chantier_cout(ch)
        obs['chantier_cout_prevu'] = cc['materiel']['cout_prevu']
        obs['chantier_devis_total_ht'] = cc['devis_total_ht']
        obs['chantier_marge'] = cc['marge']
        api = APIClient()
        api.force_authenticate(admin)
        r = api.get('/api/django/reporting/insights/job-costing/', HTTP_HOST='localhost')
        obs['job_costing_status'] = r.status_code
        if r.status_code == 200:
            obs['job_costing_rows'] = [{k: row.get(k) for k in ('ref', 'invoiced_ht', 'cost_estimate', 'margin')}
                                       for row in (r.data.get('chantiers') or [])]
    print(obs)
    repro = (Decimal(obs['marge_ca_ht']) != Decimal(obs['total_ht'])
             and ('bom_material_cost' not in obs or Decimal(obs['marge_cout']) != Decimal(obs['bom_material_cost'])))
    return {'repro': repro, **obs}

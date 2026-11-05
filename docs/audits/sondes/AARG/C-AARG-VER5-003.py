# flake8: noqa  (sonde de contre-visite de clôture PA4 « Argent », rejouable par scripts/sonde.py — METHODE §C.4)
"""VER5 : lectures d'argent ouvertes à tout rôle. Acteur : rôle canonique Admin RH (périmètre RH) ; témoin de
contrôle : `GET factures/` → 403. Puis GET `factures-lignes/` (`LigneFactureViewSet`, IsAnyRole en lecture),
`insights/cash-flow/` (`cash_flow_forecast`), `dashboard/` (`dashboard_quote_to_cash`),
`clients/<id>/credit-warning/` (`client_credit_warning`) : statuts + montants servis. Directeur en référence.
Vraies routes, société neuve, une facture émise de 1 200 TTC ; transaction annulée."""
SONDE = {"constat": "C-AARG-VER5-003", "sha": "2781a2049",
         "attendu": "repro si Admin RH reçoit 403 sur factures/ mais 200 avec montants (1200 / 1000) sur au moins une des 4 routes",
         "modeles": ["Company", "Role", "CustomUser", "Client", "Produit", "Facture", "LigneFacture"]}


def sonde(ctx):
    import json
    from datetime import date, timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    B = '/api/django/ventes'
    co = Company.objects.create(nom='Sonde VER5 003', slug='sonde-ver5-003')
    r_dir = Role.objects.create(company=co, nom='Directeur', permissions=list(reg.DIRECTEUR_PERMISSIONS), est_systeme=True)
    r_rh = Role.objects.create(company=co, nom=reg.ROLE_ADMIN_RH, permissions=list(reg.ADMIN_RH_PERMISSIONS),
                               est_systeme=True, perimetre=reg.PERIMETRE_RH)
    acteurs = {'admin_rh': User.objects.create_user(username='v503-rh', password='x', company=co, role=r_rh),
               'directeur': User.objects.create_user(username='v503-dir', password='x', company=co, role=r_dir)}
    cl = Client.objects.create(company=co, nom='Argent', prenom='V503', email='v503@example.invalid',
                               **({'plafond_credit': Decimal('500')} if hasattr(Client, 'plafond_credit') else {}))
    p = Produit.objects.create(company=co, nom='Kit V503', sku='SONDE-V503', prix_vente=Decimal('1000'), quantite_stock=5)
    kw = {}
    if any(fl.name == 'date_echeance' for fl in Facture._meta.get_fields()):
        kw['date_echeance'] = date.today() + timedelta(days=10)
    f = Facture.objects.create(company=co, reference='FAC-V503-1', client=cl, statut=Facture.Statut.EMISE,
                               taux_tva=Decimal('20.00'), date_emission=date.today(),
                               created_by=acteurs['directeur'], **kw)
    LigneFacture.objects.create(facture=f, produit=p, designation='Centrale V503', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
    routes = {'factures': f'{B}/factures/',
              'factures_lignes': f'{B}/factures-lignes/',
              'cash_flow': f'{B}/insights/cash-flow/',
              'dashboard': f'{B}/dashboard/',
              'credit_warning': f'{B}/clients/{cl.pk}/credit-warning/?montant_ttc=1000'}
    out = {}
    for nom, u in acteurs.items():
        api = APIClient()
        api.force_authenticate(u)
        g = {}
        for k, url in routes.items():
            r = api.get(url, **H)
            try:
                corps = json.dumps(r.json(), default=str, ensure_ascii=False)
            except Exception:  # noqa
                corps = ''
            g[k] = {'http': r.status_code, 'montant_1200': '1200' in corps, 'montant_1000': '1000' in corps,
                    'extrait': corps[:220]}
        out[nom] = g
    print(json.dumps(out, ensure_ascii=False)[:6000])
    rh = out['admin_rh']
    ouvertes = [k for k in ('factures_lignes', 'cash_flow', 'dashboard', 'credit_warning')
                if rh[k]['http'] == 200 and (rh[k]['montant_1200'] or rh[k]['montant_1000'])]
    return {'repro': rh['factures']['http'] == 403 and bool(ouvertes), 'ouvertes_a_admin_rh': ouvertes,
            'statuts_rh': {k: v['http'] for k, v in rh.items()},
            'statuts_dir': {k: v['http'] for k, v in out['directeur'].items()}, 'detail': out}

# flake8: noqa  (seconde lentille PA4 « Argent » sur K07, rejouable par scripts/sonde.py — AMET93)
"""K07, reproduction INDÉPENDANTE sur UNE porte (rapprochement d'un virement portail) avec d'AUTRES rôles que la
première lentille : le rôle canonique TECHNICIEN et un rôle sur mesure qui ne porte QUE `rh_voir` + `rh_gerer`.
Intention de paiement initiée par le vrai service portail (`portail.services.initier_paiement_facture`), puis
`POST portail/paiements-facture-portail/<id>/rapprocher/` (garde `IsResponsableOrAdmin` ; la vue relève de
`apps.portail`, que `authentication.permissions.module_de_la_vue` ne résout pas → contrôle de module ASEC11 sauté).
Témoin pour chacun : `factures/<id>/enregistrer-paiement/` (PeutEncaisser) → 403. Transaction annulée."""
SONDE = {"constat": "C-AARG-107", "sha": "56d5b623a",
         "attendu": "Technicien / rôle « RH seul » (sans `encaisser`) : enregistrer-paiement 403 ET rapprocher 403, "
                    "aucun Paiement (D-ASEC-VER-1 = tout l'argent exige `encaisser`)",
         "modeles": ["roles.Role", "ventes.Facture", "ventes.LigneFacture", "ventes.Paiement",
                     "portail.PaiementFacturePortail"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture, Paiement
    from apps.portail.models import PaiementFacturePortail
    from apps.portail.services import initier_paiement_facture
    H = {'HTTP_HOST': 'localhost'}
    User = get_user_model()
    co = Company.objects.create(nom='Sonde AARG 107', slug='sonde-aarg-107')
    roles = {
        'technicien': Role.objects.create(company=co, nom='Technicien', permissions=list(reg.TECHNICIEN_PERMISSIONS),
                                          est_systeme=True),
        'rh_seul': Role.objects.create(company=co, nom='Gestion RH (sur mesure)',
                                       permissions=['rh_voir', 'rh_gerer']),
    }
    cl = Client.objects.create(company=co, nom='Portail', prenom='K07bis', email='sonde-aarg-107@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit K07', sku='SONDE-AARG-107', prix_vente=Decimal('1000'),
                               quantite_stock=10)
    out = {}
    for nom, role in roles.items():
        assert 'encaisser' not in (role.permissions or [])
        u = User.objects.create_user(username=f'sonde-aarg107-{nom}', password='x', company=co, role=role)
        api = APIClient()
        api.force_authenticate(u)
        f = Facture.objects.create(company=co, reference=f'FAC-SONDE-AARG-107-{nom}', client=cl,
                                   statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'),
                                   date_emission=date.today())
        LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'),
                                    prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
        rt = api.post(f'/api/django/ventes/factures/{f.id}/enregistrer-paiement/',
                      {'montant': '100', 'date_paiement': date.today().isoformat(), 'mode': 'virement'},
                      format='json', **H)
        pp = PaiementFacturePortail.objects.create(company=co, facture_id=f.id, montant=Decimal('1200'),
                                                   methode=PaiementFacturePortail.Methode.VIREMENT)
        initier_paiement_facture(pp)
        rr = api.post(f'/api/django/portail/paiements-facture-portail/{pp.id}/rapprocher/',
                      {'reference': 'VIR-K07BIS'}, format='json', **H)
        pp.refresh_from_db()
        f = Facture.objects.get(pk=f.pk)
        out[nom] = {'temoin_enregistrer_paiement': rt.status_code, 'http_rapprocher': rr.status_code,
                    'portail_statut': pp.statut,
                    'paiements': [str(x.montant) for x in Paiement.objects.filter(facture=f)],
                    'facture_statut': f.statut, 'montant_du': str(f.montant_du)}
    print(out)
    ouverts = [n for n, g in out.items() if g['temoin_enregistrer_paiement'] == 403
               and g['http_rapprocher'] == 200 and g['paiements']]
    return {'repro': bool(ouverts), 'roles_qui_passent': ouverts, 'detail': out}

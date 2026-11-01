# flake8: noqa  (sonde de contre-visite vérifie ASEC, rejouable par scripts/sonde.py — AMET93)
"""ASEC29 : `enregistrer-paiement` et `creer-avoir` exigent `encaisser` (D-ASEC-1), mais trois portes jumelles restent
gardées par `IsResponsableOrAdmin` (droit d'écriture ventes) : `PaiementViewSet.paiement_avec_retenue`,
`facture_rectificatifs.retour_client` (avoir) et `releve_import.releve_commit`. Un Commercial à qui l'on a retiré
`encaisser` reçoit 403 sur la porte gardée et encaisse / crée un avoir par la jumelle. Vraies routes, transaction annulée."""
SONDE = {"constat": "C-ASEC-VER-003", "sha": "ba577e26a",
         "attendu": "rôle sans encaisser : enregistrer-paiement 403 mais paiement-avec-retenue / retour-client acceptés, paiement ou avoir créé"}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
    from apps.stock.models import Produit
    from apps.ventes.models import Avoir, Facture, LigneFacture, Paiement, RetenueSubie
    co = Company.objects.create(nom='Sonde ASEC VER-003', slug='sonde-asec-ver-003')
    sans = Role.objects.create(company=co, nom='Commercial sans encaisser (sonde)',
                               permissions=[c for c in COMMERCIAL_PERMISSIONS if c != 'encaisser'])
    cl = Client.objects.create(company=co, nom='Argent', prenom='VER003', email='sonde-asec-ver-003@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit VER003', sku='SONDE-ASEC-003', prix_vente=Decimal('1000'),
                               quantite_stock=10)
    u = get_user_model().objects.create_user(username='sonde-asec-ver-003', password='x', company=co, role=sans,
                                             role_legacy='normal')
    api = APIClient()
    api.force_authenticate(u)
    n = [0]

    def facture():
        n[0] += 1
        f = Facture.objects.create(company=co, reference=f'FAC-SONDE-003-{n[0]}', client=cl, statut=Facture.Statut.EMISE,
                                   taux_tva=Decimal('20.00'), created_by=u)
        LigneFacture.objects.create(facture=f, produit=p, designation='Centrale', quantite=Decimal('1'),
                                    prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
        return f
    f0 = facture()
    r0 = api.post(f'/api/django/ventes/factures/{f0.id}/enregistrer-paiement/',
                  {'montant': '100', 'date_paiement': date.today().isoformat(), 'mode': 'virement'},
                  format='json', HTTP_HOST='localhost')
    f1 = facture()
    r1 = api.post(f'/api/django/ventes/paiements/factures/{f1.id}/paiement-avec-retenue/',
                  {'montant': '1050', 'date_paiement': date.today().isoformat(), 'mode': 'virement',
                   'type_retenue': RetenueSubie.TypeRetenue.RAS_TVA, 'taux': '75'}, format='json', HTTP_HOST='localhost')
    f2 = facture()
    r2 = api.post(f'/api/django/ventes/factures/{f2.id}/retour-client/',
                  {'motif': 'sonde', 'restocker': False, 'lignes': [{'produit': p.id, 'quantite': '1'}]},
                  format='json', HTTP_HOST='localhost')
    f1.refresh_from_db()
    pay1 = Paiement.objects.filter(facture=f1).count()
    av2 = Avoir.objects.filter(facture=f2).count()
    print(f'enregistrer_paiement={r0.status_code} paiement_avec_retenue={r1.status_code} paiements_f1={pay1} '
          f'statut_f1={f1.statut} retour_client={r2.status_code} avoirs_f2={av2} (attendu 403 partout, rien créé)')
    return {'repro': r0.status_code == 403 and (pay1 > 0 or av2 > 0), 'enregistrer_paiement': r0.status_code,
            'paiement_avec_retenue': r1.status_code, 'paiements_f1': pay1, 'retour_client': r2.status_code,
            'avoirs_f2': av2}

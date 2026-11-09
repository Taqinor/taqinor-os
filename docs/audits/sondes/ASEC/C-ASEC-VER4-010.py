# flake8: noqa  (sonde de contre-visite vérifie ASEC 04/11, rejouable par scripts/sonde.py — AMET93)
"""ASEC29 / AARG9 (D-ASEC-VER-1 = tout, D-AARG-3 = exiger_encaisser) : `factures/<id>/emettre/` et `/facturer`
exigent `encaisser`, mais deux portes jumelles ÉMETTENT une facture (créance au numéro légal) avec la seule garde
`IsResponsableOrAdmin` : `devis/<id>/generer-facture/` (`utils/echeancier.creer_facture_tranche` → `_emettre`) et
`factures/consolider/` (`domain/encaissements.consolider_factures` → `emettre_facture`). Un Commercial à qui l'on a
retiré `encaisser` reçoit 403 sur `emettre` et émet par les jumelles. Vraies routes, transaction annulée."""
SONDE = {"constat": "C-ASEC-VER4-010", "sha": "8fb8ba32b",
         "attendu": "rôle sans encaisser : emettre 403 (témoin) ; generer-facture 201 et/ou consolider 201 avec facture au statut émise ; attendu sain : 403 sans facture émise",
         "modeles": ["authentication.Company", "ventes.Devis", "ventes.LigneDevis", "Facture", "LigneFacture",
                     "stock.MouvementStock"]}


def sonde(ctx):
    import inspect
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, Facture, LigneDevis, LigneFacture
    from apps.ventes.views import facture_cycle
    # Garde de version : le conteneur doit porter le correctif AARG9 (emettre gardé par encaisser).
    code_aarg9 = 'MOTIF_SANS_ENCAISSER' in inspect.getsource(facture_cycle)
    co = Company.objects.create(nom='Sonde ASEC VER4-010', slug='sonde-asec-ver4-010')
    sans = Role.objects.create(company=co, nom='Commercial sans encaisser (sonde 010)',
                               permissions=[c for c in COMMERCIAL_PERMISSIONS if c != 'encaisser'])
    cl = Client.objects.create(company=co, nom='Argent', prenom='VER4-010', email='sonde-asec-ver4-010@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit VER4-010', sku='SONDE-ASEC-V4-010', prix_vente=Decimal('1000'),
                               quantite_stock=1000)
    u = get_user_model().objects.create_user(username='sonde-asec-ver4-010', password='x', company=co, role=sans,
                                             role_legacy='normal')
    api = APIClient()
    api.force_authenticate(u)
    n = [0]

    def devis():
        n[0] += 1
        d = Devis.objects.create(company=co, reference=f'DEV-SONDE-V4-010-{n[0]}', client=cl,
                                 statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'), created_by=u)
        LigneDevis.objects.create(devis=d, produit=p, designation='Centrale', quantite=Decimal('1'),
                                  prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
        return d
    # Témoin : un brouillon de facture → emettre doit répondre 403.
    fb = Facture.objects.create(company=co, reference='FAC-SONDE-V4-010-B', client=cl, statut=Facture.Statut.BROUILLON,
                                taux_tva=Decimal('20.00'), created_by=u)
    LigneFacture.objects.create(facture=fb, produit=p, designation='Centrale', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
    r0 = api.post(f'/api/django/ventes/factures/{fb.id}/emettre/', format='json', HTTP_HOST='localhost')
    fb.refresh_from_db()
    # Jumelle 1 : generer-facture.
    d1 = devis()
    r1 = api.post(f'/api/django/ventes/devis/{d1.id}/generer-facture/', {}, format='json', HTTP_HOST='localhost')
    f1 = list(Facture.objects.filter(devis=d1).values_list('reference', 'statut'))
    # Jumelle 2 : consolider (deux devis acceptés du même client).
    d2, d3 = devis(), devis()
    r2 = api.post('/api/django/ventes/factures/consolider/', {'devis_ids': [d2.id, d3.id]}, format='json',
                  HTTP_HOST='localhost')
    f2 = []
    if r2.status_code == 201:
        f2 = list(Facture.objects.filter(pk=r2.data.get('id')).values_list('reference', 'statut'))
    emise = Facture.Statut.EMISE
    jumelle_emet = any(s == emise for _, s in f1) or any(s == emise for _, s in f2)
    obs = {'code_aarg9_present': code_aarg9,
           'emettre_temoin': r0.status_code, 'temoin_statut': fb.statut,
           'generer_facture': r1.status_code,
           'generer_facture_detail': (r1.data if r1.status_code >= 400 else None),
           'factures_d1': f1,
           'consolider': r2.status_code,
           'consolider_detail': (r2.data if r2.status_code >= 400 else None),
           'facture_consolidee': f2}
    print(f'obs={obs} (attendu sain : 403 partout, aucune facture émise)')
    return {'repro': bool(code_aarg9 and r0.status_code == 403 and jumelle_emet), **obs}

# flake8: noqa  (sonde du parcours PA4 « Argent », rejouable par scripts/sonde.py — AMET93)
"""K09 : portes d'argent résolues par SOCIÉTÉ seulement, jamais par la portée du rôle (SCOPE_SELF du Commercial) :
  * `apps/ventes/paiement_import.py::_match_facture` (Facture filtrée par `company` seule) puis `::commit` ;
  * `apps/ventes/views/bon_commande.py::BonCommandeViewSet` (aucun `scope_queryset`) → `creer-facture` ;
  * `apps/ventes/domain/encaissements.py::consolider_factures` (devis filtrés par `company` seule) ;
  * `apps/ventes/recouvrement.py::PromessePaiementViewSet.perform_create` (`_scope` = société seule).
Témoins : la fiche facture de Y et `enregistrer-paiement` sur elle (FactureViewSet scopé `created_by`) → 404 pour X.
Deux Commerciaux canoniques X et Y (SCOPE_SELF + encaisser), aucun lien hiérarchique. Vraies routes, transaction annulée."""
SONDE = {"constat": "C-AARG-009", "sha": "56d5b623a",
         "attendu": "X : GET facture de Y 404 et enregistrer-paiement 404 (témoins) mais import de relevé à la "
                    "référence de Y → Paiement sur la facture de Y ; creer-facture sur le BC de Y 201 ; consolider "
                    "deux devis de Y 201 ; promesse sur la facture de Y 201",
         "modeles": ["Company", "Role", "CustomUser", "Client", "Produit", "Devis", "LigneDevis", "BonCommande",
                     "Facture", "LigneFacture", "Paiement", "PromessePaiement"]}


def sonde(ctx):
    from datetime import date, timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.stock.models import Produit
    from apps.ventes.models import (BonCommande, Devis, Facture, LigneDevis, LigneFacture, Paiement,
                                    PromessePaiement)
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AARG 009', slug='sonde-aarg-009')
    r_com = Role.objects.create(company=co, nom='Commercial', permissions=list(reg.COMMERCIAL_PERMISSIONS),
                                est_systeme=True)
    assert reg.SCOPE_SELF in r_com.permissions and 'encaisser' in r_com.permissions
    x = User.objects.create_user(username='sonde-aarg009-x', password='x', company=co, role=r_com)
    y = User.objects.create_user(username='sonde-aarg009-y', password='x', company=co, role=r_com)
    cl = Client.objects.create(company=co, nom='Client de Y', prenom='K09', email='sonde-aarg-009@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit K09', sku='SONDE-AARG-009', prix_vente=Decimal('1000'),
                               quantite_stock=50)
    fy = Facture.objects.create(company=co, reference='FAC-SONDE-AARG9-Y', client=cl, statut=Facture.Statut.EMISE,
                                taux_tva=Decimal('20.00'), created_by=y)
    LigneFacture.objects.create(facture=fy, produit=p, designation='Centrale', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))

    def devis_y(ref):
        d = Devis.objects.create(company=co, client=cl, reference=ref, statut=Devis.Statut.ENVOYE,
                                 taux_tva=Decimal('20.00'), created_by=y)
        LigneDevis.objects.create(devis=d, produit=p, designation='Centrale', quantite=Decimal('1'),
                                  prix_unitaire=Decimal('1000'))
        Devis.objects.filter(pk=d.pk).update(statut=Devis.Statut.ACCEPTE)
        d.refresh_from_db()
        return d
    d_bc = devis_y('DEV-SONDE-AARG9-BC')
    bc = BonCommande.objects.create(company=co, reference='BC-SONDE-AARG9-Y', devis=d_bc, client=cl,
                                    statut=BonCommande.Statut.CONFIRME)
    d1, d2 = devis_y('DEV-SONDE-AARG9-C1'), devis_y('DEV-SONDE-AARG9-C2')
    api = APIClient()
    api.force_authenticate(x)
    out = {}
    # témoins : la portée SCOPE_SELF cache la facture de Y à X
    out['temoin_get_facture_y'] = api.get(f'/api/django/ventes/factures/{fy.id}/', **H).status_code
    r = api.post(f'/api/django/ventes/factures/{fy.id}/enregistrer-paiement/',
                 {'montant': '100', 'date_paiement': date.today().isoformat(), 'mode': 'virement'}, format='json', **H)
    out['temoin_enregistrer_paiement_y'] = r.status_code
    # (1) import de relevé à la référence de la facture de Y
    csv = ('date,reference,montant,mode\n'
           f'{(date.today() - timedelta(days=1)).isoformat()},{fy.reference},300.00,virement\n').encode()
    r = api.post('/api/django/ventes/paiements/import-releve/dry-run/',
                 {'file': SimpleUploadedFile('releve.csv', csv, 'text/csv')}, format='multipart', **H)
    token = (r.data or {}).get('token') if r.status_code == 200 else None
    statuts = [l.get('statut') for l in ((r.data or {}).get('lignes') or [])] if r.status_code == 200 else None
    rc = api.post('/api/django/ventes/paiements/import-releve/commit/', {'token': token}, format='json', **H) \
        if token else None
    out['releve'] = [r.status_code, statuts, rc.status_code if rc is not None else None,
                     [str(x.montant) for x in Paiement.objects.filter(facture=fy)]]
    # (2) BC de Y : lecture puis facturation
    out['bc_get'] = api.get(f'/api/django/ventes/bons-commande/{bc.id}/', **H).status_code
    r = api.post(f'/api/django/ventes/bons-commande/{bc.id}/creer-facture/', {}, format='json', **H)
    out['bc_creer_facture'] = [r.status_code, str((getattr(r, 'data', None) or {}).get('detail', ''))[:80]
                               if r.status_code >= 400 else None, Facture.objects.filter(bon_commande=bc).count()]
    # (3) consolider deux devis acceptés de Y
    r = api.post('/api/django/ventes/factures/consolider/', {'devis_ids': [d1.id, d2.id]}, format='json', **H)
    out['consolider'] = [r.status_code, str(getattr(r, 'data', ''))[:120] if r.status_code >= 400 else None,
                         Facture.objects.filter(sources__devis__in=[d1, d2]).distinct().count()
                         if hasattr(Facture, 'sources') else None]
    # (4) promesse de paiement sur la facture de Y (suspend sa relance)
    r = api.post('/api/django/ventes/promesses-paiement/',
                 {'facture': fy.id, 'montant_promis': '500.00',
                  'date_promise': (date.today() + timedelta(days=10)).isoformat()}, format='json', **H)
    fy.refresh_from_db()
    out['promesse'] = [r.status_code, PromessePaiement.objects.filter(facture=fy).count(),
                       str(fy.exclu_relances_jusquau)]
    print(out)
    temoins = out['temoin_get_facture_y'] == 404 and out['temoin_enregistrer_paiement_y'] == 404
    ouvertes = [k for k, ok in (
        ('releve', out['releve'][2] in (200, 201) and bool(out['releve'][3])),
        ('bc_creer_facture', out['bc_creer_facture'][0] == 201),
        ('consolider', out['consolider'][0] == 201),
        ('promesse', out['promesse'][0] == 201)) if ok]
    return {'repro': temoins and bool(ouvertes), 'portes_ouvertes': ouvertes, 'detail': out}

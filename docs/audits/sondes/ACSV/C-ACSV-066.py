# flake8: noqa  (sonde d'audit de parcours PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K66 — statut et rebut d'un équipement inscriptibles par PATCH /sav/equipements/<id>/ (geste « Corriger »),
contournant `retirer_piece` (garde EquipementDejaRemplaceError) et `mettre-au-rebut` (motif obligatoire).
Acteur : Technicien responsable (TECHNICIEN_RESP_PERMISSIONS : equipement_gerer + sav_gerer), auteur des tickets.
SN-1 (stock produit 0) : T1 retrait « stock occasion » -> stock 1, Remplacé ; PATCH statut en_service ;
T2 retrait « stock occasion » -> stock 2 ? Puis PATCH en_service + T3/T4 « retour fournisseur » -> 2 RMA ?
Témoin : sans le PATCH, un 2e retrait est refusé 409. Puis PATCH {mis_au_rebut: true} sans motif."""
SONDE = {"constat": "C-ACSV-066", "sha": "f57951e87",
         "attendu": "repro si PATCH statut 200 et stock 2 (une seule pièce récupérée) ou 2 WarrantyClaim pour SN-1, "
                    "ou PATCH mis_au_rebut sans motif 200 ; témoin : 2e retrait sans PATCH = 409",
         "modeles": ["sav.Equipement", "sav.PieceRetiree", "sav.WarrantyClaim", "stock.MouvementStock"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.roles.models import Role
    from apps.roles.permissions_registre import TECHNICIEN_RESP_PERMISSIONS
    from apps.sav.models import Equipement, Ticket, WarrantyClaim
    from apps.stock.models import Produit
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ACSV 066', slug='sonde-acsv-066')
    r = Role.objects.create(company=co, nom='Technicien responsable', permissions=list(TECHNICIEN_RESP_PERMISSIONS),
                            est_systeme=True)
    u = get_user_model().objects.create_user(username='sonde-acsv-066', password='x', company=co, role=r)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='K66', email='acsv066@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-ACSV-066', client=cl)
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ACSV-066', prix_vente=Decimal('5000'),
                               quantite_stock=0)
    eq = Equipement.objects.create(company=co, produit=p, installation=inst, numero_serie='SN-ACSV-066',
                                   created_by=u)

    def ticket(n):
        return Ticket.objects.create(company=co, reference=f'SAV-ACSV-066-{n}', client=cl, installation=inst,
                                     equipement=eq, type=Ticket.Type.CORRECTIF, created_by=u)

    def retrait(t, dest):
        rr = api.post(f'/api/django/sav/tickets/{t.pk}/pieces-retirees/',
                      {'produit': p.pk, 'numero_serie': 'SN-ACSV-066', 'destination': dest, 'quantite': 1},
                      format='json', **H)
        p.refresh_from_db()
        eq.refresh_from_db()
        return rr.status_code, p.quantite_stock, eq.statut

    def patch(corps):
        rp = api.patch(f'/api/django/sav/equipements/{eq.pk}/', corps, format='json', **H)
        eq.refresh_from_db()
        return rp.status_code, (str(rp.data)[:160] if rp.status_code >= 400 else None)

    obs = {}
    obs['T1_occasion'] = retrait(ticket(1), 'stock_occasion')
    obs['temoin_T1bis_sans_patch'] = retrait(ticket('1b'), 'stock_occasion')
    obs['patch_statut_1'] = patch({'statut': 'en_service'})
    obs['T2_occasion'] = retrait(ticket(2), 'stock_occasion')
    obs['patch_statut_2'] = patch({'statut': 'en_service'})
    obs['T3_rma'] = retrait(ticket(3), 'retour_fournisseur')
    obs['patch_statut_3'] = patch({'statut': 'en_service'})
    obs['T4_rma'] = retrait(ticket(4), 'retour_fournisseur')
    obs['warranty_claims_sn1'] = WarrantyClaim.objects.filter(equipement=eq).count()
    obs['patch_rebut'] = patch({'mis_au_rebut': True})
    obs['rebut'] = {'mis_au_rebut': eq.mis_au_rebut, 'date_rebut': str(eq.date_rebut), 'motif': eq.motif_rebut}
    rm = api.post(f'/api/django/sav/equipements/{eq.pk}/mettre-au-rebut/', {}, format='json', **H)
    obs['temoin_action_rebut_sans_motif'] = rm.status_code
    print(obs)
    temoin = obs['temoin_T1bis_sans_patch'][0] == 409
    repro_stock = obs['patch_statut_1'][0] == 200 and obs['T2_occasion'][0] == 201 and obs['T2_occasion'][1] == 2
    repro_rma = obs['warranty_claims_sn1'] >= 2
    repro_rebut = obs['patch_rebut'][0] == 200 and eq.mis_au_rebut and not eq.motif_rebut
    obs.update({'temoin_ok': temoin, 'repro_stock': repro_stock, 'repro_rma': repro_rma, 'repro_rebut': repro_rebut,
                'repro': bool(temoin and (repro_stock or repro_rma or repro_rebut))})
    return obs

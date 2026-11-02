# flake8: noqa  (seconde lentille PA4 « Argent » sur K22, rejouable par scripts/sonde.py — AMET93)
"""K22, reproduction INDÉPENDANTE par le champ JUMEAU `bon_commande` et la porte BC : rôle canonique Directeur,
devis accepté à ligne produit → `devis/<id>/convertir-bc/` → BC confirmé → `bons-commande/<id>/creer-facture/` →
`factures/<id>/emettre/`. Puis (1) `PATCH factures/<id>/ {"bon_commande": null}` et nouvel essai `creer-facture`
(la garde « Une facture existe déjà pour ce BC » lit `Facture.bon_commande`) ; (2) `PATCH {"devis": null}` et
nouvel essai (la garde ATOT2 `exiger_devis_facturable` lit les factures par `devis_id`). Mesure : deux factures
ÉMISES pour la même vente ? `refuser_portes_fermees` ne refuse que si la valeur posée est non nulle. Transaction
annulée."""
SONDE = {"constat": "C-AARG-022-L2", "sha": "56d5b623a",
         "attendu": "PATCH {bon_commande:null} / {devis:null} sur une facture ÉMISE → 409 (rattachement figé), "
                    "jamais une 2e facture émise pour le même BC",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "ventes.BonCommande", "ventes.Facture"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, BonCommande, Facture
    H = {'HTTP_HOST': 'localhost'}
    B = '/api/django/ventes'
    co = Company.objects.create(nom='Sonde AARG 122', slug='sonde-aarg-122')
    r_dir = Role.objects.create(company=co, nom='Directeur', permissions=list(reg.DIRECTEUR_PERMISSIONS),
                                est_systeme=True)
    u = get_user_model().objects.create_user(username='sonde-aarg122-dir', password='x', company=co, role=r_dir)
    p = Produit.objects.create(company=co, nom='Kit K22', sku='SONDE-AARG-122', prix_vente=Decimal('1000'),
                               prix_achat=Decimal('0'), quantite_stock=10)
    cl = Client.objects.create(company=co, nom='K22bis', prenom='Client', email='sonde-aarg-122@example.invalid')
    d = Devis.objects.create(company=co, reference=f"DEV-{timezone.now():%Y%m}-9122", client=cl,
                             statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'), created_by=u)
    LigneDevis.objects.create(devis=d, produit=p, designation='Kit', quantite=Decimal('1'),
                              prix_unitaire=Decimal('1000'))
    api = APIClient()
    api.force_authenticate(u)
    et = {}
    r = api.post(f'{B}/devis/{d.id}/convertir-bc/', format='json', **H)
    et['convertir_bc'] = (r.status_code, None if r.status_code < 300 else r.data)
    bc = BonCommande.objects.filter(devis=d).first()
    if bc is None:
        return {'repro': False, 'blocage': 'pas de BC', 'etapes': et}
    BonCommande.objects.filter(pk=bc.pk).update(statut=BonCommande.Statut.CONFIRME)

    def facturer_et_emettre(tag):
        r = api.post(f'{B}/bons-commande/{bc.id}/creer-facture/', format='json', **H)
        et[f'creer_facture_{tag}'] = (r.status_code, None if r.status_code < 300 else r.data)
        if r.status_code >= 300:
            return None
        fid = r.data.get('id')
        r2 = api.post(f'{B}/factures/{fid}/emettre/', **H)
        et[f'emettre_{tag}'] = (r2.status_code, None if r2.status_code < 300 else r2.data)
        return fid

    f1 = facturer_et_emettre('1')
    f1o = Facture.objects.get(pk=f1)
    et['f1'] = (f1o.reference, f1o.statut, str(f1o.total_ttc), f1o.devis_id == d.id, f1o.bon_commande_id == bc.id)
    r = api.patch(f'{B}/factures/{f1}/', {'bon_commande': None}, format='json', **H)
    et['patch_bc_null'] = (r.status_code, None if r.status_code < 300 else r.data)
    f2 = facturer_et_emettre('2_apres_bc_null')
    if f2 is None:
        r = api.patch(f'{B}/factures/{f1}/', {'devis': None}, format='json', **H)
        et['patch_devis_null'] = (r.status_code, None if r.status_code < 300 else r.data)
        f2 = facturer_et_emettre('3_apres_devis_null')
    toutes = list(Facture.objects.filter(company=co).order_by('pk')
                  .values_list('reference', 'statut', 'montant_ttc', 'devis_id', 'bon_commande_id'))
    emises = [x for x in toutes if x[1] in ('emise', 'payee', 'en_retard', 'partiellement_payee')]
    obs = {'etapes': et, 'factures': [(a, b, str(m), dv, bcid) for a, b, m, dv, bcid in toutes],
           'nb_emises': len(emises)}
    print(obs)
    obs['repro'] = len(emises) >= 2
    return obs

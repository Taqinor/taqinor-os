# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K61 — retour chantier : le plafond « retournable » est contrôlé ligne par ligne. Chantier sorti de 5
(F11 validée, stock 0). (R) un retour brouillon portant DEUX lignes du même produit, 4 et 4, puis `valider` :
passe-t-il (ENTRÉE 4 + 4 = 8 pour 5 sortis) ? (T) témoin : une seule ligne de 8 → 409.
Vraies routes `installations/retours-materiel/` et `retour-materiel-lignes/`, rôle responsable."""
SONDE = {"constat": "C-AAPV-081", "sha": "6ffa876688",
         "attendu": "repro si R : valider 200, Σ ENTRÉE RETOUR 8, stock 8 pour 5 sortis ; T : 409, stock 0",
         "modeles": ["stock.Produit", "stock.MouvementStock", "installations.RetourMateriel",
                     "installations.RetourMaterielLigne"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db.models import Sum
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import (Installation, Intervention, MaterielConsommation, ConsommationLigne)
    from apps.stock.models import Produit, MouvementStock
    H = {'HTTP_HOST': 'localhost'}
    B = '/api/django/installations'
    co = Company.objects.create(nom='Sonde AAPV 081', slug='sonde-aapv-081')
    u = get_user_model().objects.create_user(username='sonde_aapv_081', password='x', role_legacy='responsable',
                                             company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client AAPV81', prenom='T', email='aapv81@example.invalid')

    def cas(tag, quantites):
        inst = Installation.objects.create(company=co, reference=f'CHT-AAPV81-{tag}', client=cl,
                                           statut=Installation.Statut.INSTALLE)
        p = Produit.objects.create(company=co, nom=f'Panneau AAPV81 {tag}', sku=f'AAPV-081-{tag}',
                                   prix_vente=Decimal('1000'), quantite_stock=0)
        itv = Intervention.objects.create(company=co, installation=inst, type_intervention=Intervention.Type.POSE)
        cons = MaterielConsommation.objects.create(company=co, intervention=itv, valide=True)
        ConsommationLigne.objects.create(company=co, consommation=cons, produit=p, designation=p.nom,
                                         quantite_prevue=Decimal('5'), quantite_utilisee=Decimal('5'),
                                         stock_applique=True)
        r = api.post(f'{B}/retours-materiel/', {'installation': inst.id}, format='json', **H)
        lignes = [api.post(f'{B}/retour-materiel-lignes/', {'retour': r.data['id'], 'produit': p.id,
                                                             'quantite': str(q)}, format='json', **H).status_code
                  for q in quantites]
        v = api.post(f'{B}/retours-materiel/{r.data["id"]}/valider/', {}, format='json', **H)
        p.refresh_from_db()
        ent = MouvementStock.objects.filter(company=co, produit=p, reference=f'RETOUR-{inst.reference}').aggregate(
            t=Sum('quantite'))['t'] or 0
        return {'creation_lignes': lignes, 'valider': v.status_code,
                'detail': None if v.status_code < 400 else str(v.data)[:140],
                'entrees_retour': str(ent), 'stock': str(p.quantite_stock), 'sorti_f11': 5}

    obs = {'R': cas('R', [4, 4]), 'T': cas('T', [8])}
    print(obs)
    temoin_ok = obs['T']['valider'] == 409 and obs['T']['stock'] == '0'
    defaut = obs['R']['valider'] == 200 and Decimal(obs['R']['entrees_retour']) == 8
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs

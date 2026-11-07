# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K64 — demande de transfert FG325 et seuil d'approbation NTWMS21. Seuil 10 000 MAD, onduleur prix d'achat
3 000, 200 au dépôt principal.
(T) témoin : transfert direct de 50 (150 000 MAD) sans demande → 409 « seuil d'approbation ».
(A) demande de 5 (15 000) créée et approuvée par un responsable, puis PATCH `quantite: 50` sur la demande
APPROUVÉE, puis `executer` : 50 transférés sans nouvelle approbation ?
(B) demande de 50 approuvée, NON exécutée ; un Technicien (rôle système, `stock_mouvement`) fait
`POST stock/transferts/` de 50 trois fois : trois transferts acceptés sur une seule approbation ?
Vraies routes `installations/demandes-transfert/` et `stock/transferts/`."""
SONDE = {"constat": "C-AAPV-084", "sha": "6ffa876688",
         "attendu": "repro si A : PATCH 200 et executer 200 (50 transférés) ; B : 3 × 201 ; T : 409",
         "modeles": ["stock.Produit", "stock.TransfertStock", "stock.StockEmplacement", "stock.AchatsParametres",
                     "installations.DemandeTransfert", "roles.Role"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.stock.models import Produit, EmplacementStock, AchatsParametres, TransfertStock, StockEmplacement
    from apps.stock.services import ensure_emplacements
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    co = Company.objects.create(nom='Sonde AAPV 084', slug='sonde-aapv-084')
    resp = U.objects.create_user(username='sonde_aapv_084_resp', password='x', role_legacy='responsable', company=co)
    api = APIClient()
    api.force_authenticate(resp)
    perms = list(R['Technicien'])
    role, _ = Role.objects.get_or_create(company=co, nom='Technicien',
                                         defaults={'permissions': perms, 'est_systeme': True})
    tech = U.objects.create_user(username='sonde_aapv_084_tech', password='x', company=co, role=role,
                                 role_legacy=tier_for_role_fields('Technicien', True, perms))
    apit = APIClient()
    apit.force_authenticate(tech)
    principal = ensure_emplacements(co)
    van = EmplacementStock.objects.filter(company=co, is_principal=False).first()
    ap = AchatsParametres.for_company(co)
    ap.seuil_approbation_transfert = Decimal('10000')
    ap.save()
    p = Produit.objects.create(company=co, nom='Onduleur AAPV84', sku='AAPV-084', prix_vente=Decimal('4000'),
                               prix_achat=Decimal('3000'), quantite_stock=200)
    D = '/api/django/installations/demandes-transfert/'
    T = '/api/django/stock/transferts/'

    def au_van():
        se = StockEmplacement.objects.filter(company=co, produit=p, emplacement=van).first()
        return se.quantite if se else 0

    def direct(client, q):
        r = client.post(T, {'produit': p.id, 'source': principal.id, 'destination': van.id, 'quantite': q},
                        format='json', **H)
        return r.status_code, (None if r.status_code < 400 else str(r.data)[:120])

    obs = {'tech_a_stock_mouvement': 'stock_mouvement' in perms}
    obs['T_direct_sans_demande'] = direct(apit, 50)
    # (A) approuvée à 5, éditée à 50, exécutée
    a = api.post(D, {'produit': p.id, 'source': principal.id, 'destination': van.id, 'quantite': 5,
                     'motif': 'Réassort camionnette'}, format='json', **H)
    ra = api.post(f'{D}{a.data["id"]}/approuver/', {}, format='json', **H)
    pa = api.patch(f'{D}{a.data["id"]}/', {'quantite': 50}, format='json', **H)
    xa = api.post(f'{D}{a.data["id"]}/executer/', {}, format='json', **H)
    obs['A'] = {'creer': a.status_code, 'approuver': ra.status_code, 'patch_apres_approbation': pa.status_code,
                'quantite_apres_patch': pa.data.get('quantite') if pa.status_code < 400 else None,
                'executer': xa.status_code, 'detail': None if xa.status_code < 400 else str(xa.data)[:120],
                'au_van': au_van()}
    # (B) une approbation de 50 non exécutée couvre N transferts directs identiques
    van_avant = au_van()
    b = api.post(D, {'produit': p.id, 'source': principal.id, 'destination': van.id, 'quantite': 50,
                     'motif': 'Chantier'}, format='json', **H)
    rb = api.post(f'{D}{b.data["id"]}/approuver/', {}, format='json', **H)
    directs = [direct(apit, 50) for _ in range(3)]
    obs['B'] = {'creer': b.status_code, 'approuver': rb.status_code, 'directs_technicien': directs,
                'transferts_ajoutes_au_van': au_van() - van_avant,
                'demande_statut': api.get(f'{D}{b.data["id"]}/', **H).data.get('statut'),
                'nb_transferts_total': TransfertStock.objects.filter(company=co, produit=p).count()}
    print(obs)
    temoin_ok = obs['T_direct_sans_demande'][0] == 409
    defA = obs['A']['patch_apres_approbation'] == 200 and obs['A']['executer'] == 200 and obs['A']['au_van'] == 50
    defB = sum(1 for c, _ in directs if c == 201) >= 2
    obs['temoin_ok'], obs['defaut_A'], obs['defaut_B'] = temoin_ok, defA, defB
    obs['repro'] = bool(temoin_ok and (defA or defB))
    return obs

# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K30 — cross-dock (NTWMS15) affectable sur une réception BROUILLON, sur la quantité SAISIE, et jamais libéré
par l'annulation d'un brouillon.
Vague en attente de 12 onduleurs (`creer_vague_depuis_besoins`).
(A) réception brouillon 12 (vraie route `receptions-fournisseur/`, BCF de 10 — sur-livraison seule acceptée),
`affecter-cross-dock/` (vraie route) → colis ; puis `annuler/` du brouillon : le colis garde-t-il des unités
jamais entrées ?
(B) même chose puis `confirmer/` : 10 entrés (quantite_appliquee) contre un colis de 12.
(T) témoin : réception CONFIRMÉE affectée puis annulée → `_liberer_cross_dock_reception_annulee` vide le colis."""
SONDE = {"constat": "C-AAPV-027", "sha": "b432084786",
         "attendu": "repro si A : affecter 200 sur brouillon, annulation 200 et colis toujours 12 ; B : stock +10 mais colis 12 ; T : colis 0 après annulation",
         "modeles": ["stock.Produit", "stock.MouvementStock", "stock.ReceptionFournisseur",
                     "stock.UniteLogistique", "stock.UniteLogistiqueLigne", "stock.AffectationCrossDock"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db.models import Sum
    from django.test import TestCase
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import (Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur,
                                   Produit, ReceptionFournisseur, AffectationCrossDock, UniteLogistiqueLigne)
    from apps.stock.services import creer_vague_depuis_besoins
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 027', slug='sonde-aapv-027')
    u = get_user_model().objects.create_user(username='sonde_aapv_027', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV27')
    url = '/api/django/stock/receptions-fournisseur/'

    def cas(n, saisie, confirmer_avant=False):
        p = Produit.objects.create(company=co, nom=f'Onduleur AAPV27-{n}', sku=f'AAPV-027-{n}',
                                   prix_vente=Decimal('9000'), quantite_stock=0)
        creer_vague_depuis_besoins(company=co, user=u, besoins=[{'produit_id': p.id, 'quantite': 12}])
        bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference=f'BCF-AAPV-027-{n}',
                                                   statut=BonCommandeFournisseur.Statut.ENVOYE)
        lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=10,
                                                        prix_achat_unitaire=Decimal('7000'))
        r = api.post(url, {'bon_commande': bc.id, 'lignes': [{'ligne_commande': lc.id, 'quantite': saisie}]},
                     format='json', **H)
        rid = r.data['id'] if r.status_code == 201 else None
        rcf = None
        if confirmer_avant:
            rcf = api.post(f'{url}{rid}/confirmer/', {}, format='json', **H).status_code
        ra = api.post(f'{url}{rid}/affecter-cross-dock/', {}, format='json', **H)
        return p, rid, {'creation': r.status_code, 'confirmer_avant': rcf,
                        'statut_au_cross_dock': ReceptionFournisseur.objects.get(pk=rid).statut,
                        'affecter': ra.status_code, 'affecter_detail': str(getattr(ra, 'data', ''))[:160],
                        'colis_apres_affectation': colis(p)}

    def colis(p):
        return UniteLogistiqueLigne.objects.filter(produit=p).aggregate(s=Sum('quantite'))['s'] or 0

    def etat(p, rid):
        p.refresh_from_db()
        rec = ReceptionFournisseur.objects.get(pk=rid)
        return {'statut': rec.statut, 'stock': p.quantite_stock, 'colis': colis(p),
                'quantite_appliquee': list(rec.lignes.values_list('quantite_appliquee', flat=True)),
                'affectations': list(AffectationCrossDock.objects.filter(company=co, reception_id=rid).values_list(
                    'quantite', flat=True))}

    obs = {}
    p, rid, init = cas('A', 12)
    with TestCase.captureOnCommitCallbacks(execute=True):
        rann = api.post(f'{url}{rid}/annuler/', {}, format='json', **H)
    obs['A'] = {**init, 'annuler_brouillon': rann.status_code, 'apres': etat(p, rid)}
    p, rid, init = cas('B', 12)
    rc = api.post(f'{url}{rid}/confirmer/', {}, format='json', **H)
    obs['B'] = {**init, 'confirmer': rc.status_code, 'apres': etat(p, rid)}
    p, rid, init = cas('T', 10, confirmer_avant=True)
    with TestCase.captureOnCommitCallbacks(execute=True):
        rannT = api.post(f'{url}{rid}/annuler/', {}, format='json', **H)
    obs['T'] = {**init, 'annuler_confirmee': rannT.status_code, 'apres': etat(p, rid)}
    print(obs)
    a, b, t = obs['A'], obs['B'], obs['T']
    temoin_ok = (t['affecter'] == 200 and t['colis_apres_affectation'] == 10 and t['annuler_confirmee'] == 200
                 and t['apres']['colis'] == 0)
    defaut_a = (a['statut_au_cross_dock'] == 'brouillon' and a['affecter'] == 200
                and a['annuler_brouillon'] == 200 and a['apres']['statut'] == 'annule' and a['apres']['colis'] == 12)
    defaut_b = (b['affecter'] == 200 and b['confirmer'] == 200 and b['apres']['stock'] == 10
                and b['apres']['colis'] == 12)
    obs['temoin_ok'] = temoin_ok
    obs['repro_A'] = defaut_a
    obs['repro_B'] = defaut_b
    obs['repro'] = bool(temoin_ok and (defaut_a or defaut_b))
    return obs

# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K11 — le blocage fournisseur XPUR4 (`statut = bloque_total`) n'est gardé qu'à POST bons-commande-fournisseur/
(`check_fournisseur_statut_commande`, seul appelant). Vraies routes : (T) création directe chez F bloqué → 409 ;
(R1) DA approuvée `fournisseur_suggere = F` → generer-bcf → envoyer ; (R2) BCF brouillon chez F_ok → PATCH
{fournisseur: F} → envoyer ; (R3) chantier en manque → commander-besoin {fournisseur: F} → envoyer.
Attendu sain : 409 à chaque geste qui crée / réaffecte / envoie un BCF chez F ; 0 BCF envoyé chez F."""
SONDE = {"constat": "C-AAPV-065", "sha": "6ffa876688",
         "attendu": "repro si création directe 409 mais ≥ 1 BCF ENVOYÉ chez F bloqué par generer-bcf / PATCH / commander-besoin",
         "modeles": ["installations.DemandeAchat", "achats.BonCommandeFournisseur", "achats.LigneBonCommandeFournisseur",
                     "installations.Installation", "stock.Fournisseur", "stock.Produit"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import Fournisseur, Produit, BonCommandeFournisseur
    from apps.installations.models import DemandeAchat, Installation
    from apps.installations.services import seed_reservations
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 065', slug='sonde-aapv-065')
    u = get_user_model().objects.create_user(username='sonde_aapv_065', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    fb = Fournisseur.objects.create(company=co, nom='F-BLOQUE-AAPV65', statut='bloque_total',
                                    motif_blocage='litige qualité')
    fok = Fournisseur.objects.create(company=co, nom='F-OK-AAPV65')
    p = Produit.objects.create(company=co, nom='Rail AAPV65', sku='AAPV-065', prix_vente=Decimal('80'),
                               prix_achat=Decimal('40'), quantite_stock=0)
    bcf = '/api/django/stock/bons-commande-fournisseur/'
    da = '/api/django/installations/demandes-achat/'
    obs = {}
    rt = api.post(bcf, {'fournisseur': fb.id, 'lignes': [{'produit': p.id, 'quantite': 3, 'prix_achat_unitaire': 40}]},
                  format='json', **H)
    obs['T_creation_directe'] = {'http': rt.status_code, 'detail': str(rt.data)[:120]}

    def envoyer(bid):
        with TestCase.captureOnCommitCallbacks(execute=True):
            return api.post(f'{bcf}{bid}/envoyer/', {}, format='json', **H).status_code

    # R1 — DA → generer-bcf
    r = api.post(da, {'objet': 'DA AAPV65', 'fournisseur_suggere': fb.id}, format='json', **H)
    obs['R1_creation_da'] = r.status_code
    did = r.data.get('id')
    if did:
        api.post('/api/django/installations/demandes-achat-lignes/',
                 {'demande': did, 'produit': p.id, 'quantite': '3', 'prix_estime': '40'}, format='json', **H)
        s = api.post(f'{da}{did}/soumettre/', {}, format='json', **H).status_code
        a = api.post(f'{da}{did}/approuver/', {}, format='json', **H).status_code
        g = api.post(f'{da}{did}/generer-bcf/', {}, format='json', **H)
        bid = DemandeAchat.objects.get(pk=did).bon_commande_id
        obs['R1'] = {'soumettre': s, 'approuver': a, 'generer_bcf': g.status_code,
                     'envoyer': envoyer(bid) if bid else None}
    # R2 — PATCH fournisseur d'un brouillon
    r2 = api.post(bcf, {'fournisseur': fok.id, 'lignes': [{'produit': p.id, 'quantite': 3, 'prix_achat_unitaire': 40}]},
                  format='json', **H)
    b2 = r2.data['id']
    pa = api.patch(f'{bcf}{b2}/', {'fournisseur': fb.id}, format='json', **H)
    obs['R2'] = {'creation_ok': r2.status_code, 'patch_fournisseur': pa.status_code,
                 'envoyer': envoyer(b2) if pa.status_code == 200 else None}
    # R3 — commander-besoin imposé chez F
    ch = Installation.objects.create(company=co, reference='CH-AAPV65', statut='signe',
                                     bom=[{'produit_id': p.id, 'designation': p.nom, 'quantite': 4.0}])
    seed_reservations(ch)
    rc = api.post(f'/api/django/installations/chantiers/{ch.id}/commander-besoin/', {'fournisseur': fb.id},
                  format='json', **H)
    b3 = BonCommandeFournisseur.objects.filter(chantier_origine=ch, fournisseur=fb).first()
    obs['R3'] = {'commander_besoin': rc.status_code, 'envoyer': envoyer(b3.id) if b3 else None}
    envoyes = list(BonCommandeFournisseur.objects.filter(company=co, fournisseur=fb, statut='envoye')
                   .values_list('reference', flat=True))
    obs['bcf_envoyes_chez_F_bloque'] = envoyes
    print(obs)
    temoin_ok = rt.status_code == 409
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and len(envoyes) >= 1)
    return obs

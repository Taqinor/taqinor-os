# flake8: noqa  (sonde parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K49 — `FactureFournisseurViewSet.perform_update` ne traite que l'ACQUISITION d'un BCF : re-pointer ou
délier laisse les provisions GR/IR de l'ancien BCF lettrées (`delettrer_gr_ir_facture` n'est appelé que par
perform_destroy). BCF-A et BCF-B 10 × 100 HT, réceptions confirmées (provisions 1 000 chacune) ; facture
POST factures-fournisseur HT 1 000 sans BCF ; PATCH {bon_commande: A} puis {bon_commande: B} puis
{bon_commande: null}. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AAPV-049", "sha": "5f603acce",
         "attendu": "repro si après re-pointage la provision de A reste lettrée (facture = celle re-pointée), et après délier celle de B aussi",
         "modeles": ["achats.FactureFournisseur", "installations.ReceptionNonFacturee"]}

H = {'HTTP_HOST': 'localhost'}


def _base(slug):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import Produit, Fournisseur
    co = Company.objects.create(nom='Sonde ' + slug, slug='sonde-' + slug)
    u = get_user_model().objects.create_user(username='sonde-' + slug, password='x', company=co,
                                             role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    f = Fournisseur.objects.create(company=co, nom='Fournisseur ' + slug)
    p = Produit.objects.create(company=co, nom='Onduleur ' + slug, sku='SONDE-' + slug.upper(),
                               prix_vente=Decimal('2000'), quantite_stock=0, tva=Decimal('20.00'))
    return co, u, api, f, p


def _bcf(co, f, p, ref, qte=10, pu='1000'):
    import datetime
    from decimal import Decimal
    from apps.achats.models import BonCommandeFournisseur, LigneBonCommandeFournisseur
    bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference=ref,
                                               statut=BonCommandeFournisseur.Statut.ENVOYE,
                                               date_commande=datetime.date.today())
    ligne = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=qte,
                                                       prix_achat_unitaire=Decimal(pu))
    return bc, ligne


def _recevoir(api, co, bc, ligne, qte, ref):
    import datetime
    from apps.achats.models import ReceptionFournisseur, LigneReceptionFournisseur
    r = ReceptionFournisseur.objects.create(company=co, reference=ref, bon_commande=bc,
                                            date_reception=datetime.date.today())
    LigneReceptionFournisseur.objects.create(reception=r, ligne_commande=ligne, produit=ligne.produit, quantite=qte)
    resp = api.post(f'/api/django/stock/receptions-fournisseur/{r.id}/confirmer/', {}, format='json', **H)
    assert resp.status_code == 200, (resp.status_code, getattr(resp, 'data', None))
    r.refresh_from_db()
    return r



def sonde(ctx):
    from apps.installations.models_gr_ir import ReceptionNonFacturee
    co, u, api, f, p = _base('aapv-049')
    obs = {}
    ba, la = _bcf(co, f, p, 'BCF-AAPV-049-A', qte=10, pu='100')
    bb, lb = _bcf(co, f, p, 'BCF-AAPV-049-B', qte=10, pu='100')
    _recevoir(api, co, ba, la, 10, 'REC-AAPV-049-A')
    _recevoir(api, co, bb, lb, 10, 'REC-AAPV-049-B')

    def prov(bc):
        return [(str(x.montant_provision), x.lettre, x.facture_id) for x in
                ReceptionNonFacturee.objects.filter(company=co, bon_commande=bc)]

    obs['init'] = {'A': prov(ba), 'B': prov(bb)}
    rf = api.post('/api/django/stock/factures-fournisseur/',
                  {'fournisseur': f.id, 'ref_fournisseur': 'F-049', 'date_facture': '2026-11-02',
                   'montant_ht': '1000.00', 'montant_tva': '200.00', 'montant_ttc': '1200.00'}, format='json', **H)
    fid = rf.data['id']
    obs['facture_id'] = fid
    for etape, cible in (('lien_A', ba.id), ('repointe_B', bb.id), ('delie', None)):
        r = api.patch(f'/api/django/stock/factures-fournisseur/{fid}/', {'bon_commande': cible}, format='json', **H)
        obs[etape] = {'http': r.status_code, 'A': prov(ba), 'B': prov(bb)}
    print(obs)
    a_reste = obs['repointe_B']['A'] and obs['repointe_B']['A'][0][1] is True
    b_reste = obs['delie']['B'] and obs['delie']['B'][0][1] is True
    obs['repro'] = bool(obs['lien_A']['A'][0][1] is True and a_reste and b_reste)
    return obs

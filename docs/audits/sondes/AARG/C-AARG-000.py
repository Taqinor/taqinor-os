# flake8: noqa  (sonde de parcours PA4, rejouable par scripts/sonde.py — AMET93)
"""PA4 bout en bout (C19) sur UN enregistrement, par l'API réelle : devis envoyé → accepter → convertir-bc →
confirmer → creer-facture → emettre → enregistrer-paiement (moitié) → creer-avoir (une ligne) → relecture.
Oracles : aucune réponse ≥ 500 ; TTC facture = TTC devis au centime ; montant dû = TTC − payé − avoir ;
`prix_achat` absent des réponses facture / BC. Société neuve, transaction annulée."""
SONDE = {"constat": "C-AARG-000", "sha": "56d5b623a",
         "attendu": "chaque étape 2xx ; TTC facture = TTC devis ; dû = TTC − 50 % − avoir ; aucun prix_achat",
         "modeles": ["ventes.Devis", "ventes.BonCommande", "ventes.Facture", "ventes.Paiement", "ventes.Avoir"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, BonCommande, Facture
    U = get_user_model()
    c = Company.objects.create(nom='Sonde AARG 000', slug='sonde-aarg-000')
    cl = Client.objects.create(company=c, nom='Parcours', prenom='PA4', email='sonde-aarg-000@example.invalid')
    u = U.objects.create_user(username='sonde-aarg-000', password='x', role_legacy='admin', company=c)
    p1 = Produit.objects.create(company=c, nom='Panneau sonde', sku='SONDE-AARG-000-P', prix_vente=Decimal('1000'),
                                prix_achat=Decimal('700'), quantite_stock=50)
    p2 = Produit.objects.create(company=c, nom='Onduleur sonde', sku='SONDE-AARG-000-O', prix_vente=Decimal('4000'),
                                prix_achat=Decimal('3100'), quantite_stock=5)
    dv = Devis.objects.create(company=c, client=cl, reference='DEV-SONDE-AARG-000', statut='envoye',
                              taux_tva=Decimal('20'), created_by=u)
    LigneDevis.objects.create(devis=dv, produit=p1, designation='Panneau', quantite=Decimal('6'),
                              prix_unitaire=Decimal('1000'))
    LigneDevis.objects.create(devis=dv, produit=p2, designation='Onduleur', quantite=Decimal('1'),
                              prix_unitaire=Decimal('4000'))
    dv.refresh_from_db()
    ttc_devis = Decimal(str(dv.total_ttc))
    api = APIClient()
    api.force_authenticate(u)
    base = '/api/django/ventes'
    etapes, fuites = [], []

    def appel(nom, meth, url, corps=None):
        r = getattr(api, meth)(base + url, corps or {}, format='json', HTTP_HOST='localhost')
        txt = r.content.decode('utf-8', 'replace')
        etapes.append((nom, r.status_code, '' if r.status_code < 400 else txt[:200]))
        if 'prix_achat' in txt:
            fuites.append(nom)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {}

    appel('accepter', 'post', f'/devis/{dv.id}/accepter/', {'nom': 'Client PA4'})
    appel('convertir-bc', 'post', f'/devis/{dv.id}/convertir-bc/')
    bc = BonCommande.objects.filter(devis=dv).first()
    fac = None
    if bc:
        appel('confirmer', 'post', f'/bons-commande/{bc.id}/confirmer/')
        appel('bc-lecture', 'get', f'/bons-commande/{bc.id}/')
        appel('creer-facture', 'post', f'/bons-commande/{bc.id}/creer-facture/')
        fac = Facture.objects.filter(bon_commande=bc).first()
    obs = {}
    if fac:
        appel('emettre', 'post', f'/factures/{fac.id}/emettre/')
        fac.refresh_from_db()
        ttc_fac = Decimal(str(fac.total_ttc))
        moitie = (ttc_fac / 2).quantize(Decimal('0.01'))
        appel('paiement', 'post', f'/factures/{fac.id}/enregistrer-paiement/',
              {'montant': str(moitie), 'mode': 'virement',
               'date_paiement': str(fac.date_emission or '')[:10] or str(__import__('datetime').date.today())})
        ligne = fac.lignes.order_by('id').first()
        appel('avoir', 'post', f'/factures/{fac.id}/creer-avoir/',
              {'lignes': [{'produit': ligne.produit_id, 'designation': ligne.designation, 'quantite': '1',
                           'prix_unitaire': str(ligne.prix_unitaire), 'taux_tva': str(fac.taux_tva)}],
               'motif': 'Sonde PA4', 'type': 'geste_commercial'})
        appel('facture-lecture', 'get', f'/factures/{fac.id}/')
        fac.refresh_from_db()
        avoirs = Decimal(str(getattr(fac, 'avoirs_total', 0) or 0))
        attendu_du = max(Decimal('0'), ttc_fac - moitie - avoirs)
        obs = {'statut': fac.statut, 'reference': fac.reference, 'ttc_facture': str(ttc_fac),
               'paye': str(fac.montant_paye), 'avoirs': str(avoirs), 'du': str(fac.montant_du),
               'du_attendu': str(attendu_du)}
    cinq_cents = [e for e in etapes if e[1] >= 500]
    print('etapes', etapes)
    print('ttc_devis', ttc_devis, 'obs', obs, 'fuites_prix_achat', fuites)
    ecart_ttc = bool(obs) and Decimal(obs['ttc_facture']) != ttc_devis
    ecart_du = bool(obs) and abs(Decimal(obs['du']) - Decimal(obs['du_attendu'])) > Decimal('0.01')
    defaut = bool(cinq_cents or fuites or ecart_ttc or ecart_du or not fac)
    return {'repro': defaut, 'etapes': etapes, 'ttc_devis': str(ttc_devis), 'obs': obs, 'fuites': fuites}

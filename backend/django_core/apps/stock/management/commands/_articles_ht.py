"""HT24 — articles de la batterie Deye BOS-B Pro (haute tension) : le pack et
les deux accessoires d'une GRAPPE (boîtier de contrôle, rack et câblage de
puissance). Extrait de ``seed_catalogue.py`` (fichier-mur) ; la boucle du pack
y vivait à l'identique.

Prix (fondateur, 24/11/2026 : « add 30% on top and add the right prices ») :
prix d'ACHAT du devis fournisseur Solarex Maroc n° S26/001708 du 27/07/2026
(prix unitaires HT, TVA 20 % ajoutée ensuite), prix de VENTE = achat + 30 %.
Les tuples portent des TTC, comme toute la table du seeder (``ht()`` en tire le
HT stocké) :

======================================  ==========  ==========  ==========
Article (libellé fournisseur)           Achat HT    Vente HT    Vente TTC
======================================  ==========  ==========  ==========
16kWh BOS-B-Pro Battery Pack            28 000,00   36 400,00   43 680,00
BOS-B-PRO High Voltage Control Box      11 200,00   14 560,00   17 472,00
Racks, Power Cables Etc.                 6 000,00    7 800,00    9 360,00
======================================  ==========  ==========  ==========

Le jeu « Racks, Power Cables Etc. » est chiffré par le fournisseur pour UNE
grappe de 6 modules : l'appliquer à toute grappe est une HYPOTHÈSE, dite par le
moteur (``moteur_ci.batterie_ht``), jamais tue.

Additif, comme tout le seeder : un SKU ou un nom actif déjà présent est sauté,
jamais réécrit (prix, nom, rôle).
"""
from decimal import Decimal

#: Accessoires d'une grappe, déclarés par leur RÔLE C&I (donnée), jamais par
#: leur nom. Aucun stock inventé (0). Noms choisis pour ne tomber dans AUCUNE
#: famille du classement par mots (« câblage », pas « câbles » : un « câble »
#: serait lu câble DC par le résidentiel).
#: (nom, sku, role_ci, vente TTC, achat TTC, qte, seuil)
ACCESSOIRES_GRAPPE_HT = [
    # Achat 11 200 HT (13 440 TTC), vente 14 560 HT (17 472 TTC).
    ('Boîtier de contrôle haute tension Deye BOS-B-PDU-2-A', 'DEY-BOSB-PDU-2-A',
     'boitier_batterie_ht', 17472, 13440, 0, 0),
    # Achat 6 000 HT (7 200 TTC), vente 7 800 HT (9 360 TTC).
    ('Rack et câblage de puissance Deye BOS-B Pro', 'DEY-BOSB-RACK',
     'rack_batterie_ht', 9360, 7200, 0, 0),
]

#: HT24 (fondateur 24/11/2026 : « pour l'onduleur 80kw fais ça toi-même ») —
#: l'hybride haute tension du fondateur, seedé comme ses frères SG05LP3.
#: Prix de VENTE : celui que le fondateur a saisi, 100 000 HT (120 000 TTC) ;
#: prix d'ACHAT inconnu : 0 (jamais supposé). Aucun stock inventé.
#: (nom, sku, vente TTC, achat TTC, qte, seuil)
HYBRIDES_DEYE_HT = [
    ('Onduleur hybride Deye 80kW Triphasé', 'OND-H-DEY-80T', 120000, 0, 0, 0),
]

#: Achat TTC du pack (28 000 HT, même devis fournisseur).
ACHAT_TTC_PACK = Decimal('33600')


def semer_haute_tension(company, batteries, *, Produit, MouvementStock, record_stock_movement,
                        categorie_de, ht, created, skipped):
    """Le pack (``batteries`` : ``BATTERIE_DEYE_HV`` du seeder), l'hybride
    80 kW, puis les accessoires de grappe — prix réels, additifs."""
    def deja(nom, sku):
        return (Produit.objects.filter(company=company, sku=sku).exists()
                or Produit.objects.filter(company=company, nom__iexact=nom,
                                          is_archived=False).exists())

    def tracer(produit, qte, note):
        record_stock_movement(
            company=company, produit=produit,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE,
            quantite=qte, quantite_avant=0, quantite_apres=qte,
            reference='SEED-CATALOGUE', note=note,
            # Le produit est créé DÉJÀ à sa quantité : on trace l'entrée sans
            # la ré-écrire (AUD223).
            created_by=None, save_produit=False)

    for nom, sku, sell_ttc, qte, seuil in batteries:
        if deja(nom, sku):
            skipped.append(nom)
            continue
        produit = Produit.objects.create(
            company=company, nom=nom, sku=sku, categorie=categorie_de(nom),
            prix_achat=ht(ACHAT_TTC_PACK), prix_vente=ht(sell_ttc),
            quantite_stock=qte, seuil_alerte=seuil, tva=Decimal('20.00'),
            unite_stock='tranche')
        tracer(produit, qte, 'Stock initial (batterie Dyness haute tension — 16 kWh)')
        created.append(nom)
    for nom, sku, sell_ttc, achat_ttc, qte, seuil in HYBRIDES_DEYE_HT:
        if deja(nom, sku):
            skipped.append(nom)
            continue
        produit = Produit.objects.create(
            company=company, nom=nom, sku=sku, categorie=categorie_de(nom),
            prix_achat=ht(achat_ttc), prix_vente=ht(sell_ttc),
            quantite_stock=qte, seuil_alerte=seuil, tva=Decimal('20.00'),
            role_devis='onduleur_hybride')
        if qte:
            tracer(produit, qte, 'Stock initial (onduleur hybride haute tension)')
        created.append(nom)
    for nom, sku, role_ci, sell_ttc, achat_ttc, qte, seuil in ACCESSOIRES_GRAPPE_HT:
        if deja(nom, sku):
            skipped.append(nom)
            continue
        produit = Produit.objects.create(
            company=company, nom=nom, sku=sku, categorie=categorie_de(nom),
            prix_achat=ht(achat_ttc), prix_vente=ht(sell_ttc),
            quantite_stock=qte, seuil_alerte=seuil, tva=Decimal('20.00'), role_ci=role_ci)
        if qte:
            tracer(produit, qte, 'Stock initial (accessoires de grappe haute tension)')
        created.append(nom)

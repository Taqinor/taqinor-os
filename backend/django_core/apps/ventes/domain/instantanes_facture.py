"""Instantanés figés à l'émission d'une facture (Groupe VNT).

VNT9 (lot M0) — couture seule : ``figer_a_l_emission`` est appelée par
``facturation_ops.emettre_facture`` juste après l'instantané
``identite_vendeur`` (APAR61), dans la même transaction, avant le ``save``.

VNT35 — « Objet de la vente » (``Facture.objet_vente``) : les lignes de
l'option retenue du devis qui fait foi (désignation, marque, qté, P.U. HT,
total HT) et la chaîne de prix de la vente, en TEXTE décimal (forme du
contrat ``facturation/contract_samples/facture_situation_vente.json``) ;
jamais ``prix_achat``. Une facture ÉMISE garde ce que le client a reçu ;
un brouillon suit la vente (même fonction, lue au rendu par ``utils/pdf``).
"""
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal('0.01')


def _txt(valeur) -> str:
    """Montant en TEXTE décimal au centime (« 15000.00 »)."""
    brut = Decimal(str(valeur if valeur is not None else 0))
    return '{:.2f}'.format(brut.quantize(CENT, rounding=ROUND_HALF_UP))


def devis_de_la_vente(devis):
    """La version qui fait foi pour la vente de ``devis`` : le dernier
    ACCEPTÉ de sa chaîne de révisions, sinon la plus récente (même règle que
    ``vente_facturation.etat_vente``). ``None`` sans devis."""
    if devis is None:
        return None
    from apps.ventes.vente_facturation import _tete_de_vente, chaine_vente
    return _tete_de_vente(chaine_vente(devis))[0]


def _ligne_objet(ligne, taux_defaut) -> dict:
    """Une ligne du panier (``lignes_facture_du_devis``) en texte ; total HT
    = formule de ``LigneFacture.total_ht`` (qté × P.U. × (1 − remise %))."""
    remise = Decimal(str(ligne['remise'] or 0))
    total = ligne['quantite'] * ligne['prix_unitaire'] * (1 - remise / 100)
    produit = ligne['produit']
    taux = ligne['taux_tva'] if ligne['taux_tva'] is not None else taux_defaut
    return {
        'designation': ligne['designation'] or '',
        'marque': (getattr(produit, 'marque', '') or '') if produit else '',
        'quantite': _txt(ligne['quantite']),
        'prix_unitaire_ht': _txt(ligne['prix_unitaire']),
        'total_ht': _txt(total),
        'taux_tva': _txt(taux),
    }


def objet_vente_du_devis(devis):
    """Bloc « Objet de la vente » de ``devis`` (dict JSON), ``None`` sans
    devis ou sans ligne. Chaîne de prix = ``option_totaux`` (sous-total,
    remise, arrondi, HT, TVA par taux, TTC) — le prix convenu, jamais
    recalculé ici."""
    if devis is None:
        return None
    from apps.ventes.utils.options import option_totaux

    from .facturation_ops import lignes_facture_du_devis
    lignes = [_ligne_objet(li, devis.taux_tva)
              for li in lignes_facture_du_devis(devis)]
    if not lignes:
        return None
    tot = option_totaux(devis)
    return {
        'devis_reference': devis.reference,
        'devis_version': devis.version,
        'lignes': lignes,
        'sous_total_ht': _txt(tot['ht_brut']),
        'remise_pct': _txt(getattr(devis, 'remise_globale', 0) or 0),
        'remise_montant': _txt(tot['remise']),
        'arrondi': _txt(tot['arrondi']),
        'total_ht': _txt(tot['ht']),
        'tva_par_taux': [{'taux': _txt(b['taux']), 'base': _txt(b['base_ht']),
                          'tva': _txt(b['montant'])}
                         for b in (tot.get('tva_par_taux') or [])],
        'total_ttc': _txt(tot['ttc']),
    }


def figer_a_l_emission(facture):
    """Fige les blocs de la vente sur ``facture`` (appelée par
    ``emettre_facture``, dans sa transaction, avant le ``save``).

    VNT35 — ``objet_vente`` : seulement pour une facture de TRANCHE (sans
    ligne) rattachée à un devis ; une facture complète montre déjà son
    matériel. Un instantané déjà posé n'est jamais réécrit. Ne sauve rien :
    l'appelant fait le ``save``.
    """
    if not facture.devis_id:
        return None
    devis = devis_de_la_vente(facture.devis)
    sans_ligne = facture.pk is None or not facture.lignes.exists()
    if facture.objet_vente is None and sans_ligne:
        facture.objet_vente = objet_vente_du_devis(devis)
    return None

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


def langue_de_la_facture(facture) -> str:
    """Langue imprimée du PDF facture (``fr`` ou ``ar`` ; toute autre
    langue rend le français, APDF31) — même règle que le rendu."""
    from apps.ventes.utils.libelles_ar import document_langue
    langue = document_langue(facture.client, company=facture.company)
    return langue if langue in ('fr', 'ar') else 'fr'


def garanties_du_devis(devis, langue='fr') -> list:
    """VNT38 — tableau « Garanties » de la vente (``[{libelle, duree,
    detail}]``, forme du contrat) depuis ``utils/garanties`` (durées des
    fiches produit, mêmes que la bande du PDF devis du marché) ; jamais une
    ligne sans durée ; ``[]`` sans devis."""
    if devis is None:
        return []
    from apps.ventes.utils.garanties import garanties_de_la_vente
    return [{'libelle': g['designation'], 'duree': g['duree'],
             'detail': g['detail']}
            for g in garanties_de_la_vente(devis, langue)
            if (g.get('duree') or '').strip()]


def identite_acheteur_courante(facture) -> dict:
    """AARG27 — ce que le PDF et l'UBL impriment de l'acheteur, lu du client
    (langue du document comprise) au moment de l'émission."""
    from apps.ventes.utils.libelles_ar import document_langue
    client = facture.client
    return {**{champ: getattr(client, champ, '') or ''
               for champ in ('nom', 'prenom', 'type_client', 'ice', 'if_fiscal',
                             'rc', 'adresse', 'email', 'telephone')},
            'langue': document_langue(client, company=facture.company)}


def acheteur_de_la_facture(facture):
    """AARG27 — L'acheteur imprimé : l'instantané figé à l'émission, sinon
    (brouillon, facture antérieure) le client vivant. Mêmes attributs."""
    from types import SimpleNamespace
    figee = getattr(facture, 'identite_acheteur', None)
    if isinstance(figee, dict) and figee:
        return SimpleNamespace(**figee)
    return facture.client


def figer_a_l_emission(facture):
    """Fige les blocs de la vente sur ``facture`` (appelée par
    ``emettre_facture``, dans sa transaction, avant le ``save``).

    VNT35 — ``objet_vente`` : seulement pour une facture de TRANCHE (sans
    ligne) rattachée à un devis ; une facture complète montre déjà son
    matériel. VNT38 — ``garanties`` : toute facture rattachée à un devis,
    dans la langue imprimée (``[]`` = aucune garantie connue). Un instantané
    déjà posé n'est jamais réécrit. Ne sauve rien : l'appelant fait le
    ``save``.

    AARG27 — ``identite_acheteur`` : toute facture à client, devis ou non.
    """
    if not facture.identite_acheteur and facture.client_id:
        facture.identite_acheteur = identite_acheteur_courante(facture)
    if not facture.devis_id:
        return None
    devis = devis_de_la_vente(facture.devis)
    sans_ligne = facture.pk is None or not facture.lignes.exists()
    if facture.objet_vente is None and sans_ligne:
        facture.objet_vente = objet_vente_du_devis(devis)
    if facture.garanties is None:
        facture.garanties = garanties_du_devis(
            devis, langue_de_la_facture(facture))
    return None


def figer_identite_acheteur_manquante(company=None, client_id=None,
                                      appliquer=False):
    """ASUP1 (C-ASUP-001) — fige ``identite_acheteur`` des factures NON
    brouillon qui n'en ont pas (émises avant AARG27) : sans instantané,
    « Anonymiser (RGPD) » effacerait l'acheteur de leur PDF, UBL et export DGI.

    Rend ``(a_figer, identite_perdue)`` (factures, ordre pk) ; un client déjà
    anonymisé n'a plus d'identité à figer → ``identite_perdue``. ``appliquer``
    écrit par ``update`` filtré ``identite_acheteur__isnull`` : un instantané
    posé n'est jamais réécrit (aucun ``save``). ``company=None`` = toutes les
    sociétés (commande de rattrapage)."""
    from apps.ventes.models import Facture
    qs = (Facture.objects.filter(identite_acheteur__isnull=True,
                                 client__isnull=False)
          .exclude(statut=Facture.Statut.BROUILLON)
          .select_related('client', 'company').order_by('pk'))
    if company is not None:
        qs = qs.filter(company=company)
    if client_id is not None:
        qs = qs.filter(client_id=client_id)
    a_figer, perdues = [], []
    for facture in qs:
        (perdues if facture.client.is_anonymized else a_figer).append(facture)
    if appliquer:
        for facture in a_figer:
            Facture.objects.filter(
                pk=facture.pk, identite_acheteur__isnull=True).update(
                identite_acheteur=identite_acheteur_courante(facture))
    return a_figer, perdues

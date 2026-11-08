"""ACSV104 — lignes d'une facture de ticket SAV et complétion du brouillon.

Sorti de ``facturation_ops`` (fichier proche du plafond de 2 000 lignes) :
``lignes_ticket_sav`` construit les lignes (pièces au prix de VENTE, jamais
``prix_achat``, + main-d'œuvre) ; ``completer_brouillon_ticket_sav`` rattrape
sur le brouillon déjà généré ce qui a été ajouté au ticket depuis."""
from decimal import Decimal
import logging

from .bornes import verifier_capacite_facture

logger = logging.getLogger(__name__)


def lignes_ticket_sav(*, ticket, sous_garantie, pieces):
    """Lignes (dicts prêts pour ``LigneFacture``) d'un ticket SAV : une par
    pièce + la main-d'œuvre (taux horaire société × heures)."""
    from ..utils.company_settings import tva_standard
    from .facturation_ops import _main_oeuvre_produit

    company = ticket.company
    taux_tva_defaut = tva_standard(company)
    suffixe_couvert = ' (couvert garantie/contrat)' if sous_garantie else ''
    # ENF47 — lignes bornées AVANT toute écriture (bornes.ecrire_facture_generee).
    lignes = [dict(
        produit=piece.produit,
        designation=f'{piece.produit.nom}{suffixe_couvert}',
        quantite=piece.quantite,
        prix_unitaire=(Decimal('0') if sous_garantie
                       else Decimal(str(piece.produit.prix_vente or 0))),
        taux_tva=(piece.produit.tva if piece.produit.tva is not None
                  else taux_tva_defaut),
    ) for piece in pieces]

    heures = ticket.heures_main_oeuvre
    if heures and heures > 0:  # ERR-ENF11 : négatives = pas de ligne (contrainte montants positifs, 500 sinon)
        profile_taux = None
        try:
            from apps.parametres.models import CompanyProfile
            profile_taux = CompanyProfile.get(company).taux_horaire_sav
        except Exception:  # pragma: no cover - défensif
            logger.warning("facturation_ops.generer_facture_ticket_sav : erreur ignorée (mode dégradé)", exc_info=True)
            profile_taux = None
        taux_horaire = (
            Decimal('0') if sous_garantie
            else Decimal(str(profile_taux)) if profile_taux is not None
            else None)
        if taux_horaire is not None:
            lignes.append(dict(
                produit=_main_oeuvre_produit(company),
                designation=f"Main-d'œuvre{suffixe_couvert}",
                quantite=heures, prix_unitaire=taux_horaire,
                taux_tva=taux_tva_defaut,
            ))
    return lignes


def completer_brouillon_ticket_sav(facture, *, ticket, sous_garantie, pieces):
    """ACSV104 — complète un BROUILLON déjà généré avec les pièces ajoutées
    au ticket depuis : quantité manquante par produit (lignes créées, bornées
    par ``verifier_capacite_facture``) et main-d'œuvre recalée. Une facture
    émise (non brouillon) est renvoyée telle quelle ; rappel sans changement :
    identique."""
    from ..models import Facture, LigneFacture
    from .facturation_ops import _main_oeuvre_produit

    if facture.statut != Facture.Statut.BROUILLON:
        return facture
    mo_id = _main_oeuvre_produit(ticket.company).pk
    existantes = list(facture.lignes.all())
    deja = {}
    for ligne in existantes:
        if ligne.produit_id != mo_id:
            deja[ligne.produit_id] = deja.get(ligne.produit_id, 0) + ligne.quantite
    manquantes = []
    for voulue in lignes_ticket_sav(
            ticket=ticket, sous_garantie=sous_garantie, pieces=pieces):
        if voulue['produit'].pk == mo_id:
            mo = next((x for x in existantes if x.produit_id == mo_id), None)
            if mo is None:
                manquantes.append(voulue)
            elif mo.quantite != voulue['quantite']:
                mo.quantite = voulue['quantite']
                mo.save(update_fields=['quantite'])
            continue
        voulue_qte = Decimal(str(voulue['quantite']))
        pris = min(voulue_qte, Decimal(str(deja.get(voulue['produit'].pk, 0))))
        deja[voulue['produit'].pk] = deja.get(voulue['produit'].pk, 0) - pris
        if voulue_qte - pris > 0:
            manquantes.append(dict(voulue, quantite=voulue_qte - pris))
    verifier_capacite_facture(manquantes)
    for ligne in manquantes:
        LigneFacture.objects.create(facture=facture, **ligne)
    return facture

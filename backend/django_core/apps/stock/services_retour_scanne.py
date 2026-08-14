"""NTWMS41 — Retour fournisseur GUIDÉ par le casier physique.

Aujourd'hui un retour fournisseur (N19) se saisit à la main : on tape une
référence, on valide, le stock sort de nulle part. Le magasinier, lui, va
chercher la pièce dans un casier précis et la pose sur la zone « départs
fournisseur » en attendant l'enlèvement.

Ce module branche le poste scanner (NTWMS5) sur ce geste réel :

  * ``preparer_ligne_retour_scannee`` — un SCAN (GTIN, SKU ou casier) résout
    le produit ET son casier actuel (NTWMS3/FG319), et pré-remplit la ligne de
    retour : plus aucune ressaisie de référence ;
  * ``deplacer_vers_casier_retours`` — pose le mouvement de sortie AVEC son
    ``bin_source`` (le vrai casier d'où la pièce est retirée) et son
    ``bin_destination`` (le casier de départs), au lieu d'une sortie sans
    localisation ;
  * ``valider_retour_scanne`` — enchaîne le déplacement puis la validation
    existante (``apply_retour_fournisseur``) : le flux comptable/BCF (YPROC8)
    reste STRICTEMENT celui d'avant, on ne le duplique pas.

Le casier de départs est choisi par convention de code (préfixe configurable,
défaut ``EXP``) parmi les casiers existants — cette lane ne crée jamais un
casier dans ``installations``.
"""
import logging

logger = logging.getLogger(__name__)

# Préfixe conventionnel du casier « départs fournisseur ».
PREFIXE_CASIER_EXPEDITION = 'EXP'


def _modele_bin():
    """``installations.BinLocation`` résolu par l'accesseur inverse de NOTRE
    string-FK — jamais un import de ``apps.installations.models``."""
    from .models_wms import LignePicking
    return LignePicking._meta.get_field('bin').related_model


def casier_retours_fournisseur(company, *, prefixe=PREFIXE_CASIER_EXPEDITION):
    """Casier de départs fournisseur de la société, ou ``None``.

    ``None`` = comportement historique : le mouvement de sortie se fait sans
    casier de destination (aucun blocage — on ne refuse jamais un retour parce
    que le plan d'entrepôt est incomplet).
    """
    return (_modele_bin().objects
            .filter(company=company, archived=False,
                    code__istartswith=prefixe)
            .order_by('ordre', 'code').first())


def preparer_ligne_retour_scannee(company, code, *, quantite=1):
    """Résout un scan en ligne de retour PRÊTE À CONFIRMER.

    Renvoie ``{produit, produit_nom, sku, quantite, bin_source,
    bin_source_code, bin_destination, bin_destination_code,
    fournisseur, fournisseur_nom}`` ou lève ``ValueError`` si le code ne
    désigne aucun produit de cette société.
    """
    from .selectors_wms import localisation_casiers, resoudre_code_scanne
    from .models import Produit

    resolu = resoudre_code_scanne(company, code)
    if resolu is None:
        raise ValueError('Code inconnu dans cette société.')
    if resolu['type'] != 'produit':
        raise ValueError(
            'Ce code désigne un ' + resolu['type'] + ' : scannez le produit '
            'à retourner.')

    produit = Produit.objects.filter(
        id=resolu['id'], company=company).first()
    if produit is None:
        raise ValueError('Produit introuvable dans cette société.')

    try:
        # `quantite or 1` avalerait le 0 (falsy) et le remplacerait par 1 —
        # un scan à quantité nulle DOIT être refusé, pas corrigé en silence.
        quantite = int(1 if quantite is None else quantite)
    except (TypeError, ValueError):
        raise ValueError('Quantité invalide.')
    if quantite <= 0:
        raise ValueError('La quantité doit être positive.')

    # Casier ACTUEL du produit : le plus rempli d'abord (c'est là que le
    # magasinier ira réellement chercher la pièce).
    emplacements = localisation_casiers(produit) or []
    source = None
    for ligne in sorted(emplacements,
                        key=lambda li: -(li.get('quantite') or 0)):
        if ligne.get('bin_id'):
            source = ligne
            break

    destination = casier_retours_fournisseur(company)
    return {
        'produit': produit.id,
        'produit_nom': produit.nom,
        'sku': produit.sku or '',
        'quantite': quantite,
        'bin_source': (source or {}).get('bin_id'),
        'bin_source_code': (source or {}).get('code', ''),
        'bin_destination': (destination.id if destination else None),
        'bin_destination_code': (destination.code if destination else ''),
        'fournisseur': produit.fournisseur_id,
        'fournisseur_nom': getattr(produit.fournisseur, 'nom', '') or '',
    }


def deplacer_vers_casier_retours(company, user, *, produit, quantite,
                                 bin_source=None, reference=''):
    """Trace le déplacement du produit vers le casier de départs.

    C'est un mouvement de TRANSFERT (le stock total ne change pas encore : il
    ne sortira qu'à la validation du retour). Sans casier de départs déclaré,
    on ne pose AUCUN mouvement — comportement historique intact.
    """
    from .models import MouvementStock

    destination = casier_retours_fournisseur(company)
    if destination is None:
        return None
    qte_avant = produit.quantite_stock
    mouvement = MouvementStock.objects.create(
        company=company, produit=produit,
        type_mouvement=MouvementStock.TypeMouvement.TRANSFERT,
        quantite=quantite, quantite_avant=qte_avant,
        quantite_apres=qte_avant,  # transfert interne : total inchangé
        reference=reference or '',
        note='NTWMS41 — mise en zone de départs fournisseur.',
        bin_source_id=bin_source, bin_destination=destination,
        created_by=user)
    logger.info('NTWMS41 deplacement produit=%s vers casier=%s',
                produit.id, destination.id)
    return mouvement


def valider_retour_scanne(retour, user, *, bins_source=None):
    """Déplace chaque ligne vers le casier de départs PUIS valide le retour.

    ``bins_source`` = ``{ligne_id: bin_id}`` relevé au scan. La validation
    elle-même reste ``apply_retour_fournisseur`` (N19/YPROC8) : aucun second
    chemin de sortie de stock n'est créé.
    """
    from .services import apply_retour_fournisseur

    bins_source = bins_source or {}
    for ligne in retour.lignes.select_related('produit'):
        deplacer_vers_casier_retours(
            retour.company, user, produit=ligne.produit,
            quantite=ligne.quantite,
            bin_source=bins_source.get(ligne.id) or bins_source.get(
                str(ligne.id)),
            reference=retour.reference)
    return apply_retour_fournisseur(retour, user)
